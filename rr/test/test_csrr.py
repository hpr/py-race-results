import datetime
import os
import pkg_resources
import tempfile
import unittest
import xml.etree.cElementTree as ET

import rr


class TestCompuscore(unittest.TestCase):
    """
    Test parsing results from Compuscore.
    """
    def setUp(self):
        self.membership_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.racelist_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.results_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

    def tearDown(self):
        os.unlink(self.membership_file)
        os.unlink(self.racelist_file)
        if os.path.exists(self.results_file):
            os.unlink(self.results_file)

    def populate_racelist_file(self):
        """
        Put a test race into a racelist file.
        """
        with open(self.racelist_file, 'w') as fp:
            filename = pkg_resources.resource_filename(
                    rr.__name__,
                    "test/testdata/redcross.htm")
            fp.write(filename)

    def populate_membership_file(self):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file, 'w') as fp:
            fp.write('FITZGERALD,ROBERT\n')
            fp.write('STEVENS,JOANNA\n')

    def test_racelist(self):
        self.populate_membership_file()
        self.populate_racelist_file()
        obj = rr.csrr(verbose='critical',
                start_date=datetime.datetime.now(),
                stop_date=datetime.datetime.now(),
                memb_list=self.membership_file,
                race_list=self.racelist_file,
                output_file=self.results_file)
        obj.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = obj.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("Robert Fitzgerald" in p[0].text)

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        self.populate_membership_file()
        obj = rr.csrr(verbose='critical',
                start_date=datetime.datetime(2012, 1, 1),
                stop_date=datetime.datetime(2012, 2, 28),
                memb_list=self.membership_file,
                output_file=self.results_file)
        obj.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = obj.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("Joanna Stevens" in p[0].text)


if __name__ == "__main__":
    unittest.main()
