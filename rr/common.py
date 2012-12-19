"""
Collection of common routines used by all the other codes.
"""
import collections
import csv
import pkg_resources
import re
import sys
if sys.hexversion < 0x03000000:
    import urllib2
else: 
    import urllib.request
import xml.dom.minidom

import tidy

def download_file(url, local_file):
    """Download a URL to a local file."""
    if sys.hexversion < 0x03000000:
        with open(local_file, 'wb') as f:
            req = urllib2.urlopen(url)
            html = req.read()
            f.write(html)
            f.close()
    else:
        urllib.request.urlretrieve(url,local_file)

def pretty_print_xml(xml_file):
    """
    Taken from StackOverflow
    """
    xml_string = xml.dom.minidom.parse(xml_file)
    pp_string = xml_string.toprettyxml()
    fp = open(xml_file,'w')
    fp.write(pp_string)
    fp.close()


def local_tidy(html_file):
    """ 
    Tidy up the HTML.
    """
    options = dict(output_xhtml=1, 
            add_xml_decl=1, 
            indent=1,
            numeric_entities=True, 
            drop_proprietary_attributes=True, 
            bare=True,
            word_2000=True, 
            tidy_mark=1, 
            hide_comments=True,
            new_inline_tags='fb:like')
    fp = open(html_file)
    html = fp.read()
    fp.close()
    thtml = tidy.parseString(html,**options)

    fp = open(html_file,'w')
    thtml.write(fp)
    fp.close()


def remove_namespace(doc): 
    """Remove namespace in the passed document in place.""" 
    # We seem to need this for all element searches now.
    xmlns = 'http://www.w3.org/1999/xhtml'

    namespace = '{%s}' % xmlns 
    nsl = len(namespace) 
    for elem in doc.getiterator(): 
        if elem.tag.startswith(namespace): 
            elem.tag = elem.tag[nsl:]

    return(doc)

def parse_membership_list(membership_list):
    """
    Assume a comma-delimited membership list, last name first,
    followed by the first name.

    Doe,Jane, ...
    Smith,Joe, ...
    """

    mlreader = csv.reader(open(membership_list,'r'))
    first_name = []
    first_name_regex = []
    last_name = []
    last_name_regex = []
    for row in mlreader:
        fname = row[0]
        lname = row[1]
        first_name.append(fname)
        last_name.append(lname)

    FirstLast = collections.namedtuple('FirstLastName', ['first', 'last'])
    names = FirstLast(first=first_name, last=last_name)
    return names
