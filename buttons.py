""" asyncio button input
    - poll buttons and set button state
    - 0: not pressed; 1: clicked; 2: held
    - events are set on button release
"""
import uasyncio as asyncio
from machine import Pin
from micropython import const
from time import ticks_ms, ticks_diff


class Button:
    """ button with press and hold states
        - no debounce
    """

    # class variable: unique object id
    PIN_ON = const(0)
    PIN_OFF = const(1)
    CLICK = const(1)
    HOLD = const(2)

    _id = 0

    T_HOLD = const(750)  # ms - adjust as required

    def __init__(self, pin):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self._id = Button._id
        Button._id += 1
        self.state = 0
        self.press_ev = asyncio.Event()
        self.hold_ev = asyncio.Event()

    @property
    def id_(self):
        return self._id

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
            await asyncio.sleep_ms(75)

    def clear_state(self):
        """ set state to 0 """
        self.state = 0
        self.press_ev.clear()


class VolButtons:
    """ player vol inc and dec buttons """
    
    def __init__(self, pin_up, pin_down):
        self.btn_up = Button(pin_up)
        self.btn_down = Button(pin_down)
        self.vol_delta = 0
        self.vol_change = asyncio.Event()
        self.vol = 15  # for testing
        self.vol_max = 30
        self.vol_min = 0

    
    async def poll_vol_buttons(self):
        """ change player volume setting """
        asyncio.create_task(self.btn_up.poll_state())
        asyncio.create_task(self.btn_down.poll_state())
        
        while True:
            if self.btn_up.press_ev.is_set():
                if self.vol < self.vol_max:
                    self.vol += 1 
                self.btn_up.press_ev.clear()
                self.vol_change.set()
            elif self.btn_down.press_ev.is_set():
                if self.vol > self.vol_min:
                    self.vol -= 1 
                self.btn_down.press_ev.clear()
                self.vol_change.set()
            await asyncio.sleep_ms(200)


async def main():
    """ test button input """

    async def report_vol_change(vol_buttons):
        """"""
        while True:
            await vol_buttons.vol_change.wait()
            print(f'volume setting: {vol_buttons.vol}')
            vol_buttons.vol_change.clear()

    print('In main()')

    vol_buttons = VolButtons(20, 21)
    asyncio.create_task(report_vol_change(vol_buttons))
    await vol_buttons.poll_vol_buttons()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
