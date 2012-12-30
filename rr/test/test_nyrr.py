import datetime
import tempfile
import unittest

import rr

@unittest.skip("Cannot connect.")
class TestNYRR(unittest.TestCase):

    def setUp(self):
        self.membership_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.racelist_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.results_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name
        self.populate_membership_file()

    def tearDown(self):
        pass

    def populate_membership_file(self):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file,'w') as fp:
            fp.write('SCHEID,JUSTIN\n')

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        start_date = datetime.datetime(2012,12,14)
        stop_date = datetime.datetime(2012,12,15)
        o = rr.nyrr(verbose='critical',
                memb_list=self.membership_file,
                output_file=self.results_file,
                start_date=start_date,
                stop_date=stop_date)
        o.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = rr.common.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("Justin Scheid" in p[0].text)


if __name__ == "__main__":
    unittest.main()

