import met2verif.util
import numpy as np


def get(filename):
   file = open(filename, 'r')
   for i in range(5):
      header = file.readline()
      if len(header) < 5:
         continue
      else:
         if header[0:5] == "DEPAR":
            file.close()
            return Kdvh(filename)
         else:
            file.close()
            return Comps(filename)
   raise NotImplementedError


class LocInput(object):
   def __init__(self, filename):
      self.filename = filename


   def read(self, filename):
      raise NotImplementedError


class Kdvh(LocInput):
   def __init__(self, filename):
      self.filename = filename

   def read(self):
      locfile = open(self.filename, 'r')
      locations = dict()
      locfile.readline()
      header = locfile.readline().strip().split(';')
      Ilat = header.index('LAT_DEC')
      Ilon = header.index('LON_DEC')
      Iid = header.index('STNR')
      Ielev = header.index('AMSL')
      for line in locfile:
         if len(line) <= 1:
            continue
         line = line.strip().split(';')
         if '-' in [line[col] for col in [Iid, Ilat, Ilon, Ielev]]:
            continue
         if '' in [line[col] for col in [Iid, Ilat, Ilon, Ielev]]:
            continue
         id   = int(line[Iid])
         lat = float(line[Ilat])
         lon = float(line[Ilon])
         elev = float(line[Ielev])
         locations[id] = {"lat": lat, "lon": lon, "elev": elev}
      return locations


class Comps(LocInput):
   def __init__(self, filename):
      self.filename = filename

   def read(self):
      locfile = open(self.filename, 'r')
      locations = dict()
      for line in locfile:
         if(line[0] is not '#'):
            line = line.split(' ')
            line = [i for i in line if i is not '']
            id   = int(line[0])
            lat = -999
            lon = -999
            elev = -999
            for at in line:
               at = at.split('=')
               if(at[0] == "lat"):
                  lat = float(at[1])
               elif(at[0] == "lon"):
                  lon = float(at[1])
               elif(at[0] == "elev"):
                  elev = float(at[1])
            locations[id] = {"lat": lat, "lon": lon, "elev": elev}
      return locations
