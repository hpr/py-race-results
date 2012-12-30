import logging
import xml.etree.cElementTree as ET

from . import common as rrcommon

class nyrr:
    """
    Handles race results from New York Road Runners website.
    """
    def __init__(self, **kwargs):
        """
        """
        self.start_date = None
        self.stop_date = None
        self.memb_list = None
        self.race_list = None
        self.output_file = None
        self.verbose = 'info'

        self.__dict__.update(**kwargs)

        # Need to remember the current URL.
        self.downloaded_url = None

        # Set the appropriate logging level.  Requires an exact
        # match of the level string value.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        """
        Collect race results.  Start from the results link on the main NYRR
        webpage.
        """
        self.process_master_page()
        self.process_events()

    def process_master_page(self):
        """
        This page has the URLs for the recent results.
        """
        import pdb; pdb.set_trace()
        url = 'http://web2.nyrrc.org/cgi-bin/start.cgi/aes-programs/results/resultsarchive.htm'
        rrcommon.download_file(url, 'index.html')

        # Parse out the list of "Most Recent Races"

    def process_events():
        """
        Go through the list of individual events.  All these events must have
        matched the input date range.
        """
        pass


