import xpybutil
import xpybutil.keybind


class KeyUtil:
    def __init__(self, conn):
        self.conn = conn

        self.min_keycode = self.conn.get_setup().min_keycode
        self.max_keycode = self.conn.get_setup().max_keycode

        self.keyboard_mapping = self.conn.core.GetKeyboardMapping(
            self.min_keycode,
            self.max_keycode - self.min_keycode + 1
        ).reply()

    def string_to_keysym(string):
        return xpybutil.keysymdef.keysyms[string]

    def get_keysym(self, keycode, keysym_offset):
        keysyms_per_keycode = self.keyboard_mapping.keysyms_per_keycode

        return self.keyboard_mapping.keysyms[
            (keycode - self.min_keycode) *
            self.keyboard_mapping.keysyms_per_keycode + keysym_offset
        ]

    def get_keycode(self, keysym):
        keysyms_per_keycode = self.keyboard_mapping.keysyms_per_keycode

        for keycode in range(self.min_keycode, self.max_keycode + 1):
            for keysym_offset in range(0, keysyms_per_keycode):
                if self.get_keysym(keycode, keysym_offset) == keysym:
                    return keycode

        return None
