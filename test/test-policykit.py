#!/usr/bin/env python

import os.path, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pygtk
pygtk.require('2.0')
import gtk

import dbus
import os

class TestWindow:
    def on_button_clicked(self, widget, data=None):

        #Call the D-Bus method to request PolicyKit authorization:

        session_bus = dbus.SessionBus()
        policykit = session_bus.get_object('org.freedesktop.PolicyKit.AuthenticationAgent', '/', "org.gnome.PolicyKit.AuthorizationManager.SingleInstance")
        if(policykit == None):
           print("Error: Could not get PolicyKit D-Bus Interface\n")

        gdkwindow = self.window.window
        xid = gdkwindow.xid

        print "Calling ObtainAuthorization..."

        #This complains that no ObtainAuthorization(ssi) exists: 
        #granted = policykit.ObtainAuthorization("test_action_id", xid, os.getpid())

        action_id = "org.gnome.clockapplet.mechanism.settimezone"

        granted = policykit.ObtainAuthorization(action_id, (dbus.UInt32)(xid), (dbus.UInt32)(os.getpid()))
        print "...Finished."

        print "granted=", granted

    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def show(self):
       self.window.show()

    def __init__(self):

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("destroy", self.on_destroy)

        self.button = gtk.Button("Obtain Authorization")
        self.button.connect("clicked", self.on_button_clicked, None)
        self.window.add(self.button)
        self.button.show()

window = TestWindow()
window.show()
gtk.main()


