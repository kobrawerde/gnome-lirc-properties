#!/usr/bin/env python
#
# This test code is based on the pylirc "simple sample" 
# 
# This depends on 
# - A correct /etc/lirc/lircd.conf, which maps the key names to the key codes supplied by your IR remote.
# - A running lircd, with the correct device specified. For instance: "/usr/sbin/lircd --device=/dev/lirc0".
# - An example.lircrc file, which maps the key names to "command" names that an application would understand.
# On Ubuntu/Debian, dpkg-reconfigure lirc can do this for common remotes.
#
# Murray Cumming, Openismus GmbH 
#/

import os.path, pylirc, time

blocking = 0;

example = os.path.join(os.path.dirname(__file__), 'example.lircrc')

if pylirc.init('openismus-lirc-test', example):
   code = {"config" : ""}

   while code["config"] != "quit":
      # Very intuitive indeed
      if not blocking:
         print "."

         # Delay...
         time.sleep(1)

      # Read next code
      s = pylirc.nextcode(1)

      # Loop as long as there are more on the queue
      # (dont want to wait a second if the user pressed many buttons...)
      while s:
         # Print all the configs...
         for code in s:
            print "Command: %s, Repeat: %d" % (code["config"], code["repeat"])

            if(code["config"] == "blocking"):
               blocking = 1
               pylirc.blocking(1)

            elif(code["config"] == "nonblocking"):
               blocking = 0
               pylirc.blocking(0)

         # Read next code?
         if not blocking:
            s = pylirc.nextcode(1)

         else:
            s = []

   # Clean up lirc
   pylirc.exit()

