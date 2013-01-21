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

        # Make test data files into fixtures.  We need to do it before
        # changing directories.
        self.redcross_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".htm").name
        filename = pkg_resources.resource_filename(
                rr.__name__, "test/testdata/redcross.htm")
        shutil.copyfile(filename, self.redcross_file)

        self.xc_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".htm").name
        filename = pkg_resources.resource_filename(
                rr.__name__, "test/testdata/joxc.htm")
        shutil.copyfile(filename, self.xc_file)

        # Write test version of the membership file.
        self.membership_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

        # We need a file to use for a list of race files.
        self.racelist_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

        # We need a file to use for writing race results.
        self.results_file = tempfile.NamedTemporaryFile(delete=False,
                suffix=".txt").name

        # Generic membership list
        self.membership_list = ['FITZGERALD,ROBERT\n', 'STEVENS,JOANNA\n']
        self.joxc_membership_list = ['FOSTER,BILLY\n', 'FOSTER,JAIME\n']

    def tearDown(self):

        # Remove all the other temporary files.
        os.unlink(self.membership_file)
        os.unlink(self.racelist_file)
        os.unlink(self.redcross_file)
        os.unlink(self.xc_file)
        if os.path.exists(self.results_file):
            os.unlink(self.results_file)

    def populate_racelist_file(self, race_files):
        """
        Put test races into a racelist file.
        """
        with open(self.racelist_file, 'w') as fp:
            for race_file in race_files:
                fp.write(race_file)

    def populate_membership_file(self, membership_list):
        """
        Put some names into a faux membership file.
        """
        with open(self.membership_file, 'w') as fp:
            fp.writelines(membership_list)

    def test_racelist(self):
        """
        Verify that we can correctly parse race results when given a list of
        race files.
        """
        self.populate_membership_file(self.membership_list)
        self.populate_racelist_file([self.redcross_file])
        obj = rr.CompuScore(verbose='critical',
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

    @unittest.skip("Must await CompuScore refactoring.")
    def test_xcountry_banner(self):
        """
        Verify that our output file has the correct banner.  The race file is
        produced by USATF-NJ Junior Olympics.
        """
        self.populate_membership_file(self.joxc_membership_list)
        self.populate_racelist_file([self.xc_file])
        obj = rr.CompuScore(verbose='critical',
                memb_list=self.membership_file,
                race_list=self.racelist_file,
                output_file=self.results_file)
        obj.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()

        # The organization of the race result should be
        #
        # <body>
        #   <div>
        #     <hr/>
        #     <h1> blah </h1>
        #     <p class="provenance>  </p>
        #     <div class="banner>  </div>
        #     <pre class="actual_results>  </pre>
        #   </div>
        # </body>
        #
        root = obj.remove_namespace(root)
        div = root.findall('.//div/div')
        self.assertEqual(len(div), 1)
        self.assertEqual(div[0].get('class'), 'banner')

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        self.populate_membership_file(self.membership_list)
        obj = rr.CompuScore(verbose='critical',
                start_date=datetime.date(2012, 1, 1),
                stop_date=datetime.date(2012, 2, 28),
                memb_list=self.membership_file,
                output_file=self.results_file)
        obj.run()
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = obj.remove_namespace(root)
        p = root.findall('.//div/pre')
        self.assertTrue("Joanna Stevens" in p[0].text)

    def test_empty_results_because_of_date(self):
        """
        Verify that if there are no results in the given date range, the output
        file will have no results.

        This is issue 15.

        Billy Foster is in results for the 1st, in the CJRRC Hangover 5K Run.
        """
        self.populate_membership_file(['FOSTER,BILLY\n'])
        obj = rr.CompuScore(verbose='critical',
                start_date=datetime.date(2013, 1, 2),
                stop_date=datetime.date(2013, 1, 2),
                memb_list=self.membership_file,
                output_file=self.results_file)
        obj.run()

        # "no results" means that the body of the output file is empty.
        tree = ET.parse(self.results_file)
        root = tree.getroot()
        root = obj.remove_namespace(root)
        body = root.findall('.//body')
        self.assertEqual(len(body[0].getchildren()), 0)


if __name__ == "__main__":
    unittest.main()
