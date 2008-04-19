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
PolicyKit related services.
'''

import dbus, logging, os

from gnome_lirc_properties import config

class PolicyKitAuthentication(object):
    '''
    Obtains sudo/root access,
    asking the user for authentication if necessary,
    using PolicyKit
    '''

    def is_authorized(self, action_id=config.POLICY_KIT_ACTION):
        '''
        Ask PolicyKit whether we are already authorized.
        '''

        if not config.ENABLE_POLICY_KIT:
            return True

        # Check whether the process is authorized:
        pid = dbus.UInt32(os.getpid())
        authorized = self.policy_kit.IsProcessAuthorized(action_id, pid, False)
        logging.debug('%s: authorized=%r', action_id, authorized)

        return ('no' != authorized)

    def obtain_authorization(self, widget, action_id=config.POLICY_KIT_ACTION):
        '''
        Try to obtain authoriztation for the specified action.
        '''

        if not config.ENABLE_POLICY_KIT:
            return True

        xid = (widget and widget.get_toplevel().window.xid or 0)
        xid, pid = dbus.UInt32(xid), dbus.UInt32(os.getpid())

        granted = self.auth_agent.ObtainAuthorization(action_id, xid, pid)
        logging.debug('%s: granted=%r', action_id, granted)

        return bool(granted)

    def __get_policy_kit(self):
        '''Retreive the D-Bus interface of PolicyKit.'''

        # retreiving the interface raises DBusException on error:
        service = dbus.SystemBus().get_object('org.freedesktop.PolicyKit', '/')
        return dbus.Interface(service, 'org.freedesktop.PolicyKit')

    def __get_auth_agent(self):
        '''Retreive the D-Bus interface of the PolicyKit authentication agent.'''

        # retreiving the interface raises DBusException on error:
        return dbus.SessionBus().get_object(
            'org.freedesktop.PolicyKit.AuthenticationAgent', '/',
            'org.gnome.PolicyKit.AuthorizationManager.SingleInstance')

    auth_agent = property(__get_auth_agent)
    policy_kit = property(__get_policy_kit)
