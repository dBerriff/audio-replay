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
    - Queue uses collections.deque for efficiency
    - uses 'one-shot' send for commands
    - coro is short for coroutine
"""

import uasyncio as asyncio
from machine import UART, Pin
from collections import deque
from machine import Pin
import hex_fns as hex_


class Queue:
    """ simple FIFO queue """

    def __init__(self, max_len):
        self.max_len = max_len
        # use deque for efficiency
        self._q = deque((), max_len)
        self._len = 0
        self.is_data = asyncio.Event()

    def add_item(self, item):
        """ add item to the queue, checking queue length """
        # _len is not checked in this version
        self._len += 1
        self._q.append(item)
        self.is_data.set()

    def rmv_item(self):
        """ remove item from the queue if not empty """
        # assumes Event is_data prevents attempted removal from empty queue
        self._len -= 1
        item = self._q.popleft()
        if self._len == 0:
            self.is_data.clear()
        return item

    @property
    def q_len(self):
        """ number of items in the queue """
        return self._len


class StreamTR:
    """ implement UART Tx and Rx as stream_tr """

    def __init__(self, stream, buf_len):
        self.stream = stream
        self.buf_len = buf_len
        self.rx_queue = Queue(20)
        self.s_writer = asyncio.StreamWriter(self.stream, {})
        self.s_reader = asyncio.StreamReader(self.stream)
        self.in_buf = bytearray(buf_len)
        self.data_ev = asyncio.Event()

    async def sender(self, data):
        """ coro: send out data item """
        self.s_writer.write(data)
        await self.s_writer.drain()

    async def receiver(self):
        """ coro: read data stream_tr into buffer """
        while True:
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_len:
                # add copied bytearray
                self.rx_queue.add_item(bytearray(self.in_buf))
                self.data_ev.set()
            await asyncio.sleep_ms(20)


async def main():
    """ coro: test module classes """

    def q_dump(q_, name=''):
        """ destructive! : print queue contents:  """
        print(f'{name}queue contents:')
        while q_.q_len:
            item = q_.rmv_item()
            print(hex_.byte_array_str(item))

    print('Requires Pico loopback: Tx pin to Rx pin')

    data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
    
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTR(uart, buf_len=10)
    asyncio.create_task(stream_tr.receiver())
    
    for i in range(10):
        data[0] = i
        await stream_tr.sender(data)
        print(f'{i} Tx item')

    await asyncio.sleep_ms(1000)

    # demonstrate that items have been added to the queue
    q_dump(stream_tr.rx_queue, name='Receive ')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        print('Close current event loop')
        asyncio.new_event_loop()
