#!/bin/sh
# Remove BiscuitWM
rm -r /usr/bin/nostwm-src
rm /usr/bin/nostwm
# Remove session entry
rm /usr/bin/nostwm-session
rm /usr/share/xsessions/nostwm-session.desktop
# Remove config file
rm -r /etc/nostwm
