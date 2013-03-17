import datetime
import os
import pkg_resources
import shutil
import tempfile
import unittest

from bs4 import BeautifulSoup

import rr


class TestCoolRunning(unittest.TestCase):
    """
    Test parsing results from CoolRunning.
    """
    def setUp(self):

        # This test file is a regular, run-of-the-mill results
        # file typical of those uploaded to CoolRunning.
        self.vanilla_crrr_file = tempfile.NamedTemporaryFile(suffix=".shtml")
        relfile = "test/testdata/Nov24_3rdAnn_set1.shtml"
        filename = pkg_resources.resource_filename(rr.__name__, relfile)
        shutil.copyfile(filename, self.vanilla_crrr_file.name)

        # This file has an XHTML format commonly used when the
        # Cape Cod Road Runners report a result.
        self.ccrr_file = tempfile.NamedTemporaryFile(suffix=".shtml")
        relfile = "test/testdata/Jan6_CapeCo_set1.shtml"
        filename = pkg_resources.resource_filename(rr.__name__, relfile)
        shutil.copyfile(filename, self.ccrr_file.name)

        # This file format (used by Colonial Road Runners) has IE-specific
        # elements that TIDY does not properly string.
        self.colonialrr_file = tempfile.NamedTemporaryFile(suffix=".shtml")
        relfile = "test/testdata/Dec30_Coloni_set1.shtml"
        filename = pkg_resources.resource_filename(rr.__name__, relfile)
        shutil.copyfile(filename, self.colonialrr_file.name)

        # This file isn't parseable by ElementTree.
        self.black_cat_file = tempfile.NamedTemporaryFile(suffix=".shtml")
        relfile = "test/testdata/Mar2_BlackC_set1.shtml"
        filename = pkg_resources.resource_filename(rr.__name__, relfile)
        shutil.copyfile(filename, self.black_cat_file.name)

        # This file isn't parseable by ElementTree.
        self.ras_na_eireann_file = tempfile.NamedTemporaryFile(suffix=".shtml")
        relfile = "test/testdata/Mar10_Rasnah_set1.shtml"
        filename = pkg_resources.resource_filename(rr.__name__, relfile)
        shutil.copyfile(filename, self.ras_na_eireann_file.name)

        # Create other fixtures that are easy to clean up later.
        self.membership_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.racelist_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.results_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.populate_membership_file()

    def tearDown(self):
        self.membership_file.close()
        self.racelist_file.close()
        self.vanilla_crrr_file.close()
        self.ccrr_file.close()
        self.results_file.close()

    def populate_membership_file(self, lst=None):
        """
        Put some names into a faux membership file.
        """
        if lst is None:
            with open(self.membership_file.name, 'w') as fp:
                fp.write('GARTNER,CALEB\n')
                fp.write('SPALDING,SEAN\n')
                fp.write('BANNER,JOHN\n')
                fp.write('NORTON,MIKE\n')
                fp.flush()
        else:
            with open(self.membership_file.name, 'w') as fp:
                for name_line in lst:
                    fp.write(name_line)

    def populate_racelist_file(self, race_files):
        """
        Put a test race into a racelist file.
        """
        with open(self.racelist_file.name, 'w') as fp:
            for racefile in race_files:
                fp.write(racefile + '\n')
            fp.flush()

    def test_racelist(self):
        """
        Test compiling race results from a list of local files (just one).
        """
        self.populate_racelist_file([self.vanilla_crrr_file.name])
        o = rr.CoolRunning(verbose='critical',
                           memb_list=self.membership_file.name,
                           race_list=self.racelist_file.name,
                           output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("Caleb Gartner" in soup.div.pre.contents[0])
            self.assertTrue("Sean Spalding" in soup.div.pre.contents[0])

    def test_multiple_racelist(self):
        """
        Test compiling race results from a list of local files.
        """
        racelist = [self.vanilla_crrr_file.name, self.ccrr_file.name]
        self.populate_racelist_file(racelist)
        o = rr.CoolRunning(verbose='critical',
                           memb_list=self.membership_file.name,
                           race_list=self.racelist_file.name,
                           output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("Caleb Gartner" in soup.div.pre.contents[0])
            self.assertTrue("Sean Spalding" in soup.div.pre.contents[0])

    def test_cape_cod_road_runners(self):
        """
        Test compiling race results from a list of local files.
        The HTML profile is used by Cape Cod Road Runners.
        """
        self.populate_racelist_file([self.ccrr_file.name])
        o = rr.CoolRunning(verbose='critical',
                           memb_list=self.membership_file.name,
                           race_list=self.racelist_file.name,
                           output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("MIKE NORTON" in
                            soup.div.table.contents[3].contents[3].contents[0])

    def test_misaligned_columns(self):
        """
        TIDY will not properly strip some IE-specific elements such as

        <![if supportMisalignedColumns]>
        <![endif]>

        It needs to be stripped out.
        """
        self.populate_racelist_file([self.colonialrr_file.name])
        o = rr.CoolRunning()
        o.local_tidy(self.colonialrr_file.name)

        # The test succeeds if the file can be parsed.
        with open(self.colonialrr_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        start_date = datetime.datetime(2012, 12, 9)
        stop_date = datetime.datetime(2012, 12, 10)
        o = rr.CoolRunning(verbose='critical',
                           memb_list=self.membership_file.name,
                           output_file=self.results_file.name,
                           start_date=start_date,
                           stop_date=stop_date)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("John Banner" in soup.div.pre.contents[0])

    def test_black_cat(self):
        """
        Black Cat race results for 2013 could not be processed because
        ElementTree could not parse for the race banner header.
        """
        self.populate_membership_file('Popham,Michael')
        self.populate_racelist_file([self.black_cat_file.name])
        o = rr.CoolRunning(verbose='critical',
                           memb_list=self.membership_file.name,
                           race_list=self.racelist_file.name,
                           output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("MICHAEL POPHAM" in
                            soup.pre.contents[0])

    def test_ras_na_eireann(self):
        """
        All individual results for Ras na Eireann were getting included.
        """
        self.populate_membership_file('Smith-Rohrberg,Karen')
        self.populate_racelist_file([self.ras_na_eireann_file.name])
        o = rr.CoolRunning(verbose='critical',
                           memb_list=self.membership_file.name,
                           race_list=self.racelist_file.name,
                           output_file=self.results_file.name)
        o.run()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            soup = BeautifulSoup(html, 'lxml')
            self.assertTrue("Karen Smith-Rohrberg" in
                            soup.pre.contents[0])
            self.assertTrue("Dan Harrington" not in
                            soup.pre.contents[0])


if __name__ == "__main__":
    unittest.main()
