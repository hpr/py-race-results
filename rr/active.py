import datetime
import logging
import os
import re
import urllib
import xml.etree.cElementTree as ET

from .common import RaceResults

class Active(RaceResults):
    """
    Class for retrieving and processing race results from Active.com.

    Attributes:
        start_date, stop_date:  date range for retrieving results
        verbose:  how verbose to make the process.
        memb_list:  membership list
        race_list:  file containing list of races.
        output_file:  The output is collected here.
        base_url:  all URLs from active.com derive from this
        downloaded_url:  URL retrieved from Active.com
    """
    def __init__(self, **kwargs):
        """
        Constructor for Active class.

        Example:
            # You really should use this via the bin script.
            >>> from rr import Active
            >>> kwargs = {}
            >>> kwargs['start_date'] = datetime.datetime(2012,5,21)
            >>> kwargs['stop_date'] = datetime.datetime(2012,5,27)
            >>> kwargs['memb_list'] = '/Users/jevans/rvrr/rvrr.csv'
            >>> kwargs['output_file'] = 'results.html'
            >>> kwargs['location'] = 'New Brunswick, NJ'
            >>> kwargs['radius'] = 75
            >>> o = Active(**kwargs)
            >>> o.run()

        """
        RaceResults.__init__(self)
        self.__dict__.update(**kwargs)

        self.base_url = 'http://results.active.com'

        # This is the name of the file that keeps all of the high level results
        # for the location.
        self.master_file = 'geographic.html'

        # Need to remember the current URL so that we can reference it in the
        # output.
        self.downloaded_url = None

        # Set the appropriate logging level.
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        """
        Load the membership list and run through all the results.
        """
        names = self.parse_membership_list()

        # The names are actually in reverse order.
        fname = names.last
        lname = names.first

        first_name_regex = []
        last_name_regex = []
        for j in range(len(fname)):
            # For the regular expression, the first and last names are each
            # stored in separate XML elements, so the regular expressions need
            # only contain the names themselves.
            first_name_regex.append(re.compile(fname[j], re.IGNORECASE))
            last_name_regex.append(re.compile(lname[j], re.IGNORECASE))

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
        We assume that we have the master file stored locally.
        """

        tree = ET.parse(self.master_file)
        root = tree.getroot()
        root = self.remove_namespace(root)

        # Set up patterns to locate the result elements.
        pattern = './/body/div/div/div/div/div/div'
        results = root.findall(pattern)

        for result in results:
            children = result.getchildren()

            # Should be four children.  All the information is in the 2nd
            # child.
            race = children[1]

            # <div class="result-title">
            #   <h5>
            #     <a href="/events/85698">Ho Ho Ho Holiday 5K</a>
            #   </h5>
            #   <div class="result-sub-location"> Bethpage, NY </div>
            # </div>
            anchor = race.getchildren()[0].getchildren()[0]
            race_name = re.sub('\n', '', anchor.text)
            race_name = re.sub('  +', ' ', anchor.text)
            self.logger.info("Looking at '%s' ..." % race_name)
            self.process_event(anchor.get('href'))

    def process_event(self, relative_event_url):
        """
        We have the URL of an event.  Figure out if there is anything useful in
        it.
        """
        url = self.base_url + relative_event_url
        self.logger.info('Downloading %s...' % url)
        self.download_file(url, 'event.html')
        self.local_tidy('event.html')

        root = ET.parse('event.html').getroot()
        root = self.remove_namespace(root)

        # Look for the event overview.
        pattern = './/body/div/div/div/div/div/nav'
        nav = root.findall(pattern)

        # Look at all of the children except the first.  That first URL is the
        # event overview, which is where we are at now.
        divs = nav[0].getchildren()
        for div in divs[1:]:
            anchor = div.getchildren()[0]
            text = re.sub('\n', ' ', anchor.text)
            self.logger.info('Looking at sub-event %s' % text)
            self.process_sub_event(anchor.get('href'))

    def process_sub_event(self, relative_url):
        """
        We have a single event node within the overall event, kind of like
        evaluating the Philadelphia Marathon within the group of other
        events offered that day, like the Half Marathon and 8K.
        """
        url = self.base_url + relative_url
        self.logger.info('Downloading %s...' % url)

        chunk_file = 'event_0000.html'
        self.download_file(url, chunk_file)
        self.local_tidy(chunk_file)

        self.event_chunk_list = []
        self.event_chunk_list.append(chunk_file)

        last_chunk_file = chunk_file
        while self.more_event_chunks(last_chunk_file):
            url = self.get_chunk_url(last_chunk_file)
            self.logger.info('Downloading %s...' % url)
            current_chunk_file = "event_%04d.html" % len(self.event_chunk_list)
            rr.common.download_file(url, current_chunk_file)
            rr.common.local_tidy(current_chunk_file)

            self.event_chunk_list.append(current_chunk_file)
            last_chunk_file = current_chunk_file

        complete_results_file = self.concatenate_chunks()
        self.compile_native_active_results(complete_results_file)

    def get_chunk_url(self, chunk_file):
        """
        Results for native active race results format seem to only come in
        chunks of 100.  If there is another chunk, it will be indicated
        down at the bottom of the file.
        """
        root = ET.parse(chunk_file).getroot()
        root = rr.common.remove_namespace(root)

        pattern = './/body/div/div/div/div/section/div/table/tfoot/tr/td/div'
        div = root.findall(pattern)

        # The last child will have an href attribute if there is another chunk.
        next = div[0].getchildren()[-1]
        href = next.get('href')
        url = self.base_url + href
        return url

    def more_event_chunks(self, chunk_file):
        """
        Results for native active race results format seem to only come in
        chunks of 100.  If there is another chunk, it will be indicated
        down at the bottom of the file.
        """
        try:
            self.get_chunk_url(chunk_file)
            return True
        except:
            return False

    def scrub_tr(self, tr):
        """
        We need to strip the unnecessary stuff.
        <td>
            <b>
            <a href="junk">stuff</a>
            </b>
        </td>
        """
        tds = tr.getchildren()
        clean_tr = ET.Element('tr')
        for td in tds:
            ch = td.getchildren()
            ahrefs = td.findall('.//b/a')
            ahrefs2 = td.findall('.//a')
            if (len(ahrefs) != 0):
                clean_td = ET.Element('td')
                clean_td.text = ch[0].getchildren()[0].text
            elif (len(ahrefs2) != 0):
                clean_td = ET.Element('td')
                clean_td.text = ch[0].text
            else:
                # OK as-is.  Nothing to scrub.
                clean_td = td

            clean_tr.append(clean_td)
        return(clean_tr)

    def compile_race_results(self, race_file):
        """
        Go through a race file and collect results.
        """
        results = []
        for rline in open(race_file):
            line = rline.rstrip()
            if self.match_against_membership(line):
                results.append(line)

        if len(results) > 0:
            self.insert_race_results(results, race_file)

    def insert_race_results(self, results, race_file):
        """
        Insert Active results into the output file.
        """
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # The race name is in the HEAD.
        root = ET.parse(race_file).getroot()
        root = rr.common.remove_namespace(root)
        head = root.getchildren()[0]

        # The location is also in the head.
        meta = head.getchildren()[12]
        location = meta.get('content')
        meta = head.getchildren()[13]
        location += ', ' + meta.get('content')

        h1 = ET.Element('h1')
        h1.text = head.getchildren()[3].get('content')
        div.append(h1)

        h2 = ET.Element('h2')
        h2.text = location
        div.append(h2)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            url_div = ET.Element('p')

            span = ET.Element('span')
            span.text = 'Complete results '
            url_div.append(span)

            anchor = ET.Element('a')
            anchor.text = 'here'
            anchor.set('href', self.downloaded_url)
            url_div.append(anchor)

            span = ET.Element('span')
            span.text = ' at '
            url_div.append(span)

            anchor = ET.Element('a')
            anchor.text = 'Active.com.'
            anchor.set('href', 'http://www.active.com')
            url_div.append(anchor)

            div.append(url_div)

        table = ET.Element('table')
        for row in results:
            table.append(row)

        div.append(table)

        root = ET.parse(self.output_file).getroot()
        body = root.findall('.//body')[0]
        body.append(div)

        ET.ElementTree(root).write(self.output_file)

    def match_against_membership(self, line):
        """
        Match the membership list against the current line of text.
        """
        #z = zip(self.first_name_regex,self.last_name_regex)
        for idx in range(0, len(self.first_name_regex)):
            fregex = self.first_name_regex[idx]
            lregex = self.last_name_regex[idx]
            if fregex.search(line) and lregex.search(line):
                return(True)
        return(False)

    def download_master_file(self):
        """
        Download results according to the geographic location.

        The URL will have the pattern

        http://results.active.com/search?utf8=%E2%9C%93
            &search%5Bquery%5D=
            &search%5Bsource%5D=event
            &search%5Blocation%5D=Boston%2C+MA
            &search%5Bradius%5D=100
            &search%5Bstart_date%5D=2012-12-01
            &search%5Bend_date%5D=2012-12-230

        """
        self.logger.debug('Retrieving races in geographic range...')
        url = self.base_url + '/search?'
        url += 'utf8=%E2%9C%93'

        # Percent-encoding at work here.
        query = urllib.urlencode({'[query]': ''})
        source = urllib.urlencode({'[source]': 'event'})
        location = urllib.urlencode({'[location]': self.location})
        radius = urllib.urlencode({'[radius]': str(self.radius)})
        start = urllib.urlencode({'[start_date]':
            self.start_date.strftime('%Y-%m-%d')})
        stop = urllib.urlencode({'[end_date]':
            self.stop_date.strftime('%Y-%m-%d')})

        url += '&search' + '&search'.join([query, source, location, radius,
            start, stop])

        self.logger.debug('Downloading %s.' % url)
        self.download_file(url, self.master_file)

        self.local_tidy(self.master_file)

    def compile_local_results(self):
        """
        Compile results from list of local files.
        """
        for line in open(self.race_list):
            self.compile_race_results(line.rstrip())
