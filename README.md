# VWM
- vwm is a simple X11 window manager written in Python3

## REQUIREMENTS
- requiered
  - Python 3.7 and above
  - python-xlib (https://pypi.org/project/python-xlib/ )

## KEY BIND
You can configure keybinds and their actions by modifying `KEY_BINDS` in [hogewm](./hogewm).

| key bind | description |
|--|--|
| M-leftdrag | move window |
| M-rightdrag | resize window |
| C-M-i | select window |
| C-M-r | select the window the cursor is in|
| C-M-m | maximize the selected window |
| C-M-f | move the selected window to the next monitor |
| C-M-s | swap all windows between monitors |
| C-M-(h,l,j,k) | halve the selected window |
| C-M-comma | vartically maximize the selected window |
| C-M-1 | open terminal emurator |
| C-M-2 | open text editor |
| C-M-3 | open web browser |
| C-M-v | oepn system monitor (hogemonitor) |
| Print | capture the entire screen and save it into `$HOME/screenshots/` |
| C-Print | capture the selected window and save it into `$HOME/screenshots/` |
| M-(F1,F2,F3,F4) | go to the virtual screen (1,2,3,4) |
| C-M-(a,d) | move the selected window to the next virtual screen  |
| C-M-t | tile windows |
| C-M-delete | restart the window manager |
| C-M-home | reconfigure external outputs |
| C-M-end | reload external output configurations from xrandr |
| C-M-backspace | set the selected window to always be on top |

## LICENSE
- GPLv3

