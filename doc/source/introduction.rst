********************************
Introduction and Getting Started
********************************

This document is a quick overview working with the RaceResults package.

What is RaceResults?
--------------------

RaceResults is a Python package for downloading and parsing race
results from certain road racing web sites.  It should primarily
be run from the command line.

Requirements
------------

Mac
==============
I would strongly advise using MacPorts to get a usable version of
Python.  The system version of Python on Snow Leopard (10.6) will
not work out-of-the-box.  The required minimum ports are

* python3.2
* py32-beautifulsoup4
* py32-lxml

Versions 0.2.0 and later of RaceResults no longer run on Python
versions below 3.0 and currently require Python 3.2.  Version 0.1.1
does run on Python version 2.7, however.

Quick installation
------------------

There's no need to compile anything, so the following command 
should be all that is required (you should customize for your system)::

    $ [sudo] python setup.py install --prefix=/path/to/install

On my machine, this creates a ``/path/to/install/bin`` directory
that you should add to your **PATH** environment variable (not your
**PYTHONPATH**!).  If it does not already exist, it also creates a
``/path/to/install/lib/python2.7/site-packages`` directory, and this
is something that you should add to your **PYTHONPATH** environment
variable (not to your **PATH**!).  Got it?

Example Use Cases:
------------------

CoolRunning
===========

Suppose you wish to process race results from the CoolRunning web
site.  The ``crrr`` script (already on your **PATH**, remember?)
is what you want.  Invoking it with no arguments gives you the help
message::

    $ crrr
    usage: crrr [-h] [-y YEAR] [-m {1,2,3,4,5,6,7,8,9,10,11,12}] [-d DAY DAY]
            [-v {debug,info,warning,error,critical}] [-o OUTPUT_FILE]
            [-s STATES [STATES ...]] --ml MEMBERSHIP_LIST [--rl RACE_LIST]


Suppose you want all the race results for the state of Massachusetts
for the month of January in 2012, and you have your membership file
stored in ``~/ftc/ftc.csv``.  This would work::

    $ crrr -m 1 -d 1 31 -o results.html -s ma --ml ~/ftc/ftc.csv


BestRace
========

Suppose you wish to process race results from the BestRace web site.
The ``brrr`` script is what you want.  It works similar to ``crrr``,
but the BestRace web site does not store results with respect to
the state in which the race took place, so there is no need for the
``-s`` option::

    $ brrr -m 1 -d 1 31 -o results.html --ml ~/ftc/ftc.csv


New York Road Runners
=====================

Suppose you wish to process race results from the New York Road
Runners web site.  The ``nyrr`` script is what you want.  It works
similar to ``brrr`` and ``crrr``, but you must supply a "team code"
instead of supplying a membership list.  This means that your club
runners have to register for the race with your specific team code.  
To get all the results for Raritan Valley Road runners for the month
of January in 2013, you would use the following::

    $ nyrr -y 2013 -m 1 -d 1 31 -t RARI -o results.html 


CompuScore
==========

CompuScore is similar to BestRace in that it does not store results
with respect to the state in which the race took place::

    $ csrr -y 2013 -m 1 -o results.html --ml ~/ftc/ftc.csv


Active.com
==========

Processing results from Active.com works for two cases:

  - results pages offering CSV downloads
  - results pages embedding the raw results within **PRE** tags

It also requires the user to provide a "city, state" location in
conjunction with a search radius in miles around that city.  To get
results within 100 miles of Boston, MA, one would type the following::

    $ active -y 2013 -m 1 -d 1 31 -o results.html -l "Boston, MAT" -r 100 --ml ~/ftc/ftc.csv


Membership File
---------------
The club membership file should be a CSV file with the first line being
a header line.  The first two fields in the CSV file must be LAST
NAME, FIRST NAME.  The remaining fields do not matter.  For example::

   LAST,FIRST,DOB
   Doe,Jane,1967-12-1 
   Smith,Joe,1980-5-1 
   Warner,Johanna,1990-5-1 
   .
   .
   .

