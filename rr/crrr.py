"""
Backend class for handling CoolRunning race results.
"""
import itertools
import re
import warnings

import lxml
from lxml import etree, html
import requests

from .common import RaceResults


class CoolRunning(RaceResults):
    """
    Class for handling CoolRunning Race Results.

    Attributes
    ----------
    author : str
        Identifier for the authority or racing company that produced the
        results.
    """
    def __init__(self, **kwargs):
        RaceResults.__init__(self, **kwargs)

        self.author = None

    def compile_web_results(self):
        """
        Compile race results for all the requested states.
        """
        for state in self.states:

            # Download state "master" list
            self.logger.info('Processing {}...'.format(state))
            state_file = state + '.shtml'
            url = 'http://www.coolrunning.com/results/{0}/{1}'
            url = url.format(self.start_date.strftime('%y'), state_file)
            response = requests.get(url)

            self.process_state_master_list(state, response)

    def construct_state_match_pattern(self, state):
        """
        Want to match strings like

        http://www.coolrunning.com/results/07/ma/Jan16_Coloni_set1.shtml

        So we construct a regular expression to match against
        all the dates in the specified range.

        Parameters
        ----------
        state : str
            Two-letter state code, such as 'ma'

        Returns
        -------
        regex : pattern object
            Matches a pattern like

            http://www.coolrunning.com/results/MM/ST/MMMDDXXXXX.shtml
        """
        pattern = '/results/'
        pattern += self.start_date.strftime('%y')
        pattern += '/'
        pattern += state
        pattern += '/'
        pattern += self.start_date.strftime('%b')

        # continue with a regexp to match any of the days in the date range.
        # It's a non-capturing group.
        day_range = '(?:'
        for day in range(self.start_date.day, self.stop_date.day):
            day_range += "%d_|" % day
        day_range += '%d_)' % self.stop_date.day

        pattern += day_range

        pattern += '.*shtml'
        self.logger.debug('Match pattern is %s' % pattern)
        regex = re.compile(pattern)
        return regex

    def process_state_master_list(self, state, response):
        """
        Compile results for the specified state.

        Parameters
        ----------
        state : str
            Two-letter state code, such as 'ma'
        response : Response object from requests package
            What's on the other side of the state master list URL
        """
        regex = self.construct_state_match_pattern(state)

        relative_urls = regex.findall(response.text)

        for relative_url in relative_urls:

            top_level_url = 'http://www.coolrunning.com' + relative_url
            race_file = top_level_url.split('/')[-1]
            self.logger.info(top_level_url)

            response = requests.get(top_level_url)
            self.downloaded_url = top_level_url
            html = response.text
            self.compile_race_results(html)

            # Now collect any secondary result files.
            #
            # construct the secondary pattern.  If the race name is something
            # like "TheRaceSet1.shtml", then the secondary races will be
            # "TheRaceSet[2345].shmtl" etc.
            parts = race_file.split('.')
            base = parts[-2][0:-1]
            pat = r'<a href="(?P<inner_url>\.\/' + base + r'\d+\.shtml)">'
            inner_regex = re.compile(pat)
            for matchobj in inner_regex.finditer(html):

                relative_inner_url = matchobj.group('inner_url')
                if relative_inner_url in top_level_url:
                    # Already seen this one.
                    continue

                # Strip off the leading "./" to get the name we use for the
                # local file.
                race_file = relative_inner_url[2:]

                # Form the full inner url by swapping out the top level
                # url
                lst = top_level_url.split('/')
                lst[-1] = race_file
                inner_url = '/'.join(lst)
                self.logger.info(inner_url)

                inner_response = requests.get(inner_url)
                self.compile_race_results(inner_response.text)

    def compile_vanilla_results(self, markup):
        """
        Compile race results for vanilla CoolRunning races.

        Parameters
        ----------
        markup : str
            HTML from a race web page.
        """
        results = []

        doc = html.document_fromstring(markup)
        try:
            pre = doc.cssselect('pre')[0]
        except IndexError:
            warnings.warn("No <PRE> element found.  Skipping...")
            return results

        text = pre.text_content()
        for line in text.split('\n'):
            if self.match_against_membership(line):
                results.append(line)

        return results

    def compile_ccrr_race_results(self, markup):
        """
        This is the format generally used by Cape Cod
        Road Runners.

        Parameters
        ----------
        markup : str
            HTML from a race web page.

        Returns
        -------
        results : list:
            List of <TR> elements, each row containing an individual result.
        """
        doc = html.document_fromstring(markup)

        # The table rows follow a set of H1, H2, H3, and P tags.  This seems
        # a bit brittle.
        trs = doc.cssselect('h1 + h2 + h3 + p.subhead + table tr')

        results = []
        for tr in trs:
            tds = tr.getchildren()

            if len(tds) < 3:
                # Incomplete row, skip it.
                continue

            runner_name = tds[0].text
            if runner_name is None:
                continue
            for _, regex in self.df['fname_lname_regex'].iteritems():
                if regex.match(runner_name):
                    results.append(tr)

        if len(results) > 0:
            # Prepend the header.
            results.insert(0, trs[0])

        return results

    def get_author(self, markup):
        """
        Get the race company identifier.

        Example
        -------
            <meta name="Author" content="colonial" />

        Parameters
        ----------
        markup : str
            HTML from a race web page.
        """
        doc = html.document_fromstring(markup)
        elts = doc.cssselect('meta[name="Author"]')
        if len(elts) == 0:
            msg = "Could not parse the race company identifier"
            raise RuntimeError(msg)
        self.author = elts[0].get('content')

    def compile_race_results(self, markup):
        """
        Go through a race file and collect results.

        Parameters
        ----------
        markup : str
            HTML from a race web page.
        """
        html = None
        self.get_author(markup)
        if self.author in ['CapeCodRoadRunners', 'GreenfieldRecreation']:
            self.logger.debug('Cape Cod Road Runners pattern')
            results = self.compile_ccrr_race_results(markup)
            if len(results) > 0:
                html = self.webify_ccrr_results(results, markup)
                self.insert_race_results(html)
        elif self.author in ['ACCU', 'baystate', 'charlie', 'gstate',
                             'Harrier', 'netiming', 'JFRC', 'mmg1214',
                             'mooserd', 'Spitler', 'SWCL', 'yk']:
            # These cases are verified in the test suite.
            # "charlie" is "Last Mile"
            # "mmg1214" is "Wilbur Racing Systems"
            # "SWCL" is also "Wilbur Racing Systems"
            results = self.compile_vanilla_results(markup)
            if len(results) > 0:
                html = self.webify_vanilla_results(results, markup)
                self.insert_race_results(html)
        elif self.author in ['kick610', 'JB Race', 'ab-mac', 'FTO',
                             'NSTC', 'ndatrackxc', 'wcrc']:
            # Assume the usual coolrunning pattern.
            msg = '{0} ==> assuming vanilla Coolrunning pattern'
            self.logger.debug(msg.format(self.author))
            results = self.compile_vanilla_results(markup)
            if len(results) > 0:
                html = self.webify_vanilla_results(results, markup)
                self.insert_race_results(html)
        elif self.author in ['colonial', 'opportunity']:
            # 'colonial' is a local race series.  Gawd-awful
            # excel-to-bastardized-html.  The hell with it.
            #
            # 'opportunity' seems to be CMS 52 Week Series
            self.logger.info('Skipping {0} race series.'.format(self.author))
        elif self.author in ['Harriers']:
            self.logger.info('Skipping harriers (snowstorm classic?) series.')
        elif self.author in ['jalfano']:
            self.logger.info('Skipping CMS(?) series.')
        elif self.author in ['DavidWill', 'FFAST', 'lungne', 'northeastracers',
                             'sri']:
            msg = 'Skipping {0} pattern (unhandled XML pattern).'
            self.logger.info(msg.format(self.author))
        elif self.author in ['WCRCSCOTT']:
            msg = 'Skipping {0} XML pattern (looks like a race series).'
            self.logger.info(msg.format(self.author))
        else:
            msg = 'Unknown pattern (\"{0}\"), going to try vanilla CR parsing.'
            self.logger.warning(msg.format(self.author))
            results = self.compile_vanilla_results(markup)
            if len(results) > 0:
                html = self.webify_vanilla_results(results, markup)
                self.insert_race_results(html)

    def construct_common_div(self, markup):
        """
        Construct an XHTML element to contain race results.

        Parameters
        ----------
        markup : str
            HTML from a race web page.
        """
        doc = html.document_fromstring(markup)

        div = etree.Element('div')
        div.set('class', 'race')
        hr_elt = etree.Element('hr')
        hr_elt.set('class', 'race_header')
        div.append(hr_elt)

        # The H1 tag has the race name.  The H2 tag has the location and date.
        # Both are the only such tabs in the file.
        h1 = doc.cssselect('h1')[0]
        h1_elt = etree.Element('h1')
        h1_elt.text = h1.text
        div.append(h1_elt)

        h2 = doc.cssselect('h2')[0]
        h2_elt = etree.Element('h2')
        h2_elt.text = h2.text
        div.append(h2_elt)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            div.append(self.construct_source_url_reference('Coolrunning'))

        return(div)

    def webify_ccrr_results(self, results, markup):
        """
        Turn the list of results into full HTML.
        This works for Cape Cod Road Runners formatted results.

        Parameters
        ----------
        results : list
            List of HTML TR rows containing individual race results
        markup : str
            HTML from a race web page.

        Returns
        -------
        div : element tree
            DIV element containing "finished" race results.
        """
        div = self.construct_common_div(markup)

        table = etree.Element('table')
        for tr_elt in results:
            if tr_elt is not None:
                table.append(tr_elt)

        div.append(table)
        return div

    def webify_vanilla_results(self, result_lst, markup):
        """
        Insert CoolRunning results into the output file.

        Parameters
        ----------
        results_lst : list
            List of HTML TR rows containing individual race results
        markup : str
            HTML from a race web page.

        Returns
        -------
        div : element tree
            DIV element containing "finished" race results.
        """
        div = self.construct_common_div(markup)

        banner_text = self.parse_banner(markup)

        pre = etree.Element('pre')
        pre.attrib['class'] = 'actual_results'
        pre.text = banner_text + '\n' + '\n'.join(result_lst) + '\n'
        div.append(pre)

        return div

    def parse_banner(self, markup):
        """
        Tease out the "banner" from the race file.

        This will usually be found following the <pre> tag that contains the
        results.

        Parameters
        ----------
        markup : str
            HTML from a race web page.

        Returns
        -------
        banner : str
            Text to use as a banner.
        """
        doc = html.document_fromstring(markup)
        pre = doc.cssselect('pre')[0]
        text = pre.text_content()

        lines = text.split('\n')

        # accumulate lines of text until we hit a start of line followed by
        # whitespace followed by a 1 (for 1st place) followed by white space.
        regex = re.compile(r'^\s*1\b')
        lst = itertools.takewhile(lambda x: regex.match(x) is None, lines)
        banner = '\n'.join(lst)
        return banner
