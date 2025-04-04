import tomllib
import os
from Xlib import X

MOD_MAPPING = {
    'super': X.Mod4Mask,
    'shift': X.ShiftMask,
    'alt': X.Mod1Mask,
    'ctrl': X.ControlMask,
}


class Config:
    def __init__(self):
        path = os.path.expandvars('$HOME/.config/vwm/vwm.toml')
        with open(path, 'rb') as f:
            self.config = tomllib.load(f)

        self.keybinds = {}
        binds = self.config.get('keybinds', [])
        for bind in binds:
            mods = {bind.get('mod1'), bind.get('mod2')} - {None}
            xmods = 0
            for mod in mods:
                if mod in MOD_MAPPING:
                    xmods |= MOD_MAPPING[mod]

            key_combination = (bind['key'], xmods)

            action = bind['action']
            match action:
                case 'quit':
                    res = {'method': 'cb_destroy_window'}
                case _:
                    res = {'command': f'{action} &'}

            self.keybinds[key_combination] = res


KEY_BINDS = {
    ('i', X.Mod1Mask): {'method': 'cb_focus_next_window', 'arg': FORWARD},
    ('r', X.Mod1Mask): {'method': 'cb_raise_window'},
    ('1', X.Mod1Mask): {'command': f'{TERMINAL} &'},
    ('2', X.Mod1Mask): {'command': f'{EDITOR} &'},
    ('3', X.Mod1Mask): {'command': f'{BROWSER} &'},
    ('m', X.Mod1Mask): {'method': 'cb_maximize_window'},
    ('f', X.Mod1Mask): {'method': 'cb_move_window_to_next_monitor'},
    ('s', X.Mod1Mask): {'method': 'cb_swap_windows_bw_monitors'},
    ('x', X.Mod1Mask): {'method': 'cb_destroy_window'},
    ('F1', X.Mod1Mask): {'method': 'cb_select_vscreen', 'arg': 0},
    ('F2', X.Mod1Mask): {'method': 'cb_select_vscreen', 'arg': 1},
    ('F3', X.Mod1Mask): {'method': 'cb_select_vscreen', 'arg': 2},
    ('F4', X.Mod1Mask): {'method': 'cb_select_vscreen', 'arg': 3},
    ('d', X.Mod1Mask): {'method': 'cb_send_window_to_next_vscreen', 'arg': FORWARD},
    ('a', X.Mod1Mask): {'method': 'cb_send_window_to_next_vscreen', 'arg': BACKWARD},
    ('Delete', X.Mod1Mask): {'function': 'restart'},
    ('Home', X.Mod1Mask): {'method': 'cb_reconfigure_monitors', 'arg': True},
    ('End', X.Mod1Mask): {'method': 'cb_reconfigure_monitors', 'arg': False},
    ('BackSpace', X.Mod1Mask): {'method': 'cb_set_always_top'},
}
