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
    - bytearray length is 10
"""

import uasyncio as asyncio
from machine import UART
from machine import Pin


class Queue:
    """ simple FIFO list as queue
        - is_data and is_space Event.is_set() controls access
        - events should be set within tasks, hence coros for add and pop.
    """

    def __init__(self, b_array_len, max_len=16):
        self.max_len = max_len
        self.queue = [bytearray(b_array_len)] * max_len
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.is_space.set()

    async def put(self, item):
        """ coro: add item to the queue """
        self.queue[self.next] = item
        self.next = (self.next + 1) % self.max_len
        if self.next == self.head:
            self.is_space.clear()
        self.is_data.set()

    async def get(self):
        """ coro: remove item from the queue """
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
            if self.is_data.is_set():
                n = self.max_len
            else:
                n = 0
        else:
            n = (self.next - self.head) % self.max_len
        return n

    def q_print(self):
        """ print out all queue-item values """
        print(f'head: {self.head}; next: {self.next}')
        q_str = '['
        for i in range(self.max_len):
            q_str += f'{self.queue[i]}, '
        q_str = q_str[:-2] + ']'
        print(q_str)


class StreamTR:
    """ implement UART Tx and Rx as stream_tr """

    def __init__(self, stream, buf_len, rx_queue):
        self.stream = stream
        self.buf_len = buf_len  # length of bytearray
        self.rx_queue = rx_queue
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
                await self.rx_queue.put(bytearray(self.in_buf))


async def main():
    """ coro: test module classes """
    
    byte_array_len = 10
    
    # loopback test of send and receive
    
    async def data_send(sender_):
        """ send out bytearrays of data """
        data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
        for i in range(byte_array_len):
            data[0] = i
            print(f'Tx {data}')
            await sender_(data)

    async def q_consume(q_):
        """ pop queue contents:  """
        while True:
            await q_.is_data.wait()
            item = await q_.get()
            print(f'== Rx: {item} q-len: {q_.q_len}')
            # test: delay to allow q content to build
            await asyncio.sleep_ms(10)

    print('Requires Pico loopback; connect Tx pin to Rx pin')
    print()

    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    queue = Queue(32)
    stream_tr = StreamTR(uart, byte_array_len, queue)
    asyncio.create_task(stream_tr.receiver())
    asyncio.create_task(data_send(stream_tr.sender))
    await asyncio.sleep_ms(200)
    asyncio.create_task(q_consume(queue))
    await asyncio.sleep_ms(1_000)
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        print('Close current event loop')
        asyncio.new_event_loop()
