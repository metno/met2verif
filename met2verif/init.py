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
import met2verif.addobs


def add_subparser(parser):
    subparser = parser.add_parser('init', help='Initialize verif file')
    subparser.add_argument('-l', help='Locations metadata file', dest="locations_file", required=True)
    subparser.add_argument('-lt', type=met2verif.util.parse_numbers, help='Lead times (hours)', dest="leadtimes", required=True)
    subparser.add_argument('-o', metavar="FILE", help='Verif file', dest="verif_file", required=True)
    subparser.add_argument('-s', help='Standard name', dest="standard_name")
    subparser.add_argument('-u', help='Units', dest="units")
    subparser.add_argument('-q', type=met2verif.util.parse_numbers, help='Quantiles', dest="quantiles")
    subparser.add_argument('-e', default=0, type=int, help='Number of ensemble members', dest="members")
    subparser.add_argument('-t', type=met2verif.util.parse_numbers, help='Thresholds', dest="thresholds")
    subparser.add_argument('-x0', type=float, help='Lower boundary within discrete mass (e.g. 0 for precip)')
    subparser.add_argument('-x1', type=float, help='Upper boundary within discrete mass (e.g. 100 for RH)')
    subparser.add_argument('--debug', help='Display debug information', action="store_true")

    return subparser


def run(parser, argv=sys.argv[1:]):
    args = parser.parse_args(argv)

    ofilename = args.verif_file

    # Create lat/lon/elev map
    locations = met2verif.locinput.get(args.locations_file).read()

    # Write file
    file = netCDF4.Dataset(ofilename, 'w', format="NETCDF3_CLASSIC")
    file.createDimension("time", None)
    file.createDimension("leadtime", len(args.leadtimes))
    file.createDimension("location", len(locations))
    if args.quantiles is not None:
        file.createDimension("quantile", len(args.quantiles))
    if args.thresholds is not None:
        file.createDimension("threshold", len(args.thresholds))
    if args.members > 0:
        file.createDimension("ensemble_member", args.member)

    vTime = file.createVariable("time", "i4", ("time",))
    vOffset = file.createVariable("leadtime", "f4", ("leadtime",))
    vLocation = file.createVariable("location", "i4", ("location",))
    vLat = file.createVariable("lat", "f4", ("location",))
    vLon = file.createVariable("lon", "f4", ("location",))
    vElev = file.createVariable("altitude", "f4", ("location",))
    vfcst = file.createVariable("fcst", "f4", ("time", "leadtime", "location"))
    vobs = file.createVariable("obs", "f4", ("time", "leadtime", "location"))

    if args.quantiles is not None:
        var = file.createVariable("quantile", "f4", ["quantile"])
        var[:] = args.quantiles
        var = file.createVariable("x", "f4", ("time", "leadtime", "location", "quantile"))

    if args.thresholds is not None:
        var = file.createVariable("threshold", "f4", ["threshold"])
        var[:] = args.thresholds
        var = file.createVariable("cdf", "f4", ("time", "leadtime", "location", "threshold"))
    if args.members > 0:
        var = file.createVariable("ensemble", "f4", ("time", "leadtime", "location", "ensemble_member"))

    """ Attributes """
    if args.standard_name:
        file.standard_name = args.standard_name
    else:
        file.standard_name = "Unknown"
    if args.units:
        file.units = args.units
    if args.x0:
        file.x0 = args.x0
    if args.x1:
        file.x1 = args.x1

    L = len(locations)
    lats = np.zeros(L, 'float')
    lons = np.zeros(L, 'float')
    elevs = np.zeros(L, 'float')
    ids = np.sort(list(locations.keys()))
    for i in range(0, L):
        lats[i] = locations[ids[i]]["lat"]
        lons[i] = locations[ids[i]]["lon"]
        elevs[i] = locations[ids[i]]["elev"]
    vOffset[:] = args.leadtimes
    vLocation[:] = ids
    vLat[:] = lats
    vLon[:] = lons
    vElev[:] = elevs
    file.Conventions = "verif_1.0.0"
    file.close()
