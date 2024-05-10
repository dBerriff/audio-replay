# buttons.py

import asyncio
from machine import Pin
from micropython import const
from time import ticks_ms, ticks_diff


class Button:
    """ button with click state - no debounce """
    PIN_ON = const(0)
    PIN_OFF = const(1)
    CLICK = const(1)

    def __init__(self, pin):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.state = 0
        self.press_ev = asyncio.Event()

    async def poll_state(self):
        """ poll self for press or hold events
            - button state must be cleared by event handler
        """
        prev_pin_state = self.PIN_OFF
        while True:
            pin_state = self._hw_in.value()
            if pin_state != prev_pin_state:
                if pin_state == self.PIN_OFF:
                    self.state = self.CLICK
                    self.press_ev.set()
                prev_pin_state = pin_state
            await asyncio.sleep_ms(20)

    def clear_state(self):
        """ set state to 0 """
        self.state = 0
        self.press_ev.clear()


class HoldButton(Button):
    """ add hold state """

    HOLD = const(2)
    T_HOLD = const(750)  # ms - adjust as required

    def __init__(self, pin):
        super().__init__(pin)

    async def poll_state(self):
        """ poll self for press or hold events
            - button state must be cleared by event handler
        """
        on_time = None
        prev_pin_state = self.PIN_OFF
        while True:
            pin_state = self._hw_in.value()
            if pin_state != prev_pin_state:
                time_stamp = ticks_ms()
                if pin_state == self.PIN_ON:
                    on_time = time_stamp
                else:
                    if ticks_diff(time_stamp, on_time) < self.T_HOLD:
                        self.state = self.CLICK
                    else:
                        self.state = self.HOLD
                    self.press_ev.set()
                prev_pin_state = pin_state
            await asyncio.sleep_ms(20)
