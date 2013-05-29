import datetime
import os
import pkg_resources
import re
import shutil
import tempfile
import unittest

from bs4 import BeautifulSoup

import rr


class TestBestRace(unittest.TestCase):
    """
    Test parsing results from BestRace.
    """
    def setUp(self):

        # Make copies of the test files as fixtures.
        self.viking_race_file = tempfile.NamedTemporaryFile(suffix=".htm")
        relfile = "test/testdata/121202SB5.HTM"
        filename = pkg_resources.resource_filename(rr.__name__, relfile)
        shutil.copyfile(filename, self.viking_race_file.name)

        # Create other fixtures that are easy to clean up later.
        self.membership_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.racelist_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.results_file = tempfile.NamedTemporaryFile(suffix=".txt")

    def tearDown(self):
        # Remove other test fixtures.
        self.membership_file.close()
        self.racelist_file.close()
        self.viking_race_file.close()
        self.results_file.close()

    def populate_racelist_file(self, races):
        """
        Put a test race into a racelist file.
        """
        with open(self.racelist_file.name, 'w') as fp:
            for race_file in races:
                fp.write(race_file + '\n')
            fp.flush()

    def populate_membership_file(self):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file.name, 'w') as fp:
            fp.write('STRAWN,MARK\n')
            fp.write('CARR,MICHAEL\n')
            fp.flush()

    def test_racelist(self):
        self.populate_membership_file()
        lst = [self.viking_race_file.name, self.viking_race_file.name]
        self.populate_racelist_file(lst)
        o = rr.BestRace(verbose='critical',
                        memb_list=self.membership_file.name,
                        race_list=self.racelist_file.name,
                        output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("MICHAEL CARR" in soup.div.pre.contents[0])
            self.assertTrue("MARK STRAWN" in soup.div.pre.contents[0])

    def test_consecutive_newlines(self):
        """
        Verify that we don't get two consecutive newlines in the 
        race results, which makes them look bad.

        See Issue 33
        """
        self.populate_membership_file()
        lst = [self.viking_race_file.name, self.viking_race_file.name]
        self.populate_racelist_file(lst)
        o = rr.BestRace(verbose='critical',
                        memb_list=self.membership_file.name,
                        race_list=self.racelist_file.name,
                        output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            text = soup.pre.contents[0]

            # Ok, first we need to jump over the banner, because that 
            # does have consecutive newlines.  
            start = re.search('MICHAEL', text).start()
            m = re.search('\n\n', text[start:])
            self.assertIsNone(m)

    def test_web_download(self):
        """
        Verify that we can get results from BestRace.com.
        """
        self.populate_membership_file()
        start_date = datetime.datetime(2012, 12, 9)
        stop_date = datetime.datetime(2012, 12, 10)
        o = rr.BestRace(verbose='critical',
                        memb_list=self.membership_file.name,
                        output_file=self.results_file.name,
                        start_date=start_date,
                        stop_date=stop_date)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("MARK STRAWN" in soup.div.pre.contents[0])


if __name__ == "__main__":
    unittest.main()
