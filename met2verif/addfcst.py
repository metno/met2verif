import argparse
import copy
import netCDF4
import numpy as np
import os
import sys
import met2verif.fcstinput
import met2verif.locinput
import met2verif.obsinput
import met2verif.util
import met2verif.version


def add_subparser(parser):
   subparser = parser.add_parser('addfcst', help='Adds forecasts to verif file')
   subparser.add_argument('files', type=str, help='Forecast files', nargs="+")
   subparser.add_argument('-c', help='Clear forecasts?', dest="clear", action="store_true")
   subparser.add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
   subparser.add_argument('-r', default=[0], type=met2verif.util.parse_numbers, help='What hours after initialization should this be repeated for?', dest="repeats")
   subparser.add_argument('-e', type=met2verif.util.parse_ints, help='What ensemble member(s) to use? If unspecified, then take the ensemble mean.', dest="members")
   subparser.add_argument('-f', help='Overwrite values if they are there already', dest="overwrite", action="store_true")
   subparser.add_argument('-s', help='Sort times if needed?', dest="sort", action="store_true")
   subparser.add_argument('-v', type=str, help='variable name', dest="variable", required=True)
   subparser.add_argument('--add', type=float, default=0, help='Add this value to all forecasts (--multiply is done before --add)')
   subparser.add_argument('--multiply', type=float, default=1, help='Multiply all forecasts with this value')
   subparser.add_argument('--debug', help='Display debug information', action="store_true")

   return subparser


def run(parser):
   args = parser.parse_args()

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
   Read inputs
   """
   inputs = list()
   for filename in args.files:
      inputs += [met2verif.fcstinput.get(filename)]

   """
   Read forecast data and expand the array to allow new times to be created. This
   array can be resorted such that times are in chronological order.
   """

   times_file = np.zeros(0)
   for input in inputs:
      for delay in args.repeats:
         frt = input.forecast_reference_time + delay * 3600
         if not np.isnan(frt):
            times_file = np.append(times_file, frt)
   times_all = np.unique(np.append(times_orig, times_file))
   times_add = np.sort(np.setdiff1d(times_all, times_orig))
   times_new = np.append(times_orig, times_add)
   if args.debug:
      if len(times_add) == 0:
         print "No new initialization times added"
      else:
         print "Adding new intialization times:\n   " + '\n   '.join([met2verif.util.unixtime_to_str(t) for t in times_add])

   fcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig)])
   if len(times_orig) > 0 and not args.clear:
      fcst[range(len(times_orig)), :, :] = file.variables["fcst"][:]
      # Convert fill values to nan
      fcst[fcst == netCDF4.default_fillvals['f4']] = np.nan

   if args.sort:
      Itimes = np.argsort(times_new)
      if (Itimes != range(len(times_new))).any():
         if args.debug:
            print "Sorting times to be in ascending order"
         times_new = times_new[Itimes]
         fcst = fcst[Itimes, :, :]
         file.variables["obs"][:] = file.variables["obs"][Itimes, :, :]

   file.variables["time"][:] = times_new
   lats_orig = file.variables["lat"][:]
   lons_orig = file.variables["lon"][:]

   for input in inputs:
      print "Processing %s" % input.filename
      try:
         leadtimes = input.leadtimes

         curr_fcst = None
         for r, delay in enumerate(args.repeats):
            frt = input.forecast_reference_time + delay * 3600
            leadtimes_new = leadtimes - delay
            Itime = np.where(times_new == frt)[0]
            assert(len(Itime) == 1)
            Ilt_verif = [i for i in range(len(leadtimes_orig)) if leadtimes_orig[i] in leadtimes_new]
            Ilt_fcst = [np.where(lt == leadtimes_new)[0][0] for lt in leadtimes_orig[Ilt_verif]]

            # Determine if we need to write data from this filename
            do_write = args.overwrite or np.sum(np.isnan(fcst[Itime, Ilt_verif, :]) == 0) == 0
            if do_write:
               if curr_fcst is None:
                  # Only load values once
                  curr_fcst = input.extract(lats_orig, lons_orig, args.variable, args.members)

               fcst[Itime, Ilt_verif, :] = curr_fcst[Ilt_fcst, :] * args.multiply + args.add
            elif args.debug:
               print "We do not need to read this file"
      except Exception as e:
         print "Could not process"

   # Convert nans back to fill value
   fcst[np.isnan(fcst)] = netCDF4.default_fillvals['f4']
   file.variables["fcst"][:] = fcst
