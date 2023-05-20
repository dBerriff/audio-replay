# Test of uasyncio stream I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

import uasyncio as asyncio
from machine import UART, Pin
uart = UART(0, 9600)
uart.init(tx=Pin(0), rx=Pin(1))


class UartTxRx(UART):
    """ UART transmit and receive through fixed-size buffers
        - UART0 maps to pins 0/1, 12/13, 16/17
        - UART1 maps to pins 4/5, 8/9
    """

    # buffer size and indices

    baud_rate = const(9600)
    
    def __init__(self, uart_, tx_pin, rx_pin, buf_size):
        super().__init__(uart_, self.baud_rate)
        self.init(tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.buf_size = buf_size
        self.tx_buf = bytearray(buf_size)
        self.rx_buf = bytearray(buf_size)
        self.swriter = asyncio.StreamWriter(self)
        self.sreader = asyncio.StreamReader(self)

    async def sender(self):
        print(tx_buf)
        while True:
            self.swriter.write(self.tx_buf)
            await self.swriter.drain()
            await asyncio.sleep(2)

    async def receiver(self):
        while True:
            res = await self.sreader.readinto(self.rx_buf)
            print('Received', res, self.rx_buf)


async def main():
    u_tr = UartTxRx(0, 0, 1, 10)
    tx_buf = bytearray(10)
    rx_buf = bytearray(10)
    tx_buf = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')

    asyncio.create_task(u_tr.sender())
    asyncio.create_task(u_tr.receiver())
    while True:
        print('in loop')
        await asyncio.sleep(1)


def test():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
        print('as_demos.auart.test() to run again.')


test()
