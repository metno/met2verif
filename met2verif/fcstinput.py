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
   def __init__(self, filename, coord_gues=None):
      import time
      start = time.time()
      self.filename = filename
      try:
         self.file = netCDF4.Dataset(self.filename, 'r')
      except Exception as e:
         print("Could not open file '%s'. %s." % (filename, e))
         raise

   @property
   def variables(self):
      return self.file.variables.keys()

   @property
   def times(self):
      return self.file.variables["time"][:]

   @property
   def forecast_reference_time(self):
      # return self.file["time"][0]
      # TODO
      return self.file.variables["forecast_reference_time"][:]

   @property
   def leadtimes(self):
      return (self.times - self.forecast_reference_time) / 3600

   def extract(self, lats, lons, variable, members=[0]):
      """
      Arguments:
         lats (np.array): Array of latitudes
         lons (np.array): Array of longitudes
         variable (str): Variable name
         members (list): Which ensemble members to use? If None, then use all
      """
      values = np.nan * np.zeros([len(self.leadtimes), len(lats)])
      s_time = time.time()
      data = self.file.variables[variable][:]
      if(len(data.shape) == 4):
         X = data.shape[2]
         Y = data.shape[3]
         if members is None:
            data = np.nanmean(data, axis=1)
         elif len(members) == 1:
            data = data[:, members[0], :, :]
         else:
            data = np.nanmean(data[:, members, :, :], axis=1)
      elif(len(data.shape) == 3):
         X = data.shape[1]
         Y = data.shape[2]
      elif(len(data.shape) == 5):
         X = data.shape[3]
         Y = data.shape[4]
         if members is None:
            data = np.nanmean(data[:, 0, :, :, :], axis=1)
         elif len(members) == 1:
            data = data[:, 0, members[0], :, :]
         else:
            data = np.nanmean(data[:, 0, members, :, :], axis=1)
      else:
         met2verif.util.error("Input data has strange dimensions")
      q = data.flat
      I, J = self.get_i_j(lats, lons)
      for i in range(len(self.leadtimes)):
         Ivalid = np.where((I >= 0) & (J >= 0))[0]
         indices = np.array(i * X*Y + I[Ivalid]*Y + J[Ivalid], 'int')
         temp = q[indices]
         values[i, Ivalid] = temp
      print "Getting values %.2f seconds" % (time.time() - s_time)

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
      # Ivalid = np.where((I != 0) & (J != 0) & (I != lats.shape[0] - 1) & (J != lats.shape[1] - 1))[0]
      proj = None
      x = self.file.variables["x"][:]
      y = self.file.variables["y"][:]
      for v in self.file.variables:
         if hasattr(self.file.variables[v], "proj4"):
            projection = str(self.file.variables[v].proj4)
            proj = pyproj.Proj(projection)

      N = len(lats)
      I = list()
      J = list()
      if proj is not None:
         # Project lat lon onto grid projection
         xx, yy = proj(lons, lats)
         J = [int(xxx) for xxx in np.round(np.interp(xx, x, range(len(x)), -1, -1))]
         I = [int(yyy) for yyy in np.round(np.interp(yy, y, range(len(y)), -1, -1))]
      else:
         print "Could not find projection. Computing nearest neighbour from lat/lon."
         # Find lat and lons
         if "latitude" in self.file.variables:
            lats = self.file.variables["latitude"][:]
            lons = self.file.variables["longitude"][:]
         elif "lat" in self.file.variables:
            lats = self.file.variables["lat"][:]
            lons = self.file.variables["lon"][:]
         else:
            abort()

         coords = np.zeros([len(lats.flatten()), 2])
         # return np.array([1]*N, int), np.array([1]*N, int)
         coords[:, 0] = lats.flatten()
         coords[:, 1] = lons.flatten()
         for i in range(N):
            currlat = lats[i]
            currlon = lons[i]
            dist = met2verif.util.distance(currlat, currlon, lats, lons)
            indices = np.unravel_index(dist.argmin(), dist.shape)
            I += [indices[0]]
            J += [indices[1]]

      return np.array(I, int), np.array(J, int)
