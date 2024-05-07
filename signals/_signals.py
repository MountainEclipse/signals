# -*- coding: utf-8 -*-
"""
Package: src.libs
File:    signals.py

Python Version: 3.10

Created on: 7/4/2021 at 7:51 AM.
@author: MountainEclipse

Revision 1/13/2024 to add signal processor to file, reducing dependency on other files

"""
import inspect
from typing import Callable, Iterable
from weakref import WeakSet, WeakMethod, finalize
from dataclasses import dataclass, field
import traceback
import json
import threading
from concurrent.futures import Future
from functools import lru_cache

# needed for prioritized worker thread pool
import sys
import queue
import random
import atexit
import weakref
from concurrent.futures.thread import ThreadPoolExecutor, _base, _WorkItem

from baseclass import TrackedInstances, EnumDict


__all__ = ['Signal', 'SignalPriority', 'join', 'shutdown']


"""
Code below this is derived from:
    https://github.com/oleglpts/PriorityThreadPoolExecutor/blob/master/PriorityThreadPoolExecutor/__init__.py
Implementation of a ThreadPoolExecutor with PriorityQueue to simplify
    event dispatch. When new events are fired, automatically move high-priority
    tasks to the top of the event handler
"""

########################################################################################################################
#                                                Global variables                                                      #
########################################################################################################################

@dataclass(order=True)
class PriorityWorkItem:
    priority: int
    task: _WorkItem = field(compare=False)


NULL_PRIORITY_ITEM = PriorityWorkItem(
    priority=sys.maxsize, task=_WorkItem(_base.Future(), lambda: None, args=(), kwargs={}))

_threads_queues = {}

########################################################################################################################
#                                           Before system exit procedure                                               #
########################################################################################################################


def python_exit():
    """
    Cleanup before system exit
    """
    items = list(_threads_queues.items())
    for t, q in items:
        q.put(NULL_PRIORITY_ITEM)
    for t, q in items:
        t.join()

# change default cleanup

atexit.register(python_exit)


########################################################################################################################
#                                               Worker implementation                                                  #
########################################################################################################################


def _worker(executor_reference, work_queue):
    """
    Worker
    :param executor_reference: executor function
    :type executor_reference: callable
    :param work_queue: work queue
    :type work_queue: queue.PriorityQueue
    """
    try:
        while True:
            work_item = work_queue.get(block=True)
            if work_item is NULL_PRIORITY_ITEM:
                break
            if (isinstance(work_item, PriorityWorkItem) 
                    and work_item.priority != sys.maxsize):
                work_item = work_item.task
                try:
                    work_item.run()
                except Exception as e:
                    print(e)
                    raise e
                del work_item
                continue
            executor = executor_reference()
            if executor is None or executor._shutdown:
                break
            del executor
    except BaseException:
        _base.LOGGER.critical('Exception in worker', exc_info=True)


########################################################################################################################
#                           Little hack of ThreadPoolExecutor from concurrent.futures.thread                           #
########################################################################################################################


class PriorityThreadPoolExecutor(ThreadPoolExecutor):
    """
    Thread pool executor with priority queue (priorities must be different, lowest first)
    """
    _work_queue: queue.PriorityQueue

    def __init__(self, **kwargs):
        """
        Initializes a new PriorityThreadPoolExecutor instance
        :param max_workers: the maximum number of threads that can be used to execute the given calls
        :type max_workers: int
        """
        super(PriorityThreadPoolExecutor, self).__init__(**kwargs)

        # change work queue type to queue.PriorityQueue

        self._work_queue = queue.PriorityQueue()
        self._shutdown = False

    # ------------------------------------------------------------------------------------------------------------------

    def submit(self, fn, *args, **kwargs) -> Future:
        """
        Sending the function to the execution queue
        :param fn: function being executed
        :type fn: callable
        :param args: function's positional arguments
        :param kwargs: function's keywords arguments
        :return: future instance
        :rtype: _base.Future
        Added keyword:
        - priority (integer later sys.maxsize)
        """
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')

            priority = kwargs.pop('priority', random.randint(0, sys.maxsize-1))

            f = _base.Future()
            w = _WorkItem(f, fn, args, kwargs)

            self._work_queue.put(PriorityWorkItem(
                priority=priority, 
                task=w
            ))
            self._adjust_thread_count()
            return f

    # ------------------------------------------------------------------------------------------------------------------

    def _adjust_thread_count(self):
        """
        Attempt to start a new thread
        """
        def weak_ref_cb(_, q=self._work_queue):
            pass
        if len(self._threads) < self._max_workers:
            t = threading.Thread(
                target=_worker,
                args=(weakref.ref(self, weak_ref_cb), self._work_queue),
                name=f"{self._thread_name_prefix}_{len(self._threads)+1}"
            )
            t.daemon = True
            t.start()
            self._threads.add(t)
            _threads_queues[t] = self._work_queue

    # ------------------------------------------------------------------------------------------------------------------

    def shutdown(self, wait=True):
        """
        Pool shutdown
        :param wait: if True wait for all threads to complete
        :type wait: bool
        """
        with self._shutdown_lock:
            self._shutdown = True
        for _ in self._threads:
            self._work_queue.put(NULL_PRIORITY_ITEM)
        if wait:
            for t in self._threads:
                t.join()


"""
Self-produced code below this point
"""

#######################################################################################################################
#                                          Signal Processor Code                                       #
#######################################################################################################################

class SignalPriority(EnumDict):
    IMMEDIATE = 1
    HIGH = 2
    MODERATE = 3
    NORMAL = 4
    LOW = 5
    NONE = 6   


class Signal(TrackedInstances):
    """
    Signal class for event handling. Does not keep persistent any slots attached,
    so if other references to slots are destroyed, the slot will drop off the signal.
    
    :property _slots_structs: dict
        Contains all typedefs and associated slots under that typedef.
            Structured as: 
            {
                tuple(typedef1): set([slot1, slot2, ...]),
                tuple(typedef2): set([slot3, ...])
            }
    """
    _slots_structs: dict[tuple, WeakSet]

    def __init__(self, *typedefs, 
                 priority: int = SignalPriority.NORMAL):
        """
        Instantiate the class.

        :param *typedefs
            Variable positional arguments. Expecting sequence of iterables.
                e.g. Signal([int, str], [str], [object], [...], priority=...)
        :param priority: int = SignalPriority.NORMAL
            The precedence all emitted signals from this instance take in
                SignalProcessor's event dispatch relative to other Signals.
        """
        self.priority = priority

        self._slots_structs = {}  # stores typedefs as keys and WeakSets as items
        self._weak_methods = {}  # needed to store WeakMethod instances

        for typedef in typedefs:
            if isinstance(typedef, Iterable):
                self._slots_structs[tuple(typedef)] = WeakSet()
                self._slots_structs[tuple([object for _ in typedef])] = WeakSet()
                continue
            raise TypeError(
                "Signal emission data type definitions must be Iterable, not " +
                f"'{type(typedef)}'"
            )

    @property
    def typedefs(self) -> set[tuple]:
        """
        Returns explicitly defined type definitions for supported slots on this signal.
        """
        return self._slots_structs.keys()

    def slots(self, typedef: tuple, tolerance: int = float('inf')) -> set:
        """
        Return the set of slot functions to be called with arguments in the given typedef.

        :param typedef: tuple
            The type definition for which slots will be enumerated
        :param tolerance: int = 0
            The maximum deviation acceptable from the signal's defined types, provided
            all typedef values are in a defined typedef MRO chain.
            Values are cumulative, and each count is one generation gap; e.g. 'int'
            is 1 removed from 'object', so the value returned there would be '1'

            Use value of 0 for perfect match.
        """
        # build comparison table for the given typedef
        similarity = self._similarity(typedef)
        
        rtn = []
        for v in similarity:
            if v[1] < 0:  # an error / non-match found
                continue
            elif v[1] > tolerance:
                # tolerance is too high for this result
                continue
            rtn += self._slots_structs[v[0]].copy()  # append a copy to not screw with list

        # get references to methods themselves, not just weakMethods
        for i in range(len(rtn)):
            if isinstance(rtn[i], WeakMethod):
                rtn[i] = rtn[i]()
        return rtn

    def connect(self, slot: Callable) -> None:
        """
        Connect a slot to this Signal according to the slot's argument type annotations. 
        
        Slot will be called when Signal emits data that fits its argument
        type definitions according to either the @Slot(*types) decorator or
        type-hinting / annotations in the slot function definition.

        NOTE: Does not work with variable-length arguments; TODO: include this capability using parameter.kind
        """
        # get annotated types from the slot, or 'object' for all if not specified
        types = self._read_annotations(slot)
        # build the similarity matrix
        similar = [v for v in self._similarity(types) if v[1] >= 0]

        # if no similar typedefs found, raise error
        if len(similar) == 0:
            raise ValueError(
                f"No similar signal type definitions found for '{slot.__qualname__}' with argument types ({types})")

        # unzip the similarity matrix
        typedef = tuple(zip(*similar))
        # locate the minimum 'difference' value, and pull the corresponding typedef
        typedef = typedef[0][typedef[1].index(min(typedef[1]))]

        # WeakSets cannot hold bound methods from instanced classes, so we need to use
        #   WeakMethod to hold the reference
        if inspect.ismethod(slot):
            wm = WeakMethod(slot)
            finalize(wm, self._bound_method_deleted, slot.__qualname__)
            self._weak_methods[slot.__qualname__] = wm
            self._slots_structs[typedef].add(wm)
        else:
            self._slots_structs[typedef].add(slot)
        
        # clear the similarity cache to force an update on next call
        self._similarity.cache_clear()

    def disconnect(self, slot: Callable) -> None:
        """
        Disconnect a slot from this signal.
        """

        # if slot is a bound method, need to delete the WeakMethod object
        if inspect.ismethod(slot):
            # should be only reference in here
            del self._weak_methods[slot.__qualname__]
            return

        # otherwise directly remove from the slot structures dict
        for seq in self._slots_structs.values():
            if slot in seq:
                seq.remove(slot)
        
        # clear the similarity cache to force an update on next call
        self._similarity.cache_clear()

    def emit(self, *args):
        """
        Emit a signal with the given args.
        """
        # first, get the types of all arguments to determine the slots to call.
        types = tuple([type(v) for v in args])

        # get all slots that should fire
        slots = self.slots(types)

        # build the list of handler functions for passing arguments
        for handler in slots:
            registerEmission(
                SignalTask(
                    priority=self.priority,
                    func=handler,
                    args=args,
                    source=self
                )
            )

    @lru_cache(maxsize=10)
    def _similarity(self, typedef: tuple) -> tuple[tuple, int]:
        """
        Compares the given typedef to all explicit typedefs on this signal,
        returning an integer representation of how similar the two are, based on
        the MRO of items in the given typedef.

        Assume types defined in typedef are the most specific, and the signal's
        defined types are more generic (in the case of interitance), such that
        one child class doesn't send signals to another child class.

        Return Values:
        --------------
        -2 :: argument lengths do not match
        -1 :: one or more argument types do not match / are not similar (in MRO)
         0 :: all argument types match perfectly
        >0 :: how far removed the given typedef is from an explicit typedef based on MRO chain

        Raises:
        -------
        TypeError: if typedef argument not a tuple.
        """
        if not isinstance(typedef, tuple):
            raise TypeError(
                f"'typedef' parameter must be tuple, not {type(typedef)}"
            )

        rtn = []

        for cmp in zip([typedef for _ in self.typedefs], self.typedefs):
            if len(cmp[0]) != len(cmp[1]):
                # argument length not matched
                rtn.append((cmp[1], -2))
                continue
            elif all([v[0] == v[1] for v in zip(cmp[0], cmp[1])]):
                # perfect match
                rtn.append((cmp[1], 0))
                continue

            diff = 0
            for s in zip(cmp[0], cmp[1]):
                try:
                    # get the MRO index value of value 1 in value 0's MRO
                    idx = inspect.getmro(s[0]).index(s[1])
                    diff += idx
                except ValueError:
                    # at least one argument is not in the MRO of the current typedef 
                    rtn.append((cmp[1], -1))
                    break
            else:
                # append the tallied differences
                rtn.append((cmp[1], diff))
        return rtn

    def _read_annotations(self, slot: Callable) -> tuple[type]:
        """
        Determine the annotated typedef for a given slot.

        Checks annotations on function arguments, defaulting to 'object'
        if no annotation exists.
        """
        params = inspect.signature(slot).parameters
        types = (v.annotation if v.annotation is not inspect._empty else object for v in params.values())
        return tuple(types)

    def _bound_method_deleted(self, name: str):
        # FIXME: need to verify this is cleaning up objects appropriately
        # and not becoming a memory leak problem.
        for key in self._slots_structs.keys():
            if self._weak_methods.get(name, None) in self._slots_structs[key]:
                self._slots_structs[key].remove(self._weak_methods[name])
                del self._weak_methods[name]
                

@dataclass(order=True)
class SignalTask:
    priority: int
    func: Callable = field(compare=False)
    args: tuple = field(compare=False)
    source: Signal = field(compare=False)


_processor: PriorityThreadPoolExecutor = None

def getSignalProcessor(thread_ct: int = 10):
    """
    Returns the signal processor thread pool, building it if necessary.
    """
    global _processor
    if _processor is None:
        _processor = PriorityThreadPoolExecutor(max_workers=thread_ct, thread_name_prefix='SignalProcessor')
    return _processor


def registerEmission(task: SignalTask):
    """
    Submit a work task to the thread pool executor.
    """
    future = getSignalProcessor().submit(
        task.func, *task.args, priority=task.priority
    )
    future.add_done_callback(onFutureComplete)


def join():
    """
    Wait for all tasks in the SignalProcessor work queue to complete before returning.
    """
    if _processor is None:
        return
    _processor._work_queue.join()


def onFutureComplete(fut: Future):
    """
    Default completion callback for all signal processor future objects.
    Provides error handling if an exception is thrown in the future object.
    """
    global _processor
    e = fut.exception()
    if e is None:
        _processor._work_queue.task_done()
        return
    trace = []
    tb = traceback.extract_tb(e.__traceback__)

    for frame in tb:
        trace.append(
            {
                'filename': frame.filename,
                'name': frame.name,
                'lineno': frame.lineno,
                'line': frame.line
            }
        )
    result = {
        'type': type(e).__name__,
        'message': str(e),
        'thread': threading.current_thread().name,
        'trace': trace
    }
    print(json.dumps(result, indent=4))
    _processor._work_queue.task_done()


def shutdown():
    """
    Kills the thread pool executor
    """
    global _processor
    if _processor is None:
        return
    _processor.shutdown(wait=True)
    _processor = None
