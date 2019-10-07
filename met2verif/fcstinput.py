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
            self.file.close()
            raise Exception
        self.times = self.file.variables["time"][:]
        self.times = self.convert_times(self.times, self.file.variables["time"])
        self.variables = self.file.variables.keys()

        if "forecast_reference_time" in self.file.variables:
            self.forecast_reference_time = np.ma.filled(self.file.variables["forecast_reference_time"][:], fill_value=np.nan)
            self.forecast_reference_time = self.convert_times(self.forecast_reference_time, self.file.variables["forecast_reference_time"])
        else:
            verif.util.warning("forecast_reference_time not found in '%s'. Using 'time' variable." % self.filename)
            self.forecast_reference_time = self.file["time"][0]
            self.forecast_reference_time = self.convert_times(self.forecast_reference_time, self.file.variables["time"])
        self.leadtimes = (self.times - self.forecast_reference_time) / 3600

        self.file.close()

    def convert_times(self, times, ncvar):
        if hasattr(ncvar, "units"):
            dates = netCDF4.num2date(times, units=ncvar.units)
            if isinstance(dates, list) or isinstance(dates, np.ndarray):
                times = np.array([int(d.strftime("%s")) for d in dates])
            else:
                times = int(dates.strftime("%s"))
            return np.array(times)

            # units = ncvar.units
            #if units != "seconds since 1970-01-01 00:00:00 +00:00":

            #else:
            #    return times
        else:
            return times

    def extract(self, lats, lons, variable, members=[0], hood=0):
        """
        Extract forecasts from file for points. Outputs with dimensions (leadtime, location, ens)

        Arguments:
            lats (np.array): Array of latitudes
            lons (np.array): Array of longitudes
            variable (str): Variable name
            members (list): Which ensemble members to use? If None, then use all
            hood (int): Neighbourhood radius
        """
        time_0 = time.time()
        file = netCDF4.Dataset(self.filename, 'r')
        if members is None:
            members = [0]
            if 'ensemble_member' in file.dimensions:
                members = range(len(file.dimensions['ensemble_member']))
        member_size = len(members)
        if hood > 0:
            member_size = member_size * ((hood*2+1)**2)
        values = np.nan * np.zeros([len(self.leadtimes), len(lats), member_size])
        # Most time comes form this call:
        data = file.variables[variable][:]
        dims = file.variables[variable].dimensions
        has_ens = "ensemble_member" in dims
        has_time = "time" in dims
        xvar, yvar = self.get_xy()
        has_x = xvar is not None
        has_y = yvar is not None
        assert(has_time)
        X = 1
        I_time = dims.index("time")
        I_ens =None
        if has_ens:
            I_ens = dims.index("ensemble_member")
        Y = 1
        I_x = None
        I_y = None
        if has_x:
            I_x = dims.index(xvar)
            X = file.variables[variable].shape[I_x]
        elif "longitude" in dims:
            I_x = dims.index("longitude")
            X = file.variables[variable].shape[I_x]
        if has_y:
            I_y = dims.index(yvar)
            Y = file.variables[variable].shape[I_y]
        elif "latitude" in dims:
            I_y = dims.index("latitude")
            Y = file.variables[variable].shape[I_y]

        # Subset by ensemble members
        if has_ens:
            num_members_in_file = data.shape[I_ens]
            if np.max(members) >= num_members_in_file:
                raise Exception("Cannot extract member %d from a %d member ensemble" % (np.max(members), num_members_in_file))
            if members is not None and num_members_in_file > len(members):
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

        # Convert masked values to nan
        np.ma.set_fill_value(data, np.nan)
        try:
            data = data.filled()
        except Exception:
            pass

        if has_ens:
            data = np.moveaxis(data, [I_time, I_y, I_x, I_ens], [0, 1, 2, 3])
            if len(data.shape) == 5:
                data = data[:, :, :, :, 0]
        else:
            data = np.moveaxis(data, [I_time, I_y, I_x], [0, 1, 2])
            if len(data.shape) == 4:
                data = data[:, :, :, 0]
            data = np.expand_dims(data, 3)

        I, J = self.get_i_j(lats, lons)
        # print I, J
        Ivalid = np.where((I >= 0) & (J >= 0))[0]
        for lt in range(len(self.leadtimes)):
            if hood == 0:
                values[lt, Ivalid, :] = data[lt, I[Ivalid], J[Ivalid], :]
            else:
                h = 0
                for i in range(-hood, hood+1):
                    for j in range(-hood, hood+1):
                        Iens = range(len(members) * h, len(members) * (h+1))
                        II = [I[iv] + i for iv in Ivalid]
                        JJ = [J[iv] + j for iv in Ivalid]
                        for e in range(len(Iens)):
                            values[lt, Ivalid, Iens[e]] = data[lt, II, JJ, e]
                        h += 1
        print "Getting values %.2f" % (time.time() - time_0)

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
        file = netCDF4.Dataset(self.filename, 'r')
        data = file.variables[variable]
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
        Ivalid = np.where((I >= 0) & (J >= 0))[0]
        for i in range(len(self.leadtimes)):
            for e in range(E):
                indices = np.array(i * X*Y*E + I[Ivalid]*Y*E + J[Ivalid]*E + e, 'int')
                temp = q[indices]
                values[i, Ivalid, e] = temp
        file.close()
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
        file = netCDF4.Dataset(self.filename, 'r')
        proj = None
        N = len(lats)
        I = list()
        J = list()
        xvar, yvar = self.get_xy()

        if xvar is not None and yvar is not None:
            x = file.variables[xvar][:]
            y = file.variables[yvar][:]
            for v in file.variables:
                if hasattr(file.variables[v], "proj4"):
                    projection = str(file.variables[v].proj4)
                    proj = pyproj.Proj(projection)

            if proj is not None:
                # Project lat lon onto grid projection
                xx, yy = proj(lons, lats)
                Ix = np.argsort(x)
                Iy = np.argsort(y)
                IIx = np.argsort(Ix)
                IIy = np.argsort(Iy)
                J = [IIx[int(xxx)] for xxx in np.round(np.interp(xx, x[Ix], range(len(x)), 0, len(x) - 1))]
                I = [IIy[int(yyy)] for yyy in np.round(np.interp(yy, y[Iy], range(len(y)), 0, len(y) - 1))]
        if proj is None:
            print "Could not find projection. Computing nearest neighbour from lat/lon."
            # Find lat and lons
            if "latitude" in file.variables:
                ilats = file.variables["latitude"][:]
                ilons = file.variables["longitude"][:]
            elif "lat" in file.variables:
                ilats = file.variables["lat"][:]
                ilons = file.variables["lon"][:]
            else:
                met2verif.util.error("Cannot determine latitude and longitude")
            is_regular_grid = len(ilats.shape) == 1 and len(ilons.shape) == 1
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

        file.close()
        return np.array(I, int), np.array(J, int)

    def get_xy(self):
        file = netCDF4.Dataset(self.filename, 'r')
        xvar = None
        yvar = None
        if "x" in file.variables and "y" in file.variables:
            xvar = "x"
            yvar = "y"
        elif "X" in file.variables and "Y" in file.variables:
            xvar = "X"
            yvar = "Y"
        elif "Xc" in file.variables and "Yc" in file.variables:
            xvar = "Xc"
            yvar = "Yc"
        file.close()
        return xvar, yvar
