
import argparse
import copy
import netCDF4
import numpy as np
import os
import re
import requests
import sys
import urllib2

import met2verif.fcstinput
import met2verif.locinput
import met2verif.obsinput
import met2verif.util
import met2verif.version


def add_subparser(parser):
    subparser = parser.add_parser('download', help='Downloads KDVH data')
    subparser.add_argument('-l', type=str, help='Location ids. Either a comma-separated list of ids (e.g. 18700,50540), a filename with list of stations (new-line, comma-, and/or space-separated), a locations metadata file, or unspecified (all stations downloaded).', dest="locations")
    subparser.add_argument('-o', metavar="FILE", help='Output file', dest="filename", required=True)
    subparser.add_argument('-i', type=met2verif.util.parse_numbers, help='Comma-separated list of hours of the day to download. If unspecified, download all hours.', dest="hours")
    subparser.add_argument('-sd', type=str, help='Start date (yyyymmdd)', dest="sd", required=True)
    subparser.add_argument('-ed', type=str, help='End date (yyyymmdd)', dest="ed", required=True)
    subparser.add_argument('-v', type=str, help='List of variables (e.g. TA,FF)', dest="variables", required=True)
    subparser.add_argument('--api', default='frost', help="Which API to read from? 'frost', or 'ulric'. Default 'frost'", choices=['frost', 'ulric'])
    subparser.add_argument('-id', help="Frost API client ID", dest="client_id")
    subparser.add_argument('--level', help='Level, Sensor level for observations, example: 2)', dest="level") # default will get all available
    subparser.add_argument('--debug', help='Display debug information', action="store_true")

    return subparser


def run(parser, argv=sys.argv[1:]):
    args = parser.parse_args(argv)

    variables = args.variables.split(',')

    if args.api == 'frost':
        if args.client_id is None:
            met2verif.util.error('frost api needs -id')
        if args.locations is None:
            met2verif.util.error('frost api needs -l')
        if args.hours is not None:
            met2verif.util.error('frost api cannot use -i')

        if os.path.exists(args.locations):
            # Read from file
            try:
                ids = met2verif.locinput.get(args.locations).read().keys()
            except Exception as e:
                file = open(args.locations, 'r')
                ids = list()
                for line in file:
                    ids += ['SN' + word for word in re.split(',| ', line)]
        else:
            ids = ['SN' + str(id) for id in args.locations.split(',')]


        ofile = open(args.filename, 'w')
        ofile.write('id;date;hour;%s\n' % ';'.join(variables))

        ids_obs_dict = dict() # declare outside loop, since may be more than one request
        # check how long the list of stations is and potentially break it up to shorten
        it_ids = len(ids)
        while it_ids > 0:
            if it_ids > 50:
                # get last 50
                sub_idList = ids[it_ids - 50:it_ids]
                it_ids = it_ids - 50
            else:
                # get the rest if <50
                sub_idList = ids[:it_ids]
                it_ids = 0

            # use the list of stations and get the observations for those
            parameters2 = {'sources': ','.join(sub_idList), 'elements': args.variables}
            # if have specified a date and time
            # make these into a format that works for FROST
            def get_frost_date_string(date, hour):
                date_string = str(date)
                hour_string = "%02d" % (hour)
                return date_string[0:4] + '-' + date_string[4:6] + '-' + date_string[6:8] + 'T' + hour_string
            start_time = get_frost_date_string(args.sd, 0)
            ed = met2verif.util.get_date(int(args.ed), 1)
            end_time = get_frost_date_string(ed, 0)
            parameters2['referencetime'] =  start_time + '/' + end_time

            if args.level is not None:
                 parameters2['levels'] = str(args.level)

            r = requests.get('https://frost.met.no/observations/v0.jsonld',
                                    parameters2, auth=(args.client_id, ''))
            if args.debug:
                print(parameters2)
                print(r)
            if r.status_code == 200:
                data = r.json()['data']
                for i in range(len(data)):
                    values = [-999] * len(variables)
                    value = data[i]['observations'][0]['value']
                    reference_time = data[i]['referenceTime']
                    date = reference_time[0:4] + reference_time[5:7] + reference_time[8:10]
                    hour = reference_time[11:13]
                    sourceId = str(data[i]['sourceId'])
                    id = sourceId.split(':')[0].replace('SN', '')
                    for o in data[i]['observations']:
                        element = o['elementId']
                        I = variables.index(element)
                        value = o['value']
                        if value == "":
                            value = -999
                        values[I] = value
                    ofile.write("%s;%s;%s" % (id, date, hour))
                    for i in range(len(variables)):
                        ofile.write(";%.3f" % values[i])
                    ofile.write("\n")
            elif r.status_code == 404:
                 print('STATUS: No data was found for the list of query Ids.')
            else:
                 met2verif.util.error('ERROR: Could not get data from frost: %d' % r.status_code)
        ofile.close()

    elif args.api == 'ulric':
        # Set up url
        start_date = get_date(args.sd)
        end_date = get_date(args.ed)
        baseurl = "http://klapp/metnopub/production/metno?re=17&ct=text/plain&ddel=dot&del/space&nmt=0&nod=-999&qa=0"
        url = "%s&fd=%s&td=%s" % (baseurl, start_date, end_date)
        for variable in args.variables.split(','):
            url += "&p=%s" % variable
        if args.hours is not None:
            for hour in args.hours:
                url += "%h=%d" % hour
        if args.locations is not None:
            if os.path.exists(args.locations):
                # Read from file
                try:
                    ids = met2verif.locinput.get(args.locations).read().keys()
                except Exception as e:
                    file = open(args.locations, 'r')
                    ids = list()
                    for line in file:
                        ids += [int(word) for word in re.split(',| ', line)]
            else:
                ids = [int(id) for id in args.locations.split(',')]

            for id in ids:
                url += "&s=%s" % id

        if args.debug:
            print url

        # Download url
        response = urllib2.urlopen(url)
        html = response.read()
        file = open(args.filename, 'w')
        file.write(html)
        file.close()


def get_date(date):
    """
    date(str): yyyymmdd
    """
    # date = int("%02d.%02d.%04d" % (date % 100, date / 100 % 100, date / 10000))
    date = "%s.%s.%s" % (date[6:8], date[4:6], date[0:4])
    return date
