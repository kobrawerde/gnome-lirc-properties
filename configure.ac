AC_INIT([gnome-lirc-properties], [0.3.0],
        [https://code.fluendo.com/remotecontrol/trac/])

# tar-ustar asks it to use a sensible tar format that can handle long filenames
AM_INIT_AUTOMAKE([1.9 tar-ustar])

dnl check for programs ===

AM_PROG_CC_C_O
AM_PATH_PYTHON(2.4)
IT_PROG_INTLTOOL([0.35.0])

dnl localization support ===

GETTEXT_PACKAGE="$PACKAGE"
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE],
                   ["$GETTEXT_PACKAGE"],
                   [The gettext package])
AM_GLIB_GNU_GETTEXT

dnl initialize GNOME help ===

GNOME_DOC_INIT()

dnl check for glib-2.0 for the lirc-generate-linux-input helper
PKG_CHECK_MODULES(GLIB, glib-2.0)

dnl check for PolicyKit ===

AC_ARG_ENABLE([policy-kit],
              [  --disable-policy-kit     don't use PolicyKit for gaining privileges])

if test "$enable_policy_kit" != no
then
  PKG_CHECK_MODULES([POLICY_KIT], [polkit >= 0.7
                                   polkit-gnome >= 0.7])
  ENABLE_POLICY_KIT=True
  enable_policy_kit=yes
else
  ENABLE_POLICY_KIT=False
fi

AC_SUBST([ENABLE_POLICY_KIT])

POLICY_KIT_ACTION="org.gnome.lirc-properties.mechanism.configure"
AC_SUBST([POLICY_KIT_ACTION])

dnl check for new enough lirc ===

AC_PATH_PROG([LIRCD], [lircd])

HAVE_LIRCD="yes"
if test -z $LIRCD ; then
  HAVE_LIRCD="no"
else
  LIRCD_VERSION=`lircd --version|head -n 1|sed 's/^lircd //'|sed 's/ (.*)//'`
  LIRCD_MAJOR=`echo $LIRCD_VERSION | cut -d. -f1 | sed 's/[[a-zA-Z\-]].*//g'`
  LIRCD_MINOR=`echo $LIRCD_VERSION | cut -d. -f2 | sed 's/[[a-zA-Z\-]].*//g'`
  LIRCD_MICRO=`echo $LIRCD_VERSION | cut -d. -f3 | sed 's/[[a-zA-Z\-]].*//g'`
  if [[ "$LIRCD_MAJOR" -eq "0" ]] && \
	  [[ "$LIRCD_MINOR" -lt "8" ]]; then
	  AC_MSG_WARN([lircd >= 0.8.4 is required, you have $LIRCD_VERSION])
	  HAVE_LIRCD="no"
  elif [[ "$LIRCD_MAJOR" -eq "0" ]] && \
	  [[ "$LIRCD_MINOR" -eq "8" ]] && \
	  [[ "$LIRCD_MICRO" -lt "4" ]]; then
	  AC_MSG_WARN([lircd >= 0.8.4 is required, you have $LIRCD_VERSION])
	  HAVE_LIRCD="no"
  fi
fi

AC_MSG_CHECKING([new enough lircd daemon])
if test x"$HAVE_LIRCD" != xyes ;
then
  AC_MSG_ERROR([no])
else
  AC_MSG_RESULT([yes])
fi

dnl support custom LIRC folders ===

expand_vars() {
  value=`test "$prefix" == NONE && prefix="$ac_default_prefix"; eval "echo \"$1\""`
  test "$value" != "$1" && expand_vars "$value" || echo "$value"
}

if test -f /etc/fedora-release ; then
	lirc_confdir="/etc"
	remotes_database="/usr/share/lirc-remotes"
else
	lirc_confdir="$sysconfdir/lirc"
	remotes_database="$datadir/lirc/remotes"
fi

AC_ARG_WITH([lirc_confdir],
            AS_HELP_STRING([--with-lirc-confdir],
                           [Configuration folder of LIRC, e.g. $sysconfdir/lirc]),
            [], [with_lirc_confdir=`expand_vars "$lirc_confdir"`])

AC_ARG_WITH([remotes_database],
            AS_HELP_STRING([--with-remotes-database],
                           [Path of the system's LIRC remote database, e.g. $datadir/lirc/remotes]),
            [], [with_remotes_database=`expand_vars "$remotes_database"`])

AC_SUBST([with_lirc_confdir])
AC_SUBST([with_remotes_database])

AC_MSG_CHECKING([configured LIRC configuration folder])

AC_ARG_ENABLE([confdir-check],
              AS_HELP_STRING([--disable-confdir-check],
                             [don't check for the lircd.conf path])])

if test "x$enable_confdir_check" = xyes
  then if test -f "$with_lirc_confdir/lircd.conf"
    then
      AC_MSG_RESULT([$with_lirc_confdir])
    else
      AC_MSG_RESULT([no])
      if test ! -f /etc/fedora-release ; then
        AC_MSG_ERROR([Cannot find lircd.conf in $with_lirc_confdir.])
      fi
    fi
  else
    AC_MSG_RESULT([$with_lirc_confdir])
fi

AC_MSG_CHECKING([configured LIRC remotes database])

if test -d "$with_remotes_database"
then
  AC_MSG_RESULT([$with_remotes_database])
else
  AC_MSG_RESULT([no])
  AC_MSG_ERROR([Configured remotes database does not exist: $with_remotes_database])
fi

dnl support custom upload and download locations ===

AC_ARG_WITH([download_uri],
            AS_HELP_STRING([--with-download-uri],
                           [The URI for downloading user-submitted lircd.conf files.]),
            [], [with_download_uri="http://lirc.fluendo.com/lircdb/remotes.tar.gz"])
AC_ARG_WITH([upload_uri],
            AS_HELP_STRING([--with-upload-uri],
                           [The URI to use for user-submitted lircd.conf files.]),
            [], [with_upload_uri="http://lirc.fluendo.com/lircdb/upload/"])

AC_SUBST([with_download_uri])
AC_SUBST([with_upload_uri])

dnl find irrecord ===

AC_PATH_PROG([LIRC_IRRECORD], [irrecord])
AC_ARG_VAR([LIRC_IRRECORD], [path of the irrecord program])
AC_SUBST([LIRC_IRRECORD])

dnl find name of input device layer driver

AC_ARG_WITH([devinput_driver],
            AS_HELP_STRING([--with-devinput-driver],
                           [The name of the Linux Input Device driver.]),
            [], [devinput_driver="`lircd --driver=help 2>&1 | sed -ne 's:^\s*\(dev/\?input\)\s*$:\1:p'`"])

AC_SUBST([devinput_driver])

dnl generate files ===

AC_CONFIG_FILES([Makefile
                 data/Makefile
                 data/gnome-lirc-properties.desktop.in
                 data/gnome-lirc-properties-mechanism.policy
                 data/org.gnome.LircProperties.Mechanism.service
                 data/icons/Makefile
                 data/icons/16x16/Makefile
                 data/icons/22x22/Makefile
                 data/icons/24x24/Makefile
                 data/icons/scalable/Makefile
                 gnome_lirc_properties/Makefile
                 gnome_lirc_properties/config.py
                 gnome_lirc_properties/net/Makefile
                 gnome_lirc_properties/ui/Makefile
                 help/Makefile
                 po/Makefile.in])
AC_CONFIG_FILES([bin/gnome-lirc-properties],
                [chmod +x bin/gnome-lirc-properties])

AC_OUTPUT()

dnl print configuration status ===

AC_MSG_NOTICE([=====================================================================])
AC_MSG_NOTICE([  PolicyKit support: $enable_policy_kit])
AC_MSG_NOTICE([  Remotes database: $with_remotes_database])
AC_MSG_NOTICE([  IR record tool: $LIRC_IRRECORD])
AC_MSG_NOTICE([  Download URI: $with_download_uri])
AC_MSG_NOTICE([  Upload URI: $with_upload_uri])
AC_MSG_NOTICE([=====================================================================])

