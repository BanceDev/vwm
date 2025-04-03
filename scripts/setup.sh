#!/bin/sh

mkdir /usr/bin/nostwm-src
cp -r ../src/* /usr/bin/nostwm-src/
cp ../assets/nostwm /usr/bin/nostwm
cp ../assets/nostwm-session /usr/bin/nostwm-session
cp ../assets/nostwm-session.desktop /usr/share/xsessions/nostwm-session.desktop
mkdir /etc/nostwm
cp ../assets/nostwm.json /etc/nostwm/nostwm.json
chmod a+x /usr/bin/nostwm
chmod a+x /usr/bin/nostwm-session
