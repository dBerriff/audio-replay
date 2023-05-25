# Test of uasyncio stream I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

import uasyncio as asyncio
from machine import UART, Pin
from collections import deque


class UartTR:
    """ implement UART Tx and Rx as stream """
    
    def __init__(self, uart, buf_len, rx_queue):
        self.uart = uart
        self.buf_len = buf_len
        self.rx_queue = rx_queue
        self.out_buf = bytearray(buf_len)
        self.in_buf = bytearray(buf_len)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.s_reader = asyncio.StreamReader(self.uart)
        self.rx_data = ''
        self.data_ev = asyncio.Event()

    async def sender(self, data):
        """ send out data item """
        self.swriter.write(data)
        await self.swriter.drain()
        await asyncio.sleep_ms(200)

    async def receiver(self):
        """ read data stream into buffer """
        while True:
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_len:
                self.data_ev.set()
                # add copied bytearray
                self.rx_queue.add_item(bytearray(self.in_buf))


class Queue:
    """ implement simple FIFO queue
        from deque for efficiency """

    def __init__(self, size):
        self._q = deque((), size, 1)
        self.buf_len = size
        self._len = 0
        self.is_data = asyncio.Event()
    
    def add_item(self, item):
        """ add item to the queue, checking queue length """
        if self._len < self.buf_len:
            self._len += 1
            self._q.append(item)
        else:
            print('Queue overflow')
        print(self.q_len)
        self.is_data.set()
            
    def rmv_item(self):
        """ remove item from the queue, checking queue length """
        if self._len:
            self._len -= 1
            item = self._q.popleft()
        else:
            item = None
        if self._len == 0:
            self.is_data.clear()
        return item
    
    @property
    def q_len(self):
        """ number of items in the queue """
        return self._len

    def q_dump(self):
        """ for testing: print queue contents: destructive! """
        while self.q_len:
            item = self.rmv_item()
            print(self.q_len + 1, item)


async def data_consumer(uart_tr_):
    """ test for consumption of Rx data """
    while True:
        await uart_tr_.data_ev.wait()
        uart_tr_.data_ev.clear()
    
    
async def main():
    data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
    # tx_q = Queue(20)
    rx_q = Queue(5)
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    uart_tr = UartTR(uart, 10, rx_q)
    
    task1 = asyncio.create_task(uart_tr.receiver())
    task2 = asyncio.create_task(data_consumer(uart_tr))
    for i in range(10):
        data[0] = i
        print('Send:', data)
        await uart_tr.sender(data)
    print()

    await asyncio.sleep_ms(5000)
    task1.cancel()
    task2.cancel()
    uart_tr.rx_queue.q_dump()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
