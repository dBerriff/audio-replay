# data_link.py

# uasyncio stream_tr I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license

"""
    adapted and developed by David B Jones for Famous Trains Derby.
    - uses a queue or buffer for Tx and Rx streams
    - ! deque is not implemented in MP so queue uses a list of items
"""

import asyncio
from machine import Pin, UART


class StreamTR:
    """ implement UART Tx and Rx as stream_tr """

    def __init__(self, stream, buf_size, tx_queue, rx_queue):
        self.stream = stream
        self.buf_size = buf_size  # length of bytearray
        self.tx_queue = tx_queue
        self.rx_queue = rx_queue
        self.s_writer = asyncio.StreamWriter(self.stream, {})
        self.s_reader = asyncio.StreamReader(self.stream)
        self.in_buf = bytearray(buf_size)

        asyncio.create_task(self.receiver())
        asyncio.create_task(self.sender())

    async def sender(self):
        """ coro: send out Tx data-stream items from Tx queue """
        while True:
            await self.tx_queue.is_data.wait()
            data = await self.tx_queue.get()
            self.s_writer.write(data)
            await self.s_writer.drain()

    async def receiver(self):
        """ coro: read Rx data-stream item into Rx buffer """
        while True:
            await self.s_reader.readinto(self.in_buf)
            await self.rx_queue.put(bytearray(self.in_buf))


class DataLink:
    """ implement data link between player app and device """

    def __init__(self, pin_tx, pin_rx, baud_rate, ba_size, tx_queue, rx_queue):
        uart = UART(0, baud_rate)
        uart.init(tx=Pin(pin_tx), rx=Pin(pin_rx))
        self.tx_queue = tx_queue
        self.rx_queue = rx_queue
        self.stream_tx_rx = StreamTR(uart, ba_size, self.tx_queue, self.rx_queue)
        self.sender = self.stream_tx_rx.sender
