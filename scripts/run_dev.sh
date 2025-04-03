#!/bin/sh

set -e

xinit ./xinitrc -- $(command -v Xephyr) :2 -br -ac -noreset -screen 1024x768 -no-host-grab
