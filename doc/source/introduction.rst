********************************
Introduction and Getting Started
********************************

This document is a quick overview working with the RaceResults package.

What is RaceResults?
--------------------

RaceResults is a Python package for downloading and parsing race
results from certain road racing web sites.  It should primarily
be run from the command line.

Requirements (macports)
-----------------------
* Python 2.7
* tidy (20120821):  for libtidy
* py27-utidylib 0.2

Quick installation
------------------

There's no need to compile anything, so the following command 
should be all that is required (you should customize for your system)::

    $ [sudo] python setup.py install --prefix=/Users/jevans/p

On my machine, this creates a ``/Users/jevans/p/bin`` directory that you should add to
your **PATH** environment variable (not your **PYTHONPATH**!).  It also
creates a ``/Users/jevans/p/lib/python2.7/site-packages`` directory, and this is something
that you should add to your **PYTHONPATH** environment variable (not
to your **PATH**!).  Got it?

Example Use Case:
-----------------

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


CompuScore
==========

CompuScore is similar to BestRace in that it does not store results
with respect to the state in which the race took place.  But the
dates are a bit funky (checkout CompuScore and look at the URLs,
you will see)::

    $ csrr -m janfeb -o results.html --ml ~/ftc/ftc.csv


Membership File
---------------
The club membership file should be a CSV file.  The first two fields
in the CSV file must be FIRST NAME, LAST NAME.  Other than that,
the format of the CSV file can be whatever else you put into it.

