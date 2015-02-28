"""Parse race results.
"""
import datetime as dt
import logging
import re

from lxml import etree
import pandas as pd

logging.basicConfig()


class RaceResults:
    """
    Attributes
    ----------
    start_date, stop_date : datetime.datetime
        date range to restrict race searches
    df : pandas dataframe
        contains membership list information, including regular expressions
    output_file : str
        All race results written to this file
    logger : logging.logger
        Handles verbosity of program execution.  All is logged
        to standard output.
    states : list
        List of states to search.  Not all subclasses use this.
    html : str
        HTML from downloaded web page
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
        membership_list : str
            Path to membership list.  CSV files and excel files are supported.
        output_file : str
            Path to output file of race results.
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
        Load the membership file.

        In addition, construct regular expressions for each member that we use
        to search for race results.

        Parameters
        ----------
        membership_list : str
            CSV or Excel spreadsheet file of club membership
        """
        try:
            df = pd.read_csv(membership_file)
        except:
            df = pd.read_excel(membership_file)
        cols = [col.lower() for col in df]
        df.columns = cols

        if 'fname' not in df.columns and 'lname' not in df.columns:
            msg = 'The membership file must have both "FName" and '
            msg += '"LName" columns (first name and last name).'
            raise RuntimeError(msg)

        df['fname_lname_regex'] = None
        for j in range(len(df)):
            # Use word boundaries to prevent false positives, e.g. "Ed Ford"
            # does not cause every fricking person from "New Bedford" to
            # match.  Here's an example line to match.
            #   '60 Gene Gugliotta       North Plainfiel,NJ 53 M U '
            # The first and last names must be separated by just white space.
            pattern = ('\\b(?:' +
                       df['fname'][j] + '|' + df['lname'][j] + ')' +
                       '\\s+(?:'
                       + df['lname'][j] + '|' + df['fname'][j] + ')\\b')

            df['fname_lname_regex'][j] = re.compile(pattern, re.IGNORECASE)

        self.df = df

    def run(self):
        """
        Either download the requested results or go through the
        provided list.
        """
        self.initialize_output_file()
        self.compile_web_results()

    def insert_race_results(self, results):
        """
        Insert HTML-ized results into the output file.
        """
        parser = etree.HTMLParser()
        tree = etree.parse(self.output_file, parser)
        root = tree.getroot()
        body = root.findall('.//body')[0]
        body.append(results)

        result = etree.tostring(root, pretty_print=True, method="html",
                                encoding='unicode')
        result = result.replace('\r', '\n')
        with open(self.output_file, 'w') as fptr:
            fptr.write(result)

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
        ofile = etree.Element('html')
        head = etree.SubElement(ofile, 'head')
        link = etree.SubElement(head, 'link')
        link.set('rel', 'stylesheet')
        link.set('href', 'rr.css')
        link.set('type', 'text/css')
        etree.SubElement(ofile, 'body')
        etree.ElementTree(ofile).write(self.output_file, pretty_print=True)
