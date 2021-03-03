#!/usr/bin/env python3
import selectors, evdev, time


class Encoder:

    inc_callback = None  # Clockwise rotation callback (increment)
    dec_callback = None  # Anti-clockwise rotation callback (decrement)
    chg_callback = None  # Rotation callback (either way)
    sw_callback = None  # Switch pressed callback
    sw_long_callback = None  # Switch longpress callback

    def __init__(self, en_device=None, sw_device=None):

        self.sw_debounce_time = 250  # Debounce time (for switch only)
        self.sw_triggered = False  # Used to debounce a long switch click (prevent multiple callback calls)
        self.latest_switch_press = None

        self.en_device = evdev.InputDevice(en_device)
        self.sw_device = evdev.InputDevice(sw_device)

        self.selector = selectors.DefaultSelector()
        self.selector.register(self.en_device, selectors.EVENT_READ)
        self.selector.register(self.sw_device, selectors.EVENT_READ)

    def setup(self, **params):

        if "inc_callback" in params:
            assert callable(params["inc_callback"])
            self.inc_callback = params["inc_callback"]
        if "dec_callback" in params:
            assert callable(params["dec_callback"])
            self.dec_callback = params["dec_callback"]
        if "chg_callback" in params:
            assert callable(params["chg_callback"])
            self.chg_callback = params["chg_callback"]
        if "sw_callback" in params:
            assert callable(params["sw_callback"])
            self.sw_callback = params["sw_callback"]
        if "sw_long_callback" in params:
            assert callable(params["sw_long_callback"])
            self.sw_long_callback = params["sw_long_callback"]
        if "sw_debounce_time" in params:
            assert isinstance(params["sw_debounce_time"], int) or isinstance(
                params["sw_debounce_time"], float
            )
            self.sw_debounce_time = params["sw_debounce_time"]

    def _switch_press(self, long=False):
        now = time.time() * 1000
        if not self.sw_triggered:
            if self.latest_switch_press is not None:
                # Only callback if not in the debounce delta
                if now - self.latest_switch_press > self.sw_debounce_time:
                    if long:
                        self.sw_long_callback()
                    else:
                        self.sw_callback()
            else:  # Or if first press since script started
                if long:
                    self.sw_long_callback()
                else:
                    self.sw_callback()
        # self.sw_triggered = True
        self.latest_switch_press = now

    def _switch_release(self):
        self.sw_triggered = False

    def _clockwise_tick(self):

        if self.inc_callback is not None:
            self.inc_callback()
        if self.chg_callback is not None:
            self.chg_callback()

    def _counterclockwise_tick(self):

        if self.inc_callback is not None:
            self.dec_callback()
        if self.chg_callback is not None:
            self.chg_callback()

    def watch(self):
        while True:
            for key, mask in self.selector.select():
                device = key.fileobj
                for event in device.read():
                    if event.code == 0 and event.type == 2:
                        if event.value == -1:
                            self._counterclockwise_tick()
                        if event.value == 1:
                            self._clockwise_tick()
                    if event.code == 99 and event.value == 1:
                        long = False
                        press_time = time.time()
                        while 99 in self.sw_device.active_keys():
                            wait_time = time.time()
                            time.sleep(0.1)
                            if wait_time - press_time > 1.5:
                                long = True
                                self._switch_press(long=True)
                                break
                        if not long:
                            self._switch_press()
        return
