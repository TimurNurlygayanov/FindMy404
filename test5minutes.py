#!/usr/bin/python3

# This script allows to check any website for most popular errors:
#  1) 404 / 500 error pages (done by full crawling of all links)
#  2) JS errors on pages (not implemented yet)
#  3) GET parameters validation and CSS attacks (will be done by fuzzing checks)
#
# Author: Timur Nurlygayanov
#
# How To Run:
#
#    pip3 install -U -r requirements.txt
#    python3 test5minutes.py
#

import requests
from requests.utils import requote_uri
import time
from uuid import uuid4

import asyncio
from aiohttp import ClientSession
from aiohttp import TCPConnector

from fake_useragent import UserAgent
from configparser import ConfigParser
from termcolor import colored

# Read crawling parameters from the config file:
config = ConfigParser()
config.read('config5.conf')

FOUND_ISSUES = dict()
IGNORE_LIST = []
LINKS = []  # set()
TOTAL_LIMIT = 100
ua = UserAgent()
headers = {'User-Agent': str(ua.chrome)}


def get_conf_param(section, parameter, default_value):
    """ This function reads parameters from the configuration file. """
    result = config.get(section, parameter)
    return result or default_value


async def fetch(url, session):
    """ This method gets HTML content of pages.

        Note: we are using Python3 coroutines here.
    """

    try:
        url_ = requote_uri(url['link'])
        async with session.get(url_, headers=headers) as response:
            return await response.read(), response.status, response.url, url['parent']
    except Exception as e:
        return url, e   # just send an empty data in case of any errors


async def bound_fetch(sem, url, session):
    # Getter function with semaphore.
    async with sem:
        return await fetch(url, session)


async def run(urls):
    """ This method starts the main loop of async threads. """

    async_tasks = []
    sem = asyncio.Semaphore(10000)

    # Create client session that will ensure we don't open new connection
    # per each request:
    async with ClientSession(connector=TCPConnector(ssl=False)) as session:
        for url in urls:
            async_task = asyncio.ensure_future(bound_fetch(sem, url, session))
            async_tasks.append(async_task)

        # Wait for all the results:
        return await asyncio.gather(*async_tasks, return_exceptions=False)


def parse_all_links(url):
    """ This function finds all the links on the page. """

    global LINKS
    global IGNORE_LIST

    try:
        res = requests.get(url, headers=headers)

        # Split page text to identify all links
        # (this is the faster way to get all the links):
        links_ = res.text.split('http')

        for link in links_:
            if link.startswith('s://') or link.startswith('://'):
                try:
                    # Get clear link:
                    clear_link = link.split('"')[0].split(' ')[0].\
                        split("'")[0].split('&quot;')[0].split(')')[0].\
                        split('</a>')[0].split(',')[0]

                    # Make sure this link is not in ignore list:
                    parse = True
                    for i in IGNORE_LIST:
                        if i in clear_link:
                            parse = False

                    # Check the link and add it to the list of parsed links:
                    if parse and len(clear_link) > 8 and \
                            not clear_link.endswith('.') and \
                            not clear_link.endswith('='):
                        # If the link is good - add this link to
                        # the list of all good links:

                        link_new = {'link': 'http' + clear_link,
                                    'parent': url}
                        if link_new not in LINKS:
                            LINKS.append({'link': 'http' + clear_link,
                                          'parent': url})
                except Exception as e:
                    print(e)
                    pass  # Just ignore any errors
    except:
        print(colored('Failed to parse:', 'yellow'), url)


def add_to_report(error_code, error_link):
    """ This function adds information about the problem to HTML report. """

    global FOUND_ISSUES

    # Group issues by the type of error:
    error_type = str(error_code)
    if error_type not in FOUND_ISSUES:
        FOUND_ISSUES[error_type] = []

    FOUND_ISSUES[error_type].append(error_link)


def generate_html_report(html_report_name='results.html'):
    """ This function creates HTML report with the list of all
        found issues.
    """

    global FOUND_ISSUES

    # Template for HTML report:
    html = """<html>
              <head><title> Crawler Report </title>
              
              <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script> 
              
              <script>
                function anichange (objName) {
                 if ( $(objName).css('display') == 'none' ) {
                     $(objName).animate({height: 'show'}, 400);
                 } else {
                     $(objName).animate({height: 'hide'}, 200);
                 }
                }
              </script>
              
              </head>
              <body>
    """

    for i in FOUND_ISSUES:
        error_id = 'my_bug' + str(uuid4())
        errors = FOUND_ISSUES[i]

        text = ''
        msg = '<p>URL: <a href="{0}">{0}</a></p><br>'
        for e in errors:
            text += msg.format(e)

        # Add hidden div with the list of wrong links:
        my_div = """ <br><br><hr><br>
                     <a href="#" onclick="anichange('#{0}'); return false">{1}</a>
                     <div id="{0}" style="display: none">
                         {2}
                     </div>
        """

        html += my_div.format(error_id, i, text)

    html += "</body></html>"

    # Write HTML report to file:
    with open(html_report_name, 'w') as f:
        f.write(html)


# Get parameters from config file:
main_domain = get_conf_param('DEFAULT', 'main_domain', '')
start_url = get_conf_param('DEFAULT', 'start_url', '')
IGNORE_LIST = get_conf_param('DEFAULT', 'ignore_urls', '').split('\n')
TOTAL_LIMIT = int(get_conf_param('DEFAULT', 'limit', 100))

# Start timer:
start_time = int(round(time.time()))

# Start to parse all the links from the first page:
LINKS.append({'link': start_url, 'parent': start_url})
parse_all_links(start_url)

# Parse all links from all crawled pages:
total = list(LINKS)
for k, link in enumerate(total):
    print('Collecting URLs... {0:0.0f} %'.format(100.0 * k / len(total)),
          end='\r')

    if main_domain in link['link']:
        parse_all_links(link['link'])

print("Found {0} links".format(len(LINKS)) + " "*20)

# Stop timer and show how fast all links were crawled:
end_time = int(round(time.time()))
print('URLs were crawled in {0} seconds'.format(end_time - start_time))

# Start timer again:
start_time = int(round(time.time()))

k = 0
crawler_results = []

# Start check status code of each crawled page
# Note: 20 parallel threads will do the job:
while k < len(LINKS):
    print('Checking... {0:0.0f} %'.format(100.0 * k / len(LINKS)),
          end='\r')

    urls = list(LINKS)[:TOTAL_LIMIT][k:k+20]
    k += 20

    # Start processing of each url in a separate async thread:
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(urls))
    crawler_results += loop.run_until_complete(future)

# Stop timer and calculate how fast we checked all the links:
end_time = int(round(time.time()))
print('TASK WAS DONE IN {0} SECONDS'.format(end_time - start_time))

# Print results count:
print('Results:', len(crawler_results))

# Print all found issues to console:
for r in crawler_results:
    if len(r) == 4:
        if int(r[1]) != 200:
            print(colored('NOT OK', 'red'), r[1], r[2], r[3])

            add_to_report(r[1], r[2])
    else:
        print(colored('NOT OK', 'red'), r[0], r[1])
        add_to_report(r[1], r[0])

# Generate and save HTML report:
generate_html_report('results_for_{0}.html'.format(main_domain))
