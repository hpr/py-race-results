"""
Module for BestRace.
"""
import datetime
import logging
import os
import re
import warnings
import xml.etree.cElementTree as ET

from bs4 import BeautifulSoup

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
        RaceResults.local_tidy(self, local_file=self.output_file)

    def load_membership_list(self):
        """
        Construct regular expressions for each person in the membership list.
        """
        names = self.parse_membership_list()
        first_name_regex = []
        last_name_regex = []
        for j in range(len(names.first)):
            # For the regular expression, surround the name with
            # at least one white space character.  That way we cut
            # down on a lot of false positives, e.g. "Ed Ford" does
            # not cause every fricking person from "New Bedford" to
            # match.  Here's an example line to match.
            #   '60 Gene Gugliotta       North Plainfiel,NJ 53 M U '
            pattern = '\s+' + names.first[j] + '\s+'
            first_name_regex.append(re.compile(pattern, re.IGNORECASE))
            pattern = '\s+' + names.last[j] + '\s+'
            last_name_regex.append(re.compile(pattern, re.IGNORECASE))

        self.first_name_regex = first_name_regex
        self.last_name_regex = last_name_regex

    def local_tidy(self, local_file=None):
        """
        Clean up the HTML file.

        LIBTIDY doesn't seem to like p:colorspace, so get rid of it before
        calling LIBTIDY.
        """
        self.html = self.html.replace(':colorscheme', '')
        RaceResults.local_tidy(self, local_file=local_file)

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
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        root = BeautifulSoup(self.html, 'html.parser')

        h1 = ET.Element('h1')
        h1.text = root.title.text
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
            span.text = ' on BestRace.'
            p.append(span)
            div.append(p)

        pre = ET.Element('pre')
        pre.set('class', 'actual_results')

        banner_text = self.parse_banner(root)

        pre.text = banner_text + ''.join(results_lst)
        div.append(pre)

        return div

    def parse_banner(self, root):
        """Retrieve the banner from the race file.

        Example of a banner

                   The Andrea Holden 5k Thanksgiving Race
         PLC    Time  Pace  PLC/Group  PLC/Sex Bib#   Name
           1   16:40  5:23    1 30-39    1 M   142 Brian Allen

        """
        try:
            pre = root.find_all('pre')[0]
        except IndexError:
            return('')

        # Stop when we find the first "1"
        banner = ''
        for line in pre.text.split('\n'):
            if re.match('\s+1', line):
                # found it
                break
            else:
                banner += line + '\n'

        banner += '\n'
        return(banner)

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
        self.local_tidy()

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
