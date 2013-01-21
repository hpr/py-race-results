import datetime
import os
import tempfile
import unittest
import xml.etree.cElementTree as ET

import rr


class TestNYRR(unittest.TestCase):

    def setUp(self):
        self.membership_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.results_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

    def tearDown(self):
        os.remove(self.membership_file)
        os.remove(self.results_file)

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        start_date = datetime.date(2012, 12, 14)
        stop_date = datetime.date(2012, 12, 15)
        o = rr.NewYorkRR(verbose='critical',
                output_file=self.results_file,
                team='RARI',
                start_date=start_date,
                stop_date=stop_date)
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = o.remove_namespace(root)

        # This should find two divs.  One is the top-level "race" div, the 2nd
        # is an interior "provenance" div.
        divs = root.findall('.//div[@class]')
        self.assertEqual(len(divs), 2)
        self.assertEqual(divs[0].get('class'), 'race')
        self.assertEqual(divs[1].get('class'), 'provenance')


if __name__ == "__main__":
    unittest.main()
