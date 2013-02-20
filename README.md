gnome-shell-google-calendar
===========================

Google Calendar in GNOME Shell

This version of gnome-shell-google-calendar is forked from vintitres's version.  This version is intended to allow easier installation to debian based platforms.

Installation
=========

## Using .deb files
Installation using deb files is relatively easy.  Simply run the following commands:
```bash
wget http://packages.mgerow.com/static/gnome-shell-google-calendar_1.0-1_all.deb
sudo dpkg -i gnome-shell-google-calendar_1.0-1_all.deb
```
After this installation you must run the following command in order to initialize the config file.  It will as you to choose which google account to use for the calendar.  If none are set up for the user you will need to set them up and re-run the below command:
```bash
gnome-shell-google-calendar.py
```
After you answer the initial question you may ^C out of the script and log out then log back into your session.  After a minute or so you should see your calendar events show up within the GNOME 3 interface.


Excluding Calendars
==============
If you would like to exclude some calendars from showing up you should add them to ~/.gnome-shell-google-calendar-excludes with one entry per line.

Changes from vintitres's version
========================

There aren't a huge amount of changes from vintitres's version, but I'll list them here:

First, I've changed the place where the config.json file is saved.  By default it seems to be cwd, but this version saves them in ~/.config/gnome-shell-google-calendar.

I've made it to where exclusions can be loaded from /etc/gnome-shell-google-calendar/excludes if they aren't found in the user's directory.

I've made it to where the main executable can include from the /usr/lib/gnome-shell-google-calendar directory, in order to facilitate a an installation to /usr/bin

I've added an autostart script that can be used when gnome-shell-google-calendar.py is installed to /usr/bin
