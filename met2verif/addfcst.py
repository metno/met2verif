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


def add_subparser(parser):
   subparser = parser.add_parser('addfcst', help='Adds forecasts to verif file')
   subparser.add_argument('files', type=str, help='Forecast files', nargs="+")
   subparser.add_argument('-c', help='Clear forecasts?', dest="clear", action="store_true")
   subparser.add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
   subparser.add_argument('-r', default=[0], type=met2verif.util.parse_numbers, help='What hours after initialization should this be repeated for?', dest="repeats")
   subparser.add_argument('-f', help='Overwrite values if they are there already', dest="overwrite", action="store_true")
   subparser.add_argument('-s', help='Sort times if needed?', dest="sort", action="store_true")
   subparser.add_argument('-v', type=str, help='variable name', dest="variable", required=True)
   subparser.add_argument('--add', type=float, default=0, help='Add this value to all forecasts (--multiply is done before --add)')
   subparser.add_argument('--multiply', type=float, default=1, help='Multiply all forecasts with this value')
   subparser.add_argument('--debug', help='Display debug information', action="store_true")

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


   inputs = list()
   nn_tree_guess = None
   for filename in args.files:
      input = met2verif.fcstinput.get(filename, nn_tree_guess)
      nn_tree_guess = input.nn_tree
      inputs += [input]

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

   if args.sort:
      Itimes = np.argsort(new_times)
      if (Itimes != range(len(new_times))).any():
         if args.debug:
            print "Sorting times to be in ascending order"
         new_times = new_times[Itimes]
         fcst = fcst[Itimes, :, :]
         file.variables["obs"][:] = file.variables["obs"][Itimes, :, :]

   file.variables["time"][:] = new_times
   orig_lats = file.variables["lat"][:]
   orig_lons = file.variables["lon"][:]

   for input in inputs:
      print "Processing %s" % input.filename

      values = None
      for r, delay in enumerate(args.repeats):
         frt = input.forecast_reference_time + delay * 3600
         new_leadtimes = input.leadtimes - delay
         Itime = np.where(new_times == frt)[0]
         assert(len(Itime) == 1)
         Ilt_verif = [i for i in range(len(orig_leadtimes)) if orig_leadtimes[i] in new_leadtimes]
         Ilt_fcst = [np.where(lt == new_leadtimes)[0][0] for lt in orig_leadtimes[Ilt_verif]]

         # Determine if we need to write data from this filename
         do_write = args.overwrite or np.sum(np.isnan(fcst[Itime, Ilt_verif, :]) == 0) == 0
         if do_write:
            if values is None:
               # Only load values once
               values = input.extract(orig_lats, orig_lons, args.variable)
            fcst[Itime, Ilt_verif, :] = values[Ilt_fcst, :] * args.multiply + args.add
         elif args.debug:
            print "We do not need to read this file"

   file.variables["fcst"][:] = fcst
