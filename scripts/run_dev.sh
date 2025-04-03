#!/bin/sh

set -e

xinit ./xinitrc -- $(command -v Xephyr) :2 -screen 1024x768
