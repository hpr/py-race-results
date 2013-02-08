import datetime
import os
import tempfile
import unittest

from bs4 import BeautifulSoup

import rr


class TestNYRR(unittest.TestCase):

    def setUp(self):
        self.results_file = tempfile.NamedTemporaryFile(suffix=".txt")

    def tearDown(self):
        pass

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        start_date = datetime.date(2012, 12, 14)
        stop_date = datetime.date(2012, 12, 15)
        o = rr.NewYorkRR(verbose='critical',
                         output_file=self.results_file.name,
                         team='RARI',
                         start_date=start_date,
                         stop_date=stop_date)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("Petit" in
                            soup.div.table.contents[3].contents[1].contents[0])
            self.assertTrue("Ron" in
                            soup.div.table.contents[3].contents[3].contents[0])


if __name__ == "__main__":
    unittest.main()
