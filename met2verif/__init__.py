import sys
import argparse
import met2verif.util
import met2verif.version
import netCDF4
import numpy as np
import os
import met2verif.obsinput
import met2verif.fcstinput


def main():
   parser = argparse.ArgumentParser(description='Iitialises and adds to verif file')
   parser.add_argument('--version', action="version", version=met2verif.version.__version__)
   subparsers = parser.add_subparsers(title="Choose one of these commands", dest="command")

   sp = dict()
   sp["init"] = subparsers.add_parser('init', help='Initialize verif file')
   sp["init"].add_argument('-l', help='Locations file', dest="locations_file", required=True)
   sp["init"].add_argument('-lt', type=met2verif.util.parse_numbers, help='Lead times (hours)', dest="leadtimes")
   sp["init"].add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
   sp["init"].add_argument('-s', help='Standard name', dest="standard_name")
   sp["init"].add_argument('-u', help='Units', dest="units")
   sp["init"].add_argument('--debug', help='Display debug information', action="store_true")

   sp["addobs"] = subparsers.add_parser('addobs', help='Adds observations to verif file')
   sp["addobs"].add_argument('files', type=str, help='Observation files', nargs="+")
   sp["addobs"].add_argument('-c', help='Clear observations?', dest="clear", action="store_true")
   sp["addobs"].add_argument('-i', type=met2verif.util.parse_numbers, default="0", help='Initialization hours', dest="inithours")
   sp["addobs"].add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
   sp["addobs"].add_argument('-v', type=str, help='KDVH Variable', dest="variable", required=True)
   sp["addobs"].add_argument('--debug', help='Display debug information', action="store_true")
   sp["addobs"].add_argument('--force_range', type=str, default=None, help='Remove values outside the range [min,max]', dest="range")

   sp["addfcst"] = subparsers.add_parser('addfcst', help='Adds forecasts to verif file')
   sp["addfcst"].add_argument('files', type=str, help='Forecast files', nargs="+")
   sp["addfcst"].add_argument('-c', help='Clear forecasts?', dest="clear", action="store_true")
   sp["addfcst"].add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
   sp["addfcst"].add_argument('-r', default=[0], type=met2verif.util.parse_numbers, help='What hours after initialization should this be repeated for?', dest="repeats")
   sp["addfcst"].add_argument('-v', type=str, help='variable name', dest="variable", required=True)
   sp["addfcst"].add_argument('--add', type=float, default=0, help='Add this value to all forecasts (--multiply is done before --add)')
   sp["addfcst"].add_argument('--multiply', type=float, default=1, help='Multiply all forecasts with this value')
   sp["addfcst"].add_argument('--debug', help='Display debug information', action="store_true")

   if len(sys.argv) == 1:
      parser.print_help()
      sys.exit(1)
   elif len(sys.argv) == 2 and sys.argv[1] == "--version":
      print(met2verif.version.__version__)
      return
   elif len(sys.argv) == 2 and sys.argv[1] in sp.keys():
      sp[sys.argv[1]].print_help()
      return

   args = parser.parse_args()

   ofilename = args.verif_file

   if args.command == "init":
      # Create lat/lon/elev map
      slats = dict()
      slons = dict()
      selevs = dict()
      locfile = open(args.locations_file, 'r')
      for line in locfile:
         if(line[0] is not '#'):
            line = line.split(' ')
            line = [i for i in line if i is not '']
            id   = int(line[0])
            slats[id] = -999
            slons[id] = -999
            selevs[id] = -999
            for at in line:
               at = at.split('=')
               if(at[0] == "lat"):
                  slats[id] = float(at[1])
               elif(at[0] == "lon"):
                  slons[id] = float(at[1])
               elif(at[0] == "elev"):
                  selevs[id] = float(at[1])

      # Write file
      file = netCDF4.Dataset(ofilename, 'w', format="NETCDF3_CLASSIC")
      file.createDimension("time", None)
      file.createDimension("leadtime", len(args.leadtimes))
      file.createDimension("location", len(slats))
      vTime=file.createVariable("time", "i4", ("time",))
      vOffset=file.createVariable("leadtime", "f4", ("leadtime",))
      vLocation=file.createVariable("location", "i4", ("location",))
      vLat=file.createVariable("lat", "f4", ("location",))
      vLon=file.createVariable("lon", "f4", ("location",))
      vElev=file.createVariable("altitude", "f4", ("location",))
      vfcst=file.createVariable("fcst", "f4", ("time", "leadtime", "location"))
      vobs=file.createVariable("obs", "f4", ("time", "leadtime", "location"))
      if args.standard_name:
         file.standard_name = args.standard_name
      else:
         file.standard_name = "Unknown"
      if args.units:
         file.units = unit = args.units

      L = len(slats)
      lats = np.zeros(L, 'float')
      lons = np.zeros(L, 'float')
      elevs = np.zeros(L, 'float')
      ids = np.sort(slats.keys())
      for i in range(0, L):
         lats[i] = slats[ids[i]]
         lons[i] = slons[ids[i]]
         elevs[i] = selevs[ids[i]]
      vOffset[:] = args.leadtimes
      vLocation[:] = ids
      vLat[:] = lats
      vLon[:] = lons
      vElev[:] = elevs
      file.Conventions = "verif_1.0.0"
      file.close()

   else:
      if not os.path.exists(args.verif_file):
         met2verif.util.error("File '%s' does not exist" % args.verif_file)

      file = netCDF4.Dataset(args.verif_file, 'a')
      times = file.variables["time"]
      if len(times) == 0:
         orig_times = []
      else:
         orig_times = times[:]

      orig_ids = np.array(file.variables["location"][:])
      orig_leadtimes = np.array(file.variables["leadtime"][:])

      if args.command == "addobs":
         data = {"times": np.zeros(0, int), "ids": np.zeros(0, int), "obs": np.zeros(0)}
         for filename in args.files:
            input = met2verif.obsinput.get(filename)
            curr_data = input.read(args.variable)
            for key in data:
               data[key] = np.append(data[key], curr_data[key])

         file_valid_times = np.unique(data["times"]).tolist()
         file_avail_init_times = list()
         for orig_leadtime in orig_leadtimes:
            file_avail_init_times += [(t - orig_leadtime * 3600) for t in file_valid_times]
         file_times = [t for t in file_avail_init_times if (t % 86400)/3600 in args.inithours]
         all_times = np.unique(np.append(orig_times, file_times))
         add_times = np.sort(np.setdiff1d(all_times, orig_times))
         new_times = np.append(orig_times, add_times)
         if args.debug:
            if len(add_times) == 0:
               print "No new initialization times added"
            else:
               print "Adding new intialization times:\n   " + '\n   '.join([met2verif.util.unixtime_to_str(t) for t in add_times])

         new_ids = [id for id in np.unique(data["ids"]) if id in orig_ids]
         valid_times = np.zeros([len(new_times), len(orig_leadtimes)], int)
         for t in range(len(new_times)):
            for l in range(len(orig_leadtimes)):
               valid_times[t, l] = new_times[t] + orig_leadtimes[l] * 3600

         obs = np.nan * np.zeros([len(new_times), len(orig_leadtimes), len(orig_ids)])
         if len(orig_times) > 0 and not args.clear:
            obs[range(len(orig_times)), :, :] = file.variables["obs"][:]
         file.variables["time"][:] = new_times

         for i, id in enumerate(new_ids):
            I = np.where(data["ids"] == id)[0]
            Iloc = np.where(orig_ids == id)[0][0]
            curr_valid_times = data["times"][I]
            curr_obs = data["obs"][I]
            for j in range(len(curr_obs)):
               curr_valid_time = curr_valid_times[j]
               II = np.where(valid_times == curr_valid_time)
               # Slow
               # for k in range(len(II[0])):
               #    file.variables["obs"][II[0][k], II[1][k], Iloc] = curr_obs[j]
               if len(II[0]) > 0:
                  obs[II[0], II[1], [Iloc]*len(II[0])] = curr_obs[j]
         file.variables["obs"][:] = obs

         curr_times = list()
         file.close()
      elif args.command == "addfcst":
         inputs = [met2verif.fcstinput.get(filename) for filename in args.files]

         file_times = np.zeros(0)
         for input in inputs:
            for delay in args.repeats:
               frt = input.forecast_reference_time + delay * 3600
               file_times = np.append(file_times, frt)
         all_times = np.unique(np.append(orig_times, file_times))
         add_times = np.sort(np.setdiff1d(all_times, orig_times))
         new_times = np.append(orig_times, add_times)
         if args.debug:
            if len(add_times) == 0:
               print "No new initialization times added"
            else:
               print "Adding new intialization times:\n   " + '\n   '.join([met2verif.util.unixtime_to_str(t) for t in add_times])
         fcst = np.nan * np.zeros([len(new_times), len(orig_leadtimes), len(orig_ids)])
         if len(orig_times) > 0 and not args.clear:
            fcst[range(len(orig_times)), :, :] = file.variables["fcst"][:]
         file.variables["time"][:] = new_times
         orig_lats = file.variables["lat"]
         orig_lons = file.variables["lon"]

         for input in inputs:
            values = input.extract(orig_lats, orig_lons, args.variable)
            for r, delay in enumerate(args.repeats):
               frt = input.forecast_reference_time + delay * 3600
               new_leadtimes = input.leadtimes - delay
               Itime = np.where(new_times == frt)[0]
               assert(len(Itime) == 1)
               Ilt_verif = [i for i in range(len(orig_leadtimes)) if orig_leadtimes[i] in new_leadtimes]
               Ilt_fcst = [np.where(lt == new_leadtimes)[0][0] for lt in orig_leadtimes[Ilt_verif]]
               print r, delay, new_leadtimes, Itime
               print Ilt_verif, Ilt_fcst
               fcst[Itime, Ilt_verif, :] = values[Ilt_fcst, :]

         file.variables["fcst"][:] = fcst * args.multiply + args.add
         file.close()


if __name__ == '__main__':
   main()
