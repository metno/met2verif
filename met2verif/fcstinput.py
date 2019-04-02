import met2verif.util
import sys
import netCDF4
import numpy as np
import scipy.interpolate
import datetime
import copy
import argparse
import calendar
import time
import verif.data
import verif.input
import scipy.spatial
import pyproj


def get(filename):
    return Netcdf(filename)


def get_field(data, ml=0, member=None):
    """
        Arguments:
            data: N-D array of data
            ml: Prefer this model level, if there are several levels

        Returns:
            np.array: 3D array: Time X, Y
    """
    if(len(data.shape) == 4):
        # Extract the right model level, if multiple levels
        use_ml = 0
        if data.shape[1] > 1:
            print "Taking model level %d" % ml
            use_ml = ml
        data = data[:, use_ml, :, :]
    elif(len(data.shape) == 3):
        data = data[:, :, :]
    elif(len(data.shape) == 5):
        if data.shape[1] > 1:
            print "Taking the lower level"
        if member is None:
            met2verif.util.error("Variable is 5D. Need to specify ensemble member using -e")
        data = data[:, 0, member, :, :]
    else:
        met2verif.util.error("Input data has strange dimensions")
    return data


class FcstInput(object):
    def read(self, variable):
        """
        Arguments:
            variable (str): Variable to load

        Returns:
            times (np.array):
            lats (np.array):
            lons (np.array):
            obs (np.array):
        """
        raise NotImplementedError


class Netcdf(FcstInput):
    def __init__(self, filename, coord_guess=None):
        self.filename = filename
        try:
            self.file = netCDF4.Dataset(self.filename, 'r')
        except Exception as e:
            print("Could not open file '%s'. %s." % (filename, e))
            raise
        if len(self.file.variables["time"]) == 0:
            print("File '%s' does not have any times" % self.filename)
            raise Exception
        self.times = self.file.variables["time"][:]
        self.variables = self.file.variables.keys()

        if "forecast_reference_time" in self.file.variables:
            self.forecast_reference_time = np.ma.filled(self.file.variables["forecast_reference_time"][:], fill_value=np.nan)
        else:
            verif.util.warning("forecast_reference_time not found in '%s'. Using 'time' variable." % self.filename)
            self.forecast_reference_time = self.file["time"][0]
        self.leadtimes = (self.times - self.forecast_reference_time) / 3600

        self.file.close()

    def extract(self, lats, lons, variable, members=[0], aggregator=np.nanmean):
        """
        Extract forecasts from file for points.

        Arguments:
            lats (np.array): Array of latitudes
            lons (np.array): Array of longitudes
            variable (str): Variable name
            members (list): Which ensemble members to use? If None, then use all
            aggregator (function): What function to use to aggregate ensemble?
        """
        file = netCDF4.Dataset(self.filename, 'r')
        values = np.nan * np.zeros([len(self.leadtimes), len(lats)])
        s_time = time.time()
        data = file.variables[variable][:]
        dims = file.variables[variable].dimensions
        has_ens = "ensemble_member" in dims
        has_time = "time" in dims
        has_x = "x" in dims
        has_y = "y" in dims
        assert(has_time)
        X = 1
        I_time = dims.index("time")
        Y = 1
        I_x = None
        I_y = None
        if has_x:
            I_x = dims.index("x")
            X = file.variables[variable].shape[I_x]
        elif "longitude" in dims:
            I_x = dims.index("longitude")
            X = file.variables[variable].shape[I_x]
        if has_y:
            I_y = dims.index("y")
            Y = file.variables[variable].shape[I_y]
        elif "latitude" in dims:
            I_y = dims.index("latitude")
            Y = file.variables[variable].shape[I_y]

        # Collapse ensemble information
        if has_ens:
            I_ens = dims.index("ensemble_member")
            if members is None:
                data = aggregator(data, axis=I_ens)
            else:
                Im = members
                if I_ens == 0:
                    data = data[Im, ...]
                elif I_ens == 1:
                    data = data[:, Im, ...]
                elif I_ens == 2:
                    data = data[:, :, Im, ...]
                elif I_ens == 3:
                    data = data[:, :, :, Im, ...]
                elif I_ens == 4:
                    data = data[:, :, :, :, Im, ...]
                data = aggregator(data, axis=I_ens)
        # Convert masked values to nan
        np.ma.set_fill_value(data, np.nan)
        try:
            data = data.filled()
        except Exception:
            pass

        if I_time != 0:
            data = np.moveaxis(data, I_time, 0)

        q = data.flat
        I, J = self.get_i_j(lats, lons)
        for i in range(len(self.leadtimes)):
            Ivalid = np.where((I >= 0) & (J >= 0))[0]
            if I_x is None:
                indices = np.array(i * Y + I[Ivalid] + J[Ivalid], 'int')
            elif I_y is None:
                indices = np.array(i * X + I[Ivalid] + J[Ivalid], 'int')
            elif I_x < I_y:
                indices = np.array(i * X*Y + I[Ivalid]*Y + J[Ivalid], 'int')
            else:
                indices = np.array(i * X*Y + I[Ivalid]*X + J[Ivalid], 'int')
            temp = q[indices]
            values[i, Ivalid] = temp
        print "Getting values %.2f seconds" % (time.time() - s_time)

        file.close()
        return values

    def extract_ens(self, lats, lons, variable):
        """
        time, x, y, ens
        Arguments:
            lats (np.array): Array of latitudes
            lons (np.array): Array of longitudes
            variable (str): Variable name
        """
        data = self.file.variables[variable]
        data = data[:].astype(float)
        if(len(data.shape) == 4):
            X = data.shape[2]
            Y = data.shape[3]
            data = np.moveaxis(data[:, :, :, :], 1, -1)
        elif(len(data.shape) == 3):
            X = data.shape[1]
            Y = data.shape[2]
        elif(len(data.shape) == 5):
            X = data.shape[3]
            Y = data.shape[4]
            data = np.moveaxis(data[:, 0, :, :, :], 1, -1)
            # data = np.mean(data, axis=2)
        else:
            met2verif.util.error("Input data has strange dimensions")
        q = data.flat
        I, J = self.get_i_j(lats, lons)
        E = data.shape[3]
        values = np.nan * np.zeros([len(self.leadtimes), len(lats), E])
        for i in range(len(self.leadtimes)):
            for e in range(E):
                indices = np.array(i * X*Y*E + I[Ivalid]*Y*E + J[Ivalid]*E + e, 'int')
                temp = q[indices]
                values[i, Ivalid, e] = temp

        return values

    def get_i_j(self, lats, lons):
        """
            Finds the nearest neighbour in the file's grid for a list of lookup points

            Arguments:
                lats (list): Latitudes
                lons (list): Longitudes
            Returns:
                I (list): I indices, -1 if outside domain
                J (list): J indices, -1 if outside domain
        """
        proj = None
        N = len(lats)
        I = list()
        J = list()
        if "x" in self.file.variables and "y" in self.file.variables:
            x = self.file.variables["x"][:]
            y = self.file.variables["y"][:]
            for v in self.file.variables:
                if hasattr(self.file.variables[v], "proj4"):
                    projection = str(self.file.variables[v].proj4)
                    proj = pyproj.Proj(projection)

            if proj is not None:
                # Project lat lon onto grid projection
                xx, yy = proj(lons, lats)
                J = [int(xxx) for xxx in np.round(np.interp(xx, x, range(len(x)), -1, -1))]
                I = [int(yyy) for yyy in np.round(np.interp(yy, y, range(len(y)), -1, -1))]
        if proj is None:
            print "Could not find projection. Computing nearest neighbour from lat/lon."
            # Find lat and lons
            if "latitude" in self.file.variables:
                ilats = self.file.variables["latitude"][:]
                ilons = self.file.variables["longitude"][:]
            elif "lat" in self.file.variables:
                ilats = self.file.variables["lat"][:]
                ilons = self.file.variables["lon"][:]
            else:
                abort()
            is_regular_grid = len(ilats.shape)
            for i in range(N):
                currlat = lats[i]
                currlon = lons[i]
                if is_regular_grid:
                    # TODO: This assumes that latitude is before longitude in the dimensions of a variable
                    I += [np.argmin(np.abs(currlat - ilats))]
                    J += [np.argmin(np.abs(currlon - ilons))]
                else:
                    dist = met2verif.util.distance(currlat, currlon, ilats, ilons)
                    indices = np.unravel_index(dist.argmin(), dist.shape)
                    I += [indices[0]]
                    if len(indices) == 2:
                        J += [indices[1]]
                    else:
                        J += [0]

        return np.array(I, int), np.array(J, int)
