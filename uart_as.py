# Test of uasyncio stream I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

import uasyncio as asyncio
from machine import UART, Pin
from collections import deque
import hex_fns


class Queue:
    """ implement simple FIFO queue
        from deque for efficiency """
    def __init__(self, size):
        self._q = deque((), size)
        self._len = 0
        self.is_data = asyncio.Event()
    
    @property
    def n_items(self):
        return self._len

    def add_item(self, item):
        self._len += 1
        self._q.append(item)
        print('add:', item)
        self.is_data.set()
            
    def rmv_item(self):
        self._len -= 1
        item = self._q.popleft()
        print('rmv:', item)
        if self._len == 0:
            self.is_data.clear()
            print('self.is_data is cleared')
        return item
    
    @property
    def n_items(self):
        return self._len
    

class StreamTxRx:
    """ UART transmit and receive through fixed-size buffers
        - UART0 maps to pins 0/1, 12/13, 16/17
        - UART1 maps to pins 4/5, 8/9
    """

    # buffer size and indices

    baud_rate = const(9600)

    def __init__(self, stream, buf_size):
        self.stream = stream
        self.buf_size = buf_size
        self.tx_buf = Queue(buf_size)
        self.rx_buf = Queue(buf_size)
        self.s_writer = asyncio.StreamWriter(self.stream, {})
        self.s_reader = asyncio.StreamReader(self.stream)

    async def write_tx_data(self):
        """ write the Tx buffer to UART """
        item = self.tx_buf.rmv_item()
        self.s_writer.write()
        await self.s_writer.drain()

    async def read_rx_data(self):
        """ read data word into Rx buffer
            - when parser is ready """
        print('In read_rx_data()')
        while True:
            print('self.rx_buf.is_data.is_set():', self.rx_buf.is_data.is_set())
            await self.rx_buf.is_data.wait()
            print('self.rx_buf.is_data.is_set():', self.rx_buf.is_data.is_set())
            data = self.rx_buf.rmv_item()
            print(f'Rx_buf: {data}')


async def main():
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTxRx(uart, 10)
    task0 = asyncio.create_task(stream_tr.read_rx_data())
    stream_tr.tx_buf.add_item('Hello World')
    stream_tr.tx_buf.add_item('Hello World again')
    await stream_tr.write_tx_data()
    await task0


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
