import argparse
import met2verif.util
import met2verif.version
import netCDF4
import numpy as np
import os
import sys
import met2verif.obsinput
import met2verif.fcstinput
import met2verif.locinput
import met2verif.addfcst


def add_subparser(parser):
   subparser = parser.add_parser('addobs', help='Adds observations to verif file')
   subparser.add_argument('files', type=str, help='Observation files', nargs="+")
   subparser.add_argument('-c', help='Clear observations?', dest="clear", action="store_true")
   subparser.add_argument('-i', type=met2verif.util.parse_numbers, default=[0], help='Initialization hours', dest="inithours")
   subparser.add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
   subparser.add_argument('-s', help='Sort times if needed?', dest="sort", action="store_true")
   subparser.add_argument('-v', type=str, help='KDVH Variable', dest="variable", required=True)
   subparser.add_argument('--add', type=float, default=0, help='Add this value to all forecasts (--multiply is done before --add)')
   subparser.add_argument('--multiply', type=float, default=1, help='Multiply all forecasts with this value')
   subparser.add_argument('--debug', help='Display debug information', action="store_true")
   subparser.add_argument('--force_range', metavar="MIN,MAX", type=met2verif.util.parse_numbers, help='Remove values outside the range min,max', dest="range")

   return subparser


def run(parser, argv=sys.argv[1:]):
   args = parser.parse_args(argv)

   if not os.path.exists(args.verif_file):
      met2verif.util.error("File '%s' does not exist" % args.verif_file)

   file = netCDF4.Dataset(args.verif_file, 'a')
   times = file.variables["time"]
   if len(times) == 0:
      times_orig = []
   else:
      times_orig = times[:]

   ids_orig = np.array(file.variables["location"][:])
   leadtimes_orig = np.array(file.variables["leadtime"][:])

   """
   Create a dictionary where new observations from the files are added
   """
   data = {"times": np.zeros(0, int), "ids": np.zeros(0, int), "obs": np.zeros(0)}
   for filename in args.files:
      input = met2verif.obsinput.get(filename)
      curr_data = input.read(args.variable)
      for key in data:
         data[key] = np.append(data[key], curr_data[key])

   """
   Read the existing observation data and expand array to allow for the new times
   to be added. This array can be resorted such that times are in chronological order.
   """
   file_valid_times = np.unique(data["times"]).tolist()
   file_avail_init_times = list()
   for leadtime_orig in leadtimes_orig:
      file_avail_init_times += [(t - leadtime_orig * 3600) for t in file_valid_times]
   times_file = [t for t in file_avail_init_times if (t % 86400)/3600 in args.inithours]
   times_all = np.unique(np.append(times_orig, times_file))
   times_add = np.sort(np.setdiff1d(times_all, times_orig))
   times_new = np.append(times_orig, times_add)
   if args.debug:
      if len(times_add) == 0:
         print "No new initialization times added"
      else:
         print "Adding new intialization times:\n   " + '\n   '.join([met2verif.util.unixtime_to_str(t) for t in times_add])

   new_ids = [id for id in np.unique(data["ids"]) if id in ids_orig]
   valid_times = np.zeros([len(times_new), len(leadtimes_orig)], int)
   for t in range(len(times_new)):
      for l in range(len(leadtimes_orig)):
         valid_times[t, l] = times_new[t] + leadtimes_orig[l] * 3600

   obs = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig)])
   if len(times_orig) > 0 and not args.clear:
      obs[range(len(times_orig)), :, :] = file.variables["obs"][:]

   if args.sort:
      Itimes = np.argsort(times_new)
      if (Itimes != range(len(times_new))).any():
         if args.debug:
            print "Sorting times to be in ascending order"
         times_new = times_new[Itimes]
         obs = obs[Itimes, :, :]
         file.variables["fcst"][:] = file.variables["fcst"][Itimes, :, :]

   file.variables["time"][:] = times_new

   """
   Place each new observation into the appropriate time and leadtime slots
   """
   for i, id in enumerate(new_ids):
      I = np.where(data["ids"] == id)[0]
      Iloc = np.where(ids_orig == id)[0][0]
      curr_valid_times = data["times"][I]
      curr_obs = data["obs"][I]
      for j in range(len(curr_obs)):
         curr_valid_time = curr_valid_times[j]
         II = np.where(valid_times == curr_valid_time)
         # Slow
         # for k in range(len(II[0])):
         #    file.variables["obs"][II[0][k], II[1][k], Iloc] = curr_obs[j]
         if len(II[0]) > 0:
            value = curr_obs[j]
            if curr_obs[j] != -999:
               value *= args.multiply + args.add
            obs[II[0], II[1], [Iloc]*len(II[0])] = value

   """ Remove observations outside range """
   if args.range is not None:
      if len(args.range) != 2:
         met2verif.util.error("--force_range must be a vector of length 2")
      obs[obs < args.range[0]] = np.nan
      obs[obs > args.range[1]] = np.nan

   obs[np.isnan(obs)] = netCDF4.default_fillvals['f4']
   file.variables["obs"][:] = obs

   curr_times = list()
   file.close()
