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
The main window of the application.
'''

import dbus, errno, gobject, gtk, gtk.gdk, gtk.glade, pango
import httplib, locale, logging, os, subprocess

from gettext               import gettext as _
from gnome_lirc_properties import backend, config, lirc, model, hardware, policykit, net

from gnome_lirc_properties.ui.common                import show_message, thread_callback
from gnome_lirc_properties.ui.CustomConfiguration   import CustomConfiguration
from gnome_lirc_properties.ui.ProgressWindow        import ProgressWindow
from gnome_lirc_properties.ui.ReceiverChooserDialog import ReceiverChooserDialog

class RemoteControlProperties(object):
    '''The main window.'''

    def __init__(self, glade_xml):
        # Prevent UI changes from being written back to configuration files:
        #
        # Configuration files only are written when this field is zero.
        # Negative values completely lock this field. Non-negative values can
        # be modified with paired(!) calls to _begin_update_configuration()
        # and end_update_configuration().
        self.__configuration_level = -1

        # Initialize models and views.
        self.__ui = glade_xml
        self.__ui.signal_autoconnect(self)

        self.__custom_configuration = None
        self.__receiver_chooser = None
        self.__lookup_widgets()

        self.__setup_models()
        self.__setup_key_listener()
        self.__setup_product_lists()
        self.__setup_authorization()
        self.__setup_size_groups()

        # Look in the configuration to show previously-chosen details:
        self.__restore_hardware_settings()

        # Allow UI changes from being written back to configuration files:
        self.__configuration_level = 0

    def __setup_models(self):
        '''Initialize model objects of the dialog.'''

        # pylint: disable-msg=W0201,E1101

        receivers_db = hardware.HardwareDatabase(self.__ui.relative_file('receivers.conf'))
        self.__remotes_db = lirc.RemotesDatabase()

        self.__hardware_manager = hardware.HardwareManager(receivers_db)
        self.__hardware_manager.connect('search-progress', self._on_search_progress)
        self.__hardware_manager.connect('search-finished', self._on_search_finished)
        self.__hardware_manager.connect('receiver-found',  self._on_receiver_found)

        self.__receiver_vendors = model.ReceiverVendorList(self.__hardware_manager)
        self.__receiver_vendors.load(receivers_db)

        self.__remote_vendors = model.RemoteVendorList()
        self.__update_remotes_db()

    def __update_remotes_db(self):
        '''Fills the database of remote controls with information.'''

        was_using_supplied = self.use_supplied_remote
        selected_remote = self.selected_remote

        self.__remotes_db.clear()
        self.__remotes_db.load(self.__ui.relative_file('linux-input-layer-lircd.conf'))
        self.__remotes_db.load_folder()
        self.__remotes_db.load_tarball()

        self.__remote_vendors.clear()
        self.__remote_vendors.load(self.__remotes_db)

        if 0 == self.__configuration_level:
            # pylint: disable-msg=E1103

            self.selected_remote = (
                (was_using_supplied and self.supplied_remote) or
                (selected_remote and self.__remotes_db.get(selected_remote.name)))

    def __setup_key_listener(self):
        '''Initialize the key-listener and related widgets.'''

        # pylint: disable-msg=W0201,E1101

        self.__key_listener = lirc.KeyListener()
        self.__key_listener.connect('changed',     self.__on_lirc_changed)
        self.__key_listener.connect('key-pressed', self.__on_lirc_key_pressed)

    def __lookup_widgets(self):
        '''Initialize widget attributes from Glade file.'''

        # This method is more robust than looking up and assigning widgets
        # manually, but it also completly screws up pychecker and pylint. For
        # pylint we ship a plugin to fix this.

        # pylint: disable-msg=W0201

        widget_list = (
            # receiver widgets:
            'table_receiver_selection',
            'combo_receiver_product_list',
            'combo_receiver_vendor_list',

            'alignment_auto_detect',
            'hbox_auto_detect_progress',
            'progressbar_auto_detect',

            'label_device',
            'combo_device',
            'label_device_name',
            'spinbutton_device',

            # remote widgets:
            'combo_remote_product_list',
            'combo_remote_vendor_list',

            'radiobutton_supplied_remote',
            'radiobutton_other_remote',
            'alignment_remote_selection',
            'button_download',

            # preview widgets:
            'label_preview_status',
            'label_preview_result',
        )

        for widget_id in widget_list:
            attr = '_%s__%s' % (self.__class__.__name__, widget_id)
            widget = self.__ui.get_widget(widget_id)
            assert widget is not None, widget_id
            setattr(self, attr, widget)

        self.__dialog = self.__ui.get_widget('lirc_properties_dialog')
        self.__entry_device = self.__combo_device.get_child()
        self.__table_receiver_selection.set_row_spacing(2, 0)

    def __setup_size_groups(self):
        '''
        Create some size-groups to ensure that the dialog keeps its size,
        when sub-widgets change visibility.
        '''

        size_group = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        size_group.add_widget(self.__spinbutton_device.get_parent())
        size_group.add_widget(self.__combo_device)

        size_group = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        size_group.add_widget(self.__hbox_auto_detect_progress)
        size_group.add_widget(self.__alignment_auto_detect)

        size_group = gtk.SizeGroup(gtk.SIZE_GROUP_VERTICAL)
        size_group.add_widget(self.__label_preview_status)
        size_group.add_widget(self.__label_preview_result)

    def __setup_product_lists(self):
        '''Initialize widgets with product listings.'''

        def vendor_has_products(model, iter):
            products, = model.get(iter, 1)
            return len(products) > 0

        vendor_list = self.__receiver_vendors.filter_new()
        vendor_list.set_visible_func(vendor_has_products)

        self.__combo_receiver_vendor_list.set_model(vendor_list)
        self.__combo_receiver_vendor_list.set_active(0)

        self.__combo_remote_vendor_list.set_model(self.__remote_vendors)
        self.__combo_remote_vendor_list.set_active(0)

        # update widget sensitivity
        self._on_radiobutton_supplied_remote_toggled()

        # apply ellipses to combo boxes
        for widget in (
            self.__combo_receiver_vendor_list, self.__combo_receiver_product_list,
            self.__combo_remote_vendor_list, self.__combo_remote_product_list):
            widget.get_cells()[0].set_property('ellipsize', pango.ELLIPSIZE_END)

    def __setup_authorization(self):
        '''Initialize authorization facilities.'''

        # pylint: disable-msg=W0201

        self.__auth = policykit.PolicyKitAuthentication()

        # Discover whether PolicyKit has already given us authorization
        # (without asking the user) so we can unlock the UI at startup if
        # necessary:
        granted = self.__auth.is_authorized()
        self._set_widgets_locked(not granted)

    def __confirm_rewrite_configuration(self, remote):
        '''Ask the user if the configuration files should be rewritten.'''

        if not remote:
            show_message(self.__dialog,
                _('Invalid IR Configuration'),
                _('Your configuration files seems to be incorrect.'),
                gtk.BUTTONS_OK)

            return False

        responses = (
            (gtk.RESPONSE_REJECT, _('_Keep Configuration'), gtk.STOCK_CANCEL),
            (gtk.RESPONSE_ACCEPT, _('_Restore Configuration'), gtk.STOCK_REDO),
        )

        return (
            gtk.RESPONSE_ACCEPT == show_message(self.__dialog,
            _('Invalid IR Configuration'),
            _('Your configuration files seems to be incorrect. ' +
              'Should this program try to restore your settings, ' +
              'for a %s %s remote?') % (
            remote.vendor, remote.product), buttons=responses))

    def __restore_hardware_settings(self):
        '''Restore hardware settings from configuration files.'''

        # We really do not want to rewrite any configuration files
        # at that stage, so __configuration_level should be non-zero.
        assert 0 != self.__configuration_level

        # Read settings from hardware.conf:
        settings = lirc.HardwareConfParser(config.LIRC_HARDWARE_CONF)

        # Practice some sanity checks on that file:
        remote = self.__remotes_db.find(settings.get('REMOTE_VENDOR'),
                                        settings.get('REMOTE_MODEL'))

        if (not lirc.check_hardware_settings(remote) and
            self.__confirm_rewrite_configuration(remote)):
            try:
                service = backend.get_service()

                remote.update_configuration(service)

                service.ManageLircDaemon('enable')
                service.ManageLircDaemon('restart')

            except dbus.DBusException, e:
                show_message(self.__dialog,
                             _('Cannot restore IR configuration'),
                             _('Backend failed: %s') % e.message)

        # Try to select configured receiver vendor:
        #
        # NOTE: Ubuntu's lirc script doesn't distinguish between remote and
        # receiver settings in "hardware.conf", whereas we have to. For that
        # reason the device node's name is stored in REMOTE_DEVICE, instead
        # of RECEIVER_DEVICE.
        #
        self.selected_receiver = (
            settings.get('RECEIVER_VENDOR'),
            settings.get('RECEIVER_MODEL'),
            settings.get('REMOTE_DEVICE'),
        )

        # Try to select configured remote vendor:
        self.selected_remote = (
            settings.get('REMOTE_VENDOR'),
            settings.get('REMOTE_MODEL'),
        )

        # Toggle radio buttons to show if restored remote is supplied remote:
        self.use_supplied_remote = (self.supplied_remote == self.selected_remote)

    def __on_lirc_changed(self, listener):
        '''Handle state changes of the LIRC key listener.'''

        if listener.connected:
            self.__label_preview_result.show()
            self.__label_preview_result.set_text(_('<none>'))
            self.__label_preview_status.set_text(_('Press remote control buttons to test:'))

        else:
            self.__label_preview_result.hide()
            self.__label_preview_status.set_markup(_('<b>Warning:</b> Remote control daemon ' +
                                                     'not running. Cannot test buttons.'))

    # pylint: disable-msg=W0613,R0913
    def __on_lirc_key_pressed(self, listener, remote, repeat, name, code):
        '''Handle key presses reported by the LIRC key listener.'''

        display_name = lirc.KeyCodes.get_display_name(name)
        category = lirc.KeyCodes.get_category(name)

        args = map(gobject.markup_escape_text, (display_name, category))
        markup = '<b>%s</b><small> (%s)</small>' % tuple(args)

        self.__label_preview_result.set_markup(markup)

    # pylint: disable-msg=C0103
    def _on_radiobutton_supplied_remote_toggled(self, radio_button=None):
        '''
        Gray-out the custom IR remote control widgets if the user wants to use
        the remote control supplied with the IR receiver:
        '''

        # Find remote selection widgets:
        remote_selection_widgets = []

        for child in self.__alignment_remote_selection.child.get_children():
            if isinstance(child, gtk.Box):
                remote_selection_widgets.extend(child.get_children())

            else:
                remote_selection_widgets.append(child)

        # Update sensitivity of remote selection widgets:
        use_supplied = self.use_supplied_remote

        for child in remote_selection_widgets:
            if child is not self.__button_download:
                child.set_sensitive(not use_supplied)

        # Choose supplied remote when requested:
        if use_supplied and self.supplied_remote:
            self.selected_remote = self.supplied_remote

    def _on_button_download_clicked(self, button=None):
        '''Handle clicks on the auto-detection button.'''

        @thread_callback
        def on_download_progress(progress, total, action):
            '''Handle progress reports from download service.'''

            args = (
                locale.format(percent='%.1f', grouping=True, value=progress/1024.0),
                locale.format(percent='%.1f', grouping=True, value=total/1024.0))
            message = (
                total > 0 and _('%s of %s KiB retrieved...') % args
                           or _('%s KiB retrieved...') % args[0])

            progress_window.detail = action
            progress_window.update(progress, total, message)

        @thread_callback
        def on_download_success(content, headers):
            '''Handle finished downloads.'''

            self.__dialog.set_sensitive(True)
            progress_window.hide()

            if 'application/x-gzip' == headers.get('content-type'):
                try:
                    backend.get_service().InstallRemoteDatabase(content.name)
                    self.__update_remotes_db()

                except dbus.DBusException, ex:
                    show_message(self.__dialog, progress_window.title, ex.message)

            elif httplib.NOT_MODIFIED == getattr(content, 'code', None):
                show_message(self.__dialog, progress_window.title,
                             details=_('No updates available. Your remote control configuration ' +
                                       'files are already up-to-date.'),
                             message_type=gtk.MESSAGE_INFO)

            else:
                show_message(self.__dialog, progress_window.title,
                             _('Download of updated remote control configurations failed.'))

        @thread_callback
        def on_download_failure(message):
            '''Handle failure reports from download service.'''

            self.__dialog.set_sensitive(True)
            progress_window.hide()

            show_message(self.__dialog, progress_window.title, message)

        self.__dialog.set_sensitive(False)
        progress_window = ProgressWindow(self.__ui)
        progress_window.show(self.__dialog, _('Updating Remote Configuration Files'))

        gtk.gdk.threads_leave()

        try:
            timestamp = (
                os.path.isfile(config.LIRC_REMOTES_TARBALL) and
                os.path.getmtime(config.LIRC_REMOTES_TARBALL) or
                None)

            net.retrieve_tarball(tarball_uri=config.URI_UPDATES,
                                 progress_callback=on_download_progress,
                                 success_callback=on_download_success,
                                 failure_callback=on_download_failure,
                                 reference_time=timestamp)

        finally:
            gtk.gdk.threads_enter()

    # pylint: disable-msg=C0103
    def _on_radiobutton_other_remote_size_allocate(self, widget, alloc):
        '''
        Keep padding of remote properties alignment consistent
        with the padding implied by the radio buttons.
        '''

        xpad = widget.get_child().allocation.x - widget.allocation.x
        self.__alignment_remote_selection.set_padding(0, 0, xpad, 0)

    def _on_vendor_list_changed(self, vendor_list):
        '''
        Change the combobox to show the list of models for the selected 
        manufacturer:
        '''

        tree_iter = vendor_list.get_active_iter()

        if not tree_iter:
            vendor_list.set_active(0)
            return

        vendors = vendor_list.get_model()
        products, = vendors.get(tree_iter, 1)

        self.__combo_receiver_product_list.set_model(products)
        self.__combo_receiver_product_list.set_active(0)

    def __setup_devices_model(self, device_nodes):
        '''Populate the combo box for device with device nodes.'''

        self.__combo_device.show()
        self.__spinbutton_device.hide()
        self.__label_device.set_text_with_mnemonic(_('_Device:'))
        self.__label_device.set_mnemonic_widget(self.__combo_device)

        if device_nodes:
            # populate device combo's item list
            device_node_model = self.__combo_device.get_model()

            if device_node_model is None:
                device_node_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
                device_node_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
                self.__combo_device.set_model(device_node_model)
                self.__combo_device.set_text_column(0)

                self.__combo_device.clear()

                renderer = gtk.CellRendererText()
                self.__combo_device.pack_start(renderer, True)
                self.__combo_device.set_attributes(renderer, markup=2)

            else:
                device_node_model.clear()

            for device in device_nodes:
                if isinstance(device, tuple):
                    args = map(gobject.markup_escape_text, reversed(device))
                    markup = '<b>%s</b>\n<small>%s</small>' % tuple(args)
                    name, device = device

                else:
                    name, markup = '', gobject.markup_escape_text(device)

                tree_iter = device_node_model.append()
                device_node_model.set(tree_iter, 0, device, 1, name, 2, markup)

            # activate first device node
            self.__combo_device.set_sensitive(True)
            self.__combo_device.set_active(0)

        else:
            # deactivate combo box, if device is not configurable
            self.__combo_device.set_sensitive(False)
            self.selected_device = None


    def __setup_numeric_device(self, device_node):
        '''Initialize the spin-button for numeric device selection.'''

        device_node = self.__hardware_manager.parse_numeric_device_node(device_node)
        label, value, minimum, maximum = device_node

        label = label and '%s:' % label or _('_Device:')

        self.__combo_device.hide()
        self.__spinbutton_device.show()

        self.__label_device.set_text_with_mnemonic(label)
        self.__label_device.set_mnemonic_widget(self.__spinbutton_device)

        self.__spinbutton_device.set_range(minimum, maximum)
        self.__spinbutton_device.set_value(value)

        self._on_spinbutton_device_value_changed()

    def _on_combo_device_changed(self, combo=None):
        '''Handle changes to device combo-box.'''

        receiver = self.selected_receiver
        device = self.selected_device

        self.selected_receiver = receiver, device

        tree_model = self.__combo_device.get_model()
        tree_iter = self.__combo_device.get_active_iter()

        device_name = (
            tree_model is not None and tree_iter is not None and
            tree_model.get(tree_iter, 1)[0] or '')

        markup = gobject.markup_escape_text(device_name)
        self.__label_device_name.set_markup('<small>%s</small>' % markup)

    # pylint: disable-msg=C0103,W0613
    def _on_spinbutton_device_value_changed(self, spinbutton=None):
        '''Handle changes to the spin-button for numeric device selection.'''

        self.selected_device = ('%d' % self.__spinbutton_device.get_value())

    def _on_product_list_changed(self, product_list):
        '''Handle selection changes to receiver product list.'''

        # lookup selection:
        tree_iter = product_list.get_active_iter()

        if tree_iter is None:
            product_list.set_active(0)
            return

        receiver, = product_list.get_model().get(tree_iter, 1)

        #  freeze configuration updates:
        self._begin_update_configuration()

        try:
            # resolve device nodes:
            device_nodes = (receiver and receiver.device_nodes or [])

            if device_nodes:
                device_nodes = [node.strip() for node in device_nodes.split(',')]
                device_nodes = self.__hardware_manager.resolve_device_nodes(device_nodes)

            if (1 == len(device_nodes) and
                isinstance(device_nodes[0], str) and
                device_nodes[0].startswith('numeric:')):
                # show some spinbutton, when the device node requires numeric input
                self.__setup_numeric_device(device_nodes[0])

            else:
                # show the combobox, when device nodes can be choosen from list
                self.__setup_devices_model(device_nodes)

            # highlight supplied IR remote:
            if self.supplied_remote:
                self.selected_remote = self.supplied_remote

        finally:
            #  thaw configuration updates:
            self._end_update_configuration(receiver, self.selected_device)

    def _on_remote_vendor_list_changed(self, vendor_list):
        '''Handle selection changes to remote vendor list.'''

        tree_iter = vendor_list.get_active_iter()

        if tree_iter:
            products, = vendor_list.get_model().get(tree_iter, 1)
            self.__combo_remote_product_list.set_model(products)
            self.__combo_remote_product_list.set_active(0)

    def _on_remote_product_list_changed(self, product_list):
        '''Handle selection changes to remote product list.'''

        tree_iter = product_list.get_active_iter()
        remote, = product_list.get_model().get(tree_iter, 1)

        if remote:
            self._begin_update_configuration()
            self._end_update_configuration(remote)

    def _on_search_progress(self, manager, fraction, message):
        '''Handle progress reports from the auto-detection process.'''

        self.__table_receiver_selection.set_sensitive(False)
        self.__hbox_auto_detect_progress.show()
        self.__alignment_auto_detect.hide()

        if fraction >= 0:
            self.__progressbar_auto_detect.set_fraction(fraction)

        # gtk.ProgressBar doesn't support any text padding.
        # Work around that visual glitch with spaces.
        self.__progressbar_auto_detect.set_text(' %s ' % message)

    def _on_search_finished(self, manager = None):
        '''Handle end of the auto-detection process.'''

        self.__table_receiver_selection.set_sensitive(True)
        self.__hbox_auto_detect_progress.hide()
        self.__alignment_auto_detect.show()

        n_receivers = self.__receiver_chooser.n_receivers

        if 1 == n_receivers:
            self._select_chosen_receiver()

        elif 0 == n_receivers:
            self.__combo_receiver_vendor_list.set_active(0)

            responses = (
                (gtk.RESPONSE_CANCEL, gtk.STOCK_CANCEL),
                (gtk.RESPONSE_REJECT, _('_Search Again'), gtk.STOCK_REFRESH),
            )

            if (gtk.RESPONSE_REJECT ==
                show_message(self.__dialog,
                             _('No IR Receivers Found'),
                             _('Could not find any IR receiver. Is your device attached?\n\n' +
                             'Note that some devices, such as homebrew serial port ' +
                             'receivers must be selected manually since there is no ' +
                             'way to detect them automatically.'),
                             buttons=responses)):

                self._on_button_auto_detect_clicked()

    def _on_receiver_found(self, manager, receiver, udi, device):
        '''Update the list of auto-detected receivers, when a new one was found.'''

        if self.__receiver_chooser.append(receiver, udi, device) > 1:
            self.__receiver_chooser.show()

    def _select_chosen_receiver(self):
        '''Choose the receiver selected in the auto-detection list.'''

        # Unset any currently-chosen manufacturer/model, so that the combo
        # box emits a signal when we set a detected manufacturer/model, even
        # if it's the same as what was previously chosen. This ensures that
        # the configuration file will be set again (It might have been broken
        # in the meantime).
        self.selected_receiver = None
        self.selected_remote = None

        self.selected_receiver = self.__receiver_chooser.selected_receiver

        if self.supplied_remote:
            self.selected_remote = self.supplied_remote
            self.use_supplied_remote = True

    def _begin_update_configuration(self):
        '''
        Temporarly prevent UI changes from being written back to configuration
        files. Must be paired with _end_update_configuration() call.
        '''

        if self.__configuration_level >= 0:
            self.__configuration_level += 1

    def _end_update_configuration(self, device, *args):
        '''
        Allow UI changes to be written back to configuration files again.
        Must be paired with _begin_update_configuration() call.
        '''

        if self.__configuration_level < 0:
            return

        self.__configuration_level -= 1

        try:
            service = backend.get_service()

            while True:
                try:
                    if device:
                        # This can throw an AccessDeniedException exception:
                        device.update_configuration(service, *args)
                        device = None

                    elif len(args):
                        service.ManageLircDaemon('disable')

                    if 0 == self.__configuration_level:
                        # This can throw an AccessDeniedException exception:
                        service.ManageLircDaemon('restart')

                        if self.__key_listener:
                            self.__key_listener.start()

                    break

                except dbus.DBusException, ex:
                    exception_name = ex.get_dbus_name()

                    # The backend might complain
                    # that we have not yet requested authorization:
                    if exception_name == 'org.gnome.LircProperties.AccessDeniedException':
                        logging.debug('Access denied, reauthenticating: %r', ex)

                        #Request authorization from PolicyKit so we can try again.
                        granted = self._unlock()

                        if not granted:
                            # _unlock() already shows a dialog.
                            # (Though it is maybe not the right place to do that.)
                            show_message(self.__dialog,
                                         _('Cannot Update Configuration'),
                                         _('The System has refused access to this feature.'))
                            break # Stop trying.

                    elif exception_name.startswith('org.gnome.LircProperties.'):
                        logging.debug('Operation failed, aborting: %r', ex)

                        show_message(self.__dialog,
                                     _('Cannot Update Configuration'),
                                     _('Configuration backend reported %s.') % ex.message)
                        break # Stop trying.

                    else:
                        logging.error(ex)
                        break # Stop trying.

        except dbus.DBusException, ex:
            logging.error(ex)

    def _on_receiver_chooser_dialog_response(self, dialog, response):
        '''Handle confirmed selections in the chooser for auto-detected receivers.'''

        if gtk.RESPONSE_ACCEPT == response:
            self._select_chosen_receiver()

        dialog.hide()

    def _on_button_auto_detect_clicked(self, button=None):
        '''Handle clicks on the auto-detection button.'''

        # bring user interface to initial state:
        self._on_search_progress(None, 0, _('Searching for remote controls...'))

        if not self.__receiver_chooser:
            self.__receiver_chooser = ReceiverChooserDialog(self.__ui)

        self.__receiver_chooser.reset()

        # start searching for supported remote controls:
        self.__hardware_manager.search_receivers()

    def _on_auto_detect_stop_button_clicked(self, button):
        '''Handle clicks on the auto-detection's "Cancel" button.'''

        self.__hardware_manager.cancel()

    def _on_custom_configuration_button_clicked(self, button):
        '''Handle clicks on the auto-detection's "Custom Configuration" button.'''

        if not self.__custom_configuration:
            self.__custom_configuration = CustomConfiguration(self.__ui)

        self.__custom_configuration.run(self.selected_receiver,
                                        self.selected_device,
                                        self.selected_remote)

    def _on_button_close_clicked(self, button):
        '''Handle clicks on the "Close" button.'''

        self.__dialog.hide()

    def _on_button_unlock_clicked(self, button):
        '''Handle clicks on the "Unlock" button.'''

        granted = self._unlock()

        if granted:
            self.__combo_receiver_vendor_list.grab_focus()

    def _unlock(self):
        '''
        Ask PolicyKit to allow the user to use our D-BUS driven backend.
        We must ask PolicyKit again later before actually using the backend,
        but PolicyKit should only show the dialog the first time. Actually, use
        __auth.is_authorized() to check if we are already authorized, because
        ObtainAuthorization returns 0 if we are already authorized (which is
        probably a temporary bug).
        See http://bugs.freedesktop.org/show_bug.cgi?id=14600
        '''

        if self.__dialog == None:
            logging.warning('_unlock() called before the dialog ' +
                            'was instantiated, but we need an xid')
            return False

        if not self.__dialog.window:
            logging.warning('_unlock() called before the dialog ' +
                            'was realized, but we need an xid')
            return False

        if self.__auth.is_authorized():
            logging.info('Authorized already. No need to obtain authorization.')
            return True

        granted = self.__auth.obtain_authorization(self.__dialog)

        # Warn the user (because PolicyKit does not seem to)
        # Note that PolicyKit can fail silently (just returning 0) when
        # something is wrong with the backend. And it fails (!) when
        # the user is _already_ authenticated.
        if not granted:
            # Improve this text
            # (PolicyKit should maybe show this instead of failing silently,
            # or at least something should be recommended by PolicyKit.):
            # See http://bugs.freedesktop.org/show_bug.cgi?id=14599
            show_message(self.__dialog,
                         _('Could Not Unlock.'),
                         _('The system will not allow you to access ' +
                           'these features. Please contact your system ' +
                           'administrator for assistance.'))

        self._set_widgets_locked(not granted)

        return granted

    def _set_widgets_locked(self, locked):
        '''Gray (or ungray) widgets which require PolicyKit authorization.'''
        self.__ui.get_widget('vbox').set_sensitive(not locked)

        # Gray out the Unlock button if we are now already unlocked:
        button = self.__ui.get_widget('unlockbutton')
        button.set_sensitive(locked)

    # pylint: disable-msg=R0201
    def _on_button_help_clicked(self, button):
        '''Handle "Help" button clicks.'''

        display_name = self.__dialog.get_screen().make_display_name()
        args = 'yelp', 'ghelp:gnome-lirc-properties'

        try:
            subprocess.Popen(args, close_fds=True,
                             env=dict(os.environ, DISPLAY=display_name))

        except OSError, ex:
            if errno.ENOENT == ex.errno:
                error_message = _('Cannot display help since the GNOME Help ' +
                                  'Browser ("yelp") cannot be found.')

            else:
                error_message = _('Cannot display help for unexpected reason: %s') % ex.strerror

            show_message(self.__dialog, _('Cannot Display Help'), details=error_message)

    # pylint: disable-msg=R0201
    def _on_window_hide(self, window):
        '''React when the dialog is hidden.'''

        # Stop the main loop so that run() returns:
        gtk.main_quit()

    def _on_lirc_properties_dialog_realize(self, dialog):
        '''Start services which need the dialog from being realized.'''

        self.__key_listener.start()

    def run(self):
        '''Show the dialog and return when the window is hidden.'''

        self.__dialog.connect('hide', self._on_window_hide)
        self.__dialog.show()

        gtk.main()

    def __get_selected_receiver(self):
        '''Retrieve the currently selected receiver.'''

        tree_iter = self.__combo_receiver_product_list.get_active_iter()
        receiver = None

        if tree_iter:
            receiver, = self.__combo_receiver_product_list.get_model().get(tree_iter, 1)

        return receiver

    def __set_selected_receiver(self, receiver):
        '''
        Select the specified receiver.

        The receiver can be specified as Receiver object,
        or as tuple consisting of vendor and product name.
        Additionaly the device node can be passed.
        '''

        self._begin_update_configuration()

        vendor_name, product_name, device = None, None, None

        # unpack the argument(s) passed:
        if isinstance(receiver, (tuple, list)):
            if 3 == len(receiver):
                vendor_name, product_name, device = receiver
                receiver = None

            elif 2 != len(receiver):
                raise ValueError

            elif isinstance(receiver[0], lirc.Receiver):
                receiver, device = receiver

            else:
                vendor_name, product_name = receiver
                receiver = None

        elif receiver is None:
            vendor_name, product_name = None, None

        if isinstance(receiver, lirc.Receiver):
            vendor_name, product_name = receiver.vendor, receiver.product

        try:
            # highlight the selected receiver's vendor name:
            tree_iter = self.__receiver_vendors.find_iter(vendor_name)

            if(tree_iter == None):
                tree_iter = self.__receiver_vendors.get_iter_first()

            products = None

            if tree_iter:
                filter = self.__combo_receiver_vendor_list.get_model()
                filter_iter = filter.convert_child_iter_to_iter(tree_iter)
                self.__combo_receiver_vendor_list.set_active_iter(filter_iter)
                products, = self.__receiver_vendors.get(tree_iter, 1)

            # highlight the selected receiver's product name:
            tree_iter = products and products.find_iter(product_name)

            if tree_iter:
                self.__combo_receiver_product_list.set_active_iter(tree_iter)

            # enter the selected receiver's device node:
            self.selected_device = device

        finally:
            self._end_update_configuration(receiver, device)

    def __get_selected_remote(self):
        '''Retrieve the currently selected remote.'''

        tree_iter = self.__combo_remote_product_list.get_active_iter()
        remote = None

        if tree_iter:
            remote, = self.__combo_remote_product_list.get_model().get(tree_iter, 1)

        return remote

    def __set_selected_remote(self, remote):
        '''
        Select the specified remote control.

        The remote can be specified as Remote object,
        or as tuple consisting of vendor and product name.
        '''

        # analyse what got passed:
        if isinstance(remote, lirc.Remote):
            vendor_name = remote.vendor
            product_name = remote.product or remote.name

        elif isinstance(remote, (tuple, list)):
            if 2 != len(remote):
                raise ValueError

            vendor_name, product_name = remote

        elif remote is None:
            vendor_name, product_name = None, None

        else:
            raise ValueError

        if product_name and not vendor_name:
            vendor_name = _('Unknown')

        # select the remote vendor:

        tree_iter = (
            self.__remote_vendors.find_iter(vendor_name) or
            self.__remote_vendors.get_iter_first())

        self.__combo_remote_vendor_list.set_active_iter(tree_iter)
        products, = self.__remote_vendors.get(tree_iter, 1)

        # select the remote product:

        tree_iter = products and (
            products.find_iter(product_name) or
            products.get_iter_first())

        if tree_iter:
            self.__combo_remote_product_list.set_active_iter(tree_iter)

    def __get_selected_device(self):
        '''Retrieve the currently selected device.'''
        return self.__entry_device.get_text().strip()

    def __set_selected_device(self, device_node):
        '''Change the currently selected device.'''

        # try to figure out device node if not specified:
        receiver = self.selected_receiver

        if receiver:
            if device_node is None:
                device_node = receiver.device
            if device_node is None:
                device_node = self.__hardware_manager.find_instance(receiver)

        # try to select choosen device node from combo box:
        tree_model = device_node and self.__combo_device.get_model()
        tree_iter = tree_model and tree_model.get_iter_first() or None

        while tree_iter is not None:
            node, = tree_model.get(tree_iter, 1)

            if node == device_node:
                self.__combo_device.set_active_iter(tree_iter)
                return

            tree_iter = tree_model.iter_next(tree_iter)

        # device node not found in combo box, fallback to modify its entry:
        markup = (
            receiver and not device_node and
            _('<b>Warning:</b> Cannot find such receiver.') or '')

        self.__entry_device.set_text(device_node or '')
        self.__label_device_name.set_markup('<small>%s</small>' % markup)

    def __get_supplied_remote(self):
        '''Retrieve the supplied remot of the currently selected remote.'''

        receiver = self.selected_receiver

        if receiver:
            # pylint: disable-msg=E1103
            return receiver.find_supplied_remote(self.__remotes_db)

        return None

    def __set_use_supplied_remote(self, use_supplied_remote):
        '''Chooses if the supplied remote shall be used.'''

        if use_supplied_remote:
            self.__radiobutton_supplied_remote.set_active(True)

        else:
            self.__radiobutton_other_remote.set_active(True)

    def __get_use_supplied_remote(self):
        '''Checks if the supplied remote shall be used.'''

        return self.__radiobutton_supplied_remote.get_active()

    selected_receiver = property(__get_selected_receiver, __set_selected_receiver)
    selected_remote   = property(__get_selected_remote,   __set_selected_remote)
    selected_device   = property(__get_selected_device,   __set_selected_device)

    use_supplied_remote = property(__get_use_supplied_remote, __set_use_supplied_remote)
    supplied_remote     = property(__get_supplied_remote)
