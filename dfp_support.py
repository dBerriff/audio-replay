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
    
    def __init__(self, play_pin, v_dec_pin, v_inc_pin):
        self.play_btn = Button(play_pin)
        self.v_inc_btn = HoldButton(v_inc_pin)
        self.v_dec_btn = HoldButton(v_dec_pin)
        self.led = Led('LED')
        # methods assigned by dfp_player
        self.next_track = None
        self.dec_vol = None
        self.inc_vol = None
        self.save_config = None

    def poll_buttons(self):
        """ start button polling """
        # buttons: self poll
        asyncio.create_task(self.play_btn.poll_state())
        asyncio.create_task(self.v_inc_btn.poll_state())
        asyncio.create_task(self.v_dec_btn.poll_state())
        # buttons: respond to press
        asyncio.create_task(self.play_btn_pressed())
        asyncio.create_task(self.inc_btn_pressed())
        asyncio.create_task(self.dec_btn_pressed())

    async def play_btn_pressed(self):
        """ change player volume setting
            - simple Button
        """
        button = self.play_btn
        while True:
            await button.press_ev.wait()
            await self.next_track()
            button.press_ev.clear()

    async def inc_btn_pressed(self):
        """ inc player volume setting
            - HoldButton
        """
        button_ = self.v_inc_btn
        while True:
            await button_.press_ev.wait()
            if button_.state == 1:
                await self.inc_vol()
            elif button_.state == 2:
                # await self.save_config()
                pass
            button_.press_ev.clear()

    async def dec_btn_pressed(self):
        """ dec player volume setting
            - HoldButton
        """
        button_ = self.v_dec_btn
        while True:
            await button_.press_ev.wait()
            if button_.state == 1:
                await self.dec_vol()
            elif button_.state == 2:
                # await self.save_config()
                pass
            button_.press_ev.clear()


async def main():
    """ test button input """

    async def loop():
        while True:
            await asyncio.sleep_ms(1000)
    
    async def dummy_next():
        print('next-track button clicked')

    async def dummy_dec():
        print('dec button clicked')

    async def dummy_inc():
        print('inc button clicked')

    async def dummy_save_config():
        print('save config')

    print('In main()')
    # play, v_dec, v_inc, config_file
    buttons = DfpButtons(20, 21, 22)
    # assign methods to buttons
    buttons.next_track = dummy_next
    buttons.dec_vol = dummy_dec
    buttons.inc_vol = dummy_inc
    buttons.save_config = dummy_save_config
    buttons.poll_buttons()
    await loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
