import datetime
import os
import pkg_resources
import re
import shutil
import sys
import tempfile
import unittest
from xml.etree import cElementTree as ET

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
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue("Caleb Gartner" in html)
            self.assertTrue("Sean Spalding" in html)

    def test_consecutive_newlines(self):
        """
        Verify that we don't get two consecutive newlines in the
        race results, which makes them look bad.

        See Issue 33
        """
        self.populate_racelist_file([self.vanilla_crrr_file.name])
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            m = re.search(html, '\n\n')
            self.assertIsNone(m)

    def test_multiple_racelist(self):
        """
        Test compiling race results from a list of local files.
        """
        racelist = [self.vanilla_crrr_file.name, self.ccrr_file.name]
        self.populate_racelist_file(racelist)
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue("Caleb Gartner" in html)
            self.assertTrue("Sean Spalding" in html)

    def test_cape_cod_road_runners(self):
        """
        Test compiling race results from a list of local files.
        The HTML profile is used by Cape Cod Road Runners.
        """
        self.populate_racelist_file([self.ccrr_file.name])
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue("MIKE NORTON" in html)

    def test_web_download(self):
        """
        Verify that we can get results from the web.
        """
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '-y', '2012',
                '-m', '12',
                '-d', '9', '10',
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue("John Banner" in html)

    def test_black_cat(self):
        """
        Black Cat race results for 2013 could not be processed because
        ElementTree could not parse for the race banner header.
        """
        self.populate_membership_file('Popham,Michael')
        self.populate_racelist_file([self.black_cat_file.name])
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue("MICHAEL POPHAM" in html)

    def test_ras_na_eireann(self):
        """
        All individual results for Ras na Eireann were getting included.
        """
        self.populate_membership_file('Smith-Rohrberg,Karen')
        self.populate_racelist_file([self.ras_na_eireann_file.name])
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue("Karen Smith-Rohrberg" in html)
            self.assertTrue("Dan Harrington" not in html)


class TestRacingCompanies(unittest.TestCase):
    """
    Test parsing results from CoolRunning, various racing companies
    """
    def setUp(self):

        # Create other fixtures that are easy to clean up later.
        self.membership_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.racelist_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.results_file = tempfile.NamedTemporaryFile(suffix=".txt")
        self.populate_membership_file()

    def tearDown(self):
        self.membership_file.close()
        self.racelist_file.close()
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

    def run_test(self, racefile, test_string):
        """
        Parameters
        ----------
        racefile : str
            Path to race results file to be tested.
        test_string : str
            String that must be present in the results file in order for the
            test to pass.
        """
        self.populate_racelist_file([racefile])
        sys.argv = [
                '',
                '--verbose', 'critical',
                '--ml', self.membership_file.name,
                '--rl', self.racelist_file.name,
                '-o', self.results_file.name]
        rr.command_line.run_coolrunning()

        with open(self.results_file.name, 'r') as f:
            html = f.read()
            self.assertTrue(test_string in html)


    def test_accu(self):
        """
        Verify that we handle races from accu race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_accu.shtml')
        self.populate_membership_file('ANDREW,PITTS')
        self.run_test(racefile, "ANDREW PITTS")

    def test_baystate(self):
        """
        Verify that we handle races from baystate racing services.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/baystate.shtml')

        self.populate_membership_file('Dan,Chebot')
        self.run_test(racefile, "Dan Chebot")

    def test_gstate(self):
        """
        Verify that we handle races from granite state race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_gstate.shtml')

        self.populate_membership_file('BRIAN,SCHELL')
        self.run_test(racefile, "Brian Schell")

    def test_harriers(self):
        """
        Verify that we handle races from harriers race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_harrier.shtml')

        self.populate_membership_file('Dennis,MULDOON')
        self.run_test(racefile, "DENNIS MULDOON")

    def test_jfrc(self):
        """
        Verify that we handle races from jfrc race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_jfrc.shtml')

        self.populate_membership_file('CHRIS,MCCANN')
        self.run_test(racefile, "Chris McCann")

    def test_lastmile(self):
        """
        Verify that we handle races from last mile race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_lastmile.shtml')

        self.populate_membership_file('JONATHAN,JOYCE')
        self.run_test(racefile, "Jonathan Joyce")

    def test_mooserd(self):
        """
        Verify that we handle races from mooserd (
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_mooserd.shtml')

        self.populate_membership_file('CHRIS,GREENLEE')
        self.run_test(racefile, "CHRIS GREENLEE")

    def test_netiming(self):
        """
        Verify that we handle races from new england timing management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_ne.shtml')

        self.populate_membership_file('AARON,KEENE')
        self.run_test(racefile, "Aaron Keene")

    def test_spitler(self):
        """
        Verify that we handle races from spitler race management.
        """
        self.populate_membership_file('CHARLIE,COFFMAN')
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_spitler.shtml')
        self.run_test(racefile, "Charlie Coffman")

    def test_swcl(self):
        """
        Verify that we handle SWCL races from wilbur race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_swcl.shtml')

        self.populate_membership_file('ERIN,CARMONE')
        self.run_test(racefile, "Carmone, Erin")

    def test_wilbur(self):
        """
        Verify that we handle races from wilbur race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_wilbur.shtml')

        self.populate_membership_file('KEVIN,JOHNSON')
        self.run_test(racefile, "JOHNSON, KEVIN")

    def test_yankee(self):
        """
        Verify that we handle races from yankee race management.
        """
        racefile = pkg_resources.resource_filename(rr.test.__name__,
                                                   'testdata/crrr_yankee.shtml')

        self.populate_membership_file('ZACH,DAY')
        self.run_test(racefile, "ZACH DAY")


if __name__ == "__main__":
    unittest.main()
