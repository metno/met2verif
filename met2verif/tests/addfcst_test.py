import unittest
import met2verif.addfcst
import verif.input
import os
import numpy as np
import tempfile
import shutil
np.seterr('raise')


class AddFcstTest(unittest.TestCase):

    @staticmethod
    def run_addfcst(command):
        """ Runs an addfcst command line """
        file_obs = "met2verif/tests/files/obs.nc"
        fd, file_temp = tempfile.mkstemp(suffix=".nc")
        shutil.copy(file_obs, file_temp)
        command = "addfcst " + command + " -o %s" % file_temp
        argv = command.split()
        os.close(fd)
        print command
        met2verif.main(command.split())
        return file_temp

    @staticmethod
    def remove(file):
        """ Removes a file """
        os.remove(file)

    @staticmethod
    def file_size(filename):
        """ Returns the number of bytes of a file """
        statinfo = os.stat(filename)
        return statinfo.st_size

    @staticmethod
    def is_valid_file(filename, min_size=3000):
        """ Checks if a file is larger in size than min_size bytes """
        return IntegrationTest.file_size(filename) > min_size

    def test_dimensions(self):
        """
        ALl these forecast files have the same data, but with different x, y arrangements
        """
        ffiles = ['met2verif/tests/files/f%d.nc' % f for f in range(1, 7)]
        for ffile in ffiles:
            cmd = "%s -v air_temperature_2m" % ffile
            file = self.run_addfcst(cmd)
            input = verif.input.get_input(file)
            assert(len(input.locations) == 1)
            assert(input.fcst.shape[0] == 2)
            assert(input.fcst.shape[1] == 3)
            for t in range(input.fcst.shape[0]):
                for l in range(input.fcst.shape[1]):
                    if t == 1 and l == 0:
                        self.assertEqual(4, input.fcst[1, 0])
                    elif t == 1 and l == 2:
                        self.assertEqual(8, input.fcst[1, 2])
                    else:
                        self.assertTrue(np.isnan(input.fcst[t, l]))
            self.remove(file)

    def test_nn(self):
        """ Check that the correct nearest neighbour is found in a 3x3 input file """
        ffiles = ['met2verif/tests/files/f%d.nc' % f for f in range(11, 12)]
        for ffile in ffiles:
            cmd = "%s -v air_temperature_2m" % ffile
            file = self.run_addfcst(cmd)
            input = verif.input.get_input(file)
            assert(len(input.locations) == 1)
            assert(input.fcst.shape[0] == 2)
            assert(input.fcst.shape[1] == 3)
            for t in range(input.fcst.shape[0]):
                for l in range(input.fcst.shape[1]):
                    if t == 1 and l == 0:
                        self.assertAlmostEqual(8.415, input.fcst[1, 0])
                    else:
                        self.assertTrue(np.isnan(input.fcst[t, l]))
            self.remove(file)

    def test_ens(self):
        """ Check that subsetting ensemble members give the right result """

        cmd = "met2verif/tests/files/f6.nc -v air_temperature_2m -e 0"
        file = self.run_addfcst(cmd)
        input = verif.input.get_input(file)
        self.assertEqual(3, input.fcst[1, 0])
        self.assertEqual(7, input.fcst[1, 2])

        cmd = "met2verif/tests/files/f6.nc -v air_temperature_2m -e 1"
        file = self.run_addfcst(cmd)
        input = verif.input.get_input(file)
        self.assertEqual(5, input.fcst[1, 0])
        self.assertEqual(9, input.fcst[1, 2])

        # Ensemble mean of two members
        cmd = "met2verif/tests/files/f6.nc -v air_temperature_2m -e 0,1"
        file = self.run_addfcst(cmd)
        input = verif.input.get_input(file)
        self.assertEqual(4, input.fcst[1, 0])
        self.assertEqual(8, input.fcst[1, 2])


if __name__ == '__main__':
    unittest.main()
