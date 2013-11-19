import datetime
import logging
import os
import re
import urllib
import xml.etree.cElementTree as ET

from bs4 import BeautifulSoup

from .common import RaceResults, remove_namespace


class NewYorkRR(RaceResults):
    """
    Handles race results from New York Road Runners website.
    """
    def __init__(self, **kwargs):
        """
        """
        RaceResults.__init__(self)
        self.__dict__.update(**kwargs)

        # Need to remember the current URL.
        self.downloaded_url = None

        # Set the appropriate logging level.
        self.logger.setLevel(getattr(logging, self.verbose.upper()))

    def run(self):
        """
        This page has the URLs for the recent results.
        """
        self.initialize_output_file()

        url = 'http://web2.nyrrc.org'
        url += '/cgi-bin/start.cgi/aes-programs/results/resultsarchive.htm'

        self.download_file(url)

        # Parse out the list of races.  They are all in a
        # particular table.
        #soup = BeautifulSoup(self.html, 'lxml')
        soup = BeautifulSoup(self.html, 'html.parser')
        tables = soup.find_all('table')
        table = tables[4]

        # This is awful, all the entries are in a single table element.
        # The TD element has a P element, which has the list that we want.
        td = table.table.td

        links = td.find_all('a')
        for link in links:

            race_name = link.text
            url = link['href']

            # The next sibling is the race date.  In ElementTree parliance,
            # this would be the "tail" of the anchor link.
            race_date = re.sub('\s', '', link.nextSibling)
            race_date = datetime.datetime.strptime(race_date, "%m/%d/%y")
            race_date = datetime.date(race_date.year, race_date.month,
                                      race_date.day)
            if self.start_date <= race_date and race_date <= self.stop_date:
                self.logger.info("Keeping %s" % race_name)
                self.process_event(url)
            else:
                self.logger.info("Skipping %s" % race_name)

    def process_event(self, url):
        """We have the URL of a single event.  The URL does not lead to the
        results, however, it leads to a search page.
        """
        local_file = 'event_search.html'
        self.download_file(url, local_file=local_file)
        self.local_tidy(local_file)

        # There should be a single form.
        with open(local_file, 'r', encoding='utf-8') as fp:
            markup = fp.read()
        pattern = r"""<form\saction="(?P<action>.*)"\s*method="post">"""
        regex = re.compile(pattern, re.VERBOSE)
        m = regex.search(markup)
        url = m.group('action')


        # The page for POSTing the search needs POST params.
        post_params = {}
        post_params['search.method'] = 'search.team'
        post_params['input.lname'] = ''
        post_params['input.fname'] = ''
        post_params['input.bib'] = ''
        post_params['overalltype'] = 'All'
        post_params['input.agegroup.m'] = '12 to 14'
        post_params['input.agegroup.f'] = '12 to 14'
        post_params['teamgender'] = ''
        post_params['team_code'] = self.team
        post_params['items.display'] = '500'
        post_params['AESTIVACVNLIST'] = 'overalltype,input.agegroup.m,'
        post_params['AESTIVACVNLIST'] += 'input.agegroup.f,teamgender,'
        post_params['AESTIVACVNLIST'] += 'team_code'
        #data = urllib.parse.urlencode(post_params)
        #data = data.encode()

        # Provide all the search parameters for this race.  This includes, most
        # importantly, the team code, i.e. RARI for Raritan Valley Road
        # Runners.
        local_file = 'nyrrresult.html'
        self.download_file(url, local_file=local_file, params=post_params)
        self.local_tidy(local_file)

        # Use Beautifulsoup/lxml to make it compliant.
        with open(local_file, 'r', encoding='utf-8') as fp:
            markup = fp.read()
            soup = BeautifulSoup(markup, 'lxml')
        with open(local_file, 'w') as fp:
            fp.write(soup.prettify())

        # If there were no results for the specified team, then the html will
        # contain some red text to the effect of "Your search returns no
        # match."
        with open(local_file, 'r', encoding='utf-8') as fp:
            html = fp.read()
        if re.search("Your search returns no match.", html) is not None:
            return

        # So now we have a result.  Parse it for the result table.
        root = ET.parse(local_file).getroot()
        root = remove_namespace(root)

        # 3rd table is the one we want.
        pattern = './/table'
        tables = root.findall(pattern)

        if len(tables) < 3:
            return

        div = self.webify_results(tables)
        self.insert_race_results(div)

    def webify_results(self, tables):
        """Turn the results into the output form that we want.
        """

        # The table we want is the 3rd one.  We need
        # to sanitize it, though.
        table = self.sanitize_table(tables[2])

        # maybe abstract this into a webify function.
        div = ET.Element('div')
        div.set('class', 'race')
        hr = ET.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # Append the race metadata.
        tds = tables[0].findall('.//td')
        td = tds[2]
        race_meta = ET.Element('div')
        ch = td.getchildren()
        race_meta.append(ch[0])
        race_meta.append(ch[1])
        race_meta.append(ch[2])
        race_meta.append(ch[3])
        div.append(race_meta)

        # Append the URL from whence we came..
        pdiv = ET.Element('div')
        pdiv.set('class', 'provenance')
        span = ET.Element('span')
        span.text = 'Results courtesy of '
        pdiv.append(span)
        anchor = ET.Element('a')
        anchor.set('href', 'http://www.nyrr.org')
        anchor.text = 'New York Road Runners'
        pdiv.append(anchor)
        span = ET.Element('span')
        span.text = '.'
        pdiv.append(span)
        div.append(pdiv)

        # And finally, append the race results.
        div.append(table)
        return div

    def sanitize_table(self, old_table):
        """The table as-is has a few links that we need to remove.
        """
        new_table = ET.Element('table')
        new_table.set('cellpadding', '3')
        new_table.set('cellspacing', '0')
        new_table.set('border', '1')

        new_tr = ET.Element('tr')
        new_tr.set('bgcolor', '#EEEEEE')

        trs = old_table.getchildren()
        tr = trs[0]
        old_tds = tr.getchildren()

        # 1st two TD elements need to be replaced.
        td = ET.Element('td')
        td.text = old_tds[0].getchildren()[0].text
        new_tr.append(td)

        # 1st two TD elements need to be replaced.
        td = ET.Element('td')
        td.text = old_tds[1].getchildren()[0].text
        new_tr.append(td)

        # Append the rest of the TD elements in the first row.
        for td in old_tds[2:]:
            new_tr.append(td)
        new_table.append(new_tr)

        # And append the race results as-is.
        for tr in trs[1:]:
            new_table.append(tr)

        return(new_table)
