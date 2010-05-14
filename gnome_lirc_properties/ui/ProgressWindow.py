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
Progress window related code.
'''

import gobject

from gettext import gettext as _

class ProgressWindow(object):
    '''
    A window for showing progress of lengthly operations.
    '''

    def __init__(self, builder):
        self.__window       = builder.get_object('progress_window')
        self.__label_title  = builder.get_object('label_progress_title')
        self.__label_detail = builder.get_object('label_progress_detail')
        self.__progressbar  = builder.get_object('progressbar')

    def show(self, parent, title, detail = None):
        '''
        Shows the progress window and updates the message it shows.
        '''

        self.title = title
        self.detail = detail or _('Preparing...')

        self.__window.set_transient_for(parent)
        self.__window.show()

    def hide(self):
        '''
        Hides the progress window.
        '''

        self.__window.hide()

    def update(self, progress, total, message):
        '''
        Updates progress bar and progress message.
        '''

        if total > 0:
            self.__progressbar.set_fraction(min(1.0, float(progress)/float(total)))
        else:
            self.__progressbar.pulse()

        self.__progressbar.set_text(message or '')

    def __get_title(self):
        '''
        Queries the current window title.
        '''

        return self.__label_title.get_text()

    def __set_title(self, title):
        '''
        Updates the current window title.
        '''

        markup = gobject.markup_escape_text(title)
        markup = '<big><b>%s</b></big>' % markup
        self.__label_title.set_markup(markup)

    def __get_detail(self):
        '''
        Queries the current detail text.
        '''

        return self.__label_detail.get_text()

    def __set_detail(self, detail):
        '''
        Updates the current detail text.
        '''

        self.__label_detail.set_text(detail)

    title = property(__get_title, __set_title)
    detail = property(__get_detail, __set_detail)

