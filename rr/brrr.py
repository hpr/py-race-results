"""
Module for BestRace.
"""
import datetime
import logging
import os
import re
import warnings

from lxml import etree

from .common import RaceResults


class BestRace(RaceResults):
    """
    Process races found on BestRace.com.

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

        # Set the appropriate logging level.
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        self.load_membership_list()
        self.compile_results()
        # Make the output human-readable.

    def load_membership_list(self):
        """
        Construct regular expressions for each person in the membership list.
        """
        first_name_regex = []
        last_name_regex = []
        for last_name, first_name in self.parse_membership_list():
            # Use word boundaries to prevent false positives, e.g. "Ed Ford"
            # does not cause every fricking person from "New Bedford" to
            # match.  Here's an example line to match.
            #   '60 Gene Gugliotta       North Plainfiel,NJ 53 M U '
            pattern = '\\b' + first_name + '\\b'
            first_name_regex.append(re.compile(pattern, re.IGNORECASE))
            pattern = '\\b' + last_name + '\\b'
            last_name_regex.append(re.compile(pattern, re.IGNORECASE))

        self.first_name_regex = first_name_regex
        self.last_name_regex = last_name_regex

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
        Compile results for the specified state.
        """
        pattern = 'http://www.bestrace.com/results/{0}/{1}{2}'
        pattern = pattern.format(self.start_date.strftime('%y'),
                                 self.start_date.strftime('%y'),
                                 self.start_date.strftime('%m'))

        day_range = '('
        for day in range(self.start_date.day, self.stop_date.day):
            day_range += "%02d|" % day
        day_range += '%02d)' % self.stop_date.day

        pattern += day_range

        pattern += "\w+\.HTM"
        self.logger.debug('pattern is "%s"' % pattern)

        matchiter = re.finditer(pattern, self.html)
        lst = []
        for match in matchiter:
            span = match.span()
            start = span[0]
            stop = span[1]
            url = self.html[start:stop]
            lst.append(url)

        for url in lst:
            self.logger.info('Downloading %s...' % url)
            self.download_race(url)
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
        div = etree.Element('div')
        div.set('class', 'race')
        hr = etree.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # Get the title, but don't bother with the date information.
        # <title>  Purple Stride 5K     - November 10, 2013   </title>
        regex = re.compile(r"""<title>\s+
                               (?P<the_title>.*)-\s+
                               \w*\s\d+,\s+\d\d\d\d\s*
                               </title>""", re.VERBOSE | re.IGNORECASE)
        matchobj = regex.search(self.html)
        if matchobj is None:
            raise RuntimeError("Could not find the title.")

        h1 = etree.Element('h1')
        h1.text = matchobj.group('the_title')
        div.append(h1)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            p = etree.Element('p')
            p.set('class', 'provenance')
            span = etree.Element('span')
            span.text = 'Complete results '
            p.append(span)
            a = etree.Element('a')
            a.set('href', self.downloaded_url)
            a.text = 'here'
            p.append(a)
            span = etree.Element('span')
            span.text = ' on BestRace.'
            p.append(span)
            div.append(p)

        pre = etree.Element('pre')
        pre.set('class', 'actual_results')

        # Parse out the banner.
        regex = re.compile(r"""<b>
                               (?P<mixed_content_1>[^<>]*)
                               <u>(?P<mixed_content_2>[^<>]*)</u>
                               </b>""",
                           re.VERBOSE | re.IGNORECASE)
        matchobj = regex.search(self.html)
        if matchobj is None:
            raise RuntimeError("Could not parse out the banner.")

        # Construct the banner as mixed content XML.  Difficult to do this
        # any other way and still get this to look right.
        text = '<pre class="actual_results">\n'
        text += matchobj.group()
        text += '\n' + '\n'.join(results_lst)
        text += '</pre>'
        pre = etree.fromstring(text)

        div.append(pre)

        return div

    def match_against_membership(self, line):
        """
        Given a line of text, does it contain a member's name?
        """
        for idx in range(0, len(self.first_name_regex)):
            fregex = self.first_name_regex[idx]
            lregex = self.last_name_regex[idx]
            if fregex.search(line) and lregex.search(line):
                return(True)
        return(False)

    def download_master_file(self):
        """Download results for the specified state.

        The URL will have the pattern

        http://www.bestrace.com/YYYYschedule.shtml

        """
        fmt = 'http://www.bestrace.com/%sschedule.html'
        url = fmt % self.start_date.strftime('%Y')
        self.logger.info('Downloading %s.' % url)
        self.download_file(url)

    def download_race(self, url):
        """
        Download a race URL to a local file.
        """
        name = url.split('/')[-1]
        self.logger.info('Downloading %s...' % name)
        self.download_file(url)
        self.downloaded_url = url

    def compile_local_results(self):
        """Compile results from list of local files.
        """
        with open(self.race_list) as fp:
            for line in fp.readlines():
                filename = line.rstrip()
                with open(filename, 'rt') as fptr:
                    self.html = fptr.read()
                self.compile_race_results()
