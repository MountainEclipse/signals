import coverage
import unittest
import os


if __name__ == '__main__':
    try:
        cov = coverage.Coverage(omit="*/tests/*")
        cov.start()
    
        loader = unittest.TestLoader()
        tests = loader.discover(os.path.dirname(__file__))
        testRunner = unittest.runner.TextTestRunner()
        testRunner.run(tests)

        cov.stop()
        cov.save()
        cov.html_report(directory='.coverage_report_html')
    except coverage.CoverageException:
        pass