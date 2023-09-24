""" asyncio button input
    - poll buttons and set button state
    - 0: not pressed; 1: clicked; 2: held
    - events are set on button release
"""
import uasyncio as asyncio
from machine import Pin, ADC
from micropython import const
from random import randint
import json
import os
from time import ticks_ms, ticks_diff


class Led:
    """ pin-driven LED """
    def __init__(self, pin):
        self.led = Pin(pin, Pin.OUT, value=0)
        self.led.off()
        self.blink_lock = asyncio.Lock()

    async def flash(self, ms_):
        """ coro: flash the LED """
        self.led.on()
        await asyncio.sleep_ms(ms_)
        self.led.off()
        await asyncio.sleep_ms(ms_)

    async def blink(self, n):
        """ coro: blink the LED n times """
        async with self.blink_lock:
            for _ in range(n):
                await asyncio.sleep_ms(900)
                self.led.on()
                await asyncio.sleep_ms(100)
                self.led.off()
            await asyncio.sleep_ms(500)

    def turn_off(self):
        """ turn LED off """
        self.led.off()
            

class LedFlash:
    """ flash LED if ADC threshold exceeded """
    
    def __init__(self, adc_pin_, led_pin_):
        self.adc = ADC(adc_pin_)
        self.led = Led(led_pin_)

    async def poll_input(self):
        """ """
        ref_u16 = 25_400
        while True:
            await asyncio.sleep_ms(100)
            level_ = self.adc.read_u16()
            if level_ > ref_u16:
                asyncio.create_task(self.led.flash(min((level_ - ref_u16), 200)))


class ConfigFile:
    """ write and read json config files """
    def __init__(self, filename, default):
        self.filename = filename
        self.default = default

    def write_cf(self, data):
        """ write config file as json dict """
        with open(self.filename, 'w') as f:
            json.dump(data, f)

    def read_cf(self):
        """ return config data dict from file
            - calling code checks is_config() """
        if self.is_file(self.filename):
            with open(self.filename, 'r') as f:
                data = json.load(f)
        else:
            data = self.default
            self.write_cf(data)
        return data

    @staticmethod
    def is_file(f):
        """ check if config file exists """
        return f in os.listdir()
        

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


def shuffle(list_):
    """ return a shuffled list
        - Durstenfeld / Fisher-Yates shuffle algorithm """
    n = len(list_)
    if n < 2:
        return list_
    limit = n - 1
    for i in range(limit):  # exclusive range
        j = randint(i, limit)  # inclusive range
        list_[i], list_[j] = list_[j], list_[i]
    return list_
