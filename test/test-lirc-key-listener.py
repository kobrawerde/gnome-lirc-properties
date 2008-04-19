#!/usr/bin/env python

import os.path, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gnome_lirc_properties import lirc
from gobject               import MainLoop

# Called for each lirc command received:
def on_key_pressed(command, remote, repeat, name, code):
   print 'command received: %s (%s)' % (name, code)

print '''\
Press keys on the remote control.
If they are recognised then they will be shown here.
'''

# Create the listener and tell it to call our
# callback for each command that it receives:
listener = lirc.KeyListener()
listener.connect('key-pressed', on_key_pressed)
listener.start()

# Run the mainloop so that the idle handler inside LircKeysListener can work:
MainLoop().run()
