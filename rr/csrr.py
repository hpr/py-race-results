import datetime
import logging
import os
import re
import sys
import urllib
import warnings
import xml.etree.cElementTree as ET

from .common import RaceResults

logging.basicConfig()

# Need to match the month of the search window to the month strings that
# Compuscore uses.
monthstrs = {1: 'janfeb',
             2: 'janfeb',
             3: 'march',
             4: 'april',
             5: 'may',
             6: 'june',
             7: 'july',
             8: 'aug',
             9: 'sept',
             10: 'october',
             11: 'novdec',
             12: 'novdec', }


class CompuScore(RaceResults):
    def __init__(self, **kwargs):
        """
        memb_list:  membership list
        race_list:  file containing list of races
        output_file:  final race results file
        verbose:  how much output to produce
        """
        RaceResults.__init__(self)
        self.__dict__.update(**kwargs)

        if self.start_date is not None:
            self.monthstr = monthstrs[self.start_date.month]

        # Need to remember the current URL.
        self.downloaded_url = None

        # Set the appropriate logging level.
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        """
        Load the membership list and run through all the results.
        """
        first_name_regex = []
        last_name_regex = []
        for last_name, first_name in self.parse_membership_list():
            # Example to match:
            #
            #   '60.Gene Gugliotta       North Plainfiel,NJ 53 M U '
            #
            # Use word boundaries for the regexps except at the very beginning.
            pattern = '\\.' + first_name + '\\b'
            first_name_regex.append(re.compile(pattern, re.IGNORECASE))
            pattern = '\\b' + last_name + '\\b'
            last_name_regex.append(re.compile(pattern, re.IGNORECASE))

        self.first_name_regex = first_name_regex
        self.last_name_regex = last_name_regex

        self.compile_results()
        self.local_tidy(self.output_file)

    def compile_results(self):
        """
        Either download the requested results or go through the
        provided list.
        """

        self.initialize_output_file()
        if self.race_list is None:
            self.compile_web_results()
        else:
            self.compile_local_results()

    def compile_web_results(self):
        """
        Download the requested results and compile them.
        """
        self.download_master_file()
        self.process_master_file()

    def process_master_file(self):
        """
        Parse the "master" file containing an entire month's worth of races.
        Pick out the URLs of the race results and process each.  We cannot
        easily restrict based on the time frame here.
        """
        year = self.start_date.year
        monthstr = monthstrs[self.start_date.month]
        pattern = 'http://www.compuscore.com/cs{0}/{1}/(?P<race>\w+)\.htm'
        pattern = pattern.format(year, monthstr)
        matchiter = re.finditer(pattern, self.html)

        lst = []
        for match in matchiter:
            span = match.span()
            start = span[0]
            stop = span[1]
            url = self.html[start:stop]
            lst.append(url)

        for url in lst:
            self.logger.info('Downloading {0}...'.format(url))

            response = urllib.request.urlopen(url)
            try:
                self.html = response.read().decode('utf-8')
            except UnicodeDecodeError as err:
                msg = "Problem with {0}, skipping....  \"{1}\"."
                warnings.warn(msg.format(url, err))

            self.downloaded_url = url
            if self.race_date_in_range():
                self.compile_race_results()
            else:
                self.logger.info('Date not in range...')

    def get_race_date(self):
        """
        Return the race date.
        """
        # The date text is in the file's sole H3 tag.
        regex = re.compile(r'<h3.*>(?P<h3>.*)</h3>')
        matchobj = regex.search(self.html)
        if matchobj is not None:
            full_race_date_text = matchobj.group('h3')
        else:
            # Try searching for just the literal text.
            regex = re.compile(r'Race Date:\d\d-\d\d-\d\d')
            matchobj = regex.search(self.html)
            full_race_date_text = matchobj.group()

        # The race date should read something like
        #     "    Race Date:11-03-12   "
        pat = r'\s*Race\sDate:(?P<mo>\d{1,2})-(?P<dd>\d{2})-(?P<yy>\d{2})\s*'
        regex = re.compile(pat)
        matchobj = regex.search(full_race_date_text)

        # NOW we get to see if the race is in the proper time frame or not.
        year = 2000 + int(matchobj.group('yy'))
        month = int(matchobj.group('mo'))
        day = int(matchobj.group('dd'))

        return datetime.date(year, month, day)

    def race_date_in_range(self):
        """
        Determine if the race file took place in the specified date range.
        """
        race_date = self.get_race_date()
        return (self.start_date <= race_date and race_date <= self.stop_date)

    def compile_race_results(self):
        """
        Go through a race file and collect results.
        """
        results = []
        for line in self.html.split('\n'):
            if self.match_against_membership(line):
                results.append(line)

        if len(results) > 0:
            results = self.webify_results(results)
            self.insert_race_results(results)

    def webify_results(self, results):
        """
        Take the list of results and turn it into output HTML.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # The single H2 element in the file has the race name.
        regex = re.compile(r'<h2.*>(?P<h2>.*)</h2>')
        matchobj = regex.search(self.html)
        h2 = ET.Element('h2')
        if matchobj is None:
            h2.text = ''
        else:
            h2.text = matchobj.group('h2')
        div.append(h2)

        # The single H3 element in the file has the race date.
        dt = self.get_race_date()
        h3 = ET.Element('h3')
        h3.text = dt.strftime('Race Date:  %b %d, %Y')
        div.append(h3)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            p = ET.Element('p')
            p.set('class', 'provenance')

            span1 = ET.Element('span')
            span1.text = 'Complete results '
            anchor = ET.Element('a')
            anchor.set('href', self.downloaded_url)
            anchor.text = 'here'
            span2 = ET.Element('span')
            span2.text = ' on Compuscore.'

            p.append(span1)
            p.append(anchor)
            p.append(span2)

            div.append(p)

        # Append the actual race results.  Consists of the column headings
        # (banner) plus the individual results.
        pre = ET.Element('pre')
        pre.set('class', 'actual_results')

        regex = re.compile(r"""<strong>(?P<strong1>[^<>]*)</strong>\s*
                               <strong><u>(?P<strong2>[^<>]*)</u></strong>""",
                               re.VERBOSE)
        matchobj = regex.search(self.html)
        if matchobj is None:
            pre.text = '\n' + '\n'.join(results)
        else:
            # This <pre> element must be mixed content in order to look
            # right.  Difficult to do this without using "fromstring".
            inner = '\n' + matchobj.group() + '\n' + '\n'.join(results)
            mixed_content = '<pre>' + inner + '</pre>'
            pre = ET.fromstring(mixed_content)
        div.append(pre)

        return div

    def parse_banner(self):
        """
        Find the HTML preceeding the results that sets up the column
        titles.
        """
        regex = re.compile(r"""<strong>(?P<strong1>[^<>]*)</strong>\s*
                               <strong><u>(?P<strong2>[^<>]*)</u></strong>""",
                               re.VERBOSE)
        return re.search(self.html)

    def match_against_membership(self, line):
        """
        We have a line of text from the race file.  Match it against the
        membership list.
        """
        for idx in range(0, len(self.first_name_regex)):
            fregex = self.first_name_regex[idx]
            lregex = self.last_name_regex[idx]
            if fregex.search(line) and lregex.search(line):
                return(True)
        return(False)

    def download_master_file(self):
        """
        Download results for the given month.

        The URL will have the pattern

        http://compuscore.com/csYYYY/MONTH/index.htm

        """
        url = 'http://compuscore.com/cs{0}/{1}/index.htm'
        url = url.format(self.start_date.year, self.monthstr)
        self.logger.info('Downloading master file {0}.'.format(url))

        response = urllib.request.urlopen(url)
        self.html = response.read().decode('utf-8')

        self.local_tidy()

    def compile_local_results(self):
        """
        Compile results from list of local files.
        """
        with open(self.race_list) as fp:
            for racefile in fp.readlines():
                racefile = racefile.rstrip()
                self.logger.info('Processing %s...' % racefile)
                self.local_tidy(racefile)

                with open(racefile, 'rt') as fptr:
                    self.html = fptr.read()

                self.compile_race_results()
