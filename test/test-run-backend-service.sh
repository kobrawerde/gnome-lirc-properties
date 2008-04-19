#!/bin/sh

dbus-send \
    --system --print-reply \
    --dest=org.gnome.LircProperties.Mechanism / \
    org.freedesktop.DBus.Introspectable.Introspect
