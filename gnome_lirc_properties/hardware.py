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
Hardware Abstraction Layer (HAL) related classes.
'''

import dbus
import gobject
import gtk.gdk
import logging
import os, os.path

from ConfigParser          import SafeConfigParser
from gettext               import gettext as _
from gnome_lirc_properties import lirc

HAL_SERVICE = 'org.freedesktop.Hal'
HAL_MANAGER_PATH = '/org/freedesktop/Hal/Manager'
HAL_MANAGER_IFACE = 'org.freedesktop.Hal.Manager'

class HalDevice(object):
    '''A device as announced by HAL.'''

    def __init__(self, bus, hal, udi):
        proxy_object = bus.get_object ('org.freedesktop.Hal', udi)
        self.__obj = dbus.Interface (proxy_object, 'org.freedesktop.Hal.Device')
        self.__hal = hal
        self.__bus = bus
        self.__udi = udi

        self.__capabilities = None

    def __getitem__(self, key):
        try:
            return self.__obj.GetProperty(key)

        except dbus.exceptions.DBusException, ex:
            if ('org.freedesktop.Hal.NoSuchProperty' == ex.get_dbus_name()):
                raise KeyError, key

            raise

    def get(self, key, default = None):
        '''
        Returns the value of the property described by key,
        or default if the property doesn't exist.
        '''
        try:
            return self.__obj.GetProperty(key)

        except dbus.exceptions.DBusException, ex:
            if ('org.freedesktop.Hal.NoSuchProperty' == ex.get_dbus_name()):
                return default

            raise

    def lookup_parent(self):
        '''Find the parent device of this device.'''
        return HalDevice(self.__bus, self.__hal, self['info.parent'])

    def find_children(self):
        '''Lists all child devices of this device.'''
        children = self.__hal.FindDeviceStringMatch('info.parent', self.__udi)
        return [HalDevice(self.__bus, self.__hal, udi) for udi in children]

    def check_kernel_module(self, kernel_module):
        '''Checks if the driver uses the specified kernel module.'''
        for device in self.find_children():
            if device.get('info.linux.driver') == kernel_module:
                return True

        return False

    def find_device_by_class(self, device_class):
        '''Find the LIRC device node associated with this device.'''
        class_root = os.path.join(os.sep, 'sys', 'class', device_class)
        sysfs_path = self['linux.sysfs_path']

        # the class root does not exist when no such driver is loaded:
        if not os.path.isdir(class_root):
            return None

        for device in os.listdir(class_root):
            try:
                # resolve the device link found in the sysfs folder:
                root = os.path.join(class_root, device)
                link = os.path.join(root, 'device')
                link = os.path.join(root, os.readlink(link))

                # compare the resolved link and its parent with the device path
                # stored in the 'linux.sysfs_path' property:
                while link:
                    if not os.path.samefile(sysfs_path, link):
                        link = os.path.dirname(link)
                        continue

                    for filename in (
                        os.path.join(os.sep, 'dev', device_class, device),
                        os.path.join(os.sep, 'dev', device),
                    ):
                        if os.path.exists(filename):
                            return filename

                    break

            except (IOError, OSError), ex:
                logging.warning(ex)

        return None

    def find_input_device(self):
        '''Find the Linux Input System device node associated with this device.'''
        for device in self.find_children():
            if device.get('info.category') == 'input':
                return device['input.device']

        return None

    def find_device_node(self, kernel_module, lirc_driver):
        '''Finds the device node associated with this device.'''

        if 'usbhid' == kernel_module:
            return self.find_device_by_class('usb')
        if 'default' == lirc_driver:
            return self.find_device_by_class('lirc')
        if lirc_driver in ('devinput', 'dev/input'):
            return self.find_input_device()

        return None

    def __get_capabilities(self):
        '''Query device capabilities as published in sysfs.'''

        if self.__capabilities is None:
            sysfs_path = self['linux.sysfs_path']
            caps_path = os.path.join(sysfs_path, '..', 'capabilities')
            self.__capabilities = dict()

            if os.path.isdir(caps_path):
                for name in os.listdir(caps_path):
                    caps = open(os.path.join(caps_path, name)).read()
                    caps = [int(value, 16) for value in caps.split()]
                    self.__capabilities[name] = tuple(caps)

        return self.__capabilities

    def __str__(self):
        return self.__udi
    def __repr__(self):
        return '<HalDevice: %s>' % self.__udi

    # pylint: disable-msg=W0212
    udi = property(fget=lambda self: self.__udi)
    capabilities = property(fget=__get_capabilities)

class HardwareDatabase(SafeConfigParser):
    '''Information about supported hardware.'''
    def __init__(self, filename):
        SafeConfigParser.__init__(self)
        self.read(filename)

class HardwareManager(gobject.GObject):
    '''This object provides hardware detection.'''

    __gsignals__ = {
        'search-progress': (
            gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_FLOAT, gobject.TYPE_STRING)),
        'search-finished': (
            gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            tuple()),
        'receiver-found': (
            gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_PYOBJECT, gobject.TYPE_STRING,
             gobject.TYPE_STRING)),

        'receiver-added': (
            gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_PYOBJECT, )),
        'receiver-removed': (
            gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_PYOBJECT, ))
    }

    def __init__(self, hardware_db):
        # pylint: disable-msg=E1002

        assert(isinstance(hardware_db, HardwareDatabase))

        super(HardwareManager, self).__init__()

        self.__devinput_receivers = dict()
        self.__search_canceled = False
        self.__device_count = 0.0
        self.__progress = 0.0

        self.__bus = dbus.SystemBus()
        self.__hal = self.__bus.get_object(HAL_SERVICE, HAL_MANAGER_PATH)
        self.__hal = dbus.Interface(self.__hal, HAL_MANAGER_IFACE)

        self.__hal.connect_to_signal('DeviceAdded', self._on_device_added)
        self.__hal.connect_to_signal('DeviceRemoved', self._on_device_removed)

        for udi in self.__hal.FindDeviceByCapability('input.keyboard'):
            self._on_device_added(udi)

        # reading hardware database, and reording as
        # dictionary with (product-id, vendor-id) keys
        self.__receivers = dict()

        for section in hardware_db.sections():
            vendor, product = [s.strip() for s in section.split(':', 1)]
            properties = dict(hardware_db.items(section))

            receiver = lirc.Receiver(vendor, product, **properties)

            if receiver.vendor_id:
                key = (receiver.vendor_id, receiver.product_id)

            elif receiver.kernel_module:
                key = receiver.kernel_module

            else:
                key = receiver.lirc_driver

            self.__receivers[key] = receiver

    def __get_devinput_receivers(self):
        '''List all currently known Input Device Layer receiver.'''
        return self.__devinput_receivers

    def _on_device_added(self, udi, sender=None):
        '''Handle addition of hot-plugable devices.'''

        device = self.lookup_device(udi)

        if 'input.keyboard' in device.get('info.capabilities', []):
            product_name = str(device['info.product'])
            device_node = str(device['input.device'])

            properties = {
                'compatible-remotes': 'linux-input-layer',
                'lirc-driver': 'devinput',
                'device': device_node,
                'udi': udi,
            }

            receiver = lirc.Receiver(_('Linux Input Device'),
                                     product_name, **properties)

            self.__devinput_receivers[udi] = receiver
            self.emit('receiver-added', receiver)

    def _on_device_removed(self, udi, sender=None):
        '''Handle removal of hot-plugable devices.'''

        receiver = self.__devinput_receivers.pop(udi, None)

        if receiver is not None:
            self.emit('receiver-removed', receiver)

    def resolve_device_nodes(self, nodes):
        '''Resolve the requested device nodes.'''
        device_nodes = list()

        for name in nodes:
            # Use HAL manager to find device nodes,
            # when name starts with "hal-capability:"
            if name.startswith('hal-capability:'):
                capability = name.split(':')[1]
                device_property = '%s.device' % capability.split('.')[0]

                # Find devices with requested capability:

                devices = [
                    self.lookup_device(udi)
                    for udi in self.__hal.FindDeviceByCapability(capability)]

                # Extract device node and product name for matching devices:

                devices = [(
                    device['info.product'],
                    device.get(device_property))
                    for device in devices]

                # Throw away devices without device node:

                device_nodes += [
                    (str(name), str(device))
                    for name, device in devices
                    if device is not None]

            elif name.startswith('numeric:'):
                device_nodes.append(name)

            # Otherwise check if name is an existing device node.
            elif os.path.isabs(name) and os.path.exists(name):
                device_nodes.append(name)

        # Ensure that each entry exists only once, and sort them.
        device_nodes = list(set(device_nodes))
        device_nodes.sort()

        return device_nodes

    @staticmethod
    def parse_numeric_device_node(device_node):
        '''
        Parses a numeric device node as used for describing for instance UDP
        receivers. Returns the tuple label, default-value, minimum-value,
        maximum-value.
        '''

        parts  = device_node.split(':', 4)
        limits = map(int, parts[1:4])
        label  = parts[4]

        return [label] + limits

    def __report_search_progress(self, product_name):
        '''Reports progress when searching supported devices.'''

        self._search_progress(self.__progress / self.__device_count,
                              product_name)

        logging.info('%d/%d: %s', self.__progress,
                     self.__device_count, product_name)

        self.__progress += 1.0

    def __find_usb_receivers(self, usb_devices):
        '''Find IR receivers connected via USB bus.'''

        for udi in usb_devices:
            # provide cancelation point:
            if self.__search_canceled:
                break

            # process GTK+ events:
            while gtk.events_pending():
                if gtk.main_iteration():
                    return

            # lookup the current device:
            device = self.lookup_device(udi)

            # lookup the USB devices in our hardware database:
            vendor_id = device.get('usb_device.vendor_id')
            product_id = device.get('usb_device.product_id')

            # skip USB devices that do not get sufficient power:
            if vendor_id is None or product_id is None:
                continue

            # report search progress:
            self.__report_search_progress('%s %s' % (device['info.vendor'],
                                                     device['info.product']))

            # Skip devices without vendor id. Linux for instance
            # doesn't assign a vendor id to USB host controllers.
            if not vendor_id:
                continue

            # The Streamzap really has a product ID of 0000,
            # so don't skip like this on empty product ids:
            #
            #   if not vendor_id or not product_id:
            #       continue
            #

            # lookup receiver description:
            receiver_key = (vendor_id, product_id)
            receiver = self.__receivers.get(receiver_key)

            # skip unknown hardware:
            if not receiver:
                continue

            # skip devices, where the associated kernel module
            # doesn't match the expected kernel module:
            if (receiver.kernel_module and
                not device.check_kernel_module(receiver.kernel_module)):
                continue

            # find the LIRC device node, and signal search result:
            device_node = device.find_device_node(receiver.kernel_module,
                                                  receiver.lirc_driver)

            self._receiver_found(receiver, device.udi, device_node)

    def __find_input_layer_receivers(self, input_devices):
        '''Find IR receivers implementing the Linux Input Layer interface.'''

        for device in input_devices:
            # provide cancelation point:
            if self.__search_canceled:
                break

            # process GTK+ events:
            while gtk.events_pending():
                if gtk.main_iteration():
                    return

            # lookup the current device:
            device = self.lookup_device(device)
            product_name = device.get('info.product')
            device_node = device.get('input.device')

            # report search progress:
            self.__report_search_progress(product_name)

            # skip input device that do not provide sufficient information:
            if product_name is None or device_node is None:
                continue

            # Skip input devices that seem to be keyboards. Currently keyboards
            # are detected by counting the number of supported keys. The original
            # PC keyboard had 85 keys, so maybe this is a reasonable boundary.
            # Maybe it would make more sense to look for typical key-codes
            # like SHIFT, CTRL, CAPSLOCK or NUMLOCK?
            keys = device.capabilities.get('key')

            if keys and len(decode_bitmap(keys)) >= 85:
                continue

            # report findings:
            receiver = self.devinput_receivers[device.udi]
            self._receiver_found(receiver, device.udi, device_node)

    def find_instance(self, receiver):
        '''Finds the device node associated with this receiver.'''

        for udi in self.__hal.FindDeviceStringMatch('info.subsystem', 'usb_device'):
            device = self.lookup_device(udi)

            if (device['usb_device.vendor_id'] == receiver.vendor_id and
                device['usb_device.product_id'] == receiver.product_id):
                return device.find_device_node(receiver.kernel_module,
                                               receiver.lirc_driver)

        return None

    def lookup_device(self, udi):
        '''Looks up the HAL device for that UDI.'''
        return HalDevice(self.__bus, self.__hal, udi)

    def search_receivers(self):
        '''
        Search for supported IR receivers. This search actually happens
        in a separate thread and can be aborted with the cancel() method.
        Connect to the signals of this object, to monitor search progress.

        TODO: Currently the search happens in the main thread, as DBus' Python
        bindings still cause random dead-locks when used with threads. Despite
        claiming being thread-safe.
        '''

        # retreive list of USB devices from HAL
        usb_devices = self.__hal.FindDeviceStringMatch('info.subsystem', 'usb_device')
        input_devices = self.__hal.FindDeviceByCapability('input.keyboard')

        self.__search_canceled = False
        self.__device_count = float(len(usb_devices) + len(input_devices))
        self.__progress = 0.0

        self.__find_usb_receivers(usb_devices)
        self.__find_input_layer_receivers(input_devices)

        self._search_finished()

    def _search_progress(self, progress, message, *args):
        '''Report search progress.'''

        # pylint: disable-msg=E1101
        self.emit('search-progress', progress, message % args)

    def _receiver_found(self, receiver, udi, device_node):
        '''Signal that a receiver was found.'''

        # pylint: disable-msg=E1101
        self.emit('receiver-found', receiver, udi, device_node)

    def _search_finished(self):
        '''Signal that search has finished.'''

        # pylint: disable-msg=E1101
        self.emit('search-finished')

    def cancel(self):
        '''Abort current search process.'''

        self.__search_canceled = True

    devinput_receivers = property(__get_devinput_receivers)

def decode_bitmap(bits):
    '''Decodes a bitmap as published in sysfs.'''

    values, offset = list(), 0

    for b in reversed(bits):
        values += [offset + i for i in range(32) if b & (1 << i)]
        offset += 32

    return tuple(values)
