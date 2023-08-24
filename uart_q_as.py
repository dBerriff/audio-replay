# Test of uasyncio stream_tr I/O using UART
# Author: Peter Hinch
# Copyright Peter Hinch 2017-2022 Released under the MIT license
# Link X1 and X2 to test.

"""
    initial development of uasyncio.Stream UART connection:
    - uses Queues for transmit and receive
    - coro is short for coroutine
"""

import uasyncio as asyncio
from machine import UART, Pin
from uart_ba_as import Queue
import hex_fns as hex_


class UartTR:
    """ implement UART Tx and Rx as stream_tr """
    
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
        """ coro: send out data item """
        while True:
            if self.tx_queue.is_data.is_set():
                item = self.tx_queue.get()
                self.s_writer.write(item)
                await self.s_writer.drain()
            await asyncio.sleep_ms(20)

    async def receiver(self):
        """ coro: read data stream_tr into buffer """
        while True:
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_len:
                # add copied bytearray
                self.rx_queue.put(bytearray(self.in_buf))
                self.data_ev.set()
            await asyncio.sleep_ms(20)


async def main():
    """ coro: test module classes """

    def q_dump(q_, name=''):
        """ destructive! : print queue contents:  """
        print(f'{name}queue contents:')
        while q_.q_len:
            item = q_.get()
            print(hex_.byte_array_str(item))

    data = bytearray(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    uart_tr = UartTR(uart, 10, Queue(20), Queue(20))

    for i in range(10):
        print(f'{i} Add item to queue')
        data[0] = i
        uart_tr.tx_queue.put(bytearray(data))

    task0 = asyncio.create_task(uart_tr.receiver())
    task1 = asyncio.create_task(uart_tr.sender())

    await asyncio.sleep_ms(1000)
    task1.cancel()
    task0.cancel()

    # demonstrate that items have been added to the queue
    q_dump(uart_tr.rx_queue, 'Receive ')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        print('Close current event loop')
        asyncio.new_event_loop()
