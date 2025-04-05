#!/bin/bash

sudo cp ./assets/vwm /usr/bin
sudo cp ./assets/vwm-session /usr/bin
sudo cp ./assets/vwm-session.desktop /usr/share/xsessions
sudo mkdir -p /usr/bin/vwm-src
sudo cp -r ./src/* /usr/bin/vwm-src
