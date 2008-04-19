SUBDIRS = icons

# Most distros will probably want to use --sysconfdir=/etc,
# because that is what most distros have configured D-Bus to use.
dbusconfdir = $(sysconfdir)/dbus-1/system.d
dbusconf_DATA = org.gnome.LircProperties.Mechanism.conf

policykitpolicydir = $(datadir)/PolicyKit/policy
policykitpolicy_in_files = gnome-lirc-properties-mechanism.policy.in
policykitpolicy_DATA = gnome-lirc-properties-mechanism.policy

# The .service file is generated from a .service.in file
# so that the install location can be inserted.
servicedir = $(datadir)/dbus-1/system-services
service_in_files = org.gnome.LircProperties.Mechanism.service.in
service_DATA = org.gnome.LircProperties.Mechanism.service

# The .desktop file is generated from a .desktop.in file
# so that intltool can take care of localization.
desktopdir = $(datadir)/applications
desktop_in_files = gnome-lirc-properties.desktop.in
desktop_DATA = gnome-lirc-properties.desktop

resourcesdir = $(pkgdatadir)

resources_DATA = \
	gnome-lirc-properties.glade \
	linux-input-layer-lircd.conf \
	receivers.conf

EXTRA_DIST = \
	$(dbusconf_DATA) \
	$(desktop_in_files) \
	$(policykitpolicy_in_files) \
	$(resources_DATA) \
	$(service_in_files)

DISTCLEANFILES = \
	$(desktop_DATA) \
	$(policykitpolicy_DATA) \
	$(service_DATA)

@INTLTOOL_DESKTOP_RULE@
