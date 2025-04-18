import os
import sys
import subprocess
import re
import time
import math
import config
import cairo
from constants import *
from Xlib import X, XK, display


EVENTS = {
    X.ButtonPress: 'handle_button_press',
    X.ButtonRelease: 'handle_button_release',
    X.MotionNotify: 'handle_motion_notify',
    X.EnterNotify: 'handle_enter_notify',
    X.MapNotify: 'handle_map_notify',
    X.UnmapNotify: 'handle_unmap_notify',
    X.MapRequest: 'handle_map_request',
    X.DestroyNotify: 'handle_destroy_notify',
    X.KeyPress: 'handle_key_press',
    X.KeyRelease: 'handle_key_release',
    X.ConfigureRequest: 'handle_configure_request',
}


def debug(str):
    print(str, file=sys.stderr, flush=True)


def restart():
    debug(f'restrating {sys.argv[0]}')
    os.execvp(sys.argv[0], [sys.argv[0]])


class vwm:
    def __init__(self):
        self.display = display.Display()
        self.screen = self.display.screen()
        self.colormap = self.screen.default_colormap
        self.keybinds = {}
        self.config = config.Config()
        self.mode = NORMAL_MODE
        self.bar_height = 24
        self.command_buff = ''

        self.managed_windows = {}
        self.exposed_windows = []
        self.window_vscreen = {}
        self.current_vscreen = 0
        self.frame_windows = {}
        self.framed_window = None
        self.is_selection_mode_enabled = False
        self.pressed_keys = set()

        self.last_dragged_time = time.time()

        self.monitor_geometries = self.get_available_monitor_geometries()
        self.maxsize = self.get_screen_size()

        self.catch_events()
        self.map_keys()
        self.grab_buttons()
        self.create_frame_windows()
        self.create_statusbar()
        self.normal_mode()

        self.create_selection_window()
        self.font = self.display.open_font(FONT)
        self.white_gc = self.selection_window.create_gc(
            font=self.font, foreground=self.screen.white_pixel)
        self.black_gc = self.selection_window.create_gc(
            font=self.font, foreground=self.screen.black_pixel)

        self.mod_string = ['shift', 'lock', 'control',
                           'mod1', 'mod2', 'mod3', 'mod4', 'mod5']
        self.mod_mask_string = {
            X.ShiftMask: 'shift',
            X.LockMask: 'lock',
            X.ControlMask: 'control',
            X.Mod1Mask: 'mod1',
            X.Mod2Mask: 'mod2',
            X.Mod3Mask: 'mod3',
            X.Mod4Mask: 'mod4',
            X.Mod5Mask: 'mod5',
        }
        self.modmap = {}
        self.parse_xmodmap()
        for child in self.screen.root.query_tree().children:
            if child.get_attributes().map_state:
                self.manage_window(child)
        self.sort_exposed_windows()
        self.always_top = [None for _ in range(MAX_VSCREEN)]

    def catch_events(self):
        debug('function: catch_events called')
        self.screen.root.change_attributes(
            event_mask=X.SubstructureRedirectMask
            | X.SubstructureNotifyMask
            | X.EnterWindowMask
            | X.LeaveWindowMask
            | X.FocusChangeMask
        )

    def map_keys(self):
        for key, rule in self.config.keybinds.items():
            keysym = XK.string_to_keysym(key)
            keycode = self.display.keysym_to_keycode(keysym)
            self.keybinds[keycode] = rule

    def grab_buttons(self):
        for button in [1, 3]:
            self.screen.root.grab_button(
                button, X.Mod1Mask, True, X.ButtonPressMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE
            )

    def command_mode(self):
        self.mode = COMMAND_MODE
        self.screen.root.grab_keyboard(
            True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime
        )
        self.command_buff = ''
        self.draw_statusbar()

    def normal_mode(self):
        self.mode = NORMAL_MODE
        self.screen.root.grab_keyboard(
            True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime
        )
        self.command_buff = ''
        self.draw_statusbar()

    def input_mode(self):
        self.mode = INPUT_MODE
        self.display.ungrab_keyboard(X.CurrentTime)

        # global shortcut to toggle modes
        esc = XK.string_to_keysym('Escape')
        esc_keycode = self.display.keysym_to_keycode(esc)
        self.screen.root.grab_key(
            esc_keycode, X.ShiftMask, True, X.GrabModeAsync, X.GrabModeAsync)
        self.command_buff = ''
        self.draw_statusbar()

    def hex_to_rgb_float(self, hex_color):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)

    def create_statusbar(self):
        self.bar_pixel = self.colormap.alloc_named_color(BAR_COLOR).pixel
        self.bar_window = self.screen.root.create_window(
            0,
            self.screen.height_in_pixels - self.bar_height,
            self.screen.width_in_pixels,
            self.bar_height,
            0,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=self.bar_pixel,
            override_redirect=True,
        )
        self.bar_window.map()

    def draw_statusbar(self):
        gc = self.bar_window.create_gc(
            foreground=self.screen.black_pixel,
            background=self.bar_pixel,
        )

        # TODO: config the colors
        if self.mode == NORMAL_MODE:
            text = 'Normal'
            bg_color = self.hex_to_rgb_float('#7FFFD4')
        elif self.mode == INPUT_MODE:
            text = 'Insert'
            bg_color = self.hex_to_rgb_float('#87CEEB')
        elif self.mode == COMMAND_MODE:
            text = 'Command '
            text += self.command_buff
            bg_color = self.hex_to_rgb_float('#9370DB')

        drawable = self.bar_window.id
        width = self.screen.width_in_pixels
        height = self.bar_height
        depth = self.screen.root_depth

        surface = cairo.ImageSurface(
            cairo.FORMAT_RGB24,
            width,
            height
        )

        ctx = cairo.Context(surface)

        ctx.set_source_rgb(*bg_color)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()

        ctx.select_font_face(self.config.font,
                             cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(14)
        ctx.set_source_rgb(0.2, 0.2, 0.2)
        ctx.move_to(10, self.bar_height // 2 + 5)
        ctx.show_text(f'{text}')
        ctx.stroke()

        surface.flush()

        buf = bytes(surface.get_data())
        self.bar_window.put_image(
            gc,
            0, 0,
            width, height,
            2,
            self.screen.root_depth,
            0,
            buf
        )

    def create_frame_windows(self):
        debug('function: crate_frame_windows called')
        self.frame_pixel = self.colormap.alloc_named_color(FRAME_COLOR).pixel
        for side in ['left', 'right', 'upper', 'lower']:
            window = self.screen.root.create_window(
                0,
                0,
                16,
                16,
                0,
                self.screen.root_depth,
                X.InputOutput,
                background_pixel=self.frame_pixel,
                override_redirect=True,
            )
            window.map()
            self.frame_windows[side] = window

    def draw_frame_windows(self):
        # debug('function: draw_frame_windows called')
        if self.framed_window == None:
            return
        geom = self.get_window_geometry(self.framed_window)
        if geom == None:
            return
        for side in ['left', 'right', 'upper', 'lower']:
            x, y, width, height = 0, 0, 0, 0
            if side == 'left':
                x = geom.x
                y = geom.y
                width = FRAME_THICKNESS
                height = geom.height
            elif side == 'right':
                x = geom.x + geom.width - FRAME_THICKNESS
                y = geom.y
                width = FRAME_THICKNESS
                height = geom.height
            elif side == 'upper':
                x = geom.x
                y = geom.y
                width = geom.width
                height = FRAME_THICKNESS
            elif side == 'lower':
                x = geom.x
                y = geom.y + geom.height - FRAME_THICKNESS
                width = geom.width
                height = FRAME_THICKNESS
            self.frame_windows[side].configure(
                x=x, y=y, width=width, height=height, stack_mode=X.Above)
            self.frame_windows[side].map()

    def map_frame_windows(self):
        # debug('function: map_frame_windows called')
        for side in ['left', 'right', 'upper', 'lower']:
            self.frame_windows[side].map()

    def unmap_frame_windows(self):
        # debug('function: unmap_frame_windows called')
        for side in ['left', 'right', 'upper', 'lower']:
            self.frame_windows[side].unmap()

    def create_selection_window(self, monitor=1):
        debug('function: crate_selection_window called')
        monitor = list(self.monitor_geometries.values())[
            monitor % len(self.monitor_geometries)]
        width = monitor['width'] // 3
        height = 10
        x = monitor['x'] + monitor['width'] // 3
        y = monitor['y'] + monitor['height'] // 3
        self.selection_window = self.screen.root.create_window(
            x,
            y,
            width,
            height,
            0,
            self.screen.root_depth,
            X.InputOutput,
            background_pixel=self.screen.black_pixel,
            override_redirect=True,
        )
        self.selection_window.change_attributes(backing_store=X.Always)

    def update_selection_window(self):
        # debug('function: update_selection_window called')
        geom = self.get_window_geometry(self.selection_window)
        if geom == None:
            return
        self.selection_window.configure(
            x=geom.x, y=geom.y, width=geom.width, height=20 * len(self.exposed_windows))
        self.selection_window.clear_area(0, 0, geom.width, geom.height)
        idx = self.exposed_windows.index(self.framed_window)
        for i in range(len(self.exposed_windows)):
            win = self.exposed_windows[i]
            win_name = '{}: 0x{:x}'.format(
                self.get_window_class(win)[:50], win.id)
            chars = [c.encode() for c in list(win_name)]
            self.selection_window.poly_text(
                self.white_gc, 20, 20 * (i + 1) - 5, chars)
        win_name = '{self.get_window_class(self.framed_window)[:50]}: 0x{:x}'.format(
            self.get_window_class(self.framed_window)[:50], win.id
        )
        chars = [c.encode() for c in list(win_name)]
        self.selection_window.fill_rectangle(
            self.white_gc, 0, 20 * idx, geom.width, 20)
        self.selection_window.poly_text(
            self.black_gc, 20, 20 * (idx + 1) - 5, chars)
        self.selection_window.configure(stack_mode=X.Above)

    def get_window_attributes(self, window):
        # debug('function: get_window_attributes called')
        try:
            return window.get_attributes()
        except:
            return None

    def get_window_class(self, window):
        # debug('function: get_window_class called')
        try:
            cmd, cls = window.get_wm_class()
        except:
            return ''
        if cls is not None:
            return cls
        else:
            return ''

    def get_window_name(self, window):
        # debug('function: get_window_name called')
        try:
            return f'id->0x{window.id:x}, name->{self.get_window_class(window)}'
        except:
            return ''

    def get_window_id(self, window):
        # debug('function: get_window_id called')
        try:
            return window.id
        except:
            return None

    def manage_window(self, window):
        debug('function: manage_window called')
        attrs = self.get_window_attributes(window)
        if window in self.managed_windows:
            return
        if attrs == None:
            return
        if attrs.override_redirect:
            return
        debug(f'debug: managed {self.get_window_name(window)}')
        self.managed_windows[window] = self.get_monitor_geometry_with_window(
            window)
        self.exposed_windows.insert(0, window)
        self.window_vscreen[window] = self.current_vscreen
        window.map()
        window.change_attributes(
            event_mask=X.EnterWindowMask
            | X.LeaveWindowMask
            | X.ButtonPressMask
        )

    def unmanage_window(self, window):
        debug('function: unmanage_window called')
        if window in self.managed_windows:
            debug('unmanaged')
            self.window_vscreen.pop(window)
            self.managed_windows.pop(window)
        if window in self.exposed_windows:
            idx = self.exposed_windows.index(window)
            self.exposed_windows.pop(idx)
        if window == self.framed_window:
            self.framed_window = None
        if self.always_top[self.current_vscreen] == window:
            self.always_top[self.current_vscreen] = None

    def sort_exposed_windows(self):
        debug('function: sort_exposed_windows called')

        def sort_key(window):
            geom = self.get_window_geometry(window)
            if geom is None:
                return 1 << 31
            else:
                return geom.x * self.maxsize['height'] + geom.y

        self.exposed_windows = sorted(self.exposed_windows, key=sort_key)

    def focus_window(self, window):
        # debug('function: focus_window called')
        if window not in self.exposed_windows:
            return
        debug('debug: focused {}'.format(self.get_window_name(window)))
        window.set_input_focus(X.RevertToParent, 0)
        window.configure(stack_mode=X.Above)
        self.framed_window = window
        self.stack_always_top()
        self.draw_frame_windows()

    def focus_next_window(self, window, direction=FORWARD):
        # debug('function: focus_next_window called')
        if not self.exposed_windows:
            return
        if window in self.exposed_windows:
            idx = self.exposed_windows.index(window)
            if direction == FORWARD:
                idx = (idx + 1) % len(self.exposed_windows)
            else:
                idx -= 1
            next_window = self.exposed_windows[idx]
        else:
            next_window = self.exposed_windows[0]
        self.focus_window(next_window)

    def get_window_geometry(self, window):
        # debug('debug: get_window_geometry called')
        try:
            return window.get_geometry()
        except:
            return None

    def get_monitor_coverarea(self, wgeom, mgeom):
        xmin = min(wgeom.x, mgeom['x'])
        xmax = max(wgeom.x + wgeom.width, mgeom['x'] + mgeom['width'])
        xsum = wgeom.width + mgeom['width']
        xcover = max(0, xsum - (xmax - xmin))
        ymin = min(wgeom.y, mgeom['y'])
        ymax = max(wgeom.y + wgeom.height, mgeom['y'] + mgeom['height'])
        ysum = wgeom.height + mgeom['height']
        ycover = max(0, ysum - (ymax - ymin))
        return xcover * ycover

    def get_monitor_geometry_with_window(self, window):
        # debug('function: get_monitor_geometry_with_window called')
        geom = self.get_window_geometry(window)
        if not geom:
            return list(self.monitor_geometries.values())[0]
        maxcoverage = 0
        maxmonitor = list(self.monitor_geometries.values())[0]
        for name, monitor in self.monitor_geometries.items():
            coverarea = self.get_monitor_coverarea(geom, monitor)
            coverage = coverarea / (monitor['width'] * monitor['height'])
            normcoverage = coverarea * coverage
            if maxcoverage < normcoverage:
                maxcoverage = normcoverage
                maxmonitor = monitor
        return maxmonitor

    def get_screen_size(self):
        debug('function: get_screen_size called')
        lines = subprocess.getoutput('xrandr').split('\n')
        for line in lines:
            match = re.search(r'current (\d+) x (\d+)', line)
            if match:
                return {
                    'width': int(match.group(1)),
                    'height': int(match.group(2)),
                }
        raise RuntimeError(
            "Could not determine screen size from xrandr output")

    def get_available_monitor_geometries(self):
        debug('function: get_available_monitor_geometries called')
        monitors = self.get_monitors_info()
        geometries = {}
        for name, monitor in monitors.items():
            if monitor['connected']:
                geom = monitor['geometry']
                if not geom:
                    debug(f'Monitor {name} is connected but not mapped.')
                    continue
                width, height, x, y = geom['width'], geom['height'] - \
                    self.bar_height, geom['x'], geom['y']
                geometries[name] = {
                    'name': name,
                    'width': width,
                    'height': height,
                    'x': x,
                    'y': y,
                }
        return geometries

    def get_monitors_info(self):
        debug('function: get_monitors_info called')
        lines = subprocess.getoutput('xrandr').split('\n')
        monitors = {}
        for line in lines[1:]:
            if 'connected' in line:
                name = line.split()[0]
                if ' connected' in line:
                    connected = True
                else:
                    connected = False
                try:
                    m = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', line)
                    width = int(m.group(1))
                    height = int(m.group(2))
                    x = int(m.group(3))
                    y = int(m.group(4))
                    geom = {
                        'width': width,
                        'height': height,
                        'x': x,
                        'y': y,
                    }
                except:
                    geom = None
                if 'primary' in line:
                    primary = True
                else:
                    primary = False
                monitors[name] = {
                    'connected': connected,
                    'geometry': geom,
                    'primary': primary,
                }
        return monitors

    def remap_monitors(self):
        debug('function: remap_monitors called')
        monitors = self.get_monitors_info()
        leftmost = True
        for name, monitor in monitors.items():
            if monitor['connected']:
                if leftmost:
                    leftmost = False
                    os.system(f'xrandr --output {name} --auto')
                else:
                    os.system(
                        f'xrandr --output {name} --auto --right-of {rightnext}')
                rightnext = name
            else:
                os.system(f'xrandr --output {name} --off')

    def reconfigure_monitors(self, remap):
        debug('function: reconfigure_monitors called')
        if remap:
            self.remap_monitors()
        updated_geometries = self.get_available_monitor_geometries()
        if len(updated_geometries) == 0:
            debug('no monitor is connected')
            return
        basemonitor = list(updated_geometries.values())[0]
        for window in self.managed_windows.keys():
            src = self.managed_windows.get(window, None)
            if src is None:
                debug('source window is None')
                continue
            dst = updated_geometries.get(src['name'], None)
            if dst is None:
                self.move_window_to_monitor(window, basemonitor)
            else:
                self.move_window_to_monitor(window, dst)
        self.monitor_geometries = updated_geometries

    def parse_xmodmap(self):
        debug('function: parse_xmodmap called')
        out = subprocess.getoutput('xmodmap')
        for modifier in self.mod_string:
            self.modmap[modifier] = []
            match = re.search(
                r'{} +(.+\(0x[0-9a-f]+\)(,  )?)+'.format(modifier), out)
            if match == None:
                continue
            keys = re.findall(r'([^?!,.]+ \(0x[0-9a-f]+\))', match.group(1))
            for k in keys:
                m = re.search(r'0x([0-9a-f]+)', k)
                value = int(m.group(0), 16)
                self.modmap[modifier].append(value)

    def maximize_window(self, window, mask):
        # debug('function: maximize_window called')
        if window not in self.exposed_windows:
            debug('debug: at maximize_window window is not in exposed_windows')
            return
        monitor = self.managed_windows.get(window, None)
        if monitor is None:
            return
        geom = self.get_window_geometry(window)
        x = geom.x
        y = geom.y
        width = geom.width
        height = geom.height

        # if window is maximized go back to tile view
        if (
            x == monitor['x']
            and y == monitor['y']
            and width == monitor['width']
            and height == monitor['height']
        ):
            print("we in here")
            self.tile_windows(window)
            return

        if mask & VERTICAL != 0:
            y = monitor['y']
            height = monitor['height']
        if mask & HORIZONTAL != 0:
            x = monitor['x']
            width = monitor['width']
        window.configure(x=x, y=y, width=width, height=height)

    def move_window_to_monitor(self, window, dst):
        # debug('function: move_window_to_monitor called')
        # dst must be a geometry.
        if window not in self.managed_windows:
            return
        src = self.managed_windows.get(window, None)
        if src is None:
            return
        wgeom = self.get_window_geometry(window)
        if wgeom is None:
            return
        hratio = dst['width'] / src['width']
        vratio = dst['height'] / src['height']
        x, y, width, height = wgeom.x, wgeom.y, wgeom.width, wgeom.height
        xd = x - src['x']
        yd = y - src['y']
        x = int(xd * hratio) + dst['x']
        y = int(yd * vratio) + dst['y']
        width = int(width * hratio)
        height = int(height * vratio)
        window.configure(x=x, y=y, width=width, height=height)
        self.managed_windows[window] = dst

    def move_window_to_next_monitor(self, window):
        # debug('function: move_window_to_next_monitor called')
        if window not in self.exposed_windows:
            return
        geom = self.get_window_geometry(window)
        if geom is None:
            return
        # src = self.get_monitor_geometry_with_window(window)
        src = self.managed_windows.get(window, None)
        if src is None:
            return
        srcidx = list(self.monitor_geometries.values()).index(src)
        dstidx = (srcidx + 1) % len(self.monitor_geometries)
        dst = list(self.monitor_geometries.values())[dstidx]
        self.move_window_to_monitor(window, dst)

    def destroy_window(self, window):
        debug('function: destroy_window called')
        if window not in self.managed_windows:
            return
        window.destroy()
        self.unmanage_window(window)

    def select_vscreen(self, num):
        # debug('function: select_vscreen called')
        if num < 0:
            return
        if num > MAX_VSCREEN:
            return
        self.current_vscreen = num
        self.exposed_windows = []
        for window in self.managed_windows.keys():
            if self.window_vscreen[window] == num:
                window.map()
                self.exposed_windows.append(window)
            else:
                window.unmap()

    def send_window_to_next_vscreen(self, window, direction):
        # debug('debug: send_window_to_next_vscreen called')
        if window not in self.exposed_windows:
            return None
        idx = self.window_vscreen[window]
        if direction == FORWARD:
            nextidx = (idx + 1) % MAX_VSCREEN
        else:
            nextidx = (idx - 1) % MAX_VSCREEN
        if self.always_top[idx] == window:
            self.always_top[idx] = None
            self.always_top[nextidx] = window
        self.window_vscreen[window] = nextidx
        return nextidx

    def get_tile_layout(self, tile_num):
        # debug('function: get_tile_layout called')
        tmp = int(math.sqrt(tile_num))
        # (row, col)
        if tmp**2 == tile_num:
            return (tmp, tmp)
        if (tmp + 1) * tmp >= tile_num:
            return (tmp, tmp + 1)
        return (tmp + 1, tmp + 1)

    def tile_windows(self, window):
        debug('function: tile_windows called')
        monitor = self.managed_windows.get(window, None)
        if monitor is None:
            return
        target_windows = []
        for win in self.exposed_windows:
            if monitor == self.managed_windows.get(win, None):
                target_windows.append(win)

        def sort_key(window):
            return window.id

        target_windows.sort(key=sort_key)
        nrows, ncols = self.get_tile_layout(len(target_windows))
        offcuts_num = nrows * ncols - len(target_windows)
        for row in reversed(range(nrows)):
            for col in reversed(range(ncols)):
                if not target_windows:
                    break
                win = target_windows.pop(0)
                x = monitor['x'] + monitor['width'] * col // ncols
                width = monitor['width'] // ncols
                if row == 1 and col < offcuts_num:
                    height = monitor['height'] * 2 // nrows
                    y = 0 + monitor['y']
                else:
                    height = monitor['height'] // nrows
                    y = monitor['y'] + monitor['height'] * row // nrows
                win.configure(x=x, y=y, width=width, height=height)

    def set_window_to_stack_top(self, window):
        # debug('callback: set_window_to_stack_top called')
        if window not in self.exposed_windows:
            return
        idx = self.exposed_windows.index(window)
        self.exposed_windows.pop(idx)
        self.exposed_windows.insert(0, window)

    def stack_always_top(self):
        window = self.always_top[self.current_vscreen]
        if window == None:
            return
        window.configure(stack_mode=X.Above)

    def cb_focus_next_window(self, event, args):
        debug('callback: cb_focus_next_window called')
        window = self.framed_window
        # self.selection_window.map()
        if self.is_selection_mode_enabled:
            # select normally
            self.focus_next_window(window, args)
        else:
            # enable selection mode
            self.is_selection_mode_enabled = True
            self.screen.root.grab_keyboard(
                True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)
            self.set_window_to_stack_top(window)
            if self.exposed_windows:
                self.focus_next_window(self.exposed_windows[0])
            modifier = event.state
            self.pressed_keys = set()
            for i in range(len(self.mod_string) + 1):
                if 1 << i & modifier != 0:
                    self.pressed_keys = self.pressed_keys | {
                        self.mod_mask_string[1 << i]}
        # self.update_selection_window()

    def cb_maximize_window(self, event):
        debug('callback: cb_maximize_window called')
        window = self.framed_window
        try:

            self.maximize_window(window, HORIZONTAL | VERTICAL)
            self.draw_frame_windows()
        except:
            return

    def cb_move_window_to_next_monitor(self, event):
        debug('callback: cb_move_window_to_next_monitor called')
        window = self.framed_window
        try:
            self.move_window_to_next_monitor(window)
            self.draw_frame_windows()
        except:
            return

    def cb_swap_windows_bw_monitors(self, event):
        debug('callback: cb_swap_windows_bw_monitors called')
        for window in self.exposed_windows:
            self.move_window_to_next_monitor(window)
        window = self.framed_window
        self.focus_window(window)

    def cb_destroy_window(self, event):
        debug('callback: cb_destroy_window called')
        window = self.framed_window
        try:
            self.destroy_window(window)
        except:
            return

    def cb_select_vscreen(self, event, num):
        debug('callback: cb_select_vscreen called')
        if self.current_vscreen == num:
            return
        self.select_vscreen(num)
        if self.exposed_windows:
            self.sort_exposed_windows()
            self.focus_window(self.exposed_windows[0])
        else:
            self.framed_window = None
            self.unmap_frame_windows()

    def cb_send_window_to_next_vscreen(self, event, args):
        debug('callback: cb_send_window_to_next_screen called')
        window = self.framed_window
        idx = self.send_window_to_next_vscreen(window, args)
        if idx is not None:
            self.select_vscreen(idx)
            self.focus_window(window)

    def cb_reconfigure_monitors(self, event, remap):
        debug('callback: cb_reconfigure_monitors called')
        self.reconfigure_monitors(remap)
        self.focus_window(self.framed_window)

    def cb_set_always_top(self, event):
        debug('callback: cb_set_always_top called')
        if self.always_top[self.current_vscreen] == self.framed_window:
            self.always_top[self.current_vscreen] = None
        else:
            self.always_top[self.current_vscreen] = self.framed_window

    def handle_motion_notify(self, event):
        debug('handler: handle_motion_notify called')
        xd = event.root_x - self.start.root_x
        yd = event.root_y - self.start.root_y
        if self.start.child == X.NONE:
            return
        now = time.time()
        if now - self.last_dragged_time < DRAG_INTERVAL:
            return
        self.last_dragged_time = now
        if event.child in self.frame_windows.values():
            return
        if self.start.detail == 1:
            # move
            self.start.child.configure(
                x=self.start_geom.x + xd, y=self.start_geom.y + yd)
        elif self.start.detail == 3:
            # resize
            if self.start_geom.width + xd <= WINDOW_MIN_WIDTH:
                return
            if self.start_geom.height + yd <= WINDOW_MIN_HEIGHT:
                return
            self.start.child.configure(
                width=self.start_geom.width + xd, height=self.start_geom.height + yd)
        self.draw_frame_windows()

    def handle_button_press(self, event):
        debug('handler: handle_button_press called')
        window = event.child
        if window in self.frame_windows.values():
            return
        if window not in self.managed_windows:
            return
        self.screen.root.grab_pointer(
            True, X.PointerMotionMask | X.ButtonReleaseMask, X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE, 0
        )
        self.focus_window(window)
        self.input_mode()
        self.start = event
        self.start_geom = self.get_window_geometry(window)

    def handle_button_release(self, event):
        debug('handler: handle_button_release called')
        self.display.ungrab_pointer(0)
        self.managed_windows[event.child] = self.get_monitor_geometry_with_window(
            event.child)

    def handle_enter_notify(self, event):
        debug('handler: handle_enter_notify called')
        window = event.window
        self.focus_window(window)
        window.set_input_focus(X.RevertToParent, 0)

    def handle_map_notify(self, event):
        debug('handler: handle_map_notify called')
        self.manage_window(event.window)

    def handle_unmap_notify(self, event):
        debug('handler: handle_unmap_notify called')
        if event.window in self.exposed_windows:
            self.unmanage_window(event.window)

    def handle_map_request(self, event):
        debug('handler: handle_map_request called')
        self.manage_window(event.window)
        self.focus_window(event.window)
        self.tile_windows(event.window)

    def handle_destroy_notify(self, event):
        debug('handler: handle_destroy_notify called')
        self.unmanage_window(event.window)
        self.focus_next_window(event.window)
        try:
            self.tile_windows(self.framed_window)
        except:
            return

    def handle_key_press(self, event):
        debug('handler: handle_key_press called')
        keycode = event.detail
        keysym = self.display.keycode_to_keysym(keycode, 0)
        modifier = event.state

        if keysym == XK.XK_i and self.mode == NORMAL_MODE:
            self.input_mode()
            return

        if (
            modifier & X.ShiftMask and
            keysym == XK.XK_Escape and
            self.mode == INPUT_MODE
        ):
            self.normal_mode()
            return

        if (
            modifier & X.ShiftMask and
            keysym == XK.XK_semicolon and
            self.mode == NORMAL_MODE
        ):
            self.command_mode()
            return

        if self.mode == NORMAL_MODE:
            rule = self.keybinds.get(keycode, None)
            if rule:
                if 'method' in rule:
                    method = getattr(self, rule['method'], None)
                    arg = rule.get('arg', None)
                    if method:
                        if arg is not None:
                            method(event, arg)
                        else:
                            method(event)
                elif 'function' in rule:
                    function = globals().get(rule['function'], None)
                    if function:
                        function()
                elif 'command' in rule:
                    debug(f'executing "{rule["command"]}"')
                    os.system(rule['command'])
        elif self.mode == COMMAND_MODE and keysym is not None:
            match keysym:
                case XK.XK_Escape:
                    self.normal_mode()
                case XK.XK_Return:
                    os.system(self.command_buff + ' &')
                    self.normal_mode()
                case XK.XK_BackSpace:
                    self.command_buff = self.command_buff[:-1]
                    self.draw_statusbar()
                case _:
                    key = XK.keysym_to_string(keysym)
                    if key is not None:
                        self.command_buff += key
                        self.draw_statusbar()

    def handle_key_release(self, event):
        debug('handler: handle_key_release called')
        keycode = event.detail
        modgroup = None
        for mod, keys in self.modmap.items():
            if keycode in keys:
                modgroup = mod
                break
        if modgroup == None:
            return
        if modgroup in self.pressed_keys:
            # disable selection mode
            self.display.ungrab_keyboard(X.CurrentTime)
            self.is_selection_mode_enabled = False
            # self.selection_window.unmap()

    def handle_configure_request(self, event):
        debug('handler: handle_configure_request called')
        window = event.window
        x = event.x
        y = event.y
        width = event.width
        height = event.height
        mask = event.value_mask
        if mask == 0b1111:
            window.configure(x=x, y=y, width=width, height=height)
        elif mask == 0b1100:
            window.configure(width=width, height=height)
        elif mask == 0b0011:
            window.configure(x=x, y=y)
        elif mask == 0b01000000:
            window.configure(event.stack_mode)
        if window in self.managed_windows.keys():
            self.managed_windows[window] = self.get_monitor_geometry_with_window(
                window)
            self.focus_window(window)

    def loop(self):
        while True:
            event = self.display.next_event()
            if event.type in EVENTS:
                handler = getattr(self, EVENTS[event.type], None)
                if handler:
                    handler(event)


def main():
    wm = vwm()
    os.environ["GTK_THEME"] = wm.config.gtk_theme
    os.environ["GTK_APPLICATION_PREFER_DARK_THEME"] = {
        'dark': '1',
        'light': '0'
    }.get(wm.config.mode, 0)
    os.environ["GTK_ICON_THEME"] = wm.config.icons

    for win in wm.managed_windows:
        print(wm.get_window_name(win), file=sys.stderr)
    wm.loop()


if __name__ == '__main__':
    main()
