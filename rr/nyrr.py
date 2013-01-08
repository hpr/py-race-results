import logging
import os
import xml.etree.cElementTree as ET

from .common import RaceResults


class NewYorkRR(RaceResults):
    """
    Handles race results from New York Road Runners website.
    """
    def __init__(self, **kwargs):
        """
        """
        RaceResults.__init__(self)
        self.__dict__.update(**kwargs)

        # Need to remember the current URL.
        self.downloaded_url = None

        # Set the appropriate logging level.
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        """
        Collect race results.  Start from the results link on the main NYRR
        webpage.
        """
        self.process_master_page()
        self.process_events()

    def download_file(self, url, localfile):
        """
        Override the usual URL download, as URLLIB2 seems to fail.  
        """
        fmt = 'wget "%s" --output-document %s -o /dev/null'
        cmd = fmt % (url, localfile)
        os.system(cmd)
        pass

    def process_master_page(self):
        """
        This page has the URLs for the recent results.
        """
        url = 'http://web2.nyrrc.org'
        url += '/cgi-bin/start.cgi/aes-programs/results/resultsarchive.htm'
        self.download_file(url, 'resultsarchive.html')
        import pdb; pdb.set_trace()
        self.local_tidy('resultsarchive.html')

        # Parse out the list of "Most Recent Races"

    def process_events():
        """
        Go through the list of individual events.  All these events must have
        matched the input date range.
        """
        pass
