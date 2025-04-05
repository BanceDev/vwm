import tomllib
import os
from constants import *
from Xlib import X


class Config:
    def __init__(self):
        path = os.path.expandvars('$HOME/.config/vwm/vwm.toml')
        with open(path, 'rb') as f:
            self.config = tomllib.load(f)

        self.keybinds = {}
        binds = self.config.get('keybinds', [])
        for bind in binds:
            key = bind['key']

            action = bind['action']
            match action:
                case 'quit':
                    res = {'method': 'cb_destroy_window'}
                case 'focus':
                    res = {'method': 'cb_focus_next_window', 'arg': FORWARD}
                case 'maximize':
                    res = {'method': 'cb_maximize_window'}
                case 'move_monitor':  # TODO: bundle into a single window swap call
                    res = {'method': 'cb_move_window_to_next_monitor'}
                case 'swap_monitors':
                    res = {'method': 'cb_swap_windows_bw_monitors'}
                case 'desktop1':
                    res = {'method': 'cb_select_vscreen', 'arg': 0}
                case 'desktop2':
                    res = {'method': 'cb_select_vscreen', 'arg': 1}
                case 'desktop3':
                    res = {'method': 'cb_select_vscreen', 'arg': 2}
                case 'desktop4':
                    res = {'method': 'cb_select_vscreen', 'arg': 3}
                case 'restart':
                    res = {'function': 'restart'}
                case _:
                    res = {'command': f'{action} &'}

            self.keybinds[key] = res

        print(self.keybinds)
