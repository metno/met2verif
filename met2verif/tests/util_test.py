import unittest
import met2verif.util
import verif.input
import os
import numpy as np
import tempfile
import shutil
np.seterr('raise')


class UtilTest(unittest.TestCase):

    def convert_times_test(self):
        self.assertEqual(1571835600, met2verif.util.convert_time(1571835600, "seconds since 1970-01-01 00:00:00 +00:00"))


if __name__ == '__main__':
    unittest.main()
