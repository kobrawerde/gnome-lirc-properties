SUBDIRS = data gnome_lirc_properties help po
bin_SCRIPTS = bin/gnome-lirc-properties
man1_MANS = man/gnome-lirc-properties.1

EXTRA_DIST = \
	bin/lirc-receiver-list \
	bin/todo-list \
	data/overrides.conf \
	gnome-doc-utils.make \
	intltool-extract.in \
	intltool-merge.in \
	intltool-update.in \
	man/gnome-lirc-properties.1 \
	patches/0001-Use-new-instead-of-conf-as-filename-suffix.patch \
	patches/0002-Add-resume-switch-to-irrecord.patch \
	web/README \
	web/service.wsgi

DISTCLEANFILES = \
	intltool-extract \
	intltool-merge \
	intltool-update

DISTCHECK_CONFIGURE_FLAGS = \
	--disable-scrollkeeper \
	--with-lirc-confdir=/etc/lirc \
	--with-remotes-database=/usr/share/lirc/remotes

