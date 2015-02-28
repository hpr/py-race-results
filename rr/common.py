"""Parse race results.
"""
import datetime as dt
import logging
import re
import urllib
import xml.dom.minidom
import xml.etree.cElementTree as ET

from lxml import etree
import pandas as pd

logging.basicConfig()


class RaceResults:
    """
    Attributes
    ----------
    start_date, stop_date : datetime.datetime
        date range to restrict race searches
    memb_list:  membership list
    output_file : str
        All race results written to this file
    logger: handles verbosity of program execution.  All is logged to
            standard output.
    states : list
        List of states to search.  Not all subclasses use this.
    html : str
            HTML from downloaded web page
    user_agent:  masquerade as browser because some sites do not like
            "Python-urllib"
    downloaded_url:  URL to a race that has been downloaded.  We link back
            to it in the resulting output.
    """

    def __init__(self, verbose='INFO', membership_list=None,
                 start_date=dt.datetime.now() - dt.timedelta(days=7),
                 stop_date=dt.datetime.now(), states=None,
                 output_file=None):
        """
        Parameters
        ----------
        start_date, stop_date : datetime.datetime
            Specifies time range in which to search for race results.
        states : list
            List of states to search.  Not all subclasses use this.
        verbose : str
            Level of verbosity
        """
        self.start_date = start_date
        self.stop_date = stop_date
        self.output_file = output_file
        self.states = states

        # Set up a logger for relaying progress back to the user.
        self.logger = logging.getLogger('race_results')
        self.logger.setLevel(getattr(logging, verbose.upper()))

        if membership_list is not None:
            self.load_membership_list(membership_list)

        # This may be overridden by a subclass run time.
        self.downloaded_url = None

        # Not clear if this works or not.
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) "
        user_agent += "AppleWebKit/535.19 (KHTML, like Gecko) "
        user_agent += "Chrome/18.0.1025.45 "
        user_agent += "Safari/535.19"
        self.user_agent = user_agent

        self.html = None

    def match_against_membership(self, line):
        """
        We have a line of text from the race file.  Match it against the
        membership list.
        """
        for _, regex in self.df['fname_lname_regex'].iteritems():
            if regex.search(line):
                return(True)
        return(False)

    def load_membership_list(self, membership_file):
        """
        Construct regular expressions for each person in the membership list.

        Parameters
        ----------
        membership_list : str
            CSV or Excel spreadsheet file of club membership
        """
        df = pd.read_csv(membership_file)
        cols = [col.lower() for col in df]
        df.columns = cols

        df['fname_lname_regex'] = None
        for j in range(len(df)):
            # Use word boundaries to prevent false positives, e.g. "Ed Ford"
            # does not cause every fricking person from "New Bedford" to
            # match.  Here's an example line to match.
            #   '60 Gene Gugliotta       North Plainfiel,NJ 53 M U '
            # The first and last names must be separated by just white space.
            pattern = ('\\b(?:' + df['fname'][j]+ '|' + df['lname'][j] + ')'
                       + '\\s+(?:' + df['lname'][j] + '|' + df['fname'][j] + ')\\b')

            df['fname_lname_regex'][j] = re.compile(pattern, re.IGNORECASE)

        self.df = df

    def parse_membership_list(self, csv_file):
        """
        Assume a comma-delimited membership list, last name first,
        followed by the first name.

        Doe,Jane, ...
        Smith,Joe, ...

        Parameters
        ----------
        csv_file : str
            CSV file of membership
        """

        members = []
        with open(csv_file) as fptr:
            mlreader = csv.reader(fptr, delimiter=',')
            for row in mlreader:
                # members.append((lname, fname))
                members.append((row[0], row[1]))

        return members

    def run(self):
        """
        Either download the requested results or go through the
        provided list.
        """
        self.initialize_output_file()
        self.compile_web_results()

    def local_tidy(self, local_file=None):
        """
        Tidy up the HTML.
        """
        parser = etree.HTMLParser()
        tree = etree.parse(local_file, parser)
        root = tree.getroot()
        result = etree.tostring(root, pretty_print=True, method="html")
        with open(local_file, 'wb') as fptr:
            fptr.write(result)

    def insert_race_results(self, results):
        """
        Insert HTML-ized results into the output file.
        """
        parser = etree.HTMLParser()
        tree = etree.parse(self.output_file, parser)
        root = tree.getroot()
        body = root.findall('.//body')[0]
        body.append(results)

        result = etree.tostring(root, pretty_print=True, method="html")
        with open(self.output_file, 'wb') as fptr:
            fptr.write(result)
        self.local_tidy(local_file=self.output_file)

    def construct_source_url_reference(self, source):
        """
        Construct HTML that references the source of the race information.

        Parameters
        ----------
        source : str
            Name for web site from which the information comes, such as
            "CoolRunning" or "Compuscore".
        """
        p = etree.Element('p')
        span = etree.Element('span')
        span.text = 'Complete results '
        p.append(span)
        a = etree.Element('a')
        a.set('href', self.downloaded_url)
        a.text = 'here'
        p.append(a)
        span = etree.Element('span')
        span.text = ' on {0}.'.format(source)
        p.append(span)
        return p

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

    def initialize_output_file(self):
        """
        Construct a skeleton of the results of parsing race results from
        BestRace.

        <html>
            <head>
                <link href="rr.css" type="text/css" />
            </head>
            <body>
                STUFF TO GO HERE
            </body>
        </html>
        """
        ofile = ET.Element('html')
        head = ET.SubElement(ofile, 'head')
        link = ET.SubElement(head, 'link')
        link.set('rel', 'stylesheet')
        link.set('href', 'rr.css')
        link.set('type', 'text/css')
        ET.SubElement(ofile, 'body')
        ET.ElementTree(ofile).write(self.output_file)
        pretty_print_xml(self.output_file)


def pretty_print_xml(xml_file):
    """
    Taken from StackOverflow
    """
    xml_string = xml.dom.minidom.parse(xml_file)
    pp_string = xml_string.toprettyxml()
    fptr = open(xml_file, 'w')
    fptr.write(pp_string)
    fptr.close()
