from machine import UART, Pin
import uasyncio as asyncio
from time import sleep_ms
import hex_fns as hex_f


class UartTxRx:
    """ UART transmit and receive through fixed-size buffers
        - UART0 maps to pins 0/1, 12/13, 16/17
        - UART1 maps to pins 4/5, 8/9
        - inheritance appears to create problems with StreamWriter
    """

    # buffer size and indices

    baud_rate = const(9600)
    
    def __init__(self, uart, tx_pin, rx_pin, buf_size,
                 parser_ready_ev):
        self.uart = UART(0, 9600)
        self.uart.init(tx=Pin(0), rx=Pin(1))
        self.buf_size = buf_size
        self.parser_ready_ev = parser_ready_ev
        self.rx_ev = asyncio.Event()
        self.tx_buf = bytearray(buf_size)
        self.rx_buf = bytearray(buf_size)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.sreader = asyncio.StreamReader(self.uart)
        self.rx_ev = asyncio.Event()

    async def write_tx_data(self):
        """ write the Tx buffer to UART """
        self.swriter.write(self.tx_buf)
        await self.swriter.drain()

    async def read_rx_data(self):
        """ read data word into Rx buffer
            - when parser is ready """
        while True:
            await self.parser_ready_ev.wait()
            self.rx_ev.clear()
            res = await self.sreader.readinto(self.rx_buf)
            if res == self.buf_size:  # complete data word?
                self.rx_ev.set()  # data received


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

    def __init__(self, uart, tx_pin, rx_pin):
        self.parser_ready_ev = asyncio.Event()
        self.uart_tr = UartTxRx(uart=uart, tx_pin=tx_pin, rx_pin=rx_pin,
                                buf_size=10, parser_ready_ev=self.parser_ready_ev)
        # pre-load template fixed values
        for key in self.data_template:
            self.uart_tr.tx_buf[key] = self.data_template[key]
        self.rx_fn = ''
        self.rx_data = None
        self.track_count = 0
        self.current_track = 0
        self.tx_buf = self.uart_tr.tx_buf
        self.rx_buf = self.uart_tr.rx_buf
        self.track_playing_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.verbose = False
        self.tf_online = False

    def print_tx_message(self):
        """ print bytearray """
        message = self.tx_buf
        if self.verbose:
            print('Tx:', hex_f.byte_array_str(message))
        print('Tx:', self.hex_cmd[message[self.CMD]],
              hex_f.byte_str(message[self.P_H]),
              hex_f.byte_str(message[self.P_L]))

    def print_rx_message(self):
        """ print bytearray """
        message = self.rx_buf
        if self.verbose:
            print('Rx:', hex_f.byte_array_str(message))
        print('Rx:', self.hex_cmd[message[self.CMD]],
              hex_f.byte_str(message[self.P_H]),
              hex_f.byte_str(message[self.P_L]))

    def get_checksum(self):
        """ return the 2's complement checksum of:
            - bytes 1 to 6 """
        return hex_f.slice_reg16(-sum(self.tx_buf[1:7]))

    def check_checksum(self, buf_):
        """ returns 0 for consistent checksum """
        byte_sum = sum(buf_[1:self.C_H])
        checksum_ = buf_[self.C_H] << 8  # msb
        checksum_ += buf_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    async def send_command(self, cmd, param=0):
        """ set tx bytearray values and send
            - commands set own timing """
        print('send_command:', cmd, param)
        self.tx_buf[self.CMD] = self.cmd_hex[cmd]
        msb, lsb = hex_f.slice_reg16(param)
        self.tx_buf[self.P_H] = msb
        self.tx_buf[self.P_L] = lsb
        msb, lsb = self.get_checksum()
        self.tx_buf[self.C_H] = msb
        self.tx_buf[self.C_L] = lsb
        if cmd in self.play_set:
            self.track_playing_ev.set()
            self.track_end_ev.clear()
        await self.uart_tr.write_tx_data()
    
    async def send_query(self, query: str, param=0):
        """ send query to device and pause for reply """
        await asyncio.sleep_ms(500)
        await self.send_command(query, param)
        await asyncio.sleep_ms(500)

    async def consume_rx_data(self):
        """ waits for data event; parses and prints received data """

        def parse_rx_message(message_):
            """ parse incoming message parameters and
                set controller attributes
                - partial implementation for known requirements """
            rx_fn = self.hex_cmd[message_[self.CMD]]
            self.rx_fn = rx_fn

            if rx_fn == 'tf_finish':
                self.prev_track = hex_f.set_reg16(
                    message_[self.P_H], message_[self.P_L])
                self.track_playing_ev.clear()
                self.track_end_ev.set()
            elif rx_fn == 'q_init':
                self.init_param = hex_f.set_reg16(
                    message_[self.P_H], message_[self.P_L])
                self.tf_online = bool(self.init_param & 0x02)
            elif rx_fn == 're_tx':
                self.re_tx_ev = True  # not currently checked
            elif rx_fn == 'q_vol':
                self.volume = hex_f.set_reg16(
                    message_[self.P_H], message_[self.P_L])
            elif rx_fn == 'q_tf_files':
                self.track_count = hex_f.set_reg16(
                    message_[self.P_H], message_[self.P_L])
            elif rx_fn == 'q_tf_track':
                self.current_track = hex_f.set_reg16(
                    message_[self.P_H], message_[self.P_L])

        while True:
            self.parser_ready_ev.set()  # set parser ready for input
            await self.uart_tr.rx_ev.wait()  # wait for data input
            self.parser_ready_ev.clear()  # clear while busy
            self.rx_data = bytearray(self.rx_buf)
            parse_rx_message(self.rx_data)
            self.print_rx_message()


async def blink():
    """ blink onboard LED """
    from machine import Pin
    led = Pin(16, Pin.OUT)
    while True:
        led.value(1)
        await asyncio.sleep_ms(1000)
        led.value(0)
        await asyncio.sleep_ms(1000)


async def main():
    """ test CommandHandler and UartTxRx """
    ch = CommandHandler(0, 0, 1)
    print(ch)
    task0 = asyncio.create_task(blink())
    task1 = asyncio.create_task(ch.consume_rx_data())
    task2 = asyncio.create_task(ch.uart_tr.read_rx_data())
    await ch.send_command('reset')
    await asyncio.sleep_ms(3000)
    await ch.send_command('vol_set', 15)
    await asyncio.sleep_ms(2000)
    await ch.send_query('q_vol')
    await ch.send_command('playback')
    print('track playing:', ch.track_playing_ev.is_set())
    await ch.track_end_ev.wait()
    for i in range(3):
        await ch.send_command('next')
        await ch.track_end_ev.wait()
    print('final track ended:', ch.track_end_ev.is_set())
    await asyncio.sleep_ms(1000)
    print('cancel tasks')
    task0.cancel()
    task1.cancel()
    task2.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
