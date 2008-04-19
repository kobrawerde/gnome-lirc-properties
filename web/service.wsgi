# WSGI script for hosting a database of infrared remote configurations
# Copyright (C) 2008 Openismus GmbH (www.openismus.com)
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
# Authors:
#   Mathias Hasselmann <mathias@openismus.com>
'''
WSGI script for hosting a database of infrared remote configurations
'''

import cgi, fcntl, httplib, os, rfc822, tarfile, time

from errno   import ENOENT
from gettext import gettext as _
from locale  import LC_ALL, setlocale
from sha     import sha as SHA1

class Context(dict):
    '''A WSGI request context.'''

    def __init__(self, environ):
        super(Context, self).__init__(environ)

    content_type   = property(lambda self: self['CONTENT_TYPE'])
    request_method = property(lambda self: self['REQUEST_METHOD'].upper())
    request_uri    = property(lambda self: self['REQUEST_URI'])
    path_info      = property(lambda self: self['PATH_INFO'])

    errors = property(lambda self: self['wsgi.errors'])
    input  = property(lambda self: self['wsgi.input'])

class Response(dict):
    '''Wrapper arround the various parts of a WSGI response.'''

    def __init__(self, status=httplib.OK,
                 content_type='text/html',
                 content=''):

        super(Response, self).__init__()

        self['Content-Type'] = content_type
        self.__output = [content]
        self.__status = status

    def __get_status(self):
        '''Query response status as tuple of status code and message.'''
        return self.__status, __responses__.get(self.__status, '')

    def __set_status(self, status):
        '''Update response status (code).'''
        self.__status = int(status)

    def __get_output(self):
        '''Access the list of response chunks.'''
        return self.__output

    status = property(fget=__get_status, fset=__set_status)
    output = property(fget=__get_output)

def find_request_handler(request_method, path_info, default=None):
    '''Finds the request handler for the current request.'''

    handler_id = '%s:%s' % (request_method, path_info)
    return __request_handlers__.get(handler_id, default)

def find_locale(locale, localedir='/usr/lib/locale'):
    '''Finds the name of the matching locallly installed locale.'''

    for name in '%s.utf8' % locale, locale, locale[:2]:
        ident = os.path.join(localedir, name, 'LC_IDENTIFICATION')

        if os.path.isfile(ident):
            return name

    return None

def html_page(context, status, title=None, message=None, *args):
    '''Creates a response that contains a HTML page.'''

    template = '''\
<html>
 <head>
  <title>%(title)s</title>
 </head>

 <body>
  <h1>%(title)s</h1>
  <p>%(message)s</p>
  <p>%(signature)s</p>
 </body>
</htm>'''

    if not title:
        title = __responses__[status]
    if not message:
        message = _('Request failed.')
    if args:
        message %= args

    return Response(
        status=status, content=template % dict(vars(),
        signature=context.get('SERVER_SIGNATURE', ''),
    ))

def redirect(context, path, status=httplib.SEE_OTHER):
    '''Creates a response that redirects to another page.'''

    response = html_page(context, status, None,
                         _('See: <a href="%(path)s">%(path)s</a>.') %
                         dict(path=cgi.escape(path)))

    response['Location'] = path

    return response

def not_found(context):
    '''Creates a response that handles missing pages.'''

    uri = context.request_uri

    if not uri.endswith('/'):
        fallback = find_request_handler(context.request_method,
                                        context.path_info + '/')

        if fallback:
            return redirect(context, uri + '/')

    return html_page(context, httplib.NOT_FOUND,
                     _('Resource Not Found'),
                     _('Cannot find this resource: <b>%s</b>.'),
                     cgi.escape(uri))

def show_upload_form(context):
    '''Shows the HTML form for uploading LIRC configuration files.'''

    template = '''\
<html>
 <head>
  <title>%(title)s</title>
 </head>

 <body>
  <h1>%(title)s</h1>

  <form action="upload/" method="post" enctype="multipart/form-data">
   <table>
    <tr>
     <td>Configuration File:</td>
     <td><input name="config" type="file" size="40" value="/etc/lirc/lircd.conf"/></td>
    </tr>

    <tr>
     <td>SHA1 Digest:</td>
     <td><input name="digest" type="text" size="40" maxlength="40" /></td>
    </tr>

    <tr>
     <td>Language:</td>
     <td>
      <select name="locale">
       <option value="en_US">English</option>
       <option value="de_DE">German</option>
      </select>
    </tr>

    <tr>
     <td colspan="2" align="right">
      <button>Upload</button>
     </td>
    </tr>
   </table>
  </form>

  <p>Download <a href="%(dburi)s">current archive</a>.</p>
  <p>%(signature)s</p>
 </body>
</html>'''

    return Response(content=template % dict(
        signature=context.get('SERVER_SIGNATURE', ''),
        title='Upload LIRC Remote Control Configuration',
        dburi='remotes.tar.gz',
    ))

def process_upload(context):
    '''Processes an uploaded LIRC configuration file.'''

    # pylint: disable-msg=R0911

    form = cgi.FieldStorage(fp=context.input, environ=context)

    digest, config, locale = [
        form.has_key(key) and form[key]
        for key in ('digest', 'config', 'locale')]

    locale = locale is not False and find_locale(locale.value)

    if locale:
        setlocale(LC_ALL, locale)

    # validate request body:

    if form.type != 'multipart/form-data':
        return html_page(context, httplib.BAD_REQUEST, None,
                         _('Request has unexpected content type.'))

    if form.type != digest is False or config is False or locale is False:
        return html_page(context, httplib.BAD_REQUEST, None,
                         _('Some fields are missing in this request.'))

    if digest.value != SHA1(config.value).hexdigest():
        return html_page(context, httplib.BAD_REQUEST, None,
                         _('Checksum doesn\'t match the uploaded content.'))

    # process request body:

    workdir  = os.path.dirname(__file__)
    archive  = os.path.join(workdir, 'archive', 'remotes.tar.gz')
    filename = os.path.join(workdir, 'archive', 'incoming', '%s.conf' % digest.value)

    try:
        # force rebuild by removing the obsolete archive:
        os.unlink(archive)

    except OSError, ex:
        if ENOENT != ex.errno:
            return html_page(context, httplib.INTERNAL_SERVER_ERROR, None,
                             _('Cannot remove obsolete remotes archive: %s.'),
                             ex.strerror)

    # store the uploaded configuration file in the incoming folder:
    try:
        storage = open(filename, 'wb')

    except IOError, ex:
        return html_page(context, httplib.INTERNAL_SERVER_ERROR, None,
                         _('Cannot store configuration file: %s.'),
                         ex.strerror)

    try:
        fcntl.lockf(storage, fcntl.LOCK_EX)

    except IOError, ex:
        return html_page(context, httplib.INTERNAL_SERVER_ERROR, None,
                         _('Cannot get exclusive file access: %s.'),
                         ex.strerror)

    storage.write(config.file.read())
    storage.close()

    # use POST/REDIRECT/GET pattern to avoid duplicate uploads:
    return redirect(context, context.request_uri + 'success')

def show_upload_success(context):
    '''Shows success message after upload'''

    return html_page(context, httplib.OK, _('Upload Succeeded'),
                     _('Upload of your configuration file succeeded. '
                       'Thanks alot for contributing.'))

def send_archive(context, filename, must_exist=False):
    '''Sends the specified tarball.'''

    try:
        # Checks last-modified time, when requested:
        reference_time = context.get('HTTP_IF_MODIFIED_SINCE')

        if reference_time:
            reference_time = rfc822.parsedate(reference_time)
            reference_time = time.mktime(reference_time)

            if reference_time >= os.path.getmtime(filename):
                return Response(httplib.NOT_MODIFIED)

        # Deliver the file with checksum and last-modified header:
        response = Response(content_type='application/x-gzip',
                            content=open(filename, 'rb').read())

        digest = SHA1(response.output[0]).hexdigest()
        timestamp = time.ctime(os.path.getmtime(filename))

        response['X-Checksum-Sha1'] = digest
        response['Last-Modified'] = timestamp

        return response

    except (IOError, OSError), ex:
        if must_exist or ENOENT != ex.errno:
            return html_page(context,
                             httplib.INTERNAL_SERVER_ERROR, None,
                             _('Cannot read remotes archive: %s.'),
                             ex.strerror)

        return None

def send_remotes_archive(context):
    '''Sends the archive with uploaded LIRC configuration files.'''

    archive_root  = os.path.join(os.path.dirname(__file__), 'archive')
    archive_name = os.path.join(archive_root, 'remotes.tar.gz')

    response = send_archive(context, archive_name)

    if not response:
        try:
            archive = tarfile.open(archive_name, 'w:gz')

        except IOError, ex:
            return html_page(context, httplib.INTERNAL_SERVER_ERROR, None,
                             _('Cannot create remotes archive: %s.'),
                             ex.strerror)

        try:
            # pylint: disable-msg=W0612
            for path, subdirs, files in os.walk(archive_root):
                # drop folders with SCM meta-information:
                subdirs[:] = [name for name in subdirs if
                              not name.startswith('.')
                              and name != 'CVS']

                # drop archive_root from current folder name:
                dirname = path[len(archive_root):]

                # scan files in current folder:
                for name in files:
                    if name.startswith('.'):
                        continue

                    filename = os.path.join(path, name)
                    arcname = os.path.join(dirname, name)

                    if filename == archive_name:
                        continue

                    info = archive.gettarinfo(filename, arcname)
                    archive.addfile(info, open(filename))

            # Trigger finalization of the tarball instance,
            # since Python 2.4 doesn't create its file otherwise:
            archive.close()
            del archive

            response = send_archive(context, archive_name, must_exist=True)

        except:
            try:
                # Try to remove artifacts on error:
                os.unlink(archive.name)

            except:
                pass

            raise

    return response

def application(environ, start_response):
    '''The WSGI entry point of this service.'''

    context, response = Context(environ), None

    try:
        handler = find_request_handler(context.request_method,
                                       context.path_info,
                                       not_found)
        response = handler(context)

    except:
        import traceback

        response = Response(content_type='text/plain',
                            content=traceback.format_exc(),
                            status=httplib.INTERNAL_SERVER_ERROR)

        traceback.print_exc(context.errors)

    if (not response.has_key('Content-Length') and
        response.get('Transfer-Encoding', '').lower() != 'chunked'):
        response['Content-Length'] = str(len(''.join(response.output)))

    start_response('%d %s' % response.status, response.items())

    return response.output

# Map status codes to official W3C names (from httplib/2.5):
__responses__ = {
    100: 'Continue',
    101: 'Switching Protocols',

    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',

    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    306: '(Unused)',
    307: 'Temporary Redirect',

    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',

    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
}

# Mapping request paths to request handlers:
__request_handlers__ = {
    'GET:/remotes.tar.gz': send_remotes_archive,
    'GET:/upload/success': show_upload_success,
    'GET:/':               show_upload_form,

    'POST:/upload/':       process_upload,
}


# pylint: disable-msg=W0702,W0704
# vim: ft=python
