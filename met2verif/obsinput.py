import met2verif.util
import numpy as np


def get(filename):
    file = open(filename, 'r')
    header = file.readline()
    file.close()
    if len(header) > 5:
        if header[0:5] == " Stnr":
            return Kdvh(filename)
        elif header[0:2] == "id":
            return Text(filename)
        else:
            words = header.split(';')
            if "lat" in words:
                return Titan(filename)
            else:
                raise NotImplementedError
    else:
        raise NotImplementedError


class ObsInput(object):
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


class Text(ObsInput):
    def __init__(self, filename):
        self.filename = filename

    def read(self, variable):
        ifile = open(self.filename, 'r')
        header = ifile.readline().replace('\n', '').split(';')
        header = [i for i in header if i is not '']
        Iid = header.index("id")
        Idate = header.index("date")
        Ihour = header.index("hour")
        Ivar = header.index(variable)
        if None in [Iid, Idate, Ihour, Ivar]:
            print("The header in %s is invalid:" % ifilename)
            print(header)
            ifile.close()
            return {}
        times = list()
        obs = list()
        ids = list()

        date2unixtime_map = dict()  # Lookup table for converting date to unixtime
        for line in ifile:
            data = line.strip().split(';')
            if len(data) > 1 and met2verif.util.is_number(data[0]):
                try:
                    id = int(data[Iid])
                    date = int(data[Idate])
                    time = int(data[Ihour])
                except Exception:
                    print("Could not read the following:")
                    print(data)
                    continue
                raw = data[Ivar]
                if(raw == '.'):
                    value = np.nan
                elif(raw == 'x'):
                    value = np.nan
                else:
                    value = float(data[Ivar])
                if not np.isnan(value):
                    if date not in date2unixtime_map:
                        ut = met2verif.util.date_to_unixtime(date)
                        date2unixtime_map[date] = ut
                    else:
                        ut = date2unixtime_map[date]
                    times += [ut + time*3600]
                    ids += [id]
                    obs += [value]

        data = {"times": np.array(times, int), "ids": np.array(ids, int), "obs": np.array(obs)}
        return data


class Kdvh(ObsInput):
    def __init__(self, filename, locations_file=None):
        self.filename = filename

    def read(self, variable):
        ifile = open(self.filename, 'r')
        header = ifile.readline().replace('\n', '').split(' ')
        header = [i for i in header if i is not '']
        Iid = header.index("Stnr")
        Iyear = header.index("Year")
        Imonth = header.index("Month")
        Iday = header.index("Day")
        Itime = header.index("Time(UTC)")
        Imin = header.index("MIN") if "MIN" in header else None
        Ivar = header.index(variable)
        if None in [Iid, Iyear, Imonth, Iday, Itime, Ivar]:
            print("The header in %s is invalid:" % ifilename)
            print(header)
            ifile.close()
            return {}
        times = list()
        obs = list()
        ids = list()

        date2unixtime_map = dict()  # Lookup table for converting date to unixtime
        for line in ifile:
            data = line.strip().split(' ')
            data = [i for i in data if i is not '']
            if len(data) > 1 and met2verif.util.is_number(data[0]):
                try:
                    id = int(data[Iid])
                    date = int(data[Iyear])*10000 + int(data[Imonth])*100 + int(data[Iday])
                    time = int(data[Itime])
                except Exception:
                    print("Could not read the following:")
                    print(data)
                    continue
                min = 0
                if Imin is not None:
                    min = float(data[Imin])
                    time = time + min / 60.0
                raw = data[Ivar]
                if(raw == '.'):
                    value = np.nan
                elif(raw == 'x'):
                    value = np.nan
                else:
                    value = float(data[Ivar])
                if not np.isnan(value):
                    if date not in date2unixtime_map:
                        ut = met2verif.util.date_to_unixtime(date)
                        date2unixtime_map[date] = ut
                    else:
                        ut = date2unixtime_map[date]
                    times += [ut + time*3600]
                    ids += [id]
                    obs += [value]

        data = {"times": np.array(times, int), "ids": np.array(ids, int), "obs": np.array(obs)}
        return data


class Titan(ObsInput):
    def __init__(self, filename):
        self.filename = filename

    def read(self, variable):
        ifile = open(self.filename, 'r')
        header = ifile.readline().replace('\n', '').split(' ')
        header = [i for i in header if i is not '']
        Ilat = header.index("lat")
        Ilon = header.index("lon")
        Ielev = header.index("elev")
        Ivar = header.index("value")
        if None in [Ilat, Ilon, Ielev, Ivar]:
            print("The header in %s is invalid:" % ifilename)
            print(header)
            ifile.close()
            return {}
        times = list()
        obs = list()
        ids = list()
