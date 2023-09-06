# data_link.py

# uasyncio stream_tr I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license

"""
    adapted and developed by David B Jones for Famous Trains Derby.
    - http://www.famoustrains.org.uk
    - uses Queue for receive stream_tr although not actually required at 9600 BAUD
    - ! deque is not implemented in MP so code uses list
"""

import uasyncio as asyncio
from machine import Pin, UART


class StreamTR:
    """ implement UART Tx and Rx as stream_tr """

    def __init__(self, stream, buf_size, rx_queue):
        self.stream = stream
        self.buf_size = buf_size  # length of bytearray
        self.rx_queue = rx_queue
        self.s_writer = asyncio.StreamWriter(self.stream, {})
        self.s_reader = asyncio.StreamReader(self.stream)
        self.in_buf = bytearray(buf_size)

    async def sender(self, data):
        """ coro: send out data item """
        self.s_writer.write(data)
        await self.s_writer.drain()

    async def receiver(self):
        """ coro: read data stream item into buffer """
        while True:
            await self.s_reader.readinto(self.in_buf)
            await self.rx_queue.put(bytearray(self.in_buf))


class DataLink:
    """ implement data link between player app and device """

    def __init__(self, pin_tx, pin_rx, baudrate, ba_size, rx_queue):
        uart = UART(0, baudrate)
        uart.init(tx=Pin(pin_tx), rx=Pin(pin_rx))
        self.rx_queue = rx_queue
        self.stream_tx_rx = StreamTR(uart, ba_size, self.rx_queue)
        self.sender = self.stream_tx_rx.sender