# buttons.py
""" implement press and hold buttons
    class Button implements a <click> event
    class HoldButton extends Button to include a <hold> event
    - button methods are coroutines
    - create button.poll_state() as a task for a button to self-poll
"""

import asyncio
from machine import Pin, Signal
from micropython import const
from time import ticks_ms, ticks_diff


class Button:
    """ button with click state """
    # button states
    WAIT = const('0')
    CLICK = const('1')

    POLL_INTERVAL = const(20)  # ms; button self-poll period

    def __init__(self, pin, name):
        self.name = name

        self._hw_in = Signal(pin, Pin.IN, Pin.PULL_UP, invert=True)
        self.states = {'wait': self.name + self.WAIT,
                       'click': self.name + self.CLICK
                       }
        self.press_ev = asyncio.Event()  # initially cleared
        self.state = self.states['wait']

    async def poll_state(self):
        """ poll self for click event
            - event is set on button release
            - event handler must call clear_state
        """
        prev_pin_state = self._hw_in.value()
        while True:
            pin_state = self._hw_in.value()
            if pin_state != prev_pin_state:
                if not pin_state:
                    self.state = self.states['click']
                    self.press_ev.set()
                prev_pin_state = pin_state
            await asyncio.sleep_ms(self.POLL_INTERVAL)

    def clear_state(self):
        """ set state to 0 """
        self.state = self.states['wait']
        self.press_ev.clear()


class HoldButton(Button):
    """
        add button 'hold' state
        - T_HOLD sets hold time in ms
        -- set to 750 ms; adjust as required
    """
    # additional button state
    HOLD = const('2')
    T_HOLD = const(750)  # ms

    def __init__(self, pin, name=''):
        super().__init__(pin, name)
        self.states['hold'] = self.name + self.HOLD

    async def poll_state(self):
        """
            poll self for click or hold events
            - ! button state must be cleared by event handler
            - elapsed time measured in ms
        """
        on_time = ticks_ms()
        prev_pin_state = self._hw_in.value()
        while True:
            pin_state = self._hw_in.value()
            if pin_state != prev_pin_state:
                time_stamp = ticks_ms()
                if pin_state:
                    on_time = time_stamp
                else:
                    if ticks_diff(time_stamp, on_time) < self.T_HOLD:
                        self.state = self.states['click']
                    else:
                        self.state = self.states['hold']
                    self.press_ev.set()
                prev_pin_state = pin_state
            await asyncio.sleep_ms(self.POLL_INTERVAL)
