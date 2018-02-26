import sys
import argparse
import met2verif.util
import met2verif.version
import netCDF4
import numpy as np
import os
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
   subparser.add_argument('--debug', help='Display debug information', action="store_true")
   subparser.add_argument('--force_range', type=str, default=None, help='Remove values outside the range [min,max]', dest="range")

   return subparser


def run(parser):
   args = parser.parse_args()

   ofilename = args.verif_file

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

   if args.sort:
      Itimes = np.argsort(new_times)
      if (Itimes != range(len(new_times))).any():
         if args.debug:
            print "Sorting times to be in ascending order"
         new_times = new_times[Itimes]
         obs = obs[Itimes, :, :]
         file.variables["fcst"][:] = file.variables["fcst"][Itimes, :, :]

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
