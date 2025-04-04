#!/bin/sh

xset +fp $HOME/.local/share/fonts/
xrdb $HOME/.Xdefaults
xmodmap $HOME/.Xmodmap

xset r rate 200 40
setxkbmap -option ctrl:nocaps

# python3 $HOME/vwm/vwm.py 2> $HOME/vwm/debug.log &
# python3 $HOME/vwm/eternal_sleep.py
