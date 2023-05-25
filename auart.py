# Test of uasyncio stream I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

import uasyncio as asyncio
from machine import UART, Pin
from collections import deque
import hex_fns as hex_


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
        self._q = deque((), size)
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

    def q_dump(self):
        """ for testing: print queue contents: destructive! """
        print('Queue contents:')
        while self.q_len:
            item = self.rmv_item()
            print(hex_.byte_array_str(item))


async def data_consumer(uart_tr_):
    """ eventually: test for consumption of Rx data """
    while True:
        await uart_tr_.data_ev.wait()
        # print('Buffer length:', uart_tr_.rx_queue.q_len)
        await asyncio.sleep_ms(200)
    
    
async def main():
    data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
    # tx_q = Queue(20)
    rx_q = Queue(20)
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    uart_tr = UartTR(uart, 10, rx_q)
    
    task1 = asyncio.create_task(uart_tr.receiver())
    task2 = asyncio.create_task(data_consumer(uart_tr))
    for i in range(10):
        data[0] = i
        print('Send:', hex_.byte_array_str(data))
        await uart_tr.sender(data)
    print()

    await asyncio.sleep_ms(1000)
    task1.cancel()
    #task2.cancel()
    uart_tr.rx_queue.q_dump()
    await asyncio.sleep_ms(200)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()
