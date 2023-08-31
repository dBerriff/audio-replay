# data_link.py

# uasyncio stream_tr I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license

"""
    adapted and developed by David B Jones for Famous Trains Derby.
    - http://www.famoustrains.org.uk
    - uses Queue for receive stream_tr although not actually required at 9600 BAUD
    - ! deque is not implemented in MP: code uses list
    - uses 'one-shot' send for commands
"""

import uasyncio as asyncio


class Queue:
    """ simple FIFO list as queue
        - is_data and is_space Events control access
        - "events should be set within tasks" so coros for put and get.
    """

    def __init__(self, q_item, max_q_len):
        self.max_len = max_q_len
        self.queue = [q_item] * max_q_len
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.is_space.set()

    async def put(self, item):
        """ coro: add item to the queue - multiple producers """
        async with self.put_lock:
            await self.is_space.wait()
            self.queue[self.next] = item
            self.next = (self.next + 1) % self.max_len
            if self.next == self.head:
                self.is_space.clear()
            self.is_data.set()

    async def get(self):
        """ coro: remove item from the queue - single consumer """
        await self.is_data.wait()
        item = self.queue[self.head]
        self.head = (self.head + 1) % self.max_len
        if self.head == self.next:
            self.is_data.clear()
        self.is_space.set()
        return item

    @property
    def q_len(self):
        """ number of items in the queue """
        if self.head == self.next:
            n = self.max_len if self.is_data.is_set() else 0
        else:
            n = (self.next - self.head) % self.max_len
        return n

    def q_dump(self):
        """ print out queue pointers and all item values """
        print(f'head: {self.head}; next: {self.next}')
        q_str = '['
        for i in range(self.max_len):
            q_str += f'{self.queue[i]}, '
        q_str = q_str[:-2] + ']'
        print(q_str)


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
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_size:
                await self.rx_queue.put(bytearray(self.in_buf))
