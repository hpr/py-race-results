import collections
import csv
import logging
import tidy
import urllib2
import xml.dom.minidom


class RaceResults:
    """
    Attributes:
        start_date, stop_date:  date range to restrict race searches
        memb_list:  membership list
        race_list:  file containing list of races
        output_file:  final race results file
        verbose:  how much output to produce
        logger: handles verbosity of program execution
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

    def parse_membership_list(self):
        """
        Assume a comma-delimited membership list, last name first,
        followed by the first name.

        Doe,Jane, ...
        Smith,Joe, ...
        """

        mlreader = csv.reader(open(self.memb_list, 'r'))
        first_name = []
        first_name_regex = []
        last_name = []
        last_name_regex = []
        for row in mlreader:
            fname = row[0]
            lname = row[1]
            first_name.append(fname)
            last_name.append(lname)

        FirstLast = collections.namedtuple('FirstLastName', ['first', 'last'])
        names = FirstLast(first=first_name, last=last_name)
        return names

    def local_tidy(self, html_file):
        """
        Tidy up the HTML.
        """
        options = dict(output_xhtml=1,
                add_xml_decl=1,
                indent=1,
                numeric_entities=True,
                drop_proprietary_attributes=True,
                bare=True,
                word_2000=True,
                tidy_mark=1,
                hide_comments=True,
                new_inline_tags='fb:like')
        fp = open(html_file)
        html = fp.read()
        fp.close()
        thtml = tidy.parseString(html, **options)

        fp = open(html_file, 'w')
        thtml.write(fp)
        fp.close()

    def pretty_print_xml(self, xml_file):
        """
        Taken from StackOverflow
        """
        xml_string = xml.dom.minidom.parse(xml_file)
        pp_string = xml_string.toprettyxml()
        fp = open(xml_file, 'w')
        fp.write(pp_string)
        fp.close()

    def remove_namespace(self, doc):
        """Remove namespace in the passed document in place."""
        # We seem to need this for all element searches now.
        xmlns = 'http://www.w3.org/1999/xhtml'

        namespace = '{%s}' % xmlns
        nsl = len(namespace)
        for elem in doc.getiterator():
            if elem.tag.startswith(namespace):
                elem.tag = elem.tag[nsl:]

        return(doc)

    def download_file(self, url, local_file):
        """
        Download a URL to a local file.
        """
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) "
        user_agent += "AppleWebKit/535.19 (KHTML, like Gecko) "
        user_agent += "Chrome/18.0.1025.45 "
        user_agent += "Safari/535.19"
        headers = {'User-Agent': user_agent}
        with open(local_file, 'wb') as f:
            req = urllib2.Request(url, None, headers)
            response = urllib2.urlopen(req)
            html = response.read()
            f.write(html)
            f.close()
