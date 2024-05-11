# buttons.py

import asyncio
from machine import Pin, Signal
from micropython import const
from time import ticks_ms, ticks_diff


class Button:
    """
        button with click state - no debounce
        self._hw_in = Signal(
            pin, Pin.IN, Pin.PULL_UP, invert=True)
    """
    WAIT = const(0)
    CLICK = const(1)
    HOLD = const(2)
    POLL_INTERVAL = const(20)  # ms

    def __init__(self, pin, name=''):
        # Signal wraps pull-up logic with invert
        self._hw_in = Signal(pin, Pin.IN, Pin.PULL_UP, invert=True)
        if name:
            self.name = name
        else:
            self.name = str(pin)
        self.state = self.WAIT
        self.prev_state = self.WAIT
        self.active_states = (self.CLICK,)
        self.press_ev = asyncio.Event()
        self.enable_ev = asyncio.Event()
        self.press_ev.clear()
        self.enable_ev.clear()

    def get_state(self):
        """ check for button click state """
        pin_state = self._hw_in.value()
        if pin_state != self.prev_state:
            self.prev_state = pin_state
            if not pin_state:
                return self.CLICK
        return self.WAIT

    async def poll_state(self):
        """ poll self for press event
            - button state must be cleared by event handler
        """
        self.enable_ev.set()
        while True:
            await self.enable_ev.wait()
            self.state = self.get_state()
            if self.state in self.active_states:
                self.press_ev.set()
                self.enable_ev.clear()
            await asyncio.sleep_ms(self.POLL_INTERVAL)

    def clear_state(self):
        """ set state to 0 """
        self.state = self.WAIT
        self.press_ev.clear()
        self.enable_ev.set()


class HoldButton(Button):
    """ add hold state """

    T_HOLD = const(750)  # ms - adjust as required

    def __init__(self, pin, name=''):
        super().__init__(pin, name)
        self.active_states = (self.CLICK, self.HOLD)
        self.on_time = 0

    def get_state(self):
        """ check for button click or hold state """
        pin_state = self._hw_in.value()
        if pin_state != self.prev_state:
            self.prev_state = pin_state
            time_stamp = ticks_ms()
            if pin_state:
                # pressed, start timer
                self.on_time = time_stamp
            else:
                # released, determine action
                if ticks_diff(time_stamp, self.on_time) < self.T_HOLD:
                    return self.CLICK
                else:
                    return self.HOLD
        return self.WAIT


async def main():
    """ test DFPlayer controller """
    btn = Button(18, "play")
    print(btn.name)
    asyncio.create_task(btn.poll_state())
    i = 0
    while True:
        await btn.press_ev.wait()
        i += 1
        print(i, btn.state)
        print('Blocked')
        await asyncio.sleep_ms(5_000)
        btn.clear_state()
        print('Clear')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
