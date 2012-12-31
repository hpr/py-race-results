import datetime
import logging
import os
import re
import sys
import xml.etree.cElementTree as ET

from .common import RaceResults
import rr

logging.basicConfig()

# Need to match the month of the search window to the month strings that
# Compuscore uses.
monthstrs = {
        1: 'janfeb',
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
        12: 'novdec',
        }


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
            # For the regular expression, surround the name with
            # at least one white space character.  That way we cut
            # down on a lot of false positives, e.g. "Ed Ford" does
            # not cause every fricking person from "New Bedford" to
            # match.  Here's an example line to match.
            #   '60.Gene Gugliotta       North Plainfiel,NJ 53 M U '
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

    def initialize_output_file(self):
        """
        Construct an HTML skeleton.
        """
        ofile = ET.Element('html')

        head = ET.SubElement(ofile, 'head')

        link = ET.SubElement(head, 'link')
        link.set('rel', 'stylesheet')
        link.set('href', 'rr.css')
        link.set('type', 'text/css')

        body = ET.SubElement(ofile, 'body')

        ET.ElementTree(ofile).write(self.output_file)

        self.pretty_print_xml(self.output_file)

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

        tree = ET.parse('index.htm')
        root = tree.getroot()
        root = self.remove_namespace(root)

        anchor_pattern = './/a'
        anchors = root.findall(anchor_pattern)
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
                    self.logger.info('Skipping %s (not in range)...' % local_file)


    def race_date_in_range(self, race_file):
        """
        Determine if the race file took place in the specified date range.
        """
        tree = ET.parse(race_file)
        root = tree.getroot()
        root = self.remove_namespace(root)

        # The date is in a single H3 element under to BODY element.
        h3 = root.findall('.//h3')
        if len(h3) != 1:
            self.logger.warning('Unable to locate race date.')
            # Return True, force it to be parsed anyway.
            return True

        date_text = h3[0].text

        # The race date should read something like
        #     "    Race Date:11-03-12   "
        pat = '\s*Race\sDate:(?P<month>\d{2})-(?P<day>\d{2})-(?P<year>\d{2})\s*'
        m = re.match(pat, date_text)
        if m is None:
            self.logger.warning('Unable to parse the race date.')
            # Return True, force it to be parsed anyway.
            return True

        # NOW we get to see if the race is in the proper time frame or not.
        dt = datetime.date(2000 + int(m.group('year')),
                int(m.group('month')),
                int(m.group('day')))

        if self.start_date <= dt and dt <= self.stop_date:
            return True
        else:
            return False

    def compile_race_results(self, race_file):
        """
        Go through a race file and collect results.
        """
        r = []
        for rline in open(race_file):
            line = rline.rstrip()
            if self.match_against_membership(line):
                r.append(line)

        if len(r) > 0:
            self.insert_race_results(r, race_file)

    def insert_race_results(self, result, race_file):
        """
        Insert CoolRunning results into the output file.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # The H2 tag has the race name.
        # The H2 tag comes from the only H1 tag in the race file.
        tree = ET.parse(race_file)
        root = tree.getroot()
        root = self.remove_namespace(root)
        pattern = './/h2'
        source_h2 = root.findall(pattern)[0]

        h1 = ET.Element('h1')
        h1.text = source_h2.text
        div.append(h1)

        # The first H3 tag has the location and date.
        # The H3 tag comes from the only H2 tag in the race file.
        pattern = './/h3'
        source_h3 = root.findall(pattern)[0]

        h2 = ET.Element('h2')
        h2.text = source_h3.text
        div.append(h2)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            text = '<p class="provenance">Complete results '
            text += '<a href="%s">here</a> on Compuscore.</p>'
            text %= self.downloaded_url
            p = ET.XML(text)
            div.append(p)

        pre = ET.Element('pre')
        pre.set('class', 'actual_results')

        banner = self.parse_banner(root)

        text = '\n'
        for line in result:
            text += line + '\n'

        pre.text = banner + text
        div.append(pre)

        tree = ET.parse(self.output_file)
        root = tree.getroot()
        root = self.remove_namespace(root)
        body = root.findall('.//body')[0]
        body.append(div)

        ET.ElementTree(root).write(self.output_file)

        self.local_tidy(self.output_file)

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

        return(text)

    def match_against_membership(self, line):
        """
        We have a line of text from the URL.  Match it against the
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
        for line in open(self.race_list):
            line = line.rstrip()
            self.logger.info('Processing %s...' % line)
            self.local_tidy(line)
            self.compile_race_results(line)
