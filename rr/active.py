import csv
import datetime
import logging
import os
import re
import urllib
import xml.etree.cElementTree as ET

from bs4 import BeautifulSoup

from .common import RaceResults


def clean_race_name(text):
    """Clean up white space."""
    # Strip out newlines.
    text = re.sub('\n', '', text)
    # Collapse sequences of two or more spaces with just a single space.
    text = re.sub('\s+', ' ', text)
    return text


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
        self.compile_web_results()

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
        markup = open(self.master_file).read()
        root = BeautifulSoup(markup, 'lxml')
        divs = [div for div in root.find_all('div') if div.has_key('class') and
                div.get('class') == ['result-title']]

        for result in divs:

            # <div class="result-title">
            #   <h5>
            #     <a href="/events/85698">Ho Ho Ho Holiday 5K</a>
            #   </h5>
            #   <div class="result-sub-location"> Bethpage, NY </div>
            # </div>
            anchors = result.findAll('a')
            anchor = anchors[0]
            self.logger.info("Looking at '%s' ..." %
                             clean_race_name(anchor.text))
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
        divs = nav[0].getchildren()

        # Look at all of the children except the first.  That first URL is the
        # event overview, which is where we are at now.
        for div in divs[1:]:
            anchor = div.getchildren()[0]
            self.logger.info("Looking at sub-event '%s' ..." %
                             clean_race_name(anchor.text))
            self.process_sub_event(anchor.get('href'))

    def process_sub_event(self, relative_url):
        """
        We have a single event node within the overall event, kind of like
        evaluating the Philadelphia Marathon within the group of other
        events offered that day, like the Half Marathon and 8K.
        """
        self.downloaded_url = self.base_url + relative_url
        self.logger.info('Downloading %s...' % self.downloaded_url)

        local_file = 'sub_event.html'
        self.download_file(self.downloaded_url, local_file)
        self.local_tidy(local_file)

        # <form accept-charset="UTF-8"
        #       action="/events/blah-blah-blah"
        #       class="inline-block"
        #       id="table_search"
        #       method="get">
        #
        # Match all the forms that download a CSV file.
        regex = re.compile(r"""<form
                               \s+accept-charset=\s*"UTF-8"
                               \s+action=\s*"(?P<action>[\w/-]+)"
                               \s+class=\s*"inline-block"
                               \s+id=\s*"table_search"
                               \s+method=\s*"get"
                               >""", re.VERBOSE)
        html = open(local_file).read()
        m = regex.search(html)
        if m is not None:
            self.process_csv_form(local_file, m.group('action'))
            return

        # Next, see if the results are already hard-coded into the file.
        # <pre id="raw-file">
        root = ET.parse(local_file).getroot()
        root = self.remove_namespace(root)
        pres = root.findall('.//pre[@id]')
        if len(pres) == 1:
            self.process_raw_file(local_file, pres[0].text)
            return

        self.logger.info("Unhandled sub event situation")

    def process_raw_file(self, source_file, text):
        """Process results where the have been embedded raw into the HTML."""
        results = []
        for line in text.split('\n'):
            for frst, lst in zip(self.first_name_regex, self.last_name_regex):
                firstname_m = frst.search(line)
                lastname_m = lst.search(line)
                if firstname_m is not None and lastname_m is not None:
                    results.append(line)

        if len(results) == 0:
            return

        # Ok construct the webified output.
        div = ET.Element('div')
        div.set('class', 'race')

        root = ET.parse(source_file).getroot()
        root = self.remove_namespace(root)

        titles = root.findall('.//title')
        h2 = ET.Element('h2')
        h2.text = titles[0].text
        div.append(h2)

        provenance_div = self.set_provenance()
        div.append(provenance_div)

        pre = ET.Element('pre')
        pre.text = '\n'.join(results)
        div.append(pre)

        self.insert_race_results(div)

    def process_csv_form(self, source_file, relative_url):
        """Process CSV form URL.

        Process results to be retrieve as a CSV file along with some extra CGI
        form actions.
        """
        # Download the CSV file.
        url = ("http://results.active.com" + relative_url +
               ".csv?per_page=100000")
        self.download_file(url, "event.csv")

        trs = self.process_csv_file('event.csv')
        if len(trs) == 0:
            # No results were found.
            self.logger.info("No member results found.")
            return

        table = ET.Element('table')
        for tr in trs:
            table.append(tr)

        # Construct the HTML for the results.
        # Append the title and the provenance.
        root = ET.parse(source_file).getroot()
        root = self.remove_namespace(root)

        div = ET.Element('div')
        div.set('class', 'race')

        titles = root.findall('.//title')
        h2 = ET.Element('h2')
        h2.text = titles[0].text
        div.append(h2)

        provenance_div = self.set_provenance()
        div.append(provenance_div)

        div.append(table)

        self.insert_race_results(div)

    def set_provenance(self):
        """Create a DIV containing a link to the original result."""
        pdiv = ET.Element('div')
        pdiv.set('class', 'provenance')
        span = ET.Element('span')
        span.text = 'Complete results at '
        pdiv.append(span)
        anchor = ET.Element('a')
        anchor.set('href', self.downloaded_url)
        anchor.text = 'Active.com'
        pdiv.append(anchor)
        span = ET.Element('span')
        span.text = '.'
        pdiv.append(span)
        return pdiv

    def process_csv_file(self, csv_file):
        """
        Process CSV file into HTML if any results are found.

        Returns:
            List of ElementTree TR elements representing a row of valid race
            results.  If the list is [], then no results were found.
        """
        trs = []
        for row in csv.reader(open('event.csv')):
            # the 3rd row item has the name for us to search.
            for frst, lst in zip(self.first_name_regex, self.last_name_regex):
                firstname_m = frst.search(row[2])
                lastname_m = lst.search(row[2])
                if firstname_m is not None and lastname_m is not None:
                    # Construct an HTML row out of the CSV row.
                    tr = ET.Element('tr')
                    for item in row:
                        td = ET.Element('td')
                        td.text = item
                        tr.append(td)
                    trs.append(tr)

        if len(trs) == 0:
            return trs

        # Prepend the first row as a header with TH elements.
        with open('event.csv') as cvsfile:
            reader = csv.reader(cvsfile)
            row = next(reader)
            tr = ET.Element('tr')
            for item in row:
                th = ET.Element('th')
                th.text = item
                tr.append(th)
            trs.insert(0, tr)

        return trs

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

        start_dict = {'[start_date]': self.start_date.strftime('%Y-%m-%d')}
        start = urllib.urlencode(start_dict)

        stop_dict = {'[end_date]': self.stop_date.strftime('%Y-%m-%d')}
        stop = urllib.urlencode(stop_dict)

        lst = [query, source, location, radius, start, stop]
        url += '&search' + '&search'.join(lst)

        self.logger.debug('Downloading %s.' % url)
        self.download_file(url, self.master_file)

        self.local_tidy(self.master_file)
