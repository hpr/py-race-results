"""
Module for parsing Compuscore race results.
"""

import datetime
import re
import requests
import warnings

from lxml import etree, html

from .common import RaceResults

class CompuScore(RaceResults):
    """
    Class for handling compuscore results.
    """
    def __init__(self, **kwargs):
        RaceResults.__init__(self, **kwargs)

        # Need to remember the current URL.
        self.downloaded_url = None

        # Customize the regular expressions.
        # Use word boundaries to prevent false positives, e.g. "Ed Ford"
        # does not cause every fricking person from "New Bedford" to
        # match.  Here's an example line to match.
        #   '60.Gene Gugliotta       North Plainfiel,NJ 53 M U '
        # The first and last names must be separated by just white space.
        # 
        # So, match the following:
        #     start of line
        #     place (like first, 2nd, etc.)
        #     '.'
        #     First name
        #     space
        #     Last name
        self.df['regex'] = None
        for _, row in self.df.iterrows():
            pattern = (r'^\s*(?P<place>\d+)\.' +
                       row['fname'] + '\s+' + row['lname'] + r'\b')
            row['regex'] = re.compile(pattern, re.IGNORECASE)

    def compile_web_results(self):
        """
        Download the race results in the requested time frame.
        """
        fmt = 'http://www.compuscore.com/api/races/events?date_range={},{}'
        url = fmt.format(self.start_date.strftime('%Y-%m-%d'),
                         self.stop_date.strftime('%Y-%m-%d'))
        response = requests.get(url)

        # Get the list of races from the json dump.
        for event in response.json()['events']:

            # Now get the race details, from where we get the race URL.
            url2 = 'http://www.compuscore.com/api/races/event-detail?ids={}'
            url2 = url2.format(event['id'])
            details = requests.get(url2).json()
            race_name = details['events'][0]['name']
            print('Examining {}'.format(race_name))
            for sub_event in details['events'][0]['races']:
                print('    Examining {}'.format(sub_event['name']))
                try:
                    web_details = sub_event['result_files'][0]
                except IndexError:
                    print('Skipping {}'.format(race_name))
                    continue

                # And finally, download the race itself.
                url3 = 'http://{site}{rel_url}'
                kwargs = {'site': web_details['webfile']['domain'],
                          'rel_url': web_details['webfile']['resource']}
                url3 = url3.format(**kwargs)
                race_resp = requests.get(url3)
                self.downloaded_url = url3

                self.compile_race_results(race_resp)

    def compile_race_results(self, resp):
        """
        """
        doc = html.document_fromstring(resp.text)
        self.html = resp.text
        pre = doc.cssselect('strong + pre')[0]

        # The prior <STRONG> element should have a <A NAME="overall"> element
        strong = pre.getprevious()
        lst = strong.cssselect('a[name="overall"]')
        if len(lst) == 0:
            msg = "Could not find overall results."
            raise RuntimeError(msg)

        # OK, we are properly positioned.
        results = []
        for line in pre.text_content().split('\n'):
            for _, regex in self.df['regex'].iteritems():
                if regex.search(line):
                    results.append(line)

        if len(results) > 0:
            results = self.webify_results(doc, results)
            self.insert_race_results(results)

    def webify_results(self, doc, results):
        """
        Take the list of results and turn it into output HTML.
        """
        div = etree.Element('div')
        div.set('class', 'race')

        hr_elt = etree.Element('hr')
        hr_elt.set('class', 'race_header')
        div.append(hr_elt)

        # The single H2 element in the file has the race name.
        h2 = doc.cssselect('h2')[0]
        h2_elt = etree.Element('h2')
        h2_elt.text = h2.text
        div.append(h2_elt)

        # The single H3 element in the file has the race date.
        # If it's there, that is.
        h3 = doc.cssselect('h3')[0]
        h3_elt = etree.Element('h3')
        h3_elt.text = h3.text
        div.append(h3_elt)

        if self.downloaded_url is not None:
            div.append(self.construct_source_url_reference('Compuscore'))

        # Append the actual race results.  Consists of the column headings
        # (banner) plus the individual results.
        pre = etree.Element('pre')
        pre.set('class', 'actual_results')

        regex = re.compile(r"""<strong>(?P<strong1>[^<>]*)</strong>\s*
                               <strong><u>(?P<strong2>[^<>]*)</u></strong>""",
                           re.VERBOSE)
        matchobj = regex.search(self.html)
        if matchobj is None:
            pre.text = '\n' + '\n'.join(results)
        else:
            # This <pre> element must be mixed content in order to look
            # right.  Difficult to do this without using "fromstring".
            inner = '\n' + matchobj.group() + '\n' + '\n'.join(results)
            mixed_content = '<pre>' + inner + '</pre>'
            pre = etree.fromstring(mixed_content)
        div.append(pre)

        return div
