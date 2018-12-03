#!/usr/bin/python3

import requests
from requests.utils import requote_uri
import time

import asyncio
from aiohttp import ClientSession
from aiohttp import TCPConnector

from fake_useragent import UserAgent

from configparser import ConfigParser

from termcolor import colored


config = ConfigParser()
config.read('config5.conf')

IGNORE_LIST = []
LINKS = set()
ua = UserAgent()
headers = {'User-Agent': str(ua.chrome)}


def get_conf_param(section, parameter, default_value):
    result = config.get(section, parameter)
    return result or default_value


async def fetch(url, session):
    """ This method gets HTML content of pages. """

    try:
        async with session.get(url, headers=headers) as response:
            return await response.read(), response.status, response.url
    except Exception as e:
        return url, e   # just send an empty data in case of any errors


async def bound_fetch(sem, url, session):
    # Getter function with semaphore.
    async with sem:
        return await fetch(url, session)


async def run(urls):
    """ This method starts the main loop of async threads. """

    async_tasks = []
    # Create instance of Semaphore
    sem = asyncio.Semaphore(10000)

    # Create client session that will ensure we don't open new connection
    # per each request:
    async with ClientSession(connector=TCPConnector(ssl=False)) as session:
        for url in urls:
            # pass Semaphore and session to every GET request
            url = requote_uri(url)
            async_task = asyncio.ensure_future(bound_fetch(sem, url, session))
            async_tasks.append(async_task)

        # wait for all the results:
        return await asyncio.gather(*async_tasks, return_exceptions=False)


def parse_all_links(url):
    global LINKS
    global IGNORE_LIST

    try:
        res = requests.get(url, headers=headers)
        text = res.text

        links = text.split('http')

        for link in links:
            if link.startswith('s://') or link.startswith('://'):
                try:
                    clear_link = link.split('"')[0].split(' ')[0].\
                        split("'")[0].split('&quot;')[0].split(')')[0].\
                        split('</a>')[0]

                    parse = True
                    for i in IGNORE_LIST:
                        if i in clear_link:
                            parse = False

                    if parse and len(clear_link) > 8 and \
                            not clear_link.endswith('.'):
                        LINKS.add('http' + clear_link)

                except Exception as e:
                    # print(e)
                    pass
    except:
        print(colored('Failed to parse:', 'yellow'), url)



main_domain = get_conf_param('DEFAULT', 'main_domain', '')
start_url = get_conf_param('DEFAULT', 'start_url', '')
IGNORE_LIST = get_conf_param('DEFAULT', 'ignore_urls', '').split('\n')

start_time = int(round(time.time()))

LINKS.add(start_url)
parse_all_links(start_url)

total = list(LINKS)
for k, link in enumerate(total):
    print('Collecting URLs... {0:0.0f} %'.format(100.0 * k / len(total)), end='\r')

    if main_domain in link:
        parse_all_links(link)

print("Found {0} links".format(len(LINKS)))


end_time = int(round(time.time()))
print('URLs were crawled in {0} seconds'.format(end_time - start_time))


start_time = int(round(time.time()))


k = 0
crawler_results = []

while k < len(LINKS):
    print('Checking... {0:0.0f} %'.format(100.0 * k / len(LINKS)),
          end='\r')

    urls = list(LINKS)[k:k+20]
    k += 20

    # Start processing of each url in a separate async thread:
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(urls))
    crawler_results += loop.run_until_complete(future)


end_time = int(round(time.time()))
print('TASK WAS DONE IN {0} SECONDS'.format(end_time - start_time))


print('Results:', len(crawler_results))

for r in crawler_results:

    if len(r) == 3:
        if int(r[1]) != 200:
            print(colored('NOT OK', 'red'), r[1], r[2])
    else:
        print(colored('NOT OK', 'red'), r[0], r[1])
