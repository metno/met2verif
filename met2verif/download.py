import argparse
import copy
import netCDF4
import numpy as np
import os
import sys
import urllib2
import re


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
   subparser.add_argument('--debug', help='Display debug information', action="store_true")

   return subparser


def run(parser):
   args = parser.parse_args()

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
