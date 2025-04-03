from wm.utils import KeyUtil
import logging
import subprocess
import xcffib
import xcffib.xproto
import yaml

NEXT_WINDOW = 'NEXT_WINDOW'
PREVIOUS_WINDOW = 'PREVIOUS_WINDOW'


class WindowManager:
    def __init__(self):
        # TODO: put into .config/nostwm
        with open('config.yaml') as f:
            self.config = yaml.safe_load(f)

        self.conn = xcffib.connect()
        self.key_util = KeyUtil(self.conn)
        self.screen = self.conn.get_setup().roots[0]
        self.root_window = self.screen.root

        self.windows = []
        self.current_window = 0

    def run(self):
        # Tell X Server what events we want for root window
        cookie = self.conn.core.ChangeWindowAttributesChecked(
            self.root_window,
            xcffib.xproto.CW.EventMask,
            [
                xcffib.xproto.EventMask.SubstructureNotify |
                xcffib.xproto.EventMask.SubstructureRedirect,
            ]
        )

        # check req was valid
        try:
            cookie.check()
        except:
            logging.error(logging.traceback.forat_exec())
            print('Request invalid, another window manager may be running')
            exit()

        for action in self.config['actions']:
            keycode = self.key_util.get_keycode(
                KeyUtil.string_to_keysym(action['key'])
            )

            modifier = getattr(xcffib.xproto.KeyButMask,
                               self.config['modifier'], 0)

            self.conn.core.GrabKeyChecked(
                False,
                self.root_window,
                modifier,
                keycode,
                xcffib.xproto.GrabMode.Async,
                xcffib.xproto.GrabMode.Async
            ).check()

        while True:
            event = self.conn.wait_for_event()

            if isinstance(event, xcffib.xproto.KeyPressEvent):
                self._handle_key_press_event(event)
            if isinstance(event, xcffib.xproto.MapRequestEvent):
                self._handle_map_request_event(event)
            if isinstance(event, xcffib.xproto.ConfigureRequestEvent):
                self._handle_configure_request_event(event)

            self.conn.flush()

    def _handle_map_request_event(self, event):
        attributes = self.conn.core.GetWindowAttributes(
            event.window
        ).reply()

        # if a window sets override_redirect don't manage it
        if attributes.override_redirect:
            return

        self.conn.core.MapWindow(event.window)

        self.conn.core.ConfigureWindow(
            event.window,
            xcffib.xproto.ConfigWindow.X |
            xcffib.xproto.ConfigWindow.Y |
            xcffib.xproto.ConfigWindow.Width |
            xcffib.xproto.ConfigWindow.Height,
            [
                0,
                0,
                self.screen.width_in_pixels,
                self.screen.height_in_pixels,
            ]
        )

        if event.window not in self.windows:
            self.windows.insert(0, event.window)
            self.current_window = 0

    def _handle_configure_request_event(self, event):
        self.conn.core.ConfigureWindow(
            event.window,
            xcffib.xproto.ConfigWindow.X |
            xcffib.xproto.ConfigWindow.Y |
            xcffib.xproto.ConfigWindow.Width |
            xcffib.xproto.ConfigWindow.Height |
            xcffib.xproto.ConfigWindow.BorderWidth |
            xcffib.xproto.ConfigWindow.Sibling |
            xcffib.xproto.ConfigWindow.StackMode,
            [
                event.x,
                event.y,
                event.width,
                event.height,
                event.border_width,
                event.sibling,
                event.stack_mode
            ]
        )

    def _handle_action(self, action):
        if action == NEXT_WINDOW:
            if len(self.windows) == 0:
                return

            self.conn.core.UnmapWindow(self.windows[self.current_window])
            self.current_window += 1

            if self.current_window >= len(self.windows):
                self.current_window = 0

            self.conn.core.MapWindow(self.windows[self.current_window])

        if action == PREVIOUS_WINDOW:
            if len(self.windows) == 0:
                return

            self.conn.core.UnmapWindow(self.windows[self.current_window])
            self.current_window -= 1

            if self.current_window < 0:
                self.current_window = len(self.windows) - 1

            self.conn.core.MapWindow(self.windows[self.current_window])

    def _handle_key_press_event(self, event):
        for action in self.config['actions']:
            keycode = self.key_util.get_keycode(
                KeyUtil.string_to_keysym(action['key'])
            )

            modifier = getattr(xcffib.xproto.KeyButMask,
                               self.config['modifier'], 0)

            if keycode == event.detail and modifier == event.state:
                if 'command' in action:
                    subprocess.Popen(action['command'])
                if 'action' in action:
                    self._handle_action(action['action'])
