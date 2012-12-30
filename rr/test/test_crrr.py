import datetime
import os
import pkg_resources
import shutil
import tempfile
import unittest
import xml.etree.cElementTree as ET

import rr


class TestCoolRunning(unittest.TestCase):
    """
    Test parsing results from CoolRunning.
    """
    def setUp(self):

        # Make copies of the test files as fixtures BEFORE we change into a
        # scratch directory.

        # This test file is a regular, run-of-the-mill results
        # file typical of those uploaded to CoolRunning.
        self.vanilla_crrr_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".shtml").name
        filename = pkg_resources.resource_filename(
                    rr.__name__,
                    "test/testdata/Nov24_3rdAnn_set1.shtml")
        shutil.copyfile(filename, self.vanilla_crrr_file)

        # This file has an XHTML format commonly used when the
        # Cape Cod Road Runners report a result.
        self.ccrr_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".shtml").name
        filename = pkg_resources.resource_filename(rr.__name__,
                "test/testdata/Jan8_CapeCo_set1.shtml")
        shutil.copyfile(filename, self.ccrr_file)

        # We should do all our testing in a temporary directory.
        self.old_directory = os.getcwd()
        self.scratch_directory = tempfile.mkdtemp()
        os.chdir(self.scratch_directory)

        # Create other fixtures that are easy to clean up later.
        self.membership_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.racelist_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.results_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.populate_membership_file()

    def tearDown(self):

        # Remove the scratch work directory.
        os.chdir(self.old_directory)
        shutil.rmtree(self.scratch_directory)

        os.unlink(self.membership_file)
        os.unlink(self.racelist_file)
        os.unlink(self.vanilla_crrr_file)
        os.unlink(self.ccrr_file)
        if os.path.exists(self.results_file):
            os.unlink(self.results_file)

    def populate_racelist_file(self, race_files):
        """
        Put a test race into a racelist file.
        """
        with open(self.racelist_file, 'w') as fp:
            for race_file in race_files:
                fp.write(race_file)

    def populate_membership_file(self):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file, 'w') as fp:
            fp.write('CALEB,GARTNER\n')
            fp.write('SEAN,SPALDING\n')
            fp.write('JOHN,BANNER\n')
            fp.write('MIKE,NORTON\n')

    def test_racelist(self):
        """
        Test compiling race results from a list of local files.
        """
        self.populate_racelist_file([self.vanilla_crrr_file])
        o = rr.crrr(verbose='critical',
                memb_list=self.membership_file,
                race_list=self.racelist_file,
                output_file=self.results_file)
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        NS = 'http://www.w3.org/1999/xhtml'
        p = root.findall('.//{%s}div/{%s}pre' % (NS, NS))
        self.assertTrue("Caleb Gartner" in p[0].text)
        self.assertTrue("Sean Spalding" in p[0].text)

    def test_cape_cod_road_runners(self):
        """
        Test compiling race results from a list of local files.
        The HTML profile is used by Cape Cod Road Runners.
        """
        self.populate_racelist_file([self.ccrr_file])
        o = rr.crrr(verbose='critical',
                memb_list=self.membership_file,
                race_list=self.racelist_file,
                output_file=self.results_file)
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = o.remove_namespace(root)

        # Mike Northon shows up in the 2nd TR row (the first
        # real result).
        p = root.findall('.//div/table/tr/td')
        self.assertTrue("MIKE NORTON" in p[12].text)

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        start_date = datetime.datetime(2012, 12, 9)
        stop_date = datetime.datetime(2012, 12, 10)
        o = rr.crrr(verbose='critical',
                memb_list=self.membership_file,
                output_file=self.results_file,
                start_date=start_date,
                stop_date=stop_date)
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = o.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("John Banner" in p[0].text)


if __name__ == "__main__":
    unittest.main()
