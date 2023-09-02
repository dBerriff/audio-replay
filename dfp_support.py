""" asyncio button input
    - poll buttons and set button state
    - 0: not pressed; 1: clicked; 2: held
    - events are set on button release
"""
import uasyncio as asyncio
from machine import Pin
from micropython import const
import json
import os
from time import ticks_ms, ticks_diff


class Led:
    """ pin-driven LED """
    
    def __init__(self, pin):
        self.led = Pin(pin, Pin.OUT, value=0)
        self.led.off()

    async def blink(self, n):
        """ coro: blink the LED n times """
        # flash LED every 1000 ms
        for _ in range(n):
            await asyncio.sleep_ms(900)
            self.led.on()
            await asyncio.sleep_ms(100)
            self.led.off()
            

class ConfigFile:
    """ write and read json config files """
    
    def __init__(self, filename):
        self.filename = filename
        self.is_file = self.is_config()
    
    def write_config(self, data):
        """ write config file as json dict """
        with open(self.filename, 'w') as write_f:
            json.dump(data, write_f)
            self.is_file = True

    def read_config(self):
        """ return config data dict from file
            - calling code checks is_config() """
        with open(self.filename, 'r') as read_f:
            data = json.load(read_f)
        return data

    def is_config(self):
        """ check if config file exists """
        return self.filename in os.listdir()
        

class Button:
    """ button with click state - no debounce """

    PIN_ON = const(0)
    PIN_OFF = const(1)
    CLICK = const(1)

    def __init__(self, pin, name=''):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.name = name
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

    def __init__(self, pin, name=''):
        super().__init__(pin, name)

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


class VolButtons:
    """ player vol inc and dec buttons """
    
    def __init__(self, pin_up, pin_down, config_file):
        self.btn_inc = HoldButton(pin_up, 'v_inc')
        self.btn_dec = HoldButton(pin_down, 'v_dec')
        self.vol_max = 10
        self.vol_min = 0
        self.cf = config_file
        self.config = {}
        self.init_config()
        self.led = Led('LED')

    @property
    def vol(self):
        """ called infrequently; efficiency not an issue """
        return self.config['vol']

    @vol.setter
    def vol(self, value):
        self.config['vol'] = value

    def init_config(self):
        """ initialise from file or set to mid-point """
        if self.cf.is_config:
            self.config = self.cf.read_config()
        else:
            self.config = {'vol': 5}
        self.vol = self.config['vol']
        print(f'Volume set to: {self.vol}')

    def inc_vol(self):
        """ increment volume by 1 unit """
        if self.vol < self.vol_max:
            self.vol += 1 
    
    def dec_vol(self):
        """ decrement volume by 1 unit """
        if self.vol > self.vol_min:
            self.vol -= 1 
    
    def save_config(self):
        """ save volume setting """
        print('Configuration saved')
        self.cf.write_config(self.config)
        asyncio.create_task(self.led.blink(self.config['vol']))

    async def btn_inc_pressed(self):
        """ change player volume setting """
        button = self.btn_inc
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                self.inc_vol()
                print(f'Volume set to: {self.vol}')
            elif button.state == 2:
                self.save_config()
            button.press_ev.clear()

    async def btn_dec_pressed(self):
        """ change player volume setting """
        button = self.btn_dec
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                self.dec_vol()
                print(f'Volume set to: {self.vol}')
            elif button.state == 2:
                self.save_config()
            button.press_ev.clear()

    def poll_vol_buttons(self):
        """ start button polling """
        # buttons: self poll
        asyncio.create_task(self.btn_inc.poll_state())
        asyncio.create_task(self.btn_dec.poll_state())
        # inc and dec buttons: poll
        asyncio.create_task(self.btn_inc_pressed())
        asyncio.create_task(self.btn_dec_pressed())


async def loop():
    while True:
        await asyncio.sleep_ms(1000)


async def main():
    
    """ test button input """
    print('In main()')    
    cf = ConfigFile('config.json')
    vol_buttons = VolButtons(20, 21, cf)
    vol_buttons.poll_vol_buttons()
    await loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
