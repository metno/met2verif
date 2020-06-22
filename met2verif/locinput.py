import sys
import os
import numpy as np
import netCDF4


import met2verif.util
import verif.input


def get(filename):
    _stderr = sys.stderr
    _stdout = sys.stdout
    try:
        # Avoid showing error message
        null = open(os.devnull,'wb')
        sys.stdout = sys.stderr = null

        file = verif.input.get_input(filename)
        f = Verif(filename)
        sys.stderr = _stderr
        sys.stdout = _stdout
        return f
    except:
        sys.stderr = _stderr
        sys.stdout = _stdout
        file = open(filename, 'r', encoding = "ISO-8859-1")
        for i in range(5):
            header = file.readline()
            print(header)
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

    def read(self):
        raise NotImplementedError


class Verif(LocInput):
    def __init__(self, filename):
        self.filename = filename

    def read(self):
        file = verif.input.get_input(self.filename)
        locations = dict()
        for location in file.locations:
            locations[location.id] = {"lat": location.lat, "lon": location.lon, "elev": location.elev}
        return locations


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
        Iwmo = header.index('WMO_NO')
        for line in locfile:
            if len(line) <= 1:
                continue
            if line[0] == "#":
                continue
            line = line.strip().split(';')
            if '-' in [line[col] for col in [Iid, Ilat, Ilon, Ielev]]:
                continue
            if '' in [line[col] for col in [Iid, Ilat, Ilon, Ielev]]:
                continue
            id = int(line[Iid])
            lat = float(line[Ilat])
            lon = float(line[Ilon])
            elev = float(line[Ielev])
            wmo = np.nan
            try:
                wmo = int(line[Iwmo])
            except Exception:
                pass
            locations[id] = {"lat": lat, "lon": lon, "elev": elev, "wmo": wmo}
        return locations


class Comps(LocInput):
    def __init__(self, filename):
        self.filename = filename

    def read(self):
        locfile = open(self.filename, 'r', encoding = "ISO-8859-1")
        locations = dict()
        for line in locfile:
            if(line[0] is not '#'):
                line = line.split(' ')
                line = [i for i in line if i is not '']
                id = int(line[0])
                lat = -999
                lon = -999
                elev = -999
                locations[id] = {"lat": lat, "lon": lon, "elev": elev}
                for at in line:
                    at = at.strip().split('=')
                    if len(at) == 2:
                        try:
                            value = float(at[1])
                        except Exception as e:
                            value = at[1]
                        locations[id][at[0]] = value
        return locations
