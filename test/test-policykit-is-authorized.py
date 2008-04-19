#!/usr/bin/python

import dbus
import os

bus = dbus.SystemBus()
policy_kit = bus.get_object('org.freedesktop.PolicyKit', '/')
#print policy_kit_mechanism.Introspect()

if(policy_kit == None):
    print("Error: Could not get the PolicyKit interface.\n")

action_id = "org.gnome.clockapplet.mechanism.settimezone"

result = "";

# Check whether the process is authorized:
try:
    result = policy_kit.IsProcessAuthorized(action_id, (dbus.UInt32)(os.getpid()), False)
except dbus.exceptions.DBusException, e:
    print "exception: ", e
except Exception, e:
    print "other exception: ", e

print "IsProcessAuthorized() result=", result
print "IsProcessAuthorized() authorized=", (result == "yes")

# Check whether the dbus session is authorized:
# Only works in a dbus service, so we have a sender dbus session name:
#try:
#    result = policy_kit.IsSystemBusNameAuthorized(action_id, "fake-sender-dbus-session-name", False)
#except dbus.exceptions.DBusException, e:
#    print "exception: ", e
#except Exception, e:
#    print "other exception: ", e

