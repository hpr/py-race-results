import rr
import sys

if sys.hexversion < 0x02070000:
    import unittest2
    unittest = unittest2
else:
    import unittest

def runtests():
    loader = unittest.TestLoader()

    # Not sure if this is the best way to do this?
    tests = loader.discover(rr.__path__[0])
    testRunner = unittest.runner.TextTestRunner()
    testRunner.run(tests)
