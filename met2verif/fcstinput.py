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


def get(filename, nn_tree_guess):
   return Netcdf(filename, nn_tree_guess)


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
   def __init__(self, filename, nn_tree_guess=None):
      import time
      start = time.time()
      self.filename = filename
      self.file = netCDF4.Dataset(self.filename, 'r')

      # Find lat and lons
      if "latitude" in self.file.variables:
         self.lats = self.file.variables["latitude"][:]
         self.lons = self.file.variables["longitude"][:]
      elif "lat" in self.file.variables:
         self.lats = self.file.variables["lat"][:]
         self.lons = self.file.variables["lon"][:]
      else:
         abort()

      self.nn_tree = None
      self.proj = None
      if nn_tree_guess is not None:
         print "Reusing tree"
         # TODO: Check if compatible
         if "x" in self.file.variables:
            x = self.file.variables["x"][:]
            y = self.file.variables["y"][:]
         xx, yy = np.meshgrid(x, y)
         guess_coords = nn_tree_guess.data
         coords = np.zeros([len(self.lats.flatten()), 2])
         coords[:, 0] = xx.flatten()
         coords[:, 1] = yy.flatten()
         if guess_coords.shape == coords.shape and (guess_coords == coords).all():
            self.nn_tree = nn_tree_guess
         else:
            print "Cannot reuse tree: Missmatch in coordinates"
         for v in self.file.variables:
            if hasattr(self.file.variables[v], "proj4"):
               projection = str(self.file.variables[v].proj4)
               self.proj = pyproj.Proj(projection)

      if self.nn_tree is None:
         for v in self.file.variables:
            if hasattr(self.file.variables[v], "proj4"):
               projection = str(self.file.variables[v].proj4)
               self.proj = pyproj.Proj(projection)
               print "Creating KDTree"
               if "x" in self.file.variables:
                  x = self.file.variables["x"][:]
                  y = self.file.variables["y"][:]
               else:
                  continue
               xx, yy = np.meshgrid(x, y)
               self.lons, self.lats = self.proj(xx, yy, inverse=True)

               coords = np.zeros([len(self.lats.flatten()), 2])
               coords[:, 0] = xx.flatten()
               coords[:, 1] = yy.flatten()
               self.nn_tree = scipy.spatial.KDTree(coords)

      # print "Initialization took %f seconds" % (time.time() - start)

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
      data = self.file.variables[variable]
      data = data[:].astype(float)
      if(len(data.shape) == 4):
         X = data.shape[2]
         Y = data.shape[3]
         if members is None:
            data = np.nanmean(data, axis=1)
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
         else:
            data = np.nanmean(data[:, 0, members, :, :], axis=1)
      else:
         met2verif.util.error("Input data has strange dimensions")
      q = data.flat
      I, J = self.get_i_j(lats, lons)
      values = np.nan * np.zeros([len(self.leadtimes), len(lats)])
      for i in range(len(self.leadtimes)):
         Ivalid = np.where((I != 0) & (J != 0) & (I != self.lats.shape[0] - 1) & (J != self.lats.shape[1] - 1))[0]
         for k in range(len(I)):
            if k not in Ivalid:
               pass
               # print "Removing stations %d. Outside domain." % k
         indices = np.array(i * X*Y + I[Ivalid]*Y + J[Ivalid], 'int')
         temp = q[indices]
         values[i, Ivalid] = temp

      return values

   def get_i_j(self, lats, lons):
      N = len(lats)
      I = list()
      J = list()
      if self.nn_tree is not None and self.proj is not None:
         # Project lat lon onto grid projection
         xx, yy = self.proj(lons, lats)
         for i in range(N):
            x = xx[i]
            y = yy[i]
            dist, index = self.nn_tree.query([x, y])
            indices = np.unravel_index(index, self.lats.shape)
            I += [indices[0]]
            J += [indices[1]]
      else:
         print "Could not find tree"
         coords = np.zeros([len(self.lats.flatten()), 2])
         # return np.array([1]*N, int), np.array([1]*N, int)
         coords[:, 0] = self.lats.flatten()
         coords[:, 1] = self.lons.flatten()
         for i in range(N):
            currlat = lats[i]
            currlon = lons[i]
            dist = met2verif.util.distance(currlat, currlon, self.lats, self.lons)
            indices = np.unravel_index(dist.argmin(), dist.shape)
            I += [indices[0]]
            J += [indices[1]]

      return np.array(I, int), np.array(J, int)
