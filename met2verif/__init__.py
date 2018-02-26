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
import met2verif.addobs
import met2verif.init


def main():
   parser = argparse.ArgumentParser(description='Iitialises and adds to verif file')
   parser.add_argument('--version', action="version", version=met2verif.version.__version__)
   subparsers = parser.add_subparsers(title="Choose one of these commands", dest="command")

   sp = dict()
   sp["init"] = met2verif.init.add_subparser(subparsers)
   sp["addobs"] = met2verif.addobs.add_subparser(subparsers)
   sp["addfcst"] = met2verif.addfcst.add_subparser(subparsers)

   args = parser.parse_args()

   if len(sys.argv) == 1:
      parser.print_help()
      sys.exit(1)
   elif len(sys.argv) == 2 and sys.argv[1] == "--version":
      print(met2verif.version.__version__)
      return
   elif len(sys.argv) == 2 and sys.argv[1] in sp.keys():
      sp[sys.argv[1]].print_help()
      return

   if args.command == "init":
      met2verif.init.run(parser)
   elif args.command == "addobs":
      met2verif.addobs.run(parser)
   elif args.command == "addfcst":
      met2verif.addfcst.run(parser)


if __name__ == '__main__':
   main()
