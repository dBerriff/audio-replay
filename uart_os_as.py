# uart_os_as.py

# Test of uasyncio stream_tr I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

"""
    developed by David B Jones for Famous Trains model railway, Derby.
    - http://www.famoustrains.org.uk
    initial development of uasyncio.Stream UART connection:
    - uses Queue for receive stream_tr although not actually required at 9600 BAUD
    - ! deque is not implemented in MP so circular list !
    - uses 'one-shot' send for commands
    - coro is short for coroutine
"""

import uasyncio as asyncio
from machine import UART
from machine import Pin


class Queue:
    """ simple FIFO list as queue
        - is_data and is_space Event.is_set() controls access
        - events should be set within tasks, hence coros.
    """

    def __init__(self, max_len=16):
        self.max_len = max_len
        self.q = [None] * max_len
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.is_space.set()

    async def add_item(self, item):
        """ coro: add item to the queue """
        self.q[self.next] = item
        self.next = (self.next + 1) % self.max_len
        if self.next == self.head:
            self.is_space.clear()
        self.is_data.set()

    async def pop_item(self):
        """ coro: remove item from the queue """
        item = self.q[self.head]
        self.head = (self.head + 1) % self.max_len
        if self.head == self.next:
            self.is_data.clear()
        self.is_space.set()
        return item

    @property
    def q_len(self):
        """ number of items in the queue """
        if self.head == self.next:
            if self.is_data.is_set():
                n = self.max_len
            else:
                n = 0
        else:
            n = (self.next - self.head) % self.max_len
        return n


class StreamTR:
    """ implement UART Tx and Rx as stream_tr """

    def __init__(self, stream, buf_len):
        self.stream = stream
        self.buf_len = buf_len
        self.rx_queue = Queue()
        self.s_writer = asyncio.StreamWriter(self.stream, {})
        self.s_reader = asyncio.StreamReader(self.stream)
        self.in_buf = bytearray(buf_len)

    async def sender(self, data):
        """ coro: send out data item """
        self.s_writer.write(data)
        await self.s_writer.drain()

    async def receiver(self):
        """ coro: read data stream_tr into buffer """
        while True:
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_len:
                # add received bytearray to queue
                await self.rx_queue.is_space.wait()
                # add copy of in_buf to queue, not pointer to in_buf!
                await self.rx_queue.add_item(bytearray(self.in_buf))


async def main():
    """ coro: test module classes """
    
    async def data_send(sender_):
        """ send out bytearrays of data """
        data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
        for i in range(10):
            data[0] = i
            print(f'Tx {data}')
            await sender_(data)

    async def q_consume(q_):
        """ pop queue contents:  """
        while True:
            await q_.is_data.wait()
            item = await q_.pop_item()
            print(f'Rx: {item} q-len: {q_.q_len}')
            # add short delay to force q content
            await asyncio.sleep_ms(200)

    print('Requires Pico loopback; connect Tx pin to Rx pin')
    print()

    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTR(uart, buf_len=10)
    asyncio.create_task(stream_tr.receiver())
    asyncio.create_task(q_consume(stream_tr.rx_queue))
    asyncio.create_task(data_send(stream_tr.sender))
    await asyncio.sleep_ms(5_000)
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        print('Close current event loop')
        asyncio.new_event_loop()
