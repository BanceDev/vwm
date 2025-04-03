#!/bin/sh
DISPLAY=:2
Xephyr -br -ac -noreset -screen 1280x720 :2 &
