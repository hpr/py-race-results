import datetime
import os
import pkg_resources
import shutil
import tempfile
import unittest
import xml.etree.cElementTree as ET

import rr


class TestCompuscore(unittest.TestCase):
    """
    Test parsing results from Compuscore.
    """
    def setUp(self):

        # Make a copy of this test file, and we need to do it before
        # changing directories.
        self.redcross_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".htm").name
        filename = pkg_resources.resource_filename(
                rr.__name__, "test/testdata/redcross.htm")
        shutil.copyfile(filename, self.redcross_file)

        # We should do all our testing in a temporary directory.
        self.old_directory = os.getcwd()
        self.scratch_directory = tempfile.mkdtemp()
        os.chdir(self.scratch_directory)

        # Write test version of the membership file.
        self.membership_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

        # We need a file to use for a list of race files.
        self.racelist_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

        # We need a file to use for writing race results.
        self.results_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

    def tearDown(self):

        # Remove the scratch work directory.
        os.chdir(self.old_directory)
        shutil.rmtree(self.scratch_directory)

        # Remove all the other temporary files.
        os.unlink(self.membership_file)
        os.unlink(self.racelist_file)
        os.unlink(self.redcross_file)
        if os.path.exists(self.results_file):
            os.unlink(self.results_file)

    def populate_racelist_file(self, race_files):
        """
        Put test races into a racelist file.
        """
        with open(self.racelist_file, 'w') as fp:
            for race_file in race_files:
                fp.write(race_file)

    def populate_membership_file(self):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file, 'w') as fp:
            fp.write('FITZGERALD,ROBERT\n')
            fp.write('STEVENS,JOANNA\n')

    def test_racelist(self):
        """
        Verify that we can correctly parse race results when given a list of
        race files.
        """
        self.populate_membership_file()
        self.populate_racelist_file([self.redcross_file])
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
