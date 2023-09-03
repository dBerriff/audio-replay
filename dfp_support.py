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
        for _ in range(n):
            await asyncio.sleep_ms(900)
            self.led.on()
            await asyncio.sleep_ms(100)
            self.led.off()
            

class ConfigFile:
    """ write and read json config files """
    def __init__(self, filename):
        self.filename = filename

    def write_file(self, data):
        """ write config file as json dict """
        with open(self.filename, 'w') as write_f:
            json.dump(data, write_f)

    def read_file(self):
        """ return config data dict from file
            - calling code checks is_config() """
        with open(self.filename, 'r') as read_f:
            data = json.load(read_f)
        return data

    def is_file(self):
        """ check if config file exists """
        return self.filename in os.listdir()
        

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


class DfpButtons:
    """ player buttons """
    
    def __init__(self, play, v_dec, v_inc, config_file):
        self.buttons = {
            'play': Button(play),
            'v_inc': HoldButton(v_inc),
            'v_dec': HoldButton(v_dec)
        }
        self.led = Led('LED')
        self.cf = config_file
        self.track = 1
        self.vol_max = 10
        self.vol_min = 0
        self.config = {}
        self.init_config()

    @property
    def vol(self):
        """ called infrequently; efficiency not an issue """
        return self.config['vol']

    @vol.setter
    def vol(self, value):
        self.config['vol'] = value

    def init_config(self):
        """ initialise from file or set to mid-point """
        if self.cf.is_file():
            self.config = self.cf.read_file()
        else:
            self.config = {'vol': 5}
            self.save_config()
        self.vol = self.config['vol']
        print(f'Volume: {self.vol}')

    def play_track(self):
        """ play current track """
        # TEST
        print(f'Play track: {self.track}')
        self.track += 1

    def inc_vol(self):
        """ increment volume by 1 unit """
        # TEST
        if self.vol < self.vol_max:
            self.vol += 1
            print(f'Volume: {self.vol}')
    
    def dec_vol(self):
        """ decrement volume by 1 unit """
        # TEST
        if self.vol > self.vol_min:
            self.vol -= 1
            print(f'Volume: {self.vol}')
    
    def save_config(self):
        """ save volume setting """
        print('Save config')
        self.cf.write_file(self.config)
        asyncio.create_task(self.led.blink(self.config['vol']))

    async def play_btn_pressed(self):
        """ change player volume setting """
        button = self.buttons['play']
        while True:
            await button.press_ev.wait()
            self.play_track()
            button.press_ev.clear()

    async def v_btn_pressed(self, btn_, click_action):
        """ change player volume setting """
        button = self.buttons[btn_]
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                click_action()
            elif button.state == 2:
                self.save_config()
            button.press_ev.clear()

    async def inc_btn_pressed(self):
        """ change player volume setting """
        asyncio.create_task(self.v_btn_pressed('v_inc', self.inc_vol))

    async def dec_btn_pressed(self):
        """ change player volume setting """
        asyncio.create_task(self.v_btn_pressed('v_dec', self.dec_vol))

    def poll_buttons(self):
        """ start button polling """
        # buttons: self poll
        asyncio.create_task(self.buttons['play'].poll_state())
        asyncio.create_task(self.buttons['v_inc'].poll_state())
        asyncio.create_task(self.buttons['v_dec'].poll_state())
        # buttons: respond to press
        asyncio.create_task(self.play_btn_pressed())
        asyncio.create_task(self.inc_btn_pressed())
        asyncio.create_task(self.dec_btn_pressed())


async def main():
    """ test button input """

    async def loop():
        while True:
            await asyncio.sleep_ms(1000)

    print('In main()')
    # play, v_dec, v_inc, config_file
    buttons = DfpButtons(20, 21, 22, ConfigFile('config.json'))
    buttons.poll_buttons()
    await loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
