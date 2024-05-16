# data_link.py

# uasyncio stream_tr I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license

"""
    adapted and developed by David B Jones
    - uses a queue or buffer for Tx and Rx streams
    - ! deque was not (yet?) implemented in MP so
        queue uses a list of items
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
        # aliases - parameters 'loop' and 'reader' magically supplied
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


class Buffer:
    """ single item buffer
        - put_lock supports multiple data producers
    """

    def __init__(self):
        self._item = None
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.get_lock = asyncio.Lock()
        self.is_space.set()

    async def put(self, item):
        """ coro: add item to buffer
            - put_lock supports multiple producers
        """
        async with self.put_lock:
            await self.is_space.wait()
            self._item = item
            self.is_data.set()
            self.is_space.clear()

    async def get(self):
        """ coro: remove item from buffer
            - get_lock supports multiple consumers
                -- not tested
        """
        async with self.get_lock:
            await self.is_data.wait()
            self.is_space.set()
            self.is_data.clear()
            return self._item

    @property
    def q_len(self):
        """ number of items in the buffer to match queue interface """
        if self.is_data.is_set():
            return 1
        else:
            return 0


class Queue(Buffer):
    """ FIFO queue
        - is_data and is_space events control access
        - Event.set() "must be called from within a task",
          hence coros.
        - using array rather than list gave no measurable advantages
    """

    def __init__(self, length):
        super().__init__()
        self.length = length
        self.queue = [None] * length
        self.head = 0
        self.next = 0

    async def put(self, item):
        """ coro: add item to the queue """
        async with self.put_lock:
            await self.is_space.wait()
            self.queue[self.next] = item
            self.next = (self.next + 1) % self.length
            if self.next == self.head:
                self.is_space.clear()
            self.is_data.set()

    async def get(self):
        """ coro: remove item from the queue """
        async with self.get_lock:
            await self.is_data.wait()
            item = self.queue[self.head]
            self.head = (self.head + 1) % self.length
            if self.head == self.next:
                self.is_data.clear()
            self.is_space.set()
            return item

    @property
    def q_len(self):
        """ number of items in the queue """
        if self.head == self.next:
            n = self.length if self.is_data.is_set() else 0
        else:
            n = (self.next - self.head) % self.length
        return n
