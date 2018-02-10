Scripts to convert MET-data to use in Verif
===========================================

Pre-requisites
--------------

To use the scripts in this repository, you need to install verif, see https://github.com/WFRT/verif/
for installation instructions, but it should hopefully be as easy as:

.. code-block:: bash

   sudo pip install verif

Or if you do not have sudo privileges:

.. code-block:: bash

   pip install verif --user

Converting KDVH observations to Verif
-------------------------------------

There are three steps: 1) Download data from KDVH web-interface. 2) Convert the observation data to
a Verif file. 3) Add forecast data from a forecast NetCDF file. The proceedure is shown in
./example.

First download the data from KDVH, using the provided kdhv_download script

.. code-block:: bash

  ./download_kdvh -l 18700,50540 -sd 20150101 -ed 20150131 -o data.txt -v TA,RR_1,FF

This will download data for the stations 18700 (Blindern) and 50540 (Bergen). Dates 20150101 to
20150131 are downloaded and variables TA (temperature) RR_1 (hourly precipitation) and FF (wind
speed) are used. The data is stored in data.txt. For more information about KDVH, check out
https://dokit.met.no/klima/userservices/urlinterface/brukerdok?s[]=klapp.

Next, convert the text data in data.txt to Verif NetCDF file.

.. code-block:: bash

  ./kdvh2verif data.txt -l kdvh_locations.txt -o data.nc -v TA -i 0,6,12,18 -lt 0:66

Since data.txt does not contain any metadata about the stations, the metadata must be provided by a
locations file (kdvh_locations.txt). A verif file can only contain a single variable, set this using
-v. Finally, if the verif file will be used to evaluate forecasts, then we need to specify which
forecast initializtion times (e.g. 0,6,12,18 specify 00 UTC, 06 UTC, 12 UTC, and 18 UTC
initializations) and lead times (0:66 specify every hour from 0 to 66). The script will then
duplicate the observations filling them in as necessary to match the initialization and lead times.


Adding AROME data to Verif file
-------------------------------

Finally, we need to add forecast data to these files.

.. code-block:: bash

  ./addtoverif /lustre/storeB/immutable/short-term-archive/DNMI_AROME_METCOOP/2015/01/*/AROME_MetCoOp_*_DEF.nc_* -o data.nc -v air_temperature_2m

You need to specify the name of the variable in the AROME files you want to copy
(air_temperature_2m) in this case. addtoverif uses the lat/lon positions in the data.nc to
interpolate the gridded field to, using nearest neighbour.

Copyright and license
---------------------

Copyright © 2017-2018 MET-Norway. Verif is licensed under the 3-clause BSD license. See LICENSE
file.
