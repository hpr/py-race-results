import datetime
import logging
import os
import re
import xml.etree.cElementTree as ET

import rr.common

class Active:
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
    def __init__(self, start_date=None, stop_date=None, verbose=None,
            radius=None, near=None, memb_list=None, race_list=None, output_file=None):
        """Constructor for Active class.

        Args:
            start_date, stop_date:  date range for retrieving results
            verbose:  how verbose to make the process.
            states:  list of two-letter abbreviations of the states we wish to
                search.
            memb_list:  membership list
            race_list:  file containing list of races.
            output_file:  The output is collected here.

        Example:
            # You really should use this via the bin script.
            >>> import datetime, rr
            >>> kwargs = {}
            >>> kwargs['start_date'] = datetime.datetime(2012,5,21)
            >>> kwargs['stop_date'] = datetime.datetime(2012,5,27)
            >>> kwargs['states'] = ['ny', 'nj']
            >>> kwargs['memb_list'] = '/Users/jevans/rvrr/rvrr.csv'
            >>> kwargs['output_file'] = 'results.html'
            >>> a = rr.active.Active(**kwargs)

        """
        self.start_date = start_date
        self.stop_date = stop_date
        self.radius = radius
        self.center = near
        self.verbose = verbose
        self.memb_list = memb_list
        self.race_list = race_list
        self.output_file = output_file

        self.base_url = 'http://results.active.com/search?'

        # Need to remember the current URL so that we can reference it in the
        # output.
        self.downloaded_url = None

        # Set the appropriate logging level.  Requires an exact
        # match of the level string value.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel( getattr(logging, verbose.upper()) )

    def run(self):
        names = rr.common.parse_membership_list(self.memb_list)

        # The names are actually in reverse order.
        fname = names.last
        lname = names.first

        first_name_regex = []
        last_name_regex = []
        for j in range(len(fname)):
            # For the regular expression, the first and last names are each
            # stored in separate XML elements, so the regular expressions need
            # only contain the names themselves.  
            first_name_regex.append(re.compile(fname[j],re.IGNORECASE))
            last_name_regex.append(re.compile(lname[j],re.IGNORECASE))
        
        self.first_name_regex = first_name_regex
        self.last_name_regex = last_name_regex

        self.download_command_fmt = 'wget --no-check-certificate '
        self.download_command_fmt += '"'
        self.download_command_fmt += '%s'
        self.download_command_fmt += '"'
        self.download_command_fmt += ' --output-document='
        self.download_command_fmt += '%s'
        self.download_command_fmt += ' -o /dev/null'

        self.compile_results()
        self.local_tidy(self.output_file)

    def local_tidy(self,html_file):
        """Have to get rid of facebook:like tags before calling our general
        tidy routine.
        """
        #fp = open(html_file,'r',errors='ignore') 
        fp = open(html_file,'r')
        html = fp.read() 
        fp.close() 
        html = html.replace('fb:like','div') 
        #fp = open(html_file,'w',encoding='ascii') 
        fp = open(html_file,'w')
        fp.write(html) 
        fp.close()

        rr.common.local_tidy(html_file)

    def compile_results(self):
        """Either download the requested results or go through the
        provided list.
        """
        self.initialize_output_file()
        if self.race_list is None:
            self.compile_web_results()
        else:
            self.compile_local_results()

    def initialize_output_file(self):
        """Construct an HTML skeleton.
        """
        ofile = ET.Element('html')

        head = ET.SubElement(ofile, 'head')

        link = ET.SubElement(head, 'link')
        link.set('rel', 'stylesheet')
        link.set('href', 'rr.css')
        link.set('type', 'text/css')

        ET.SubElement(ofile, 'body')

        ET.ElementTree(ofile).write(self.output_file)

        rr.common.pretty_print_xml(self.output_file)

    def compile_web_results(self):
        """Download the requested results and compile them.
        """
        for state in self.states:
            self.download_state_master_file(state)
            self.process_state_master_file(state)

    def process_state_master_file(self, state):
        """Compile results for the specified state.
        We assume that we have the state file stored locally.
        """
        local_state_file = state + '.html'

        tree = ET.parse(local_state_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)

        # Set up patterns to locate the elements.
        trs = root.findall('.//body/div/div/div/table/tr/td/table/tr')

        # Set up the date pattern against which we
        # pick out the races.
        # The date pattern is [M]M/DD/YYYY
        if self.start_date.month < 10:
            date_pattern = self.start_date.strftime('%m')[1]
        else:
            date_pattern = self.start_date.strftime('%m')

        date_pattern += '/'
        date_pattern += '('
        date_pattern += str(self.start_date.day)
        for day in range(self.start_date.day + 1, self.stop_date.day + 1):
            date_pattern += '|'
            date_pattern += str(day)
        date_pattern += ')'
        date_pattern += '/'
        date_pattern += self.start_date.strftime('%Y')
        logging.debug('date pattern = %s' % date_pattern)

        for tr in trs:
            self.evaluate_row(state, tr, date_pattern)

    def evaluate_row(self, state, tr, date_pattern):
        """
        We have a row from the state file.  Figure
        out if there is anything useful in it.
        """
        tds = tr.findall('.//td')
        if len(tds) < 4:
            return

        # 3rd TD element has the date.
        if not re.search(date_pattern, tds[1].text):
            return

        # 4th TD element has the URL and race name.
        a_nodes = tds[2].findall('.//a')
        if len(a_nodes) == 0:
            return

        a = a_nodes[0]
        logging.debug('Downloading %s on %s' % (a.text, tds[1].text))

        url = self.base_url + '/' + a.get('href')
        output_file = '%s_event.html' % state

        download_command = 'wget --no-check-certificate '
        download_command += '"'
        download_command += url
        download_command += '"'
        download_command += ' --output-document='
        download_command += output_file
        download_command += ' -o /dev/null'
        logging.debug(download_command)
        os.system(download_command)
        self.process_event(output_file, state)

    def process_event(self, output_file, state):
        """
        We have a file that represents a single event within an
        overall event, kind of like evaluating the Philadelphia Marathon
        within the group of other events offered that day, like the Half
        Marathon and 8K.
        """
        # Look for the div/div/ul/li/a patterns
        rr.common.local_tidy(output_file)
        tree = ET.parse(output_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)

        pattern = './/body/div/div/table/tr/td/div/div'
        divs = root.findall(pattern)
        a_s = divs[0].findall('.//a')
        count = 0
        for anode in a_s:
            count += 1
            self.process_event_node(anode, state, count)

    def process_event_node(self, a_node, state, count):
        """
        We have a single event node within the overall event, kind of like
        evaluating the Philadelphia Marathon within the group of other
        events offered that day, like the Half Marathon and 8K.
        """
        href = a_node.get('href')
        if href is None:
            return
        if href[0:4] == 'http':
            # Only take relative urls.
            logging.debug('Discarding %s' % href)
            return
        race_file = '%s_%d_result.html' % (state, count)

        url = 'http://resultsarchive.active.com/pages/' + href
        logging.debug('Downloading event result at %s' % url)
        cmd = self.download_command_fmt % (url, race_file)
        self.downloaded_url = url
        logging.debug(cmd)
        os.system(cmd)
        self.local_tidy(race_file)

        # Need to see if there could be more files.
        root = ET.parse(race_file).getroot()
        root = rr.common.remove_namespace(root)
        pattern = './/body/div/div/div/div/div'
        divs = root.findall(pattern)
        if len(divs) < 8:
            logging.debug('Discarding %s, not ACTIVE format.' % href)
            return

        # Should be the 8th div
        # <div class="left">
        #     displaying: 1 - 656 of 656
        # </div>
        tokens = divs[7].text.rstrip().split(' ')
        num_runners = int(tokens[-1])

        # If the number of runners is greater than the
        # default (25), then re-retrieve the page with
        # that number of runners.
        if num_runners > 25:
            url += '&numPerPage=%d' % num_runners
            logging.debug('Downloading event result at %s' % url)
            cmd = self.download_command_fmt % (url, race_file)
            logging.debug(cmd)
            os.system(cmd)
            self.local_tidy(race_file)

        #self.comile_race_results(race_file)
        # body/div/div/div/table/tr
        root = ET.parse(race_file).getroot()
        root = rr.common.remove_namespace(root)
        pattern = './/body/div/div/div/table/tr'
        trs = root.findall(pattern)

        results = []
        for tr in trs[1:]:
            try:
                tds = tr.getchildren()
                fname_text = tds[1].getchildren()[0].getchildren()[0].text
                lname_text = tds[2].getchildren()[0].getchildren()[0].text
                for idx in range(0, len(self.first_name_regex)):
                    fregex = self.first_name_regex[idx]
                    lregex = self.last_name_regex[idx]
                    if fregex.search(fname_text) and lregex.search(lname_text):
                        tr = self.scrub_tr(tr)
                        results.append(tr)
            except IndexError:
                # This exception is thrown usually if the TD element is empty
                continue

        if len(results) > 0:
            # Insert the header.
            results.insert(0, self.scrub_tr(trs[0]))

            self.insert_race_results(results, race_file)

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

    def download_state_master_file(self, state):
        """
        Download results for the specified state.

        The URL will have the pattern

        [BASE_URL]/eventSearch.jsp?stateID=[ID]

        [BASE_URL]/eventSearch.jsp?fromDate=05%2F01%2F2012
             &toDate=05%2F24%2F2012&stateID=35&sportID=1
        """
        logging.debug('Processing %s...' % state)
        local_state_file = state + '.html'
        url = self.base_url + '/eventSearch.jsp'
        url += '?stateID=%s' % state_map[state]
        url += '&fromDate=%02d%%2F%02d%%2F%04d' % (self.start_date.month,
                self.start_date.day, self.start_date.year)
        url += '&toDate=%02d%%2F%02d%%2F%04d' % (self.stop_date.month, self.stop_date.day, self.stop_date.year)
        logging.debug('Downloading %s.' % url)

        download_command = 'wget --no-check-certificate '
        download_command += '"' + url + '"'
        download_command += ' --output-document='
        download_command += local_state_file
        download_command += ' -o /dev/null'
        logging.debug(download_command)
        os.system(download_command)
        self.local_tidy(local_state_file)

    def compile_local_results(self):
        """
        Compile results from list of local files.
        """
        for line in open(self.race_list):
            self.compile_race_results(line.rstrip())
