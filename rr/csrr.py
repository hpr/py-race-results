import datetime
import logging
import os
import re
import sys
import xml.etree.cElementTree as ET

import rr

class csrr:
    def __init__(self, **kwargs):
        """
        month:  month in which to look for results
        year:  year in which to look for results
        memb_list:  membership list
        race_list:  file containing list of races
        output_file:  final race results file
        verbose:  how much output to produce
        """
        self.year  = None
        self.month   = None
        self.memb_list   = None
        self.race_list   = None
        self.output_file = None
        self.verbose     = 'info'
        self.__dict__.update(**kwargs)

        # Need to remember the current URL.
        self.downloaded_url = None

        # Set the appropriate logging level.  Requires an exact
        # match of the level string value.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel( getattr(logging, self.verbose.upper()) )

    def run(self):
        """
        Load the membership list and run through all the results.
        """
        names = rr.common.parse_membership_list(self.memb_list)

        # The names are actually in reverse order.
        fname = names.last
        lname = names.first

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
            first_name_regex.append(re.compile(pattern,re.IGNORECASE))
            pattern = '\s' + lname[j] + '\s'
            last_name_regex.append(re.compile(pattern,re.IGNORECASE))
        
        self.first_name_regex = first_name_regex
        self.last_name_regex = last_name_regex

        self.compile_results();
        rr.common.local_tidy(self.output_file)

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

        head = ET.SubElement(ofile,'head')

        link = ET.SubElement(head,'link')
        link.set('rel','stylesheet')
        link.set('href','rr.css')
        link.set('type','text/css')

        body = ET.SubElement(ofile,'body')

        ET.ElementTree(ofile).write(self.output_file)

        rr.common.pretty_print_xml(self.output_file)


    def compile_web_results(self):
        """
        Download the requested results and compile them.
        """
        self.download_master_file()
        self.process_master_file()


    def construct_state_match_pattern(self,state):
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
        for day in range(self.start_date.day,self.stop_date.day):
            day_range += "%d_|" % day
        day_range += '%d_)' % self.stop_date.day

        pattern += day_range

        pattern += '.*shtml'
        self.logger.debug('Match pattern is %s...' % pattern)
        r = re.compile(pattern,re.DOTALL)
        return(r)


    def process_master_file(self):
        """
        Compile results.
        """
        pattern = 'http://www.compuscore.com/cs%s/%s' % (self.date.strftime('%Y'), self.month)

        tree = ET.parse('index.htm')
        root = tree.getroot()
        root = rr.common.remove_namespace(root)

        anchor_pattern = './/a'
        anchors = root.findall(anchor_pattern)
        for anchor in anchors:
            href = anchor.get('href')
            if re.match(pattern,href):
                local_file = href.split('/')[-1] 
                self.logger.info('Downloading %s...' % local_file)
                rr.common.download_file(href, local_file)
                self.downloaded_url = href 
                rr.common.local_tidy(local_file) 
                self.compile_race_results(local_file)




    def compile_race_results(self,race_file):
        """
        Go through a race file and collect results.
        """
        r = []
        for rline in open(race_file):
            line = rline.rstrip()
            if self.match_against_membership(line):
                r.append(line)

        if len(r) > 0:
            self.insert_race_results(r,race_file)


    def insert_race_results(self,result,race_file):
        """
        Insert CoolRunning results into the output file.
        """
        div = ET.Element('div')
        div.set('class','race')
        hr = ET.Element('hr')
        hr.set('class','race_header')
        div.append(hr)

        # The H2 tag has the race name.
        # The H2 tag comes from the only H1 tag in the race file.
        tree = ET.parse(race_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
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
            text = '<p class="provenance">Complete results <a href="%s">here</a> on Compuscore.</p>' % self.downloaded_url
            p = ET.XML(text)
            div.append(p)

        pre = ET.Element('pre')
        pre.set('class','actual_results')

        banner = self.parse_banner(root)

        text = '\n'
        for line in result:
            text += line + '\n'

        pre.text = banner + text
        div.append(pre)

        tree = ET.parse(self.output_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
        body = root.findall('.//body')[0]
        body.append(div)

        ET.ElementTree(root).write(self.output_file)

        rr.common.local_tidy(self.output_file)

    def parse_banner(self,root):
        """
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


    def match_against_membership(self,line):
        """
        """
        for idx in range(0,len(self.first_name_regex)):
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
        url = 'http://compuscore.com/cs%s/%s/index.htm' % (self.date.strftime('%Y'),self.month)
        self.logger.info('Downloading %s.' % url)
        rr.common.download_file(url, 'index.htm')
        rr.common.local_tidy('index.htm')



    def compile_local_results(self):
        """
        Compile results from list of local files.
        """
        for line in open(self.race_list):
            line = line.rstrip()
            self.logger.info('Processing %s...' % line)
            rr.common.local_tidy(line) 
            self.compile_race_results(line)


