# Test of uasyncio stream I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

"""
    initial development of uasyncio.Stream UART connection:
    - uses Queues for transmit and receive
"""

import uasyncio as asyncio
from machine import UART, Pin
from collections import deque
import hex_fns as hex_


class Queue:
    """
    implement simple FIFO queue from deque for efficiency
    """

    def __init__(self, max_len):
        self.max_len = max_len
        self._q = deque((), max_len)
        self._len = 0
        self.is_data = asyncio.Event()
    
    def add_item(self, item):
        """ add item to the queue, checking queue length """
        if self._len < self.max_len:
            self._len += 1
            self._q.append(item)
        else:
            print('Queue overflow')
        self.is_data.set()
            
    def rmv_item(self):
        """ remove item from the queue """
        self._len -= 1
        if self._len == 0:
            self.is_data.clear()
        return self._q.popleft()
    
    @property
    def q_len(self):
        """ number of items in the queue """
        return self._len


class UartTR:
    """ implement UART Tx and Rx as stream """
    
    def __init__(self, uart, buf_len, tx_queue, rx_queue):
        self.uart = uart
        self.buf_len = buf_len
        self.tx_queue = tx_queue
        self.rx_queue = rx_queue
        self.s_writer = asyncio.StreamWriter(self.uart, {})
        self.s_reader = asyncio.StreamReader(self.uart)
        self.in_buf = bytearray(buf_len)
        self.data_ev = asyncio.Event()

    async def sender(self):
        """ send out data item """
        while True:
            if self.tx_queue.is_data.is_set():
                self.s_writer.write(self.tx_queue.rmv_item())
                await self.s_writer.drain()
            await asyncio.sleep_ms(20)

    async def receiver(self):
        """ read data stream into buffer """
        while True:
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_len:
                # add copied bytearray
                self.rx_queue.add_item(bytearray(self.in_buf))
                self.data_ev.set()
            await asyncio.sleep_ms(20)


async def main():
    
    def q_dump(q_, name=''):
        """ destructive! : print queue contents:  """
        print(f'{name}queue contents:')
        while q_.q_len:
            item = q_.rmv_item()
            print(hex_.byte_array_str(item))

    data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    uart_tr = UartTR(uart, 10, Queue(20), Queue(20))

    for i in range(10):
        print(f'{i} Add item to queue')
        data[0] = i
        uart_tr.tx_queue.add_item(bytearray(data))

    task0 = asyncio.create_task(uart_tr.receiver())
    task1 = asyncio.create_task(uart_tr.sender())

    await asyncio.sleep_ms(1000)
    task1.cancel()
    task0.cancel()
    q_dump(uart_tr.rx_queue, 'Receive ')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        print('Close current event loop')
        asyncio.new_event_loop()
