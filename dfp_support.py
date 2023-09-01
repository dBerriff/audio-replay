""" asyncio button input
    - poll buttons and set button state
    - 0: not pressed; 1: clicked; 2: held
    - events are set on button release
"""
import uasyncio as asyncio
from machine import Pin
from micropython import const
import json
from time import ticks_ms, ticks_diff


class Led:
    """ implement pin-driven LED """
    
    def __init__(self, pin):
        self.led = Pin(pin, Pin.OUT, value=0)
        self.led.off()

    async def blink(self, n_blinks):
        """ coro: blink the onboard LED
            - earlier versions of MicroPython require
              25 rather than 'LED' if not Pico W
        """
        # flash LED every 1000 ms
        on_ms = 100
        off_ms = 900
        for _ in range(n_blinks):
            await asyncio.sleep_ms(off_ms)
            self.led.on()
            await asyncio.sleep_ms(on_ms)
            self.led.off()
            

class ConfigFile:
    """ write and read json config files """
    
    def __init__(self, filename):
        self.filename = filename
    
    def write_config(self, data):
        """ write configuration dictionary """
        with open(self.filename, 'w') as write_f:
            json.dump(data, write_f)

    def read_config(self):
        with open(self.filename, 'r') as read_f:
            data = json.load(read_f)
        return data


class Button:
    """ button with press and hold states
        - no debounce
    """

    # class variable: unique object id
    PIN_ON = const(0)
    PIN_OFF = const(1)
    CLICK = const(1)
    HOLD = const(2)
    T_HOLD = const(750)  # ms - adjust as required

    def __init__(self, pin, name):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.name = name
        self.state = 0
        self.press_ev = asyncio.Event()

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

    def clear_state(self):
        """ set state to 0 """
        self.state = 0
        self.press_ev.clear()


class VolButtons:
    """ player vol inc and dec buttons """
    
    def __init__(self, pin_up, pin_down):
        self.btn_inc = Button(pin_up, 'v_inc')
        self.btn_dec = Button(pin_down, 'v_dec')
        self.buttons = {'v_inc': self.btn_inc, 'v_dec': self.btn_dec}
        self.vol_delta = 0
        self.vol = 5  # for testing
        self.vol_max = 10
        self.vol_min = 0
        self.vol_changed = asyncio.Event()
        self.vol_save = asyncio.Event()
        
        self.led = Led('LED')

    async def btn_inc_pressed(self):
        """ change player volume setting """
        button = self.btn_inc
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                if self.vol < self.vol_max:
                    self.vol += 1 
                    self.vol_changed.set()
            elif button.state == 2:
                self.vol_save.set()
            button.press_ev.clear()

    async def btn_dec_pressed(self):
        """ change player volume setting """
        button = self.btn_dec
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                if self.vol > self.vol_min:
                    self.vol -= 1
                    self.vol_changed.set()
            elif button.state == 2:
                self.vol_save.set()
            button.press_ev.clear()

    def poll_vol_buttons(self):
        """ start button polling """
        # button-press: click or hold
        asyncio.create_task(self.btn_inc.poll_state())
        asyncio.create_task(self.btn_dec.poll_state())
        # inc or dec button pressed
        asyncio.create_task(self.btn_inc_pressed())
        asyncio.create_task(self.btn_dec_pressed())        

    async def vol_change_respond(self):
        """ act on volume change """
        while True:
            await self.vol_changed.wait()
            self.vol_changed.clear()
            print(self.vol)

    async def vol_save_respond(self):
        """ act on volume save """
        while True:
            await self.vol_save.wait()
            self.vol_save.clear()
            asyncio.create_task(self.led.blink(self.vol))


async def main():
    """ test button input """
    print('In main()')    
    onboard = Led('LED')
    asyncio.create_task(onboard.blink(5))

    vol_buttons = VolButtons(20, 21)
    # asyncio.create_task(vol_buttons.poll_vol_buttons())
    vol_buttons.poll_vol_buttons()
    asyncio.create_task(vol_buttons.vol_change_respond())
    await vol_buttons.vol_save_respond()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
