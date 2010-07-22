#!/usr/bin/python
#
# Copyright (C) 2004 Gerome Fournier <jefke(at)free.fr>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

__author__ = 'Gerome Fournier <jefke(at)free.fr>'
__license__ = 'GPL'
__version__ = '0.1'
__revision__ = '$Id: grepurl,v 1.2 2004/10/28 19:01:02 jef Exp jef $'

import urlparse
import StringIO
import htmllib
import formatter
import threading
import Queue
import pycurl
import getopt
import sys
import re
import os

class HTTP:
    def __init__(self):
        self.curl = pycurl.Curl()
        self.curl.setopt(pycurl.FOLLOWLOCATION, 1)

    def get(self, url):
        file = StringIO.StringIO()
        self.curl.setopt(pycurl.WRITEFUNCTION, file.write)
        self.curl.setopt(pycurl.URL, url)
        try:
            self.curl.perform()
        except pycurl.error, reason:
            sys.stderr.write("Error getting '%s': %s\n" % (url, reason[1]))
            return None
        return file.getvalue()

    def last_fetched_url(self):
        return self.curl.getinfo(pycurl.EFFECTIVE_URL)

class FetchThreads:
    def __init__(self, urls, output_dir, max=5):
        self.queue = Queue.Queue()
        for url in urls:
            self.queue.put(url)
        self.output_dir = output_dir
        self.max = max

    def fetch_file(self, url):
        content = HTTP().get(url)
        if content != None:
            filename = self.url_to_filename(url)
            sys.stderr.write("Downloading %s as %s\n" % (url, filename))
            try:
                file=open(filename, "w")
                file.write(content)
                file.close()
            except IOError, reason:
                sys.stderr.write("Can't write '%s': %s\n" 
                        % (filename, reason[1]))

    def url_to_filename(self, url):
        base = self.output_dir + "/" 
        base += os.path.basename(urlparse.urlsplit(url)[2])
        filename = base
        i = 1
        try:
            while os.stat(filename):
                filename = "%s.%d" % (base, i)
                i += 1
        except OSError:
            return filename

    def handle_queue(self):
        while 1:
            try:
                url = self.queue.get(False)
            except Queue.Empty:
                break
            self.fetch_file(url)

    def run(self):
        threads = []
        for i in range(self.max):
            thread = threading.Thread(target=self.handle_queue)
            thread.start()
            threads.append(thread)
        for t in threads:
            t.join()
        
class GrepURLs(htmllib.HTMLParser):
    def __init__(self):
        self.handle_a = True
        self.handle_img = True
        self.regexp = None
        self.base_href = None
        self.urls = []
        self.output_dir = "."
        htmllib.HTMLParser.__init__(self, formatter.NullFormatter())

    def set_only_a(self):
        self.handle_a = True
        self.handle_img = False

    def set_only_img(self):
        self.handle_a = False
        self.handle_img = True

    def set_regexp(self, regexp):
        self.regexp = re.compile(regexp)

    def set_output_dir(self, dir):
        self.output_dir = dir

    def grep(self, urls):
        self.urls = []
        http = HTTP()
        for url in urls:
            content = http.get(url)
            self.base_href = http.last_fetched_url()
            if content != None:
                self.feed(content)

    def match(self, attrs, key):
        for attr in attrs:
            if attr[0] == key:
                if not self.regexp or self.regexp.search(attr[1]):
                    url = urlparse.urljoin(self.base_href, attr[1])
                    if url not in self.urls:
                        self.urls.append(url)
                        print url
                    break

    def start_a(self, attrs):
        if self.handle_a:
            self.match(attrs, "href")

    def do_img(self, attrs):
        if self.handle_img:
            self.match(attrs, "src")

    def download(self):
        fetch = FetchThreads(self.urls, self.output_dir)
        fetch.run()

def usage():
    sys.stderr.write("""\
Usage: %s [OPTION]... URL...
Grep URLs from a web page and eventually download the resources they point to.

Options:
  -h            display this help and exit
  -a            grep only URLs inside <a> tags
  -i            grep only URLs inside <img> tags
                (by default, both <a> and <img> tags are processed)
  -r <regexp>   return only URLs matching '<regexp>'
  -d            download resources
  -o <dir>      store downloaded resources inside '<dir>'
""" % sys.argv[0])

download = False
try:
    opts, args = getopt.getopt(sys.argv[1:], "hair:do:")
except getopt.GetoptError:
    usage()
    sys.exit(1)

grepurls = GrepURLs()
for flag, value in opts:
    if flag == '-h':
        usage()
        sys.exit(0)
    if flag == '-a':
        grepurls.set_only_a()
    if flag == '-i':
        grepurls.set_only_img()
    if flag == "-r":
        grepurls.set_regexp(value)
    if flag == "-d":
        download = True
    if flag == '-o':
        grepurls.set_output_dir(value)

if len(args) == 0:
    usage()
    sys.exit(1)

grepurls.grep(args)
if download:
    grepurls.download()
