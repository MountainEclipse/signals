import unittest
import _signals as signals


test_results = None

def func(v1, v2):
    global test_results
    test_results["func"] = (v1, v2)

def func_w_typing(v1: int, v2: str):
    global test_results
    test_results["func_w_typing"] = (v1, v2)

def func_error(v1: str, v2: str, v3: str):
    return 'func_error', v1, v2, v3

class TestFuncs:

    def method(self, v1, v2):
        global test_results
        test_results["method"] = (v1, v2)

    def method_w_typing(self, v1: int, v2: str):
        global test_results
        test_results["method_w_typing"] = (v1, v2)

class TestSignal(unittest.TestCase):

    def setUp(self) -> None:
        global test_results
        test_results = {}
        self.signal = signals.Signal([int, str],
                                     priority=signals.SignalPriority.NORMAL)

    def tearDown(self) -> None:
        global test_results
        test_results = None
        del self.signal

    def test_init(self):
        # signal should have two handler types: (str, int) and (object, object)
        self.assertEqual(len(self.signal.typedefs), 2)
        self.assertEqual(self.signal.typedefs,
                         {(int, str), (object, object)})
        self.assertRaises(TypeError, signals.Signal, str)

    def test_priority_changing(self):
        self.assertEqual(self.signal.priority, signals.SignalPriority.NORMAL)
        self.signal.priority = signals.SignalPriority.HIGH
        self.assertEqual(self.signal.priority, signals.SignalPriority.HIGH)

    def test_std_connections(self):
        # ensure specific slot list is empty, then add and check it was added correclty
        self.assertEqual(len(self.signal.slots((int, str))), 0)
        self.signal.connect(func_w_typing)
        self.assertEqual(len(self.signal.slots((int, str))), 1)
        self.assertTrue(func_w_typing in self.signal.slots((int, str)))

        # ensure generic slot did not receive a copy of the specific, then add
        # generic and ensure added correctly
        self.assertEqual(len(self.signal.slots((object, object))), 0)
        self.signal.connect(func)
        self.assertEqual(len(self.signal.slots((object, object))), 1)
        self.assertTrue(func in self.signal.slots((object, object)))

        self.assertRaises(ValueError, self.signal.connect, func_error)

    def test_method_connections(self):
        tf = TestFuncs()
        # ensure specific slot list is empty, then add and check it was added correclty
        self.assertEqual(len(self.signal.slots((int, str))), 0)
        self.signal.connect(tf.method_w_typing)
        self.assertEqual(len(self.signal.slots((int, str))), 1)
        self.assertTrue(tf.method_w_typing in self.signal.slots((int, str)))

        # ensure generic slot did not receive a copy of the specific, then add
        # generic and ensure added correctly
        self.assertEqual(len(self.signal.slots((object, object))), 0)
        self.signal.connect(tf.method)
        self.assertEqual(len(self.signal.slots((object, object))), 1)
        self.assertTrue(tf.method in self.signal.slots((object, object)))

    def test_disconnection(self):
        # ensure specific slot list is empty, then add and check it was added correclty
        tf = TestFuncs()
        self.signal.connect(func_w_typing)
        self.signal.connect(tf.method_w_typing)

        # ensure slots were connected correctly
        self.assertEqual(len(self.signal.slots((int, str))), 2)
        self.assertTrue(func_w_typing in self.signal.slots((int, str)))
        self.assertTrue(tf.method_w_typing in self.signal.slots((int, str)))

        # remove the type-specific slot now
        self.signal.disconnect(func_w_typing)
        self.assertEqual(len(self.signal.slots((int, str))), 1)
        self.assertFalse(func_w_typing in self.signal.slots((int, str)))

        # now remove the generic slot
        self.signal.disconnect(tf.method_w_typing)
        self.assertEqual(len(self.signal.slots((int, str))), 0)
        self.assertFalse(tf.method_w_typing in self.signal.slots((int, str)))

    def test_similarity(self):
        class ChildStr(str):
            pass

        class ChildInt(int):
            pass

        cmp = (int, str)  # should return 0 for (int, str) 2 for (object, object)
        cmp2 = (str, str)  # should return -1 for (int, str) and 2 for (object, object)
        cmp3 = (ChildInt, ChildStr)  # should return 2 for (int, str) and 4 for (object, object)
        cmp4 = (int, str, str)  # should return -2 for all

        self.assertEqual(self.signal._similarity(cmp)[0][1], 0)
        self.assertEqual(self.signal._similarity(cmp)[1][1], 2)

        self.assertEqual(self.signal._similarity(cmp2)[0][1], -1)
        self.assertEqual(self.signal._similarity(cmp2)[1][1], 2)

        self.assertEqual(self.signal._similarity(cmp3)[0][1], 2)
        self.assertEqual(self.signal._similarity(cmp3)[1][1], 4)

        self.assertEqual(self.signal._similarity(cmp4)[0][1], -2)
        self.assertEqual(self.signal._similarity(cmp4)[1][1], -2)

        self.assertRaises(TypeError, self.signal._similarity, [int, object, str])

    # def test_weakref_cleanup(self):
    #     """
    #     FIXME: this function doesn't seem to work correctly; WeakMethod becomes dead
    #            but doesn't seem to get cleaned up correctly, so it lingers.
    #            Need to verify whether this is actually a bug, or expected behavior
    #            limited by the test case.
    #     """
    #     tf = TestFuncs()
    #     self.signal.connect(func_w_typing)
    #     self.signal.connect(tf.method_w_typing)

    #     self.assertEqual(len(self.signal.slots((int, str))), 2)
    #     del tf
    #     self.assertEqual(len(self.signal.slots((int, str))), 1)  # error: still shows 2

    def test_emission(self):
        tf = TestFuncs()
        self.signal.connect(func_w_typing)
        self.signal.connect(func)
        self.signal.connect(tf.method)
        self.signal.connect(tf.method_w_typing)

        self.assertEqual(len(self.signal.slots((int, str))), 4)
        self.assertEqual(len(self.signal.slots((int, str), tolerance=0)), 2)

        self.signal.emit(6, "Boo")
        signals.join()

        global test_results
        for slot in self.signal.slots((int, str)):
            self.assertTrue(slot.__name__ in test_results.keys())
            self.assertTrue(test_results[slot.__name__] == (6, "Boo"))

        signals.shutdown()
