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

    def add_item(self, item):
        self._len += 1
        self._q.append(item)
            
    def rmv_item(self):
        self._len -= 1
        return self._q.popleft()
    
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
        self.tx_buf = bytearray(buf_size)
        self.rx_buf = bytearray(buf_size)
        self.s_writer = asyncio.StreamWriter(self.stream, {})
        self.s_reader = asyncio.StreamReader(self.stream)

    async def write_tx_data(self):
        """ write the Tx buffer to UART """
        self.s_writer.write(self.tx_buf)
        await self.s_writer.drain()
        print(f'Tx_buf: {hex_fns.byte_array_str(self.tx_buf)}')

    async def read_rx_data(self):
        """ read data word into Rx buffer
            - when parser is ready """
        while True:
            await self.s_reader.readinto(self.rx_buf)
            print(f'Rx_buf: {hex_fns.byte_array_str(self.rx_buf)}')


async def main():
    test_data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
    print(hex_fns.byte_array_str(test_data))
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTxRx(uart, 10)
    stream_tr.tx_buf = test_data
    task0 = asyncio.create_task(stream_tr.read_rx_data())
    await stream_tr.write_tx_data()
    out_q = Queue(size=7)
    out_q.add_item('Hello World')
    out_q.add_item('Hello World again')
    print(out_q.n_items)
    while out_q.n_items:
        item = out_q.rmv_item()
        print(item)
    print(out_q.n_items)
    await task0


def test():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()


test()
