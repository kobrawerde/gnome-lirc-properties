#!/usr/bin/python

import dbus

bus = dbus.SystemBus()
policy_kit_mechanism = bus.get_object('org.gnome.LircProperties.Mechanism', '/')
#print policy_kit_mechanism.Introspect()

if(policy_kit_mechanism == None):
    print("Error: Could not get our PolicyKit mechanism.\n")

try:
    result = policy_kit_mechanism.WriteLircdConfFile("yadda yadda test contents")
    print "Called. result=", result
except dbus.exceptions.DBusException, e:
    print "exception: ", e
except Exception, e:
    print "other exception: ", e
