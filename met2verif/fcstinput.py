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

"""

   Arguments:
      data: N-D array of data
      ml: Prefer this model level, if there are several levels

   Returns:
      np.array: 3D array: Time X, Y

"""
def get_field(data, ml=0, member=None):
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
   def __init__(self, filename):
      self.filename = filename
      self.file = netCDF4.Dataset(self.filename, 'r')
      if "latitude" in self.file.variables:
         self.lats = self.file.variables["latitude"][:]
         self.lons = self.file.variables["longitude"][:]
      elif "lat" in self.file.variables:
         self.lats = self.file.variables["lat"][:]
         self.lons = self.file.variables["lon"][:]
      else:
         proj = None
         for v in self.file.variables:
            if hasattr(self.file.variables[v], "proj4"):
               projection = str(self.file.variables[v].proj4)
               proj = pyproj.Proj(projection)
               print "Reading projection information"
               if "x" in self.file.variables:
                  x = self.file.variables["x"][:]
                  y = self.file.variables["y"][:]
               else:
                  abort()
               xx, yy = np.meshgrid(x, y)
               self.lons, self.lats = proj(xx, yy, inverse=True)


   @property
   def times(self):
      return self.file.variables["time"][:]

   @property
   def forecast_reference_time(self):
      return self.file.variables["forecast_reference_time"][:]

   @property
   def leadtimes(self):
      return (self.times - self.forecast_reference_time) / 3600

   def extract(self, lats, lons, variable):
      """
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
      elif(len(data.shape) == 3):
         X = data.shape[1]
         Y = data.shape[2]
      elif(len(data.shape) == 5):
         X = data.shape[3]
         Y = data.shape[4]
         data = np.mean(data, axis=2)
         print "Taking the ensemble mean, since 5D array"
      else:
         met2verif.util.error("Input data has strange dimensions")
      q = data.flat
      I, J = self.get_i_j(lats, lons)
      values = np.zeros([len(self.leadtimes), len(lats)])
      for i in range(len(self.leadtimes)):
         indices = np.array(i * X*Y + I*Y + J, 'int')
         temp = q[indices]
         values[i, :] = temp

      return values

   def get_i_j(self, lats, lons):
      N = len(lats)
      coords = np.zeros([len(self.lats.flatten()), 2])
      # return np.array([1]*N, int), np.array([1]*N, int)
      coords[:, 0] = self.lats.flatten()
      coords[:, 1] = self.lons.flatten()
      nn_tree = scipy.spatial.KDTree(coords)
      I = list()
      J = list()
      for i in range(N):
         currlat = lats[i]
         currlon = lons[i]
         dist, index = nn_tree.query([currlat, currlon])
         indices = np.unravel_index(index, self.lats.shape)
         I += [indices[0]]
         J += [indices[1]]
      return np.array(I, int), np.array(J, int)
