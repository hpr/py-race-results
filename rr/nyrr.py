"""
Module for compiling NYRR race resuts.
"""
import datetime as dt
import re
import http
import http.cookiejar
import urllib.request

from lxml import etree
from lxml import html as html2

from .common import RaceResults


class NewYorkRR(RaceResults):
    """
    Handles race results from New York Road Runners website.
    """
    def __init__(self, team=None, **kwargs):
        """
        Parameters
        ----------
        team : str
            Search for results by team name, not individual.
        """
        RaceResults.__init__(self, membership_list=None, **kwargs)

        self.team = team

        # Need to remember the current URL.
        self.downloaded_url = None

        self.cookies = None
        self.cookie_jar = None

        # This URL is used in a regular expression that teases out the URLs
        # for all of the results.
        self.result_url_base = "http://web2.nyrrc.org/cgi-bin/start.cgi/"
        self.result_url_base += "aes-programs/results/startup.html"

    def run(self):
        """
        This page has the URLs for the recent results.
        """
        self.initialize_output_file()

        url = 'http://web2.nyrrc.org'
        url += '/cgi-bin/start.cgi/aes-programs/results/resultsarchive.htm'

        text = self.download_file(url)

        # There are two forms used for searches.  The one that we want (list
        # all the results for an entire year) is the 2nd on that this regex
        # retrieves.
        doc = html2.document_fromstring(text)
        forms = doc.cssselect('form[name="findOtherRaces"]')
        form = forms[0]
        url = form.get('action')

        # The page for POSTing the search needs POST params.
        post_params = {}
        post_params['NYRRYEAR'] = str(self.start_date.year)
        post_params['AESTIVACVNLIST'] = 'NYRRYEAR'
        data = urllib.parse.urlencode(post_params)
        data = data.encode()

        # Download the race list page for the specified year
        text = self.download_file(url, data)

        doc2 = html2.document_fromstring(text)
        links = doc2.cssselect('a')

        for link in links:
            url = link.get('href')
            if self.result_url_base not in url:
                continue

            url = re.sub('&amp;', '&', url)

            race_name = link.text
            race_date_text = link.tail.strip()
            rdt = dt.datetime.strptime(race_date_text, '%m/%d/%y')
            race_date = dt.date(rdt.year, rdt.month, rdt.day)

            if self.start_date <= race_date and race_date <= self.stop_date:
                self.logger.info("Keeping {0}".format(race_name))
                self.process_event(url)
            else:
                self.logger.info("Skipping %s" % race_name)

    def process_event(self, url):
        """We have the URL of a single event.  The URL does not lead to the
        results, however, it leads to a search page.
        """
        markup = self.download_file(url)
        doc = html2.document_fromstring(markup)
        forms = doc.cssselect('form')
        form = forms[0]
        url = form.get('action')

        # The page for POSTing the search needs POST params.
        # Provide all the search parameters for this race.  This includes, most
        # importantly, the team code, i.e. RARI for Raritan Valley Road
        # Runners.
        post_params = {}
        post_params['search.method'] = 'search.team'
        post_params['input.lname'] = ''
        post_params['input.fname'] = ''
        post_params['input.bib'] = ''
        post_params['overalltype'] = 'All'
        post_params['input.agegroup.m'] = '12 to 19'
        post_params['input.agegroup.f'] = '12 to 19'
        post_params['teamgender'] = ''
        post_params['team_code'] = self.team
        post_params['items.display'] = '500'
        post_params['AESTIVACVNLIST'] = 'overalltype,input.agegroup.m,'
        post_params['AESTIVACVNLIST'] += 'input.agegroup.f,teamgender'
        post_params['AESTIVACVNLIST'] += 'team_code'
        data = urllib.parse.urlencode(post_params)
        data = data.encode()

        markup = self.download_file(url, data)

        # If there were no results for the specified team, then the html will
        # contain some red text to the effect of "Your search returns no
        # match."
        if re.search("Your search returns no match.", markup) is not None:
            return

        doc = html2.document_fromstring(markup)
        tables = doc.cssselect('table')

        if len(tables) < 4:
            return

        div = self.webify_results(tables[1], tables[3])
        self.insert_race_results(div)

    def webify_results(self, meta_table, results_table):
        """
        Turn the results into the output form that we want.
        """

        # maybe abstract this into a webify function.
        div = etree.Element('div')
        div.set('class', 'race')
        hr = etree.Element('hr')
        hr.set('class', 'race_header')
        div.append(hr)

        # Append the race metadata.
        td = meta_table.cssselect('td:nth-child(3)')[0]
        race_meta = etree.Element('div')

        # race name
        h1 = etree.Element('h1')
        elts = td.cssselect('span')
        h1.text = elts[0].text
        race_meta.append(h1)
        race_meta.append(etree.Element('br'))

        # list by team
        race_meta.append(elts[1])
        race_meta.append(etree.Element('br'))

        # distance, race time, location
        race_meta.append(elts[2])
        div.append(race_meta)

        # Append the URL from whence we came..
        pdiv = etree.Element('div')
        pdiv.set('class', 'provenance')
        span = etree.Element('span')
        span.text = 'Results courtesy of '
        pdiv.append(span)
        anchor = etree.Element('a')
        anchor.set('href', 'http://www.nyrr.org')
        anchor.text = 'New York Road Runners'
        pdiv.append(anchor)
        span = etree.Element('span')
        span.text = '.'
        pdiv.append(span)
        div.append(pdiv)

        # The table we want is the 3rd one.  We need
        # to sanitize it, though.
        table = self.sanitize_table(results_table)
        div.append(table)
        return div

    def sanitize_table(self, old_table):
        """The table as-is has a few links that we need to remove.
        """
        new_table = etree.Element('table')
        new_table.set('cellpadding', '3')
        new_table.set('cellspacing', '0')
        new_table.set('border', '1')

        new_tr = etree.Element('tr')
        new_tr.set('bgcolor', '#EEEEEE')

        trs = old_table.getchildren()
        tr = trs[0]
        old_tds = tr.getchildren()

        # 1st two TD elements need to be replaced.
        td = etree.Element('td')
        td.text = old_tds[1].getchildren()[0].text
        new_tr.append(td)

        # 1st two TD elements need to be replaced.
        td = etree.Element('td')
        td.text = old_tds[2].getchildren()[0].text
        new_tr.append(td)

        # Append the rest of the TD elements in the first row.
        for td in old_tds[3:]:
            new_tr.append(td)
        new_table.append(new_tr)

        # And append the race results as-is.
        for tr in trs[1:]:
            new_table.append(tr)

        return(new_table)

    def download_file(self, url, params=None):
        """
        Download a URL to a local file.

        Parameters
        ----------
        url : str
            The URL to retrieve
        params : dict
            POST parameters to supply
        """
        # Store the url in case we need it later.
        self.downloaded_url = url

        # cookie support needed for NYRR results.
        if self.cookies is None:
            self.cookies = http.cookiejar.LWPCookieJar()
        cookie_processor = urllib.request.HTTPCookieProcessor(self.cookies)
        opener = urllib.request.build_opener(cookie_processor)
        urllib.request.install_opener(opener)

        req = urllib.request.Request(url)
        response = urllib.request.urlopen(req, params)
        html = response.readall()
        try:
            html = html.decode('utf-8')
        except UnicodeDecodeError:
            html = html.decode('latin1')

        return html
