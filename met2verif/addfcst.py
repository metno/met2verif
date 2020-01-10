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
    subparser.add_argument('-d', default=[0], type=met2verif.util.parse_numbers, help='What forecast delays in hours should be used?', dest="delays")
    subparser.add_argument('-e', type=met2verif.util.parse_ints, help='What ensemble member(s) to use? If unspecified, then take the ensemble mean.', dest="members")
    subparser.add_argument('-a', default="mean", help='Aggregator for computing fcst', dest="aggregator", choices=["mean", "median", "min", "max"])
    subparser.add_argument('-f', help='Overwrite values if they are there already', dest="overwrite", action="store_true")
    subparser.add_argument('-s', help='Sort times if needed?', dest="sort", action="store_true")
    subparser.add_argument('-n', default=0, type=int, help='Neighbourhood radius', dest="hood")
    subparser.add_argument('-v', type=str, help='Variable name in forecast files', dest="variable", required=True)
    subparser.add_argument('-vo', default="fcst", type=str, help='Variable name in verif file', dest="ovariable")
    subparser.add_argument('-w', default=1, type=int, help='Time aggregation window in number of timesteps of input file', dest="time_window")
    subparser.add_argument('-to', type=float, help='Output threshold or quantile', dest="othreshold")
    subparser.add_argument('--windspeed', help='Compute wind speed?', action="store_true")
    subparser.add_argument('--add', type=float, default=0, help='Add this value to all forecasts (--multiply is done before --add)')
    subparser.add_argument('--multiply', type=float, default=1, help='Multiply all forecasts with this value')
    subparser.add_argument('--debug', help='Display debug information', action="store_true")
    subparser.add_argument('--deacc', help='Deaccumulate values in time', action="store_true")
    subparser.add_argument('-ft', help='Fill in time', dest="fill_time", action="store_true")
    subparser.add_argument('--sync', type=int, help='How often to Sync?', dest="sync_frequency")

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
        for delay in args.delays:
            frt = input.forecast_reference_time + delay * 3600
            if not np.isnan(frt) and frt < 1e10:
                times_file = np.append(times_file, frt)
    times_all = np.unique(np.append(times_orig, times_file))
    times_add = np.sort(np.setdiff1d(times_all, times_orig))
    times_new = np.append(times_orig, times_add)
    if args.debug:
        if len(times_add) == 0:
            print("No new initialization times added")
        else:
            print("Adding new intialization times:\n    " + '\n '.join([met2verif.util.unixtime_to_str(t) for t in times_add]))

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

    num_dims = len(file.variables[args.ovariable].shape)
    is_threshold_field = num_dims == 4
    if is_threshold_field:
        if args.othreshold is not None:
            if 'threshold' in file.variables[args.ovariable].dimensions:
                thresholds = file.variables['threshold'][:]
            elif 'quantile' in file.variables[args.ovariable].dimensions:
                thresholds = file.variables['quantile'][:]
            else:
                met2verif.util.error("Variable '%s' does not have threshold or quantile dimension.")
            Ithreshold = np.where(thresholds == args.othreshold)[0]
            if len(Ithreshold) == 0:
                met2verif.util.error("Variable '%s' does not have threshold '%f'." % (args.othreshold))
            Ithreshold = Ithreshold[0]
        else:
            met2verif.util.error("Variable '%s' has 4 dimensions. You need to specify threshold '-to'." % (num_dims))

    fcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig)])
    tfcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig), len(thresholds_orig)])
    qfcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig), len(quantiles_orig)])
    efcst = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig), num_members])
    pit = np.nan * np.zeros([len(times_new), len(leadtimes_orig), len(ids_orig)])
    if len(times_orig) > 0 and not args.clear:
        if is_threshold_field:
            fcst[range(len(times_orig)), :, :] = file.variables[args.ovariable][:, :, :, Ithreshold]
        else:
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
            Itime, Ilt_input, Ilt_output = get_time_indices(input.leadtimes, input.forecast_reference_time, leadtimes_orig, times_new, args.delays, args.fill_time)
            print(Itime, Ilt_input, Ilt_output)

            """
            Determine if we need to write data from this filename. This is only
            when the data we are writing to is missing.
            """
            do_write = args.overwrite
            for i in range(len(Itime)):
                if np.sum(np.isnan(fcst[Itime[i], Ilt_output[i], :]) == 0) == 0:
                    do_write = True
                break

            if not do_write:
                if args.debug:
                    print("We do not need to read this file")
                continue

            if args.windspeed:
                """ Diagnose winds from x and y """
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
            else:
                if args.time_window == 1:
                    pass
                    # Faster, potentially. Though should give the same results as code below
                else:
                    curr_fcst = np.cumsum(curr_fcst, axis=0)
                    curr_fcst[args.time_window:, ...] = curr_fcst[args.time_window:, ...] - curr_fcst[0:-args.time_window, ...]
                    curr_fcst[0:args.time_window, ...] = np.nan

            curr_fcst = curr_fcst * args.multiply + args.add

            """ Now figure out where to put this data """
            for i in range(len(Itime)):
                curr_Itime = Itime[i]
                curr_Ilt_output = Ilt_output[i]
                curr_Ilt_input = Ilt_input[i]
                curr_fcst0 = curr_fcst[curr_Ilt_input, :, :]
                fcst[curr_Itime, curr_Ilt_output, :] = aggregator(curr_fcst0, axis=2)
                for i in range(len(thresholds_orig)):
                    # The inequality operator does not respect nans (returns 0 instead)
                    temp = np.zeros(curr_fcst0.shape, float)
                    temp[:] = curr_fcst0 < thresholds_orig[i]
                    temp[np.isnan(curr_fcst0)] = np.nan
                    tfcst[curr_Itime, curr_Ilt_output, :, i] = np.nanmean(temp, axis=2)
                for i in range(len(quantiles_orig)):
                    # Avoid using nanpercentile, if possible, since it is much slower
                    num_missing = np.sum(np.isnan(curr_fcst0))
                    if num_missing == 0:
                        qfcst[curr_Itime, curr_Ilt_output, :, i] = np.percentile(curr_fcst0, quantiles_orig[i] * 100, axis=2)
                    else:
                        qfcst[curr_Itime, curr_Ilt_output, :, i] = np.nanpercentile(curr_fcst0, quantiles_orig[i] * 100, axis=2)
                if num_members > 0:
                    if curr_fcst0.shape[2] != num_members:
                        met2verif.util.error("Number of members in file (%d) does not equal number in verif file (%d)" % (curr_fcst0.shape[2], num_members))
                    efcst[curr_Itime, curr_Ilt_output, :, :] = curr_fcst0

            if args.sync_frequency is not None and Iinput % args.sync_frequency == 0:
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
    if is_threshold_field:
        file.variables[args.ovariable][:, :, :, Ithreshold] = fcst
    else:
        file.variables[args.ovariable][:] = fcst
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


"""

"""
def get_time_indices(input_leadtimes, input_frt, output_leadtimes, output_times, delays, fill_time):
    Itime = list()
    Ilt_input = list()
    Ilt_output = list()
    for d, delay in enumerate(delays):
        frt = input_frt + delay * 3600
        input_leadtimes0 = input_leadtimes - delay
        Itemp =  np.where(output_times == frt)[0]
        if len(Itemp) == 1:
            Itime += [Itemp[0]]
            curr_Ilt_output = list()
            curr_Ilt_input = list()
            for lt, leadtime in enumerate(output_leadtimes):
                Iexact = np.where(input_leadtimes0 == leadtime)[0]
                if len(Iexact) == 1:
                    curr_Ilt_output += [lt]
                    curr_Ilt_input += [Iexact[0]]
                elif fill_time:
                    # TODO: If the delay is long enough, then there aren't enough
                    # input leadtimes to cover the end and in this case the last one gets
                    # used for a potentially long time
                    Ipossible = np.where(input_leadtimes0 <= leadtime)[0]
                    curr_Ilt_output += [lt]
                    curr_Ilt_input += [Ipossible[-1]]
            Ilt_output += [curr_Ilt_output]
            Ilt_input += [curr_Ilt_input]
    return Itime, Ilt_input, Ilt_output
