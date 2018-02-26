# Use this file to build debian packages
# Create a file called stdb.cfg in this directory with the following
# contents, where # "precise" is your linux version:
# [DEFAULT]
# Suite: precise
.PHONY: other/met2verif.sh dist

default: nothing

nothing:
	@ echo "This makefile does not build met2verif, use setup.py"

VERSION=$(shell grep __version__ met2verif/version.py | cut -d"=" -f2 | sed s"/ //g" | sed s"/'//g")
coverage:
	#nosetests --with-coverage --cover-erase --cover-package=met2verif --cover-html --cover-branches
	nosetests --with-coverage --cover-erase --cover-package=met2verif --cover-html

test:
	nosetests

# Creating distribution for pip
dist:
	echo $(VERSION)
	rm -rf dist
	python setup.py sdist
	python setup.py bdist_wheel
	@ echo "Next, run 'twine upload dist/*'"

clean:
	python setup.py clean
	rm -rf build/
	find . -name '*.pyc' -delete
	rm -rf deb_dist
	rm -rf met2verif.egg-info

lint:
	python met2verif/tests/pep8_test.py

count:
	@wc -l met2verif/*.py | tail -1

other/met2verif.sh:
	python other/create_bash_completion.py > met2verif.sh
