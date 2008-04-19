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
Linux Standard Base (LSB) releated information.
'''

from ConfigParser import SafeConfigParser
from StringIO     import StringIO

import re

def version_number(text):
    '''Parses a version number and converts it into a tuple.'''

    return tuple([int(n, 10) for n in re.split(r'[^0-9]', text)])

class ReleaseInfo(object):
    '''LSB compliant distribution description.'''

    def __init__(self, filename=None, fileobj=None):
        lsb_section = 'LSB-Release'

        if not fileobj:
            fileobj = open(filename or '/etc/lsb-release')

        strbuf = StringIO()
        strbuf.write('[%s]\n' % lsb_section)
        strbuf.write(fileobj.read())
        strbuf.seek(0)

        parser = SafeConfigParser()
        parser.readfp(strbuf)

        self.__name = parser.get(lsb_section, 'DISTRIB_ID').strip('"')
        self.__release = parser.get(lsb_section, 'DISTRIB_RELEASE').strip('"')
        self.__codename = parser.get(lsb_section, 'DISTRIB_CODENAME').strip('"')
        self.__description = parser.get(lsb_section, 'DISTRIB_DESCRIPTION').strip('"')

    def check(self, name=None, codename=None, release=None):
        '''Checks if this Linux distribution matches certain criterions.'''

        if name is not None and name != self.name:
            return False

        if codename is not None and codename != self.codename:
            return False

        if release is not None:
            if version_number(release) > version_number(self.release):
                return False

        return True

    def __str__(self):
        return '%s (%s)' % (self.description, self.codename)

    # pylint: disable-msg=W0212
    name = property(lambda self: self.__name)
    release = property(lambda self: self.__release)
    codename = property(lambda self: self.__codename)
    description = property(lambda self: self.__description)

if '__main__' == __name__:
    print ReleaseInfo()
