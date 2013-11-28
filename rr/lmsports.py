"""
Module for L & M Computer Sports timing company.
"""
import datetime
import logging
import os
import re
import urllib
import warnings

from lxml import etree as ET

from .common import RaceResults


class LMSports(RaceResults):
    """
    Process races found on lmsports.com.

    Attributes:
        start_date, stop_date:  date range to restrict race searches
        memb_list:  membership list
        race_list:  file containing list of races
        output_file:  final race results file
        verbose:  how much output to produce
        logger: handles verbosity of program execution
        downloaded_url:  If a race retrieved from a URL has results for anyone
            in the membership list, then we want to record that URL in the
            output.
    """

    def __init__(self, **kwargs):
        RaceResults.__init__(self)
        self.__dict__.update(**kwargs)

        self.base_url = 'http://www.lmsports.com/'

        # Set the appropriate logging level.
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

        self.load_membership_list()

    def run(self):
        self.compile_results()
        self.local_tidy(local_file=self.output_file)

    def compile_results(self):
        """
        Start collecting race result files.
        """

        self.initialize_output_file()
        if self.race_list is None:
            # No race list specified, so look at the remote web site.
            self.compile_web_results()
        else:
            # Get race results
            self.compile_local_results()

    def compile_web_results(self):
        """
        Download the requested results and compile them.
        """
        self.download_master_file()
        self.process_master_file()

    def process_master_file(self):
        """
        We have the full year of results, now fish out the ones that are in
        the specified time range.
        """
        # <a href="trail13.htm">Trail of Two Cities 5k Run</a>
        # - Saturday, November 2, 2013 - OC/Somers Point, NJ -
        # ( <a href="trail12.htm">2012 results</a> )
        pattern = r"""<a\s
                      href=\"(?P<href>\w*?\d\d.htm)\">\s*
                      (?P<race_name>.*?)\s*
                      </a>\s*
                      -\s*
                      (?P<day_of_week>[A-Z][a-z]*?),\s*
                      (?P<month>.*?)\s+
                      (?P<day>\d+),\s+
                      (?P<year>\d+)\s*-"""
        regex = re.compile(pattern, re.VERBOSE | re.DOTALL | re.IGNORECASE)
        for matchobj in regex.finditer(self.html):
            datestring = '{0} {1:02d}, {2}'.format(matchobj.group('month'),
                                                   int(matchobj.group('day')),
                                                   matchobj.group('year'))
            dt = datetime.datetime.strptime(datestring, "%B %d, %Y")
            dt = datetime.date(dt.year, dt.month, dt.day)
            if not (self.start_date <= dt and dt <= self.stop_date):
                msg = 'Skipping {0}...'.format(matchobj.group('race_name'))
                self.logger.info(msg)
                continue

            url = self.base_url + matchobj.group('href')
            self.logger.info('Downloading {0}.'.format(url))

            self.downloaded_url = url
            response = urllib.request.urlopen(url)
            self.html = response.readall().decode('utf-8')
            self.compile_race_results()

    def compile_race_results(self):
        """
        Go through a single race file and collect results.
        """
        results = []
        for line in self.html.split('\n'):
            if self.match_against_membership(line):
                results.append(line)

        if len(results) > 0:
            results = self.webify_results(results)
            self.insert_race_results(results)

    def webify_results(self, results_lst):
        """
        Take the list of results and turn it into output HTML.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # <TITLE>Cooper Norcross Run the Bridge 10k</TITLE>
        regex = re.compile(r"""<title>(?P<the_title>.*)</title>""",
                           re.VERBOSE | re.IGNORECASE)
        matchobj = regex.search(self.html)
        if matchobj is None:
            raise RuntimeError("Could not find the title.")

        h1 = ET.Element('h1')
        h1.text = matchobj.group('the_title')
        div.append(h1)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            p = ET.Element('p')
            p.set('class', 'provenance')
            span = ET.Element('span')
            span.text = 'Complete results '
            p.append(span)
            a = ET.Element('a')
            a.set('href', self.downloaded_url)
            a.text = 'here'
            p.append(a)
            span = ET.Element('span')
            span.text = ' on L&M Sports.'
            p.append(span)
            div.append(p)

        pre = ET.Element('pre')
        pre.set('class', 'actual_results')

        # Parse out the banner.
        # age|#in
        regex = re.compile(r"""\r\n(?P<banner>\s*age.*?=====)\r\n""",
                           re.DOTALL)
        matchobj = regex.search(self.html)
        if matchobj is None:
            raise RuntimeError("Could not parse out the banner.")

        # Construct the banner as mixed content XML.  Difficult to do this
        # any other way and still get this to look right.
        text = '<pre class="actual_results">\n'
        text += matchobj.group('banner')
        text += '\n' + '\n'.join(results_lst)
        text += '</pre>'
        pre = ET.fromstring(text)

        div.append(pre)

        return div

    def download_master_file(self):
        """Download results for the entire year.

        The URL will have the pattern

        http://www.lmsports.com/resultsYY.htm

        where YY is the two-digit year.
        """
        url = 'http://www.lmsports.com/results{0}.htm'
        url = url.format(self.start_date.strftime('%y'))
        self.logger.info('Downloading {0}.'.format(url))
        response = urllib.request.urlopen(url)
        self.html = response.read().decode('utf-8')

    def download_race(self, url):
        """
        Download a race URL to a local file.
        """
        name = url.split('/')[-1]
        self.logger.info('Downloading %s...' % name)
        self.download_file(url)
        self.downloaded_url = url
        self.local_tidy()

    def compile_local_results(self):
        """Compile results from list of local files.
        """
        with open(self.race_list) as fp:
            for line in fp.readlines():
                filename = line.rstrip()
                with open(filename, 'rt') as fptr:
                    self.html = fptr.read()
                self.compile_race_results()
