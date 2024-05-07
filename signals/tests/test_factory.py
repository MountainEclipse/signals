import unittest

import _signals as signals
import factory

class TestSignalFactory(unittest.TestCase):

    def setUp(self):
        signals.getSignalProcessor()

    def tearDown(self):
        signals.join()
        signals.shutdown()

    def test_std_func_decoration(self):

        @factory.signalFactory
        def sample_func(var1: int, var2: str):
            if var1 == 42:
                raise ValueError()
            return var1, var2
        
        self.assertTrue(hasattr(sample_func, 'onCall'))
        self.assertTrue(hasattr(sample_func, 'onError'))
        self.assertTrue(hasattr(sample_func, 'onComplete'))

        # test reducing which signals are created

        @factory.signalFactory(onCall=False, onError=False)
        def sample_func(var1: int, var2: str):
            if var1 == 42:
                raise ValueError()
            return var1, var2
        
        self.assertFalse(hasattr(sample_func, 'onCall'))
        self.assertFalse(hasattr(sample_func, 'onError'))
        self.assertTrue(hasattr(sample_func, 'onComplete'))

    # def test_bound_method_decoration(self):
    #     # FIXME: will not work
    #     class T:
    #         @factory.signal_factory
    #         def sample_method(self, var1: int, var2: str):
    #             if var1 == 42:
    #                 raise ValueError()
    #             return var1, var2

    #     t = T()
    #     self.assertTrue(hasattr(t.sample_method, 'onCall'))
    #     self.assertTrue(hasattr(t.sample_method, 'onError'))
    #     self.assertTrue(hasattr(t.sample_method, 'onComplete'))

    def test_std_func_emissions(self):

        # flags for [called, error, complete]
        flags = [False]*3

        def onCall(func, var1, var2):
            flags[0] = True
        
        def onError(func, error):
            flags[1] = True

        def onComplete(func, rtn):
            flags[2] = True

        @factory.signalFactory
        def sample_function(var1: int, var2: str):
            if var1 == 42:
                raise ValueError()
            return var1, var2
        
        # test normal functions
        sample_function.onCall.connect(onCall)
        sample_function.onError.connect(onError)
        sample_function.onComplete.connect(onComplete)

        sample_function(5, "hello")
        self.assertTrue(flags[0], msg="onCall not called")
        self.assertTrue(flags[2], msg="onComplete not called")
        
        flags = [False]*3
        self.assertRaises(ValueError, sample_function, *(42, "blargh"))
        self.assertTrue(flags[1], msg="onError not called")

    # def test_bound_method_emission(self):
    #     # flags for [called, error, complete]
    #     flags = [False]*3

    #     def onCall(func, var1, var2):
    #         flags[0] = True
        
    #     def onError(func, error):
    #         flags[1] = True

    #     def onComplete(func, rtn):
    #         flags[2] = True
        
    #     # test methods
    #     class T:

    #         @factory.signal_factory
    #         def sample_method(self, var1: int, var2: str):
    #             if var1 == 42:
    #                 raise ValueError()
    #             return var1, var2
            
    #         @classmethod
    #         @factory.signal_factory
    #         def sample_cm(cls, var1, var2):
    #             return var1, var2

    #     flags = [False]*3
    #     t = T()

    #     t.sample_method.onCall.connect(onCall)
    #     t.sample_method.onError.connect(onError)
    #     t.sample_method.onComplete.connect(onComplete)

    #     t.sample_method(8, "bueno")
    #     self.assertTrue(flags[0], msg="onCall not called")
    #     self.assertTrue(flags[2], msg="onComplete not called")
        
    #     flags = [False]*3
    #     self.assertRaises(ValueError, t.sample_method, *(42, "blargh"))
    #     self.assertTrue(flags[1], msg="onError not called")

    #     flags = [False]*3
    #     t.sample_cm.onCall.connect(onCall)

    #     t.sample_cm(1, "abc")

