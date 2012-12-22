"""
Module for BestRace.
"""
import datetime
import logging
import os
import re
import warnings
import xml.etree.cElementTree as ET

import rr


class brrr:
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
        self.start_date = None
        self.stop_date = None
        self.memb_list = None
        self.race_list = None
        self.output_file = None
        self.verbose = 'info'
        self.__dict__.update(**kwargs)

        self.downloaded_url = None

        # Set the appropriate logging level.  Requires an exact
        # match of the level string value.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        self.load_membership_list()
        self.compile_results()
        # Make the output human-readable.
        rr.common.local_tidy(self.output_file)

    def load_membership_list(self):
        """
        Construct regular expressions for each person in the membership list.
        """
        names = rr.common.parse_membership_list(self.memb_list)
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

    def local_tidy(self, html_file):
        """
        Cleans up the HTML file.

        LIBTIDY doesn't seem to like p:colorspace, so get rid of it before
        calling LIBTIDY.
        """
        fp = open(html_file, 'r')
        html = fp.read()
        fp.close()
        html = html.replace(':colorscheme', '')
        #fp = open(html_file,'w',encoding='ascii')
        fp = open(html_file, 'w')
        fp.write(html)
        fp.close()

        rr.common.local_tidy(html_file)

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

    def initialize_output_file(self):
        """
        Construct a skeleton of the results of parsing race results from
        BestRace.

        <html>
            <head>
                <link rel='stylesheet' href='rr.css' type='text/css'/>
                <body>
                    STUFF TO GO HERE
                </body>
            </head>
        </html>
        """
        ofile = ET.Element('html')
        head = ET.SubElement(ofile, 'head')
        link = ET.SubElement(head, 'link')
        link.set('rel', 'stylesheet')
        link.set('href', 'rr.css')
        link.set('type', 'text/css')
        body = ET.SubElement(ofile, 'body')
        ET.ElementTree(ofile).write(self.output_file)
        rr.common.pretty_print_xml(self.output_file)

    def compile_web_results(self):
        """
        Download the requested results and compile them.
        """
        self.download_master_file()
        self.process_master_file()

    def process_master_file(self):
        """
        Compile results for the specified state.

        We assume that we have the state file stored locally.
        """
        local_file = 'index.html'
        fmt = 'http://www.bestrace.com/results/%s/%s%s'
        pattern = fmt % (self.start_date.strftime('%y'),
                self.start_date.strftime('%y'),
                self.start_date.strftime('%m'))

        day_range = '('
        for day in range(self.start_date.day, self.stop_date.day):
            day_range += "%02d|" % day
        day_range += '%02d)' % self.stop_date.day

        pattern += day_range

        pattern += ".*HTM"
        self.logger.debug('pattern is "%s"' % pattern)

        tree = ET.parse(local_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)

        anchors = root.findall('.//a')
        for anchor in anchors:
            href = anchor.get('href')
            if href is None:
                continue
            if re.match(pattern, href):
                self.logger.info('Downloading %s...' % href)
                race_file = self.download_race(href)
                self.compile_race_results(race_file)

    def compile_race_results(self, race_file):
        """
        Go through a single race file and collect results.
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
        Insert results into the output file.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        tree = ET.parse(race_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
        source_title = root.findall('.//title')[0]

        h1 = ET.Element('h1')
        h1.text = source_title.text
        div.append(h1)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            text = '<p class="provenance">Complete results '
            text += '<a href="%s">here</a> on BestRace.</p>'
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
        body = root.findall('.//body')[0]
        body.append(div)

        ET.ElementTree(root).write(self.output_file)

    def parse_banner(self, root):
        """Retrieve the banner from the race file.

        Example of a banner

                   The Andrea Holden 5k Thanksgiving Race
         PLC    Time  Pace  PLC/Group  PLC/Sex Bib#   Name
           1   16:40  5:23    1 30-39    1 M   142 Brian Allen

        """
        try:
            pre = root.findall('.//pre')[0]
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
        rr.common.download_file(url, 'index.html')
        self.local_tidy('index.html')

    def download_race(self, url):
        """
        Download a race URL to a local file.
        """
        local_file = url.split('/')[-1]
        self.logger.info('Downloading %s...' % local_file)
        rr.common.download_file(url, local_file)
        self.downloaded_url = url
        rr.common.local_tidy(local_file)
        return(local_file)

    def compile_local_results(self):
        """Compile results from list of local files.
        """
        for line in open(self.race_list):
            self.compile_race_results(line.rstrip())
