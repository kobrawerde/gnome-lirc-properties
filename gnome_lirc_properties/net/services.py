# Infrared Remote Control Properties for GNOME
# Copyright (C) 2008 Fluendo Embedded S.L. (www.fluendo.com)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
'''
Download and update services.
'''

import gobject, httplib, locale, logging
import md5, os, re, rfc822, sha, time, urllib2

from gettext   import gettext as _
from StringIO  import StringIO
from tempfile  import NamedTemporaryFile
from threading import Thread

from gnome_lirc_properties.net.MultipartPostHandler import MultipartPostHandler

__re_html_response__ = re.compile(r'<h1>(.*?)</h1>\s*<p>(.*?)</p>', re.DOTALL)

class NetworkError(Exception):
    '''Exception for network related problems.'''

    def __init__(self, context, cause):
        self.details = self.extract_details(cause)
        self.context = context
        self.cause = cause

        if self.details:
            message = '%s: %s.' % (context, self.details)

        else:
            message = '%s.' % context

        super(NetworkError, self).__init__(message)

    @staticmethod
    def extract_details(ex):
        '''Extract error details from various network related exception types.'''

        if isinstance(ex, urllib2.HTTPError):
            return (extract_html_message(ex) or ex.msg)

        if isinstance(ex, urllib2.URLError):
            from socket import gaierror

            if isinstance(ex.reason, gaierror):
                return ex.reason[1]

            return _('Cannot resolve host name.')

        return getattr(ex, 'message', None)

def report(callback, *args, **kwargs):
    '''Invokes the callback in within the main-thread.'''

    if callback:
        gobject.idle_add(lambda: callback(*args, **kwargs) and False)

def extract_html_message(response):
    '''Extracts the first paragraph of a HTML document.'''

    match = __re_html_response__.search(response.read())
    return match and match.group(2)

# pylint: disable-msg=R0913
def post_file(target_uri, filename,
              context, content=None,
              finished_callback=None,
              failure_callback=logging.error):
    '''Uploads a certain file to some web service.'''
    # TODO: Maybe use GObject signals instead of callbacks.

    if content is None:
        fileobj = open(filename, 'rb')

    else:
        fileobj = StringIO(content)
        setattr(fileobj, 'name', filename)

    params = {
        'config': fileobj,
        'digest': sha.new(fileobj.read()).hexdigest(),
        'locale': locale.setlocale(locale.LC_MESSAGES, None),
    }

    fileobj.seek(0)

    # We use a custom OpenerDirector, instead of just using urllib2.openurl(),
    # so we can specify handlers to use our cookies store, and multipart posts:
    multipart_opener = urllib2.build_opener(MultipartPostHandler)

    # Passing a request body makes this a POST instead of a GET request:

    try:
        response = multipart_opener.open(target_uri, params)

        if finished_callback:
            finished_callback(extract_html_message(response) or
                              (_('Upload of %s succeeded.') % context))

    except urllib2.HTTPError, ex:
        logging.error("post_file(): target_uri=%s, HTTPError exception: code=%d, message=%s\n" % (target_uri, ex.code, ex.message))
        if failure_callback:
            error = NetworkError(_('Upload of %s failed') % context, ex)
            failure_callback(error.message)
  
    except (urllib2.URLError, httplib.HTTPException), ex:
        # Note: When this catches an httplib.BadStatusLine, the ex.message is empty:
        logging.error("post_file(): target_uri=%s, exception: type=%s, message=%s\n" % (target_uri, type(ex), ex.message))
        if failure_callback:
            error = NetworkError(_('Upload of %s failed') % context, ex)
            failure_callback(error.message)

class RetrieveTarballThread(Thread):
    '''Worker thread for retrieving tarballs.'''

    def __init__(self, tarball_uri, checksum_uri=None):
        super(RetrieveTarballThread, self).__init__()

        last_slash = tarball_uri.rindex('/')
        self.__basename = tarball_uri[last_slash + 1:]
        self.__baseuri = tarball_uri[:last_slash + 1]

        if not checksum_uri:
            dot = self.__basename.index('.')
            checksum_uri = self.__baseuri + self.__basename[:dot] + '.md5sum'

        self.__tarball_uri  = tarball_uri
        self.__checksum_uri = checksum_uri
        self.__action_label = None
        self.__tempfile = None

        self.on_progress    = None
        self.on_success     = None
        self.on_failure     = logging.error
        self.reference_time = None

    def _retrieve(self, request, target=None):
        '''Reads from a file-like object, and reports progress to the main thread.
           This can throw: urllib2.HTTPError, urllib2.URLError, httplib.HTTPException
        '''

        response = urllib2.urlopen(request)
        headers = response.info()

        if target is None:
            target = StringIO()

        if self.on_progress is None:
            target.write(response.read())

        else:
            file_size = int(headers.get('content-length', '-1'))
            offset = 0

            while True:
                chunk = response.read(8192)

                if not chunk:
                    break

                offset += len(chunk)
                target.write(chunk)

                report(self.on_progress, offset, file_size, self.__action_label)

                from time import sleep
                sleep(0.1)

        target.seek(0)

        return target, headers

    def _retrieve_checksum(self):
        '''Retrieves the checksum file associated with the tarball.'''

        try:
            self.__action_label = _('Downloading checksum list...')
            content, headers = self._retrieve(self.__checksum_uri)

        except urllib2.HTTPError, ex:
            logging.error("RetrieveTarballThread._retrieve_checksum(): _retrieve() threw HTTPError exception: code=%d, message=%s\n" % (ex.code, ex.message))
            raise NetworkError(_('Cannot retrieve checksum list.'), ex)
        except (urllib2.URLError, httplib.HTTPException), ex:
            # Note: When this catches an httplib.BadStatusLine, the ex.message is empty:
            logging.error("RetrieveTarballThread._retrieve_checksum(): _retrieve() threw exception: type=%s, message=%s\n" % (type(ex), ex.message))
            raise NetworkError(_('Cannot retrieve checksum list.'), ex)

        if headers is None:
            raise NetworkError(_('Cannot retrieve checksum list.'),
                               _('Empty headers.'))

        if 'text/plain' != headers['content-type']:
            raise NetworkError(_('Cannot retrieve checksum list.'),
                               _('Unexpected content type.'))

        if content is None:
            raise NetworkError(_('Cannot retrieve checksum list.'),
                               _('Empty content.'))

        checksums = dict([
            reversed(line.rstrip().split('  '))
            for line in content.readlines()])

        return checksums.get(self.__basename)

    def _retrieve_archive(self):
        '''Retrieves the file archive.'''

        try:
            self.__action_label = _('Downloading file archive...')

            logging.info("RetrieveTarballThread._retrieve_archive(): calling urllib2.Request() with __tarball_uri=%s\n" % self.__tarball_uri)
            request = urllib2.Request(self.__tarball_uri)
            logging.info("RetrieveTarballThread._retrieve_archive(): __tarball_uri=%s, urllib2.Request() was successful.\n" % self.__tarball_uri)

            if self.reference_time is not None:
                timestamp = time.ctime(self.reference_time)
                request.add_header('If-Modified-Since', timestamp)

            self.__tempfile = NamedTemporaryFile(prefix='remote-updates-', suffix='.tar.gz')
            logging.info("RetrieveTarballThread._retrieve_archive(): calling retrieve() with tempfile.\n")
            return self._retrieve(request, target=self.__tempfile)

        except urllib2.HTTPError, ex:
            if httplib.NOT_MODIFIED != ex.code:
                logging.error("RetrieveTarballThread._retrieve_archive(): __tarball_uri=%s, exception: type=%s, message=%s\n" % (self.__tarball_uri, type(ex), ex.message))
                raise NetworkError(_('Cannot retrieve file archive'), ex)

            elif self.on_success:
                report(self.on_success, ex, ex.info())

        except urllib2.URLError, ex:
            logging.error("RetrieveTarballThread._retrieve_archive(): __tarball_uri=%s, exception: type=%s, message=%s\n" % (self.__tarball_uri, type(ex), ex.message))    
            raise NetworkError(_('Cannot retrieve file archive.'), ex)

        except httplib.HTTPException, ex:
            # Note: When this catches an httplib.BadStatusLine, the ex.message is empty:
            logging.error("RetrieveTarballThread._retrieve_archive(): __tarball_uri=%s, exception: type=%s, message=%s\n" % (self.__tarball_uri, type(ex), ex.message))
            raise NetworkError(_('Cannot retrieve file archive.'), ex)

        return None, None

    def run(self):
        '''Entry point of the worker thread.'''

        try:
            # Retrieve the file archive:
            content, headers = self._retrieve_archive()

            if content is None:
                return True

            if headers is None:
                return False

            # Update last-modified timestamp from response header:
            timestamp = headers.get('last-modified')

            if timestamp:
                timestamp = time.mktime(rfc822.parsedate(timestamp))
                os.utime(self.__tempfile.name, (timestamp, timestamp))

            # Check that the file's content matches the provided checksum:
            return self._verify_checksum(content, headers)

        except NetworkError, ex:
            report(self.on_failure, ex.message)
            if ex.cause:
                logging.error("NetworkError: %s\n", ex.cause.message)

            return False

    def _verify_checksum(self, content, headers):
        '''Check that the file's content matches the provided checksum.'''

        expected_checksum = headers.get('x-checksum-sha1')

        if expected_checksum is None:
            expected_checksum = self._retrieve_checksum()
        if expected_checksum is None:
            report(self.on_failure, _('Checksum for %s not found.') % self.__basename)

        if expected_checksum:
            checksum_algorithm = {32: md5, 40: sha}[len(expected_checksum)]
            checksum = checksum_algorithm.new(content.read())

            content.seek(0)

            if checksum.hexdigest() == expected_checksum:
                report(self.on_success, content, headers)
                return True

        report(self.on_failure, _('Checksum for %s doesn\'t match.') % self.__basename)
        return False

# pylint: disable-msg=R0913
def retrieve_tarball(tarball_uri,
                     checksum_uri=None,
                     reference_time=None,
                     progress_callback=None,
                     success_callback=None,
                     failure_callback=logging.error):
    '''Downloads a certain tarball from the internet.'''
    # TODO: Maybe use GObject signals instead of callbacks.

    worker = RetrieveTarballThread(tarball_uri, checksum_uri)

    worker.on_progress = progress_callback
    worker.on_success  = success_callback
    worker.on_failure  = failure_callback

    if reference_time is not None:
        worker.reference_time = reference_time

    worker.start()

__all__ = 'post_file', 'retrieve_tarball'

