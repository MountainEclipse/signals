import unittest

from .. import _signals as signals


class TestSignalFactory(unittest.TestCase):

    def setUp(self):
        signals.getSignalProcessor()

    def tearDown(self):
        signals.join()
        signals.shutdown()

    def test_std_func_decoration(self):

        @signals.SignalFactory()
        def sample_func(var1: int, var2: str):
            if var1 == 42:
                raise ValueError()
            return var1, var2

        self.assertTrue(hasattr(sample_func, 'onCall'))
        self.assertTrue(hasattr(sample_func, 'onError'))
        self.assertTrue(hasattr(sample_func, 'onComplete'))

        # test reducing which signals are created

        @signals.SignalFactory(onCall=False, onError=False)
        def sample_func(var1: int, var2: str):
            if var1 == 42:
                raise ValueError()
            return var1, var2

        self.assertFalse(hasattr(sample_func, 'onCall'))
        self.assertFalse(hasattr(sample_func, 'onError'))
        self.assertTrue(hasattr(sample_func, 'onComplete'))

    def test_std_func_emissions(self):

        # flags for [called, error, complete]
        flags = [False]*3

        def onCall(func, args):
            flags[0] = True

        def onError(func, error):
            flags[1] = True

        def onComplete(func, rtn):
            flags[2] = True

        @signals.SignalFactory()
        def sample_function(var1: int, var2: str):
            if var1 == 42:
                raise ValueError()
            return var1, var2

        # test normal functions
        sample_function.onCall.connect(onCall)
        sample_function.onError.connect(onError)
        sample_function.onComplete.connect(onComplete)

        sample_function(5, var2="hello")
        self.assertTrue(flags[0], msg="onCall not called")
        self.assertTrue(flags[2], msg="onComplete not called")

        flags = [False]*3
        self.assertRaises(ValueError, sample_function, *(42, "blargh"))
        self.assertTrue(flags[1], msg="onError not called")

    def test_bound_method_decoration(self):
        # test binding signals to bound method

        class T:
            @signals.SignalFactory()
            def sample_method(self, var1: int, var2: str):
                if var1 == 42:
                    raise ValueError()
                return var1, var2

            @signals.SignalFactory(onCall=False, onError=False)
            def sample_method_2(self, var1: int):
                return var1

        t = T()
        self.assertTrue(hasattr(t.sample_method, 'onCall'))
        self.assertTrue(hasattr(t.sample_method, 'onError'))
        self.assertTrue(hasattr(t.sample_method, 'onComplete'))

    def test_bound_method_emission(self):
        # flags for [called, error, complete]
        flags = [False]*3

        def onCall(func, args):
            flags[0] = True

        def onError(func, error):
            flags[1] = True

        def onComplete(func, rtn):
            flags[2] = True

        # test methods
        class T:

            @signals.SignalFactory()
            def sample_method(self, var1: int, var2: str):
                if var1 == 42:
                    raise ValueError()
                return var1, var2

            @classmethod
            @signals.SignalFactory()
            def sample_cm(cls, var1, var2):
                return var1, var2

        flags = [False]*3
        t = T()

        t.sample_method.onCall.connect(onCall)
        t.sample_method.onError.connect(onError)
        t.sample_method.onComplete.connect(onComplete)

        t.sample_method(8, "bueno")
        self.assertTrue(flags[0], msg="onCall not called")
        self.assertTrue(flags[2], msg="onComplete not called")

        flags = [False]*3
        self.assertRaises(ValueError, t.sample_method, *(42, "blargh"))
        self.assertTrue(flags[1], msg="onError not called")

        flags = [False]*3
        t.sample_cm.onCall.connect(onCall)

        t.sample_cm(1, "abc")
