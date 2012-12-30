"""
Backend class for handling CoolRunning race results.
"""

import datetime
import logging
import os
import re
import sys
import xml.etree.cElementTree as ET

import rr


class crrr:
    """
    Class for handling CoolRunning Race Results.
    """
    def __init__(self, start_date=None, stop_date=None, verbose=None,
            states=['ma'], memb_list=None, race_list=None, output_file=None):
        """
        base_url:
        memb_list:  membership list
        race_list:  file containing list of races
        output_file:  final race results file
        verbose:  how much output to produce
        """
        self.start_date = start_date
        self.stop_date = stop_date
        self.states = states
        self.memb_list = memb_list
        self.race_list = race_list
        self.output_file = output_file

        self.base_url = 'http://www.coolrunning.com'

        # Need to remember the current URL.
        self.downloaded_url = None

        # Set the appropriate logging level.  Requires an exact
        # match of the level string value.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, verbose.upper()))

    def run(self):
        self.load_membership_list()
        self.compile_results()
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
        ET.SubElement(ofile, 'body')
        ET.ElementTree(ofile).write(self.output_file)
        rr.pretty_print_xml(self.output_file)

    def compile_web_results(self):
        """
        Download the requested results and compile them.
        """
        for state in self.states:
            self.download_state_master_file(state)
            self.process_state_master_file(state)

    def construct_state_match_pattern(self, state):
        """
        Want to match strings like

        http://www.coolrunning.com/results/07/ma/Jan16_Coloni_set1.shtml

        So we construct a regular expression to match against
        all the dates in the specified range.
        """

        #pattern = 'http://ww.coolrunning.com/results/'
        pattern = '/results/'
        pattern += self.start_date.strftime('%y')
        pattern += '/'
        pattern += state
        pattern += '/'
        pattern += self.start_date.strftime('%b')

        # continue with a regexp to match any of the days in the range.
        day_range = '('
        for day in range(self.start_date.day, self.stop_date.day):
            day_range += "%d_|" % day
        day_range += '%d_)' % self.stop_date.day

        pattern += day_range

        pattern += '.*shtml'
        self.logger.debug('Match pattern is %s' % pattern)
        r = re.compile(pattern, re.DOTALL)
        return(r)

    def process_state_master_file(self, state):
        """
        Compile results for the specified state.
        We assume that we have the state file stored locally.
        """
        local_state_file = state + '.shtml'
        pattern = self.construct_state_match_pattern(state)

        tree = ET.parse(local_state_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)

        anchor_pattern = './/a'
        anchors = root.findall(anchor_pattern)

        urls = set()

        for anchor in anchors:

            href = anchor.get('href')
            if href is None:
                continue
            match = pattern.search(href)
            if match is None:
                continue

            # keep track of the last part of the URL.
            # That should be unique.
            parts = href.split('/')
            urls.add(parts[-1])

            race_file = self.download_race(anchor)
            self.compile_race_results(race_file)

            # Now collect any secondary result files.
            try:
                tree = ET.parse(race_file)
            except ET.ParseError:
                self.logger.debug('ElementTree ParseError:  %s' % race_file)
                continue
            except:
                raise
            root = tree.getroot()
            root = rr.common.remove_namespace(root)

            inner_anchors = root.findall(anchor_pattern)

            # construct the 2ndary pattern
            parts = race_file.split('.')
            s = parts[0][:-1]
            secondary_pattern = re.compile(s, re.DOTALL)
            for inner_anchor in inner_anchors:

                href = inner_anchor.get('href')
                if href is None:
                    continue
                match = secondary_pattern.search(href)
                if match is None:
                    continue

                parts = href.split('/')
                if parts[-1] in urls:
                    # yes we did
                    continue

                urls.add(parts[-1])

                inner_race_file = self.download_race(inner_anchor,
                        inner_url=True,
                        state=state)
                if inner_race_file is None:
                    continue

                self.compile_race_results(inner_race_file)

    def compile_vanilla_results(self, race_file):
        """
        Compile race results for CoolRunning races posted inXML pattern
        2 format.
        """
        pattern = './/body/table/tr/td/table/tr/td/table/tr/td/div/pre'

        tree = ET.parse(race_file)
        root = tree.getroot()
        rr.common.remove_namespace(root)
        nodes = root.findall(pattern)

        r = []
        for node in nodes:
            text = ET.tostring(node)
            for line in text.split('\n'):
                if self.match_against_membership(line):
                    r.append(line)

        if len(r) > 0:
            self.insert_race_results(r, race_file)

    def is_vanilla_pattern(self, race_file):
        """
        Check to see if the current race file matches the usual
        pattern found on CoolRunning.
        """
        pattern = './/body/table/tr/td/table/tr/td/table/tr/td/div/pre'

        try:
            tree = ET.parse(race_file)
        except ET.ParseError:
            self.logger.debug('XML_02 ParseError on %s' % race_file)
            return False
        except:
            raise

        root = tree.getroot()
        rr.common.remove_namespace(root)
        nodes = root.findall(pattern)
        if len(nodes) > 0:
            return True
        else:
            return False

    def is_ccrr_pattern(self, race_file):
        """
        Check to see if the current race file matches what the Cape Cod
        Road Runners seem to use.

        See
        http://www.coolrunning.com/results/12/ma/Jan8_CapeCo_set1.shtml
        for an example.
        """
        pattern = './/body/table/tr/td/table/tr/td/table/tr/td/div/table/tr'

        try:
            tree = ET.parse(race_file)
        except ET.ParseError:
            self.logger.debug('CCRR XHTML ParseError on %s' % race_file)
            return False
        except:
            raise

        root = tree.getroot()
        rr.common.remove_namespace(root)
        nodes = root.findall(pattern)
        if len(nodes) > 0:
            return True
        else:
            return False

    def compile_ccrr_race_results(self, race_file):
        """
        This is the format generally used by Cape Cod
        Road Runners.
        """
        pattern = './/body/table/tr/td/table/tr/td/table/tr/td/div/table/tr'

        tree = ET.parse(race_file)
        root = tree.getroot()
        rr.common.remove_namespace(root)

        trs = root.findall(pattern)

        results = []
        for tr in trs:
            tds = tr.getchildren()

            if len(tds) < 3:
                continue

            runner_name = tds[2].text
            if runner_name is None:
                continue
            for idx in range(0, len(self.first_name_regex)):
                fregex = self.first_name_regex[idx]
                lregex = self.last_name_regex[idx]
                if fregex.search(runner_name) and lregex.search(runner_name):
                    tr = rr.common.remove_namespace(tr)
                    results.append(tr)

        if len(results) > 0:
            # Prepend the header.
            tr = rr.common.remove_namespace(trs[0])
            results.insert(0, tr)
            self.insert_race_results_ccrr(results, race_file)

    def compile_race_results(self, race_file):
        """
        Go through a race file and collect results.
        body table tr td table tr td table tr td div TABLE TR
        """
        if self.is_vanilla_pattern(race_file):
            self.logger.debug('XML pattern 2')
            self.compile_vanilla_results(race_file)
        elif self.is_ccrr_pattern(race_file):
            self.logger.debug('XML pattern 1')
            self.compile_ccrr_race_results(race_file)
        else:
            self.logger.warning('Unknown pattern.')

    def construct_common_div(self, race_file):
        """
        Construct an XHTML element to contain race results.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # The H1 tag has the race name.
        # The H1 tag comes from the only H1 tag in the race file.
        tree = ET.parse(race_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
        pattern = './/h1'
        source_h1 = root.findall(pattern)[0]

        h1 = ET.Element('h1')
        h1.text = source_h1.text
        div.append(h1)

        # The first H2 tag has the location and date.
        # The H2 tag comes from the only H2 tag in the race file.
        pattern = './/h2'
        source_h2 = root.findall(pattern)[0]

        h2 = ET.Element('h2')
        h2.text = source_h2.text
        div.append(h2)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            p = ET.Element('p')
            span = ET.Element('span')
            span.text = 'Complete results '
            p.append(span)
            a = ET.Element('a')
            a.set('href', self.downloaded_url)
            a.text = 'here'
            p.append(a)
            span = ET.Element('span')
            span.text = ' on Coolrunning.'
            p.append(span)
            div.append(p)

        return(div)

    def insert_race_results_ccrr(self, results, race_file):
        """
        Insert CoolRunning results into the output file.
        This works for CCRR races.
        """
        div = self.construct_common_div(race_file)

        table = ET.Element('table')
        for tr in results:
            if tr is not None:
                table.append(tr)

        div.append(table)
        self.insert_common_div(div)

    def insert_race_results(self, result, race_file):
        """
        Insert CoolRunning results into the output file.
        """
        div = self.construct_common_div(race_file)

        pre = ET.Element('pre')
        pre.set('class', 'actual_results')

        root = ET.parse(race_file).getroot()
        root = rr.common.remove_namespace(root)
        banner = self.parse_banner(root)

        text = '\n'
        for line in result:
            text += line + '\n'

        pre.text = banner + text
        div.append(pre)

        self.insert_common_div(div)

    def insert_common_div(self, div):
        """
        The DIV element has been completely construct, so
        now we just put it into the output file.
        """
        tree = ET.parse(self.output_file)
        root = tree.getroot()
        body = root.findall('.//body')[0]
        body.append(div)

        ET.ElementTree(root).write(self.output_file)

    def parse_banner(self, root):
        """
                   The Andrea Holden 5k Thanksgiving Race
         PLC    Time  Pace  PLC/Group  PLC/Sex Bib#   Name
           1   16:40  5:23    1 30-39    1 M   142 Brian Allen

        """
        pattern = './/pre'
        try:
            pre = root.findall(pattern)[0]
        except IndexError:
            return('')

        # Stop when we find the first "1"
        # First line is <pre>, so skip that.
        banner = ''
        for line in ET.tostring(pre).split('\n')[1:]:
            if re.match('\s+1', line):
                # found it
                break
            else:
                banner += line + '\n'

        # If there are ANY html elements in here, then forget it, because the
        # html elements will end up converted into entities, which we do not
        # want.
        if re.search('<.*?>', banner) is not None:
            return('')
        else:
            return(banner)

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

    def download_state_master_file(self, state):
        """
        Download results for the specified state.

        The URL will have the pattern

        http://www.coolrunning.com/results/[YY]/[STATE].shtml

        """
        self.logger.info('Processing %s...' % state)
        local_state_file = state + '.shtml'
        fmt = 'http://www.coolrunning.com/results/%s/%s'
        url = fmt % (self.start_date.strftime('%y'), local_state_file)
        self.logger.info('Downloading %s.' % url)
        rr.common.download_file(url, local_state_file)
        rr.common.local_tidy(local_state_file)

    def download_race(self, anchor, inner_url=False, state=''):
        """
        """
        href = anchor.get('href')

        if inner_url:
            pattern = '/results/'
            pattern += self.start_date.strftime('%y')
            pattern += '/'
            pattern += state
            href = pattern + '/' + href

        url = 'http://www.coolrunning.com/%s' % href
        local_file = href.split('/')[-1]
        self.logger.info('Downloading %s...' % url)
        rr.common.download_file(url, local_file)
        self.downloaded_url = url
        try:
            rr.common.local_tidy(local_file)
        except IOError:
            fmt = 'Encountered an error processing %s, skipping it.'
            self.logger.debug(fmt % local_file)
            local_file = None

        return(local_file)

    def compile_local_results(self):
        """
        Compile results from list of local files.
        """
        for line in open(self.race_list):
            try:
                self.logger.info('Processing file %s' % line)
                race_file = line.rstrip()
                rr.common.local_tidy(race_file)
                self.compile_race_results(race_file)
            except IOError:
                fmt = 'Encountered an error processing %s, skipping it.'
                self.logger.debug(fmt % line)
