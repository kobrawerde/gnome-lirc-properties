####
# 02/2006 Will Holcomb <wholcomb@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
"""
Usage:
  Enables the use of multipart/form-data for posting forms

Inspirations:
  Upload files in python:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/146306
  urllib2_file:
    Fabien Seisen: <fabien@seisen.org>

Example:
  import MultipartPostHandler, urllib2, cookielib

  cookies = cookielib.CookieJar()
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies),
                                MultipartPostHandler.MultipartPostHandler)
  params = { "username" : "bob", "password" : "riviera",
             "file" : open("filename", "rb") }
  opener.open("http://wwww.bobsite.com/upload/", params)

Further Example:
  The main function of this file is a sample which downloads a page and
  then uploads it to the W3C validator.
"""

import urllib
import urllib2
import mimetools, mimetypes
import os, sys

class MultipartPostHandler(urllib2.BaseHandler):
    """
    URL handler for posting multipart/form-data forms.
    """

    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

    def __init__(self):
        pass

    def http_request(self, request):
        """
        Handles a HTTP request.
        """

        data = request.get_data()

        if data is not None and type(data) != str:
            v_files = []
            v_vars = []

            try:
                for key, value in data.items():
                    if hasattr(value, 'read'):
                        v_files.append((key, value))

                    else:
                        v_vars.append((key, value))

            except TypeError:
                traceback = sys.exc_info()[2]
                raise TypeError, "not a valid non-string sequence or mapping object", traceback

            if len(v_files) == 0:
                data = urllib.urlencode(v_vars, True)

            else:
                boundary, data = self.multipart_encode(v_vars, v_files)
                content_type = 'multipart/form-data; boundary=%s' % boundary

                if (request.has_header('Content-Type') and
                    request.get_header('Content-Type').find('multipart/form-data') != 0):

                    print "Replacing %s with %s" % (
                        request.get_header('content-type'),
                        'multipart/form-data')

                request.add_unredirected_header('Content-Type', content_type)

            request.add_data(data)

        return request

    @staticmethod
    def multipart_encode(fields, files, boundary = None, output = None):
        """
        Encodes a multipart request body.
        """

        if boundary is None:
            boundary = mimetools.choose_boundary()

        if output is None:
            output = ''

        for key, value in fields:
            output += '--%s\r\n' % boundary
            output += 'Content-Disposition: form-data; name="%s"' % key
            output += '\r\n\r\n' + value + '\r\n'

        for key, fd in files:
            filename = os.path.basename(fd.name)

            content_type = (
                mimetypes.guess_type(filename)[0] or
                'application/octet-stream')

            output += '--%s\r\n' % boundary
            output += 'Content-Disposition: form-data; '
            output += 'name="%s"; ' % urllib.quote(key)
            output += 'filename="%s"\r\n' % urllib.quote(filename)
            output += 'Content-Type: %s\r\n' % content_type

            # file_size = os.fstat(fd.fileno())[stat.ST_SIZE]
            # output += 'Content-Length: %s\r\n' % file_size

            fd.seek(0)

            output += '\r\n' + fd.read() + '\r\n'

        output += '--%s--\r\n\r\n' % boundary

        return boundary, output

    https_request = http_request

def main():
    '''
    Entry point for testing this class.
    '''

    validator_url = "http://validator.w3.org/check"
    opener = urllib2.build_opener(MultipartPostHandler)

    def validate_file(url):
        '''
        Validates the specified page at the W3C validator.
        '''

        import tempfile

        temp = tempfile.mkstemp(suffix=".html")
        os.write(temp[0], opener.open(url).read())

        params = {
            "ss" : "0",            # show source
            "doctype" : "Inline",
            "uploaded_file" : open(temp[1], "rb"),
        }

        print opener.open(validator_url, params).read()
        os.remove(temp[1])

    if len(sys.argv[1:]) > 0:
        for arg in sys.argv[1:]:
            validate_file(arg)

    else:
        validate_file("http://www.google.com")

if __name__ == "__main__":
    main()
