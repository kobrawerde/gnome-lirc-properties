SUBDIRS = data gnome_lirc_properties help po
bin_SCRIPTS = bin/gnome-lirc-properties
man1_MANS = man/gnome-lirc-properties.1

EXTRA_DIST = \
        autogen.sh \
	bin/lirc-receiver-list \
	bin/todo-list \
	data/overrides.conf \
	gnome-doc-utils.make \
	man/gnome-lirc-properties.1 \
	patches/0001-Use-new-instead-of-conf-as-filename-suffix.patch \
	patches/0002-Add-resume-switch-to-irrecord.patch

DISTCLEANFILES = \
	intltool-extract \
	intltool-merge \
	intltool-update

DISTCHECK_CONFIGURE_FLAGS = \
	--disable-scrollkeeper

# Build ChangeLog from GIT history
ChangeLog:
	@if test -f $(top_srcdir)/.git/HEAD; then \
		git log --stat --after="Thu Sep 10 18:00:37 2009" > $@; \
	fi

dist: ChangeLog

.PHONY: ChangeLog

