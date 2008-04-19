#!/usr/bin/env python

import os.path, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gnome_lirc_properties import policykit_obtain_authorization

import pygtk
pygtk.require('2.0')

import gtk

class TestWindow:
    def on_button_clicked(self, widget, data=None):
        print "Calling ObtainAuthorization..."
        helper = policykit_obtain_authorization.PolicyKitObtainAuthorization()
        helper.obtain_authorization(None)
        print "...Finished."

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


