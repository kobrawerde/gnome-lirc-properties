#!/usr/bin/env python

import os.path, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gnome_lirc_properties.upload import HttpUploader

#A site with a known working file upload feature: 
LOGIN_URL='http://www.glom.org/wiki/index.php?title=Special:Userlogin&action=submitlogin&type=login&wpLoginattempt=Log+in'
UPLOAD_URL='http://www.glom.org/wiki/index.php?title=Special:Upload&wpUpload=Upload+file'

uploader = HttpUploader(UPLOAD_URL, LOGIN_URL, "Murrayc", "luftballons")

#The name should start with a capital letter, and have no spaces.
uploader.upload_file("/etc/lirc/lircd.conf", "Test_lircd.conf")
