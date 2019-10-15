import argparse
import copy
import netCDF4
import numpy as np
import os
import sys
import time
import traceback
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
    subparser.add_argument('-a', default="mean", help='Aggregator for computing fcst', dest="aggregator", choices=["mean", "median", "min", "max"])
    subparser.add_argument('-f', help='Overwrite values if they are there already', dest="overwrite", action="store_true")
    subparser.add_argument('-s', help='Sort times if needed?', dest="sort", action="store_true")
    subparser.add_argument('-n', default=0, type=int, help='Neighbourhood radius', dest="hood")
    subparser.add_argument('-v', type=str, help='Variable name in forecast files', dest="variable", required=True)
    subparser.add_argument('-vo', default="fcst", type=str, help='Variable name in verif file', dest="ovariable")
    subparser.add_argument('-w', default=1, type=int, help='Time aggregation window in number of timesteps of input file', dest="time_window")
    subparser.add_argument('--windspeed', help='Compute wind speed?', action="store_true")
    subparser.add_argument('--add', type=float, default=0, help='Add this value to all forecasts (--multiply is done before --add)')
    subparser.add_argument('--multiply', type=float, default=1, help='Multiply all forecasts with this value')
    subparser.add_argument('--debug', help='Display debug information', action="store_true")
    subparser.add_argument('--deacc', help='Deaccumulate values in time', action="store_true")

    return subparser


def run(parser, argv=sys.argv[1:]):
    args = parser.parse_args(argv)
    aggregator = get_aggregator(args.aggregator)

    if not os.path.exists(args.verif_file):
        met2verif.util.error("File '%s' does not exist" % args.verif_file)

    file = netCDF4.Dataset(args.verif_file, 'a')
    times = file.variables["time"]
    if len(times) == 0:
        times_orig = []
    else:
        times_orig = times[:]
    if args.ovariable not in file.variables:
        file.createVariable(args.ovariable, 'f4', ('time', 'leadtime', 'location'))

    ids_orig = np.array(file.variables["location"][:])
    leadtimes_orig = np.array(file.variables["leadtime"][:])

    """
    Read inputs
    """
    inputs = list()
    for filename in args.files:
        try:
            inputs += [met2verif.fcstinput.get(filename)]
        except Exception as e:
            print "Could not open file '%s'. %s." % (filename, e)
            if args.debug:
                traceback.print_exc()

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
            print "Adding new intialization times:\n    " + '\n    '.join([met2verif.util.unixtime_to_str(t) for t in times_add])

    thresholds_orig = list()
    quantiles_orig = list()
    if "threshold" in file.variables:
        thresholds_orig = file.variables["threshold"]
    if "quantile" in file.variables:
        quantiles_orig = file.variables["quantile"]
    num_members = 0
    if "ensemble" in file.variables:
        ensemble_orig = file.variables["ensemble"]
        num_members = ensemble_orig.shape[3]

    fcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig)])
    tfcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig), len(thresholds_orig)])
    qfcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig), len(quantiles_orig)])
    efcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig), num_members])
    pit = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig)])
    if len(times_orig) > 0 and not args.clear:
        fcst[range(len(times_orig)), :, :] = file.variables[args.ovariable][:]
        # Convert fill values to nan
        fcst[fcst == netCDF4.default_fillvals['f4']] = np.nan

        if len(thresholds_orig) > 0:
            tfcst[range(len(times_orig)), :, :, :] = file.variables['cdf'][:]
            tfcst[tfcst == netCDF4.default_fillvals['f4']] = np.nan
        if len(quantiles_orig) > 0:
            qfcst[range(len(times_orig)), :, :, :] = file.variables['x'][:]
            qfcst[qfcst == netCDF4.default_fillvals['f4']] = np.nan
        if num_members > 0:
            efcst[range(len(times_orig)), :, :, :] = file.variables['ensemble'][:]
            efcst[efcst == netCDF4.default_fillvals['f4']] = np.nan

    file.variables["time"][:] = times_new
    lats_orig = file.variables["lat"][:]
    lons_orig = file.variables["lon"][:]

    for Iinput, input in enumerate(inputs):
        time_s = time.time()
        print "Processing %s" % input.filename
        if args.debug:
            step = max(1, len(inputs) / 100)
            frac = float(Iinput) / len(inputs)
            #if Iinput % step == 0:
            #                met2verif.util.progress_bar(frac, 80)
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
                        if args.windspeed:
                            variables = args.variable.split(',')
                            if len(variables) != 2:
                                met2verif.util.error("-v must be x_variable_name,y_variable_name")
                            xvariable = variables[0]
                            yvariable = variables[1]
                            curr_x = input.extract(lats_orig, lons_orig, xvariable, args.members, args.hood)
                            curr_y = input.extract(lats_orig, lons_orig, yvariable, args.members, args.hood)
                            curr_fcst = np.sqrt(curr_x ** 2 + curr_y ** 2)
                        else:
                            curr_fcst = input.extract(lats_orig, lons_orig, args.variable, args.members, args.hood)

                        if args.deacc:
                            assert(args.time_window > 0)
                            curr_fcst[args.time_window:, ...] = curr_fcst[args.time_window:, ...] - curr_fcst[0:-args.time_window, ...]
                            curr_fcst[0:args.time_window, ...] = np.nan
                            curr_fcst = curr_fcst[Ilt_fcst, :, :]
                        else:
                            if args.time_window == 1:
                                # Faster, potentially. Though should give the same results as code below
                                curr_fcst = curr_fcst[Ilt_fcst, :, :]
                            else:
                                curr_fcst = np.cumsum(curr_fcst, axis=0)
                                curr_fcst[args.time_window:, ...] = curr_fcst[args.time_window:, ...] - curr_fcst[0:-args.time_window, ...]
                                curr_fcst[0:args.time_window, ...] = np.nan
                                curr_fcst = curr_fcst[Ilt_fcst, :, :]

                    fcst[Itime, Ilt_verif, :] = aggregator(curr_fcst * args.multiply + args.add, axis=2)
                    for i in range(len(thresholds_orig)):
                        # The inequality operator does not respect nans (returns 0 instead)
                        temp = np.zeros(curr_fcst.shape, float)
                        temp[:] = curr_fcst * args.multiply + args.add < thresholds_orig[i]
                        temp[np.isnan(curr_fcst)] = np.nan
                        tfcst[Itime, Ilt_verif, :, i] = np.nanmean(temp, axis=2)
                    for i in range(len(quantiles_orig)):
                        # Avoid using nanpercentile, if possible, since it is much slower
                        num_missing = np.sum(np.isnan(curr_fcst))
                        if num_missing == 0:
                            qfcst[Itime, Ilt_verif, :, i] = np.percentile(curr_fcst * args.multiply + args.add, quantiles_orig[i] * 100, axis=2)
                        else:
                            qfcst[Itime, Ilt_verif, :, i] = np.nanpercentile(curr_fcst * args.multiply + args.add, quantiles_orig[i] * 100, axis=2)
                    if num_members > 0:
                        if curr_fcst.shape[2] != num_members:
                            met2verif.util.error("Number of members in file (%d) does not equal number in verif file (%d)" % (curr_fcst.shape[2], num_members))
                        efcst[Itime, Ilt_verif, :, :] = curr_fcst * args.multiply + args.add

                elif args.debug:
                    print "We do not need to read this file"
            file.variables[args.ovariable][:] = fcst
            if len(thresholds_orig) > 0:
                file.variables['cdf'][:] = tfcst
            if len(quantiles_orig) > 0:
                file.variables['x'][:] = qfcst
            file.sync()
            # print "%.1f s" % (time.time() - time_s)
        except Exception as e:
            print "Could not process: %s" % e
            if args.debug:
                traceback.print_exc()

    # Convert nans back to fill value
    fcst[np.isnan(fcst)] = netCDF4.default_fillvals['f4']
    file.variables[args.ovariable][:] = fcst
    if len(thresholds_orig) > 0:
        tfcst[np.isnan(tfcst)] = netCDF4.default_fillvals['f4']
        file.variables['cdf'][:] = tfcst
    if len(quantiles_orig) > 0:
        qfcst[np.isnan(qfcst)] = netCDF4.default_fillvals['f4']
        file.variables['x'][:] = qfcst
    if num_members > 0:
        efcst[np.isnan(efcst)] = netCDF4.default_fillvals['f4']
        file.variables['ensemble'][:] = efcst
    file.close()


def get_aggregator(string):
    if string == "mean":
        return np.nanmean
    elif string == "median":
        return np.nanmedian
    elif string == "min":
        return np.nanmin
    elif string == "max":
        return np.nanmax
    else:
        met2verif.util.error("Could not understand aggregator '%s'" % string)
