import datetime
import logging
import os
import re
import urllib
import urllib2
import xml.etree.cElementTree as ET

from .common import RaceResults


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
        url = 'http://web2.nyrrc.org'
        url += '/cgi-bin/start.cgi/aes-programs/results/resultsarchive.htm'

        local_file = 'resultsarchive.html'
        self.download_file(url, local_file)

        # This is not valid HTML.  Need to get rid of some bad FORMs.
        html = open(local_file).read()
        html = html.replace('form','div')
        with open(local_file,'w') as f:
            f.write(html)

        self.local_tidy(local_file)

        # Parse out the list of "Most Recent Races".  They are all in a
        # particular table.
        tree = ET.parse(local_file)
        root = self.remove_namespace(tree.getroot())
        tables = root.findall('.//table')
        table = tables[5]

        # This is awful, all the entries are in a single table element.
        tds = table.findall('.//td')
        td = tds[0]
        links = [link for link in td.getchildren() if link.tag == 'a']

        if len(links) == 0:
            raise RuntimeError("No links found.  Please manually verify.")

        for link in links:
            url = link.get('href')
            race_name = re.sub('\n *', '', link.text)
            race_date = re.sub('\s', '', link.tail)
            race_date = datetime.datetime.strptime(race_date, "%m/%d/%y")
            race_date = datetime.date(race_date.year, race_date.month,
                    race_date.day)
            if self.start_date <= race_date and race_date <= self.stop_date: 
                self.logger.info("Keeping %s" % race_name)
                self.process_event(url)
            else:
                self.logger.info("Skipping %s" % race_name)


    def process_event(self, url):
        """
        We have the url of a single event.
        """
        local_file = 'race.html'
        self.download_file(url, local_file)
        self.local_tidy(local_file)

        # There should be a single form.
        tree = ET.parse(local_file)
        root = self.remove_namespace(tree.getroot())

        forms = root.findall('.//form')
        form = forms[0]

        url = form.get('action')

        # post parameters
        # search.method="Team"
        # items.display="500"
        post_params = {}
        post_params['search.method'] = 'search.team'
        post_params['input.lname'] = ''
        post_params['input.fname'] = ''
        post_params['input.bib'] = ''
        post_params['overalltype'] = 'All'
        post_params['input.agegroup.m'] = '12 to 19'
        post_params['input.agegroup.f'] = '12 to 19'
        #post_params['input.agegroup.m'] = ''
        #post_params['input.agegroup.f'] = ''
        #post_params['teamgender'] = 'All'
        post_params['teamgender'] = ''
        post_params['team_code'] = 'RARI'
        post_params['items.display'] = '500'
        post_params['AESTIVACVNLIST'] = 'overalltype,input.agegroup.m,input.agegroup.f,teamgender,team_code'
        params = urllib.urlencode(post_params)
        print(url)
        print(params)

        # method 1:  nope, get a 302 response
        #from httplib2 import Http
        #h = Http()
        #resp, contents = h.request(url, "POST", params)
        #print(contents)

        # method 2:  302 error
        #headers = {'User-Agent': self.user_agent}
        #req = urllib2.Request(url, None, headers)
        #response = urllib2.urlopen(req, params)
        #html = response.read()
        #with open('nyrrresult.html', 'wb') as f:
        #    f.write(html)


        # method 3:  cookies
        #opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        #urllib2.install_opener(opener)
        #headers = {'User-Agent': self.user_agent}
        #opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        #req = urllib2.Request(url, None, headers)
        #response = urllib2.urlopen(req, params)
        #html = response.read()
        #with open('nyrrresult.html', 'wb') as f:
        #    f.write(html)
        local_file = 'nyrrresult.html'
        self.download_file(url, local_file, params)
        self.local_tidy(local_file)


        #fmt = 'wget "%s" --output-document=nyrrresult.html --post-data="%s" -o /dev/null'
        #cmd = fmt % (url, params)
        #os.system(cmd)

        #fp = urllib.urlopen(url, params.encode('utf-8'))
        #x = fp.read()
        #open('raceresult.html','wb').write(x)
        


