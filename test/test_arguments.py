import unittest

import argparse
from play4500 import valid_time


class TestArguments(unittest.TestCase):

    def setUp(self):
        pass

    def test_valid_times(self):
        times = ['2s', '2.0s', '3.456s',
                 '2000ms', '2000.0ms', '3000.456ms']
        for time in times:
            self.assertEqual(valid_time(time), time)

    def test_invalid_times(self):
        times = ['abc', '2', '3xyz', '4.$%ms']
        for time in times:
            with self.assertRaises(argparse.ArgumentTypeError):
                valid_time(time)

if __name__ == '__main__':
    unittest.main()
