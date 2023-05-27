from machine import UART, Pin
from collections import deque
import uasyncio as asyncio
import hex_fns as hex_


class Queue:
    """
    implement simple FIFO queue (of bytearray)
    using deque for efficiency
    """

    def __init__(self, max_len):
        self._q = deque((), max_len)
        self.max_len = max_len
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

    def __init__(self, uart, buf_len, rx_queue):
        self.uart = uart
        self.buf_len = buf_len
        self.rx_queue = rx_queue
        self.s_writer = asyncio.StreamWriter(self.uart, {})
        self.s_reader = asyncio.StreamReader(self.uart)
        self.in_buf = bytearray(buf_len)
        self.data_ev = asyncio.Event()

    async def sender(self, data, wait_ms=0):
        """ coro: send out data item """
        self.s_writer.write(data)
        await self.s_writer.drain()
        await asyncio.sleep_ms(wait_ms)

    async def receiver(self):
        """ coro: read data stream into buffer """
        while True:
            res = await self.s_reader.readinto(self.in_buf)
            if res == self.buf_len:
                # add copied bytearray
                self.rx_queue.add_item(bytearray(self.in_buf))
                self.data_ev.set()
            await asyncio.sleep_ms(20)


class CommandHandler:
    """ formats, sends and receives command and query messages """

    BUF_SIZE = const(10)
    # data-byte indices
    CMD = const(3)
    P_H = const(5)  # parameter
    P_L = const(6)
    C_H = const(7)  # checksum
    C_L = const(8)

    R_FB = const(0)  # require player feedback? 0 or 1

    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}
    
    hex_cmd = {
        0x01: 'next',
        0x02: 'prev',
        0x03: 'track',  # 0-2999 (? 1-2999)
        0x04: 'vol_inc',
        0x05: 'vol_dec',
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # normal/pop/rock/jazz/classic/bass
        0x08: 'playback_mode',  # repeat/folder-repeat/single-repeat/random
        0x09: 'play_src',  # u/tf/aux/sleep/flash 1/2/3/4/5
        0x0c: 'reset',
        0x0d: 'playback',
        0x0e: 'pause',
        0x0f: 'folder',  # 1-10
        0x11: 'repeat_play',  # 0: stop; 1: start
        0x3d: 'tf_finish',
        0x3f: 'q_init',  # 01: U-disk, 02: TF-card, 04: PC, 08: Flash
        0x40: 're_tx',
        0x41: 'reply',
        0x42: 'q_status',
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x45: 'q_mode',
        0x46: 'q_version',
        0x48: 'q_tf_files',
        0x4a: 'keep_on',  # not understood
        0x4c: 'q_tf_track',
        }
    
    # inverse dictionary mapping
    cmd_hex = {value: key for key, value in hex_cmd.items()}
    
    play_set = {'next', 'prev', 'track', 'playback'}

    def __init__(self, stream):
        self.stream = stream
        self.tx_word = bytearray(self.BUF_SIZE)
        self.rx_word = bytearray(self.BUF_SIZE)
        self.rx_queue = Queue(15)
        # pre-load template fixed values
        for key in self.data_template:
            self.tx_word[key] = self.data_template[key]
        self.parser_ready_ev = asyncio.Event()
        self.rx_fn = ''
        self.track_count = 0
        self.current_track = 0
        self.track_playing_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.verbose = False
        self.tf_online = False

    def print_tx_message(self):
        """ print bytearray """
        message = self.tx_word
        if self.verbose:
            print('Tx:', hex_f.byte_array_str(message))
        print('Tx:', self.hex_cmd[message[self.CMD]],
              hex_f.byte_str(message[self.P_H]),
              hex_f.byte_str(message[self.P_L]))

    def print_rx_message(self):
        """ print bytearray """
        message = self.rx_word
        if self.verbose:
            print('Rx:', hex_f.byte_array_str(message))
        print('Rx:', self.hex_cmd[message[self.CMD]],
              hex_.byte_str(message[self.P_H]),
              hex_.byte_str(message[self.P_L]))

    def get_checksum(self):
        """ return the 2's complement checksum of:
            - bytes 1 to 6 """
        return hex_.slice_reg16(-sum(self.tx_word[1:7]))

    def check_checksum(self, buf_):
        """ returns 0 for consistent checksum """
        byte_sum = sum(buf_[1:self.C_H])
        checksum_ = buf_[self.C_H] << 8  # msb
        checksum_ += buf_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    async def send_command(self, cmd, param=0, wait_ms=20):
        """ set tx bytearray values and send
            - commands set own timing """
        print('send_command:', cmd, param)
        self.tx_word[self.CMD] = self.cmd_hex[cmd]
        msb, lsb = hex_.slice_reg16(param)
        self.tx_word[self.P_H] = msb
        self.tx_word[self.P_L] = lsb
        msb, lsb = self.get_checksum()
        self.tx_word[self.C_H] = msb
        self.tx_word[self.C_L] = lsb
        if cmd in self.play_set:
            self.track_playing_ev.set()
            self.track_end_ev.clear()
        await self.stream.sender(self.tx_word, wait_ms)
    
    async def send_query(self, query: str, param=0):
        """ send query to device and pause for reply """
        await asyncio.sleep_ms(500)
        await self.send_command(query, param)
        await asyncio.sleep_ms(500)

    async def consume_rx_data(self):
        """ waits for then parses and prints queued data """

        def parse_rx_message(message_):
            """ parse incoming message parameters and
                set controller attributes
                - partial implementation for known requirements """
            rx_fn = self.hex_cmd[message_[self.CMD]]
            self.rx_fn = rx_fn

            if rx_fn == 'tf_finish':
                self.prev_track = hex_.set_reg16(
                    message_[self.P_H], message_[self.P_L])
                self.track_playing_ev.clear()
                self.track_end_ev.set()
            elif rx_fn == 'q_init':
                self.init_param = hex_.set_reg16(
                    message_[self.P_H], message_[self.P_L])
                self.tf_online = bool(self.init_param & 0x02)
            elif rx_fn == 're_tx':
                self.re_tx_ev = True  # not currently checked
            elif rx_fn == 'q_vol':
                self.volume = hex_.set_reg16(
                    message_[self.P_H], message_[self.P_L])
            elif rx_fn == 'q_tf_files':
                self.track_count = hex_.set_reg16(
                    message_[self.P_H], message_[self.P_L])
            elif rx_fn == 'q_tf_track':
                self.current_track = hex_.set_reg16(
                    message_[self.P_H], message_[self.P_L])

        while True:
            self.parser_ready_ev.set()  # set parser ready for input
            await self.stream.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = self.stream.rx_queue.rmv_item()
            parse_rx_message(self.rx_word)
            self.print_rx_message()


async def main():
    """ test CommandHandler and UartTxRx """

    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    uart_tr = UartTR(uart, 10, Queue(20))
    ch = CommandHandler(uart_tr)
    
    task0 = asyncio.create_task(uart_tr.receiver())
    task1 = asyncio.create_task(ch.consume_rx_data())

    await ch.send_command('reset', 0, wait_ms=3000)
    await ch.send_command('vol_set', 15)
    await asyncio.sleep_ms(2000)
    await ch.send_query('q_vol')
    await ch.send_command('playback')

    await ch.track_end_ev.wait()
    
    print('cancel tasks')
    task1.cancel()
    task0.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
