import datetime
import os
import pkg_resources
import shutil
import tempfile
import unittest
import xml.etree.cElementTree as ET

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
                fp.write(race_file)
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
        self.populate_racelist_file([self.viking_race_file.name])
        o = rr.BestRace(verbose='critical',
                        memb_list=self.membership_file.name,
                        race_list=self.racelist_file.name,
                        output_file=self.results_file.name)
        o.run()
        tree = ET.parse(self.results_file.name)
        root = tree.getroot()
        p = root.findall('.//div/pre')
        self.assertTrue("MICHAEL CARR" in p[0].text)
        self.assertTrue("MARK STRAWN" in p[0].text)

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
        root = ET.parse(self.results_file).getroot()
        p = root.findall('.//div/pre')
        self.assertTrue("MARK STRAWN" in p[0].text)


if __name__ == "__main__":
    unittest.main()
