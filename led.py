# led.py
""" for (onboard) LED methods """
import asyncio
from machine import Pin, ADC


class Led:
    """ pin-driven LED """
    def __init__(self, pin):
        self.led = Pin(pin, Pin.OUT, value=0)
        self.led.off()
        self.blink_lock = asyncio.Lock()

    async def show(self, ms_):
        """ coro: light the LED for ms_ """
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
                asyncio.create_task(self.led.show(min((level_ - ref_u16), 200)))

async def main():
    l = Led('LED')
    await l.blink(10)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
