import datetime
import os
import pkg_resources
import tempfile
import unittest
import xml.etree.cElementTree as ET

from rr import Active


@unittest.skip('Does not download all results')
class TestActive(unittest.TestCase):
    """
    Test parsing results from Active.
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

    def populate_membership_file(self):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file, 'w') as fp:
            fp.write('STRAWN,MARK\n')
            fp.write('CARR,MICHAEL\n')

    def test_racelist(self):
        self.assertTrue(False)
        self.populate_membership_file()
        self.populate_racelist_file()
        o = rr.brrr(verbose='critical',
                memb_list=self.membership_file,
                race_list=self.racelist_file,
                output_file=self.results_file)
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("MICHAEL CARR" in p[0].text)
        self.assertTrue("MARK STRAWN" in p[0].text)

    def test_bad_location(self):
        """
        Test an invalid location, such as "Boston, ZZ"
        """
        self.assertTrue(False)

    def test_web_download(self):
        """
        Verify that we can get results from active.com.
        """
        self.populate_membership_file()
        start_date = datetime.datetime(2010, 7, 10)
        stop_date = datetime.datetime(2010, 7, 10)
        o = Active(verbose='critical',
                memb_list=self.membership_file,
                output_file=self.results_file,
                start_date=start_date,
                stop_date=stop_date,
                radius=100,
                location='New Brunswick, NJ')
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("MARK STRAWN" in p[0].text)


if __name__ == "__main__":
    unittest.main()
