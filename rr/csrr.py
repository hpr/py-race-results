"""
Module for parsing Compuscore race results.
"""

import datetime
import re
import requests
import warnings

from lxml import etree

from .common import RaceResults

# Need to match the month of the search window to the month strings that
# Compuscore uses.
MONTHSTRS = {1: 'janfeb',
             2: 'janfeb',
             3: 'march',
             4: 'april',
             5: 'may',
             6: 'june',
             7: 'july',
             8: 'aug',
             9: 'sept',
             10: 'october',
             11: 'novdec',
             12: 'novdec', }


class CompuScore(RaceResults):
    """
    Class for handling compuscore results.
    """
    def __init__(self, **kwargs):
        RaceResults.__init__(self, **kwargs)

        self.monthstr = MONTHSTRS[self.start_date.month]

        # Need to remember the current URL.
        self.downloaded_url = None

    def compile_web_results(self):
        """
        Download the requested results and compile them.
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
                url3 = url3.format(site=web_details['webfile']['domain'],
                                   rel_url=web_details['webfile']['resource'])
                race_resp = requests.get(url3)
                self.downloaded_url = url3
                try:
                    self.html = race_resp.content.decode('utf-8')
                except UnicodeDecodeError:
                    self.html = race_resp.content.decode('latin1')
                self.compile_race_results()

    def get_race_date(self):
        """
        Return the race date.
        """
        # The date text is in the file's sole H3 tag.
        regex = re.compile(r'<h3.*>(?P<h3>.*)</h3>')
        matchobj = regex.search(self.html)
        if matchobj is not None:
            full_race_date_text = matchobj.group('h3')
        else:
            # Try searching for just the literal text.
            regex = re.compile(r'Race Date:\d\d-\d\d-\d\d')
            matchobj = regex.search(self.html)
            if matchobj is not None:
                full_race_date_text = matchobj.group()
            else:
                # Give up, nothing here.
                return None

        # The race date should read something like
        #     "    Race Date:11-03-12   "
        pat = r'\s*Race\sDate:(?P<mo>\d{1,2})-(?P<dd>\d{2})-(?P<yy>\d{2})\s*'
        regex = re.compile(pat)
        matchobj = regex.search(full_race_date_text)

        # NOW we get to see if the race is in the proper time frame or not.
        year = 2000 + int(matchobj.group('yy'))
        month = int(matchobj.group('mo'))
        day = int(matchobj.group('dd'))

        return datetime.date(year, month, day)

    def webify_results(self, results):
        """
        Take the list of results and turn it into output HTML.
        """
        div = etree.Element('div')
        div.set('class', 'race')

        hr_elt = etree.Element('hr')
        hr_elt.set('class', 'race_header')
        div.append(hr_elt)

        # The single H2 element in the file has the race name.
        regex = re.compile(r'<h2.*>(?P<h2>.*)</h2>')
        matchobj = regex.search(self.html)
        h2_elt = etree.Element('h2')
        if matchobj is None:
            h2_elt.text = ''
        else:
            h2_elt.text = matchobj.group('h2')
        div.append(h2_elt)

        # The single H3 element in the file has the race date.
        # If it's there, that is.
        race_date = self.get_race_date()
        if race_date is not None:
            h3_elt = etree.Element('h3')
            h3_elt.text = race_date.strftime('Race Date:  %b %d, %Y')
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
