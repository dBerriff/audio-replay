from machine import UART, Pin
import uasyncio as asyncio
import hex_fns as hex_f
from uart_os_as import Queue, StreamTR


class CommandHandler:
    """ formats, sends and receives command and query messages
        - see Flyron Technology Co documentation for references
        - www.flyrontech.com
    """

    BUF_SIZE = const(10)
    # data-byte indices
    CMD = const(3)
    P_H = const(5)  # parameter
    P_L = const(6)
    C_H = const(7)  # checksum
    C_L = const(8)

    R_FB = const(0)  # require player feedback? 0 or 1
    R_VERBOSE = const(False)  # print out data as hex bytearray
    
    WAIT_MS = const(200)

    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}
    
    hex_cmd = {
        0x01: 'next',
        0x02: 'prev',
        0x03: 'track',  # 1-3000
        0x04: 'vol_inc',
        0x05: 'vol_dec',
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # 0:normal/1:pop/2:rock/3:jazz/4:classic/5:bass
        0x08: 'repeat_trk',  # track # as parameter; 3.6.3
        0x0c: 'reset',
        0x0d: 'play',
        0x0e: 'pause',  # need timeout!
        0x0f: 'folder_trk',  # play: MSB: folder; LSB: track
        0x11: 'repeat_root',  # root folder; 0: stop; 1: start
        0x3d: 'tf_finish',
        0x3f: 'q_init',  # 01: U-disk, 02: TF-card, 04: PC, 08: Flash
        0x40: 'error',
        0x41: 'feedback',
        0x42: 'q_status',  # 0: stopped; 1: playing; 2: paused
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x48: 'q_tf_files',  # in root directory
        0x4c: 'q_tf_trk'
        }
    
    hex_wait_ms = {0x0c: 3000}
    
    # inverse dictionary mapping
    cmd_hex = {value: key for key, value in hex_cmd.items()}
    
    play_set = {'next', 'prev', 'track', 'repeat_trk', 'playback'}

    def __init__(self, stream):
        self.stream = stream
        self.tx_word = bytearray(self.BUF_SIZE)
        self.rx_word = bytearray(self.BUF_SIZE)
        # pre-load template fixed values
        for key in self.data_template:
            self.tx_word[key] = self.data_template[key]
        self.parser_ready_ev = asyncio.Event()
        self.rx_fn = ''
        self.track_count = 0
        self.current_track = 0
        self.track_playing_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.verbose = True
        self.tf_online = False

    def print_tx_message(self):
        """ print bytearray """
        message = self.tx_word
        if self.R_VERBOSE:
            print('Tx:', hex_f.byte_array_str(message))
        print('Tx:', self.hex_cmd[message[self.CMD]],
              hex_f.byte_str(message[self.P_H]),
              hex_f.byte_str(message[self.P_L]))

    def print_rx_message(self):
        """ print bytearray """
        message = self.rx_word
        if self.R_VERBOSE:
            print('Rx:', hex_f.byte_array_str(message))
        print('Rx:', self.hex_cmd[message[self.CMD]],
              hex_f.set_reg16(message[self.P_H], message[self.P_L]))

    def get_checksum(self):
        """ return the 2's complement checksum of:
            - bytes 1 to 6 """
        # following algorithm at 3.2 in Flyron Tech documentation
        checksum = hex_f.slice_reg16(
            (0xffff - sum(self.tx_word[1:7])) + 1)
        return checksum

    def check_checksum(self, buf_):
        """ returns 0 for consistent checksum """
        byte_sum = sum(buf_[1:self.C_H])
        checksum_ = buf_[self.C_H] << 8  # msb
        checksum_ += buf_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    async def send_command(self, cmd, param=0):
        """ set tx bytearray values and send
            - commands set own timing """
        cmd_hex = self.cmd_hex[cmd]
        if cmd_hex in self.hex_wait_ms:
            wait_time_ms = self.hex_wait_ms[cmd_hex]
        else:
            wait_time_ms = self.WAIT_MS
        self.tx_word[self.CMD] = cmd_hex
        msb, lsb = hex_f.slice_reg16(param)
        self.tx_word[self.P_H] = msb
        self.tx_word[self.P_L] = lsb
        msb, lsb = self.get_checksum()
        self.tx_word[self.C_H] = msb
        self.tx_word[self.C_L] = lsb
        if cmd in self.play_set:
            self.track_playing_ev.set()
            self.track_end_ev.clear()
        await self.stream.sender(self.tx_word)
        self.print_tx_message()
        await asyncio.sleep_ms(wait_time_ms)

    async def consume_rx_data(self):
        """ waits for then parses and prints queued data """

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
            await self.stream.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = self.stream.rx_queue.rmv_item()
            parse_rx_message(self.rx_word)
            self.print_rx_message()


async def main():
    """ test CommandHandler and UartTxRx """
    
    async def busy_pin_state(pin_):
        """ poll DFPlayer Pin 16 - Busy
            - low when working, high when standby
            - 'working' means playing a track
            - follows LED on DFPlayer?
            - set Pico onboard LED to On if busy
        """
        pin_in = Pin(pin_, Pin.IN, Pin.PULL_UP)
        led = Pin('LED', Pin.OUT)
        while True:
            if pin_in.value():
                led.value(0)
            else:
                led.value(1)
            await asyncio.sleep_ms(20)
    
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTR(uart, 10, Queue(20))
    c_h = CommandHandler(stream_tr)
    
    # Rx tasks run as cooperative tasks
    task0 = asyncio.create_task(stream_tr.receiver())
    task1 = asyncio.create_task(c_h.consume_rx_data())
    task2 = asyncio.create_task(busy_pin_state(2))
    
    print('Send commands')
    await c_h.send_command('reset')
    await c_h.send_command('vol_set', 15)
    await c_h.send_command('q_vol')
    await c_h.send_command('play')
    await c_h.track_end_ev.wait()
    await c_h.send_command('next')
    await asyncio.sleep_ms(2000)
    await c_h.send_command('pause')
    # to do: avoid 'pause' locking up the system
    try:
        await asyncio.wait_for(c_h.track_end_ev.wait(), 10)
    except asyncio.TimeoutError:
        print('Pause time exceeded.')
    await c_h.send_command('play')
    await c_h.track_end_ev.wait()
    
    print('cancel tasks')
    await c_h.send_command('reset')

    task1.cancel()
    task0.cancel()
    await asyncio.sleep_ms(1000)
    task2.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
