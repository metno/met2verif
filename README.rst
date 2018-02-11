Scripts to convert MET-data to use in Verif
===========================================

This package contains the program ``met2verif``, which can be used to generate verification files
used by Verif (https://github.com/WFRT/verif). It arranges observations from MET-Norways
observation database and forecasts from NetCDF files.

See the wiki page (https://github.com/metno/met2verif/wiki) for instructions on how to use the
program.

Installing on Ubuntu
--------------------

**Prerequisites**

met2verif requires NetCDF as well as the python packages numpy. Install as follows:

.. code-block:: bash

  sudo apt-get update
  sudo apt-get install netcdf-bin libnetcdf-dev libhdf5-serial-dev
  sudo apt-get install python-setuptools python-pip
  sudo apt-get install python-numpy 

**Installing using pip**

After this, the easiest is to install the lastest version of met2verif using pip:

.. code-block:: bash

   sudo pip install met2verif

met2verif should then be accessible by typing ``met2verif`` on the command-line. If you do not have
sudo-rights, then install met2verif as follows:

.. code-block:: bash

   pip install met2verif --user

This will create the executable ``~/.local/bin/met2verif``. Add this to your PATH environment
variable if necessary (i.e add ``export PATH=$PATH:~/.local/bin`` to ``~/.bashrc``).

**Installing from source**

Alternatively, to install from source, download the source code of the latest version:
https://github.com/metno/met2verif/releases/. Unzip the file and navigate into the extracted folder.

Then install met2verif by executing the following inside the extracted folder:

.. code-block:: bash

  sudo pip install -r requirements.txt
  sudo python setup.py install

This will create the executable ``/usr/local/bin/met2verif``. Add ``/usr/local/bin`` to your PATH environment
variable if necessary. If you do not have sudo privileges do:

.. code-block:: bash

  pip install -r requirements.txt --user
  python setup.py install --user

This will create the executable ``~/.local/bin/met2verif``. Add ``~/.local/bin`` to your PATH environment
variable.

Copyright and license
---------------------

Copyright © 2017-2018 MET-Norway. met2verif is licensed under the 3-clause BSD license. See LICENSE
file.
