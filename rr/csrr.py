import datetime
import logging
import os
import re
import sys

from bs4 import BeautifulSoup
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
             10: 'oct',
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
        names = self.parse_membership_list()

        fname = names.first
        lname = names.last

        first_name_regex = []
        last_name_regex = []
        for j in range(len(fname)):
            # Example to match:
            #
            #   '60.Gene Gugliotta       North Plainfiel,NJ 53 M U '
            #
            pattern = '\.' + fname[j] + '\s'
            first_name_regex.append(re.compile(pattern, re.IGNORECASE))
            pattern = '\s' + lname[j] + '\s'
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
        pattern = 'http://www.compuscore.com/cs%s/%s' % (year, monthstr)

        with open('index.htm') as fp:
            markup = fp.read()
        root = BeautifulSoup(markup, 'lxml')
        anchors = root.find_all('a')
        for anchor in anchors:
            href = anchor.get('href')
            if re.match(pattern, href):
                local_file = href.split('/')[-1]
                self.logger.info('Downloading %s...' % local_file)
                self.download_file(href, local_file)
                self.downloaded_url = href
                self.local_tidy(local_file)
                if self.race_date_in_range(local_file):
                    self.compile_race_results(local_file)
                else:
                    self.logger.info('Date not in range...')

    def race_date_in_range(self, race_file):
        """
        Determine if the race file took place in the specified date range.
        """
        with open(race_file) as fp:
            markup = fp.read()
        root = BeautifulSoup(markup, 'lxml')

        # The date is in a single H3 element under to BODY element.
        h3 = root.find_all('h3')
        if len(h3) != 1:
            self.logger.warning('Unable to locate race date.')
            # Return True, force it to be parsed anyway.
            return True

        date_text = h3[0].text

        # The race date should read something like
        #     "    Race Date:11-03-12   "
        pat = '\s*Race\sDate:(?P<mo>\d{1,2})-(?P<dd>\d{2})-(?P<yy>\d{2})\s*'
        m = re.match(pat, date_text)
        if m is None:
            # We could not parse the race date, so force this racefile to be
            # searched, just in case.
            self.logger.warning('Unable to parse the race date.')
            return True

        # NOW we get to see if the race is in the proper time frame or not.
        year = 2000 + int(m.group('yy'))
        month = int(m.group('mo'))
        day = int(m.group('dd'))
        dt = datetime.date(year, month, day)

        if self.start_date <= dt and dt <= self.stop_date:
            return True
        else:
            return False

    def compile_race_results(self, race_file):
        """
        Go through a race file and collect results.
        """
        results = []
        with open(race_file) as fp:
            for line in fp.readlines():
                if self.match_against_membership(line):
                    results.append(line)

        if len(results) > 0:
            results = self.webify_results(race_file, results)
            self.insert_race_results(results)

    def webify_results(self, race_file, results):
        """
        Take the list of results and turn it into output HTML.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # The single H2 element in the file has the race name.
        tree = ET.parse(race_file)
        root = tree.getroot()
        root = self.remove_namespace(root)
        pattern = './/h2'
        race_name_element = root.findall(pattern)[0]
        div.append(race_name_element)

        # The single H3 element in the file has the race date.
        pattern = './/h3'
        race_date_element = root.findall(pattern)[0]
        div.append(race_date_element)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            text = '<p class="provenance">Complete results '
            text += '<a href="%s">here</a> on Compuscore.</p>'
            text %= self.downloaded_url
            p = ET.XML(text)
            div.append(p)

        # Append the actual race results.  Consists of the column headings
        # (banner) plus the individual results.
        pre = ET.Element('pre')
        pre.set('class', 'actual_results')
        banner_text = self.parse_banner(root)
        pre.text = banner_text + '\n'.join(results)
        div.append(pre)

        return div

    def parse_banner(self, root):
        """
        Find the HTML preceeding the results that sets up the column
        titles.
        """
        pattern = './/strong'
        strongs = root.findall(pattern)
        pattern = './/u'
        us = root.findall(pattern)
        try:
            text = strongs[2].text
            text += '\n' + us[1].text
        except (IndexError, TypeError):
            # TypeError if the ET parsing is wrong
            self.logger.warning('Could not locate all of the banner.')
            text = ''

        text += '\n'
        return(text)

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
        url = 'http://compuscore.com/cs%s/%s/index.htm'
        url %= (self.start_date.year, self.monthstr)
        self.logger.info('Downloading %s.' % url)
        self.download_file(url, 'index.htm')
        self.local_tidy('index.htm')

    def compile_local_results(self):
        """
        Compile results from list of local files.
        """
        with open(self.race_list) as fp:
            for racefile in fp.readlines():
                self.logger.info('Processing %s...' % racefile)
                self.local_tidy(racefile)
            self.compile_race_results(racefile)
