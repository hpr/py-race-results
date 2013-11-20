"""Parse race results.
"""
import copy
import codecs
import csv
import logging
import xml.dom.minidom
import xml.etree.cElementTree as ET

from bs4 import BeautifulSoup
import requests


class RaceResults:
    """
    Attributes:
        start_date, stop_date:  date range to restrict race searches
        memb_list:  membership list
        race_list:  file containing list of race files
        output_file:  final race results file
        verbose:  how much output to produce
        logger: handles verbosity of program execution.  All is logged to
            standard output.
        cookies : NYRR requires cookies
        html : str
            HTML from downloaded web page
        user_agent:  masquerade as browser because some sites do not like
            "Python-urllib"
        downloaded_url:  URL to a race that has been downloaded.  We link back
            to it in the resulting output.
    """

    def __init__(self):
        # These attributes could/should be overridden by a subclass
        # initialization.
        self.start_date = None
        self.stop_date = None
        self.memb_list = None
        self.race_list = None
        self.output_file = None
        self.verbose = 'info'

        # Set up a logger for relaying progress back to the user.
        self.logger = logging.getLogger('race_results')

        # This may be overridden by a subclass run time.
        self.downloaded_url = None

        # Not clear if this works or not.
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) "
        user_agent += "AppleWebKit/535.19 (KHTML, like Gecko) "
        user_agent += "Chrome/18.0.1025.45 "
        user_agent += "Safari/535.19"
        self.user_agent = user_agent

        self.html = None
        self.cookies = None

    def parse_membership_list(self):
        """
        Assume a comma-delimited membership list, last name first,
        followed by the first name.

        Doe,Jane, ...
        Smith,Joe, ...
        """

        members = []
        with open(self.memb_list) as csvfile:
            mlreader = csv.reader(csvfile, delimiter=',')
            first_name = []
            last_name = []
            for row in mlreader:
                # members.append((lname, fname))
                members.append((row[0], row[1]))

        return members

    def local_tidy(self, local_file=None):
        """
        Tidy up the HTML.
        """
        if local_file is None:
            html = self.html
        else:
            with open(local_file, encoding='utf-8') as fptr:
                html = fptr.read()
        soup = BeautifulSoup(html, "html.parser")

        if local_file is None:
            self.html = soup.prettify()
        else:
            fptr = codecs.open(local_file, encoding='utf-8', mode='w')
            fptr.write(soup.prettify())
            fptr.close()

    def download_file(self, url, params=None, local_file=None):
        """
        Download a URL.

        Parameters
        ----------
        url : The URL to retrieve
        params : POST parameters to supply
        """

        headers = {'User-Agent': self.user_agent}
        if params is None:
            request = requests.get(url, headers=headers)
        else:
            kwargs = {'headers': headers}
            kwargs['params'] = params
            if self.cookies is not None:
                kwargs['cookies'] = self.cookies
            request = requests.post(url, **kwargs)

        # Save any cookies for the next download.
        self.cookies = copy.deepcopy(request.cookies)

        if local_file is not None:
            with open(local_file, 'w') as fptr:
                fptr.write(request.text)
        else:
            self.html = request.text
        request.close()

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

    def insert_race_results(self, results):
        """
        Insert HTML-ized results into the output file.
        """
        tree = ET.parse(self.output_file)
        root = tree.getroot()
        root = remove_namespace(root)
        body = root.findall('.//body')[0]
        body.append(results)
        ET.ElementTree(root).write(self.output_file)
        self.local_tidy(local_file=self.output_file)


def pretty_print_xml(xml_file):
    """
    Taken from StackOverflow
    """
    xml_string = xml.dom.minidom.parse(xml_file)
    pp_string = xml_string.toprettyxml()
    fptr = open(xml_file, 'w')
    fptr.write(pp_string)
    fptr.close()


def remove_namespace(doc):
    """Remove namespace in the passed document in place."""
    # We seem to need this for all element searches now.
    xmlns = 'http://www.w3.org/1999/xhtml'

    namespace = '{%s}' % xmlns
    nsl = len(namespace)
    for elem in doc.getiterator():
        if elem.tag.startswith(namespace):
            elem.tag = elem.tag[nsl:]

    return(doc)
