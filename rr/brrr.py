"""
Module for BestRace.
"""
import re

from lxml import etree, html
import requests

from .common import RaceResults


class BestRace(RaceResults):
    """
    Process races found on BestRace.com.
    """

    def __init__(self, **kwargs):
        RaceResults.__init__(self, **kwargs)

    def compile_web_results(self):
        """
        Download the requested results and compile them.
        """
        # The URL for the "master" list will have the pattern
        #
        # http://www.bestrace.com/YYYYschedule.shtml
        url = 'http://www.bestrace.com/{year}schedule.html'
        url = url.format(year=self.start_date.strftime('%Y'))
        self.logger.info('Downloading {}'.format(url))
        self.response = requests.get(url)

        # Look for the following pattern in the "master" list.
        #
        # http://www.bestrace.com/results/YY/YYMMDDXXX.HTM
        pattern = 'http://www.bestrace.com/results/{}/{}{}'
        pattern = pattern.format(self.start_date.strftime('%y'),
                                 self.start_date.strftime('%y'),
                                 self.start_date.strftime('%m'))

        ndays = self.stop_date.day - self.start_date.day + 1
        fmt = '|'.join(['{:02d}' for r in range(ndays)])
        pargs = [x for x in range(self.start_date.day, self.stop_date.day + 1)]
        day_range = fmt.format(*pargs)

        pattern += '(' + day_range + ')'

        pattern += r"\w+\.HTM"
        self.logger.debug('pattern is "{}"'.format(pattern))

        matchiter = re.finditer(pattern, self.response.text)
        urls = [matchobj.group() for matchobj in matchiter]

        for url in urls:
            self.logger.info('Downloading {}...'.format(url))
            response = requests.get(url)
            self.downloaded_url = url
            self.html = response.text
            self.compile_race_results(response)

    def compile_race_results(self, resp):
        """
        """
        doc = html.document_fromstring(resp.text)
        self.html = resp.text

        # We are looking for a <PRE> element.  That element is preceded by
        # a <PRE><A NAME="overall"></PRE> set of tags.
        pre = doc.cssselect('pre + pre')[0]

        # OK, we are properly positioned.
        results = []
        for line in pre.text_content().split('\n'):
            for _, regex in self.df['fname_lname_regex'].iteritems():
                if regex.search(line):
                    results.append(line)

        if len(results) > 0:
            results = self.webify_results(results)
            self.insert_race_results(results)

    def webify_results(self, results_lst):
        """
        Take the list of results and turn it into output HTML.
        """
        div = etree.Element('div')
        div.set('class', 'race')
        hr_elt = etree.Element('hr')
        hr_elt.set('class', 'race_header')
        div.append(hr_elt)

        # Get the title, but don't bother with the date information.
        # <title>  Purple Stride 5K     - November 10, 2013   </title>
        doc = html.document_fromstring(self.html)
        title = doc.cssselect('title')[0]
        title_string = title.text.split('-')[0]

        h1_elt = etree.Element('h1')
        h1_elt.text = title_string
        div.append(h1_elt)

        # Append the URL if possible.
        if self.downloaded_url is not None:
            div.append(self.construct_source_url_reference('BestRace'))

        # Parse out the banner.  The banner has 'tail' content, however, so we
        # have to be careful.
        banner = doc.cssselect('pre + pre > b')[0]
        pre = etree.Element('pre')
        pre.append(banner)
        banner.tail = '\n' + '\n'.join(results_lst)
        div.append(pre)

        return div
