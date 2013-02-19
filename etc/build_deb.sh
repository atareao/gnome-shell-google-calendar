#!/bin/bash

# This script should be run from within the etc directory

# This should be bumped every time a new deb
# is published
VERSION=1.0-1

# The main executable will go here
mkdir -p ./debian/usr/bin
# The autostart script will go here
mkdir -p ./debian/etc/xdg/autostart
# The config files (exclude file) will go here
mkdir -p ./debian/etc/gnome-shell-google-calendar
# The library files will go here
mkdir -p ./debian/usr/lib/gnome-shell-google-calendar
# Where the control script will go
mkdir -p ./debian/DEBIAN

# Some versions of dpkg require these permissions
find ./debian -type d | xargs chmod 775

cp ../gnome-shell-google-calendar.py ./debian/usr/bin
cp gnome-shell-google-calendar.desktop ./debian/etc/xdg/autostart
cp ../excludes-example ./debian/etc/gnome-shell-google-calendar
# Create an excludes file in the right place
touch ./debian/etc/gnome-shell-google-calendar/excludes
# Copy all the libraries over
cp ../config.py ../keyring.py ../oauth.py ../README.md ../README.old ../test ./debian/usr/lib/gnome-shell-google-calendar
# Put the control file into place (replacing the version with the one in here)
sed s\/%%VERSION%%\/${VERSION}\/g ./control > ./debian/DEBIAN/control

dpkg-deb --build debian

mv debian.deb gnome-shell-google-calendar_${VERSION}_all.deb

rm -r debian

echo gnome-shell-google-calendar_${VERSION}.deb created in `pwd`
