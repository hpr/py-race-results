import datetime
import os
import pkg_resources
import tempfile
import time
import unittest
import xml.etree.cElementTree as ET

from rr import Active


class TestActive(unittest.TestCase):
    """
    Test parsing results from Active.
    """
    def setUp(self):
        self.membership_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.racelist_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.results_file = tempfile.NamedTemporaryFile(suffix=".html")

    def tearDown(self):
        self.membership_file.close()
        self.racelist_file.close()
        self.results_file.close()

    def populate_membership_file(self, membership_list):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file.name, 'w') as fp:
            fp.writelines(membership_list)
            fp.flush()

    def test_web_csv_download(self):
        """
        Verify that we can get CSV results from the web.
        """
        self.populate_membership_file(['KENNEDY,JASON'])
        start_date = datetime.date(2013, 1, 1)
        stop_date = datetime.date(2013, 1, 31)
        o = Active(verbose='critical',
                   output_file=self.results_file.name,
                   location="New Brunswick, NJ",
                   radius="100",
                   memb_list=self.membership_file.name,
                   start_date=start_date,
                   stop_date=stop_date)
        o.run()
        tree = ET.parse(self.results_file.name)
        root = tree.getroot()
        root = o.remove_namespace(root)

        # This should find four divs.  Two are the top-level "race" divs,
        # the other two are interior "provenance" div.
        divs = root.findall('.//div[@class]')
        self.assertEqual(len(divs), 4)
        self.assertEqual(divs[0].get('class'), 'race')
        self.assertEqual(divs[1].get('class'), 'provenance')
        self.assertEqual(divs[2].get('class'), 'race')
        self.assertEqual(divs[3].get('class'), 'provenance')

    def test_raw_file_download(self):
        """
        Verify that we get results that are embedded raw.
        """
        self.populate_membership_file(['HIMBERGER,PAUL'])
        start_date = datetime.date(2012, 12, 2)
        stop_date = datetime.date(2012, 12, 2)
        o = Active(verbose='critical',
                   output_file=self.results_file.name,
                   memb_list=self.membership_file.name,
                   location="Boston, MA",
                   radius="100",
                   start_date=start_date,
                   stop_date=stop_date)
        o.run()
        tree = ET.parse(self.results_file.name)
        root = tree.getroot()
        root = o.remove_namespace(root)

        # This should find two divs.  One is the top-level "race" div,
        # the other is an interior "provenance" div.
        divs = root.findall('.//div[@class]')
        self.assertEqual(len(divs), 2)
        self.assertEqual(divs[0].get('class'), 'race')
        self.assertEqual(divs[1].get('class'), 'provenance')

        # Verify that we got the member result correct.
        pre = root.findall('.//pre')
        self.assertTrue("HIMBERGER" in pre[0].text)


if __name__ == "__main__":
    unittest.main()
