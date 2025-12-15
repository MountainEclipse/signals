#----------------------------------------------------------------------------------
#                   Signal Factory Helper class and decorator function
#                       01/21/2024 By MountainEclipse
#----------------------------------------------------------------------------------

import inspect
from functools import partial
from typing import Callable

from _signals import Signal

class _Signalized:
    """
    Class for building signals into a wrapped function.

    Signals created are:
    - onCall: fired when the function or method is called; signal arguments are:
              (function_being_called: Callable, *arguments_to_call_with: [*Any])
    - onError: fired if an exception is thrown by the called function or method
               Arguments are: (function_being_called: Callable, Exception_thrown: Exception)
    - onCompleted: fired when the function or method returns. Arguments are:
                   (function_being_called: Callable, result_of_call: Any)

    FIXME: allow for applying signalizer decorator to bound methods, class methods, etc.
    """

    # emitted when the target of this callable is called. Arguments are the target
    # function's signature and arguments used to call the target
    onCall: Signal

    # emitted if the target function suffers an exception. Arguments are the target
    # function's signature and exception raised
    onError: Signal

    # emitted if the target function completes successfully. Arguments are the
    # target function's signature and any return value from the function.
    onComplete: Signal

    def __init__(self, func: Callable = None, onCall: bool = True, onError: bool = True,
                 onComplete: bool = True):
        """
        Instantiate the class for the given function.
        """
        self._func = func
        sig = inspect.signature(func)
        
        # get the type annotations for the target function
        types = [Callable]
        for param in sig.parameters.values():
            # account for methods of a class or instance whose first argument is the class or instance
            if param.name in ['self', 'cls']:
                raise NotImplementedError("Cannot signalize a bound method / class method. Not yet set up.")
            types.append(param.annotation if param.annotation is not inspect.Parameter.empty else object)
        types = tuple(types)
        
        # get the annotation for the target function's return value
        rtn_type = (Callable, 
                    (sig.return_annotation
                     if sig.return_annotation is not inspect.Signature.empty
                     else object))

        if onCall:
            self.onCall = Signal(types)
        if onError:
            self.onError = Signal((Callable, Exception))
        if onComplete:
            self.onComplete = Signal(rtn_type)

    def __call__(self, *args):        
        # emit the onCall signal with arguments passed
        if hasattr(self, "onCall"):
            self.onCall.emit(self._func, *args)
        try:
            result = self._func(*args)
        except Exception as e:
            # emit the onError signal with exception message
            if hasattr(self, "onError"):
                self.onError.emit(self._func, e)
            raise e
        else:
            # emit the onCompleted signal with return value
            if hasattr(self, "onComplete"):
                self.onComplete.emit(self._func, result)
            return result

def signalFactory(func: Callable = None, *, onCall: bool = True, 
                   onError: bool = True, onComplete: bool = True):
    """
    Decorator function to create a _SignalFactory instance wrapping a function/method

    If specified, creation of specific signals can be suppressed by setting False
    on optional arguments.

    NOTE: only works for functions currently, so applying to a bound method / class method
    WILL NOT WORK
    """
    if func is None:
        return partial(signalFactory, onCall=onCall, onError=onError, 
                       onComplete=onComplete)
    
    return _Signalized(func, onCall=onCall, onError=onError, onComplete=onComplete)
