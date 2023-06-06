# command_handler_as.py
"""
Control a DFPlayer Mini (DFP) from a Raspberry Pi Pico.
Requires modules hex_fns and uart_os_as to be loaded onto the Pico.
See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for DFP documentation
Not all DFP commands are required or have been tested.

- TF-card is synonymous with microSD Card
- this version is for TF-cards only
- simplified: no folder-related commands

"""

from machine import UART, Pin, ADC
import uasyncio as asyncio
import hex_fns as hex_f
from uart_os_as import StreamTR


class AdcReader:
    """ read ADC input """
    def __init__(self, pin, c_h):
        self.adc = ADC(Pin(pin))
        self.c_h = c_h
        self.threshold = 28_000
        self.trigger_ev = asyncio.Event()

    async def check_trigger(self):
        """ read ADC input while track playing """
        while True:
            await self.c_h.playing_ev.wait()
            while self.c_h.playing_ev.is_set():
                print('in buffer_adc playing')
                if self.adc.read_u16() > self.threshold:
                    self.trigger_ev.set()
                await asyncio.sleep_ms(20)


class CommandHandler:
    """ formats, sends and receives command and query messages
        - see Flyron Technology Co documentation for references
        - www.flyrontech.com
        - coro is short for coroutine
    """

    BUF_SIZE = const(10)
    # data-byte indices
    CMD = const(3)
    P_M = const(5)  # parameter
    P_L = const(6)
    C_M = const(7)  # checksum
    C_L = const(8)

    R_FB = const(1)  # require ACK feedback
    WAIT_MS = const(200)

    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}
    
    # repeat and sleep commands removed as problematic
    # use software to emulate
    hex_str = {
        0x01: 'next',
        0x02: 'prev',
        0x03: 'track',  # 1-3000
        0x04: 'vol_inc',
        0x05: 'vol_dec',
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # 0:normal/1:pop/2:rock/3:jazz/4:classic/5:bass
        0x0c: 'reset',
        0x0d: 'play',  # normally use 'track'
        0x0e: 'stop',
        0x3a: 'media_insert',
        0x3b: 'media_remove',
        0x3d: 'sd_fin',
        0x3f: 'q_init',  # 02: TF-card
        0x40: 'error',
        0x41: 'ack',
        0x42: 'q_status',  # 0: stopped; 1: playing; 2: paused
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x48: 'q_sd_files',  # in root directory
        0x4c: 'q_sd_trk'
        }
    
    # inverse dictionary mapping
    str_hex = {value: key for key, value in hex_str.items()}

    # build set of commands that play a track
    # required to set track-play Events
    play_set_str = {'next', 'prev', 'track'}
    play_set = {0x01, 0x02, 0x03}

    def __init__(self, stream):
        self.stream_tr = stream
        self.sender = stream.sender
        self.rx_queue = stream.rx_queue
        self.tx_word = bytearray(self.BUF_SIZE)
        self.rx_word = bytearray(self.BUF_SIZE)
        # pre-load template fixed values
        for key in self.data_template:
            self.tx_word[key] = self.data_template[key]
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.volume = 0  # for info
        self.track_count = 0  # for info
        self.current_track = 0  # for info
        self.ack_ev = asyncio.Event()
        self.playing_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored

    def print_rx_message(self):
        """ for testing """
        print('Latest Rx message:', hex_f.byte_str(self.rx_cmd),
              hex_f.byte_str(self.rx_param))

    def get_checksum(self):
        """ return the 2's complement checksum of:
            - bytes 1 to 6 """
        return hex_f.slice_reg16(-sum(self.tx_word[1:7]))

    def check_checksum(self, buf_):
        """ returns 0 for consistent checksum """
        byte_sum = sum(buf_[1:self.C_M])
        checksum_ = buf_[self.C_M] << 8  # msb
        checksum_ += buf_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    async def send_command_str(self, cmd_str, param=0):
        """ coro: set tx bytearray values and send
            - commands set own timing """
        await self.send_command(self.str_hex[cmd_str], param)

    async def send_command(self, cmd, param=0):
        """ coro: set tx bytearray values and send
            - commands set own timing """
        self.ack_ev.clear()  # require ACK
        self.tx_word[self.CMD] = cmd
        # slice msb and lsb
        self.tx_word[self.P_M], self.tx_word[self.P_L] = \
            hex_f.slice_reg16(param)
        self.tx_word[self.C_M], self.tx_word[self.C_L] = \
            self.get_checksum()
        # track-is-playing Events
        if cmd in self.play_set:
            self.track_end_ev.clear()
            self.playing_ev.set()
        await self.sender(self.tx_word)
        # ack_ev is set in parse_rx_message()
        await self.ack_ev.wait()

    async def consume_rx_data(self):
        """ coro: consume and parse received data """

        def parse_rx_message(message_):
            """ parse incoming message_ parameters and
                set dependent attributes
                - continue following checksum error (non-zero)
                - partial implementation for known requirements """

            rx_cmd = message_[self.CMD]
            if self.check_checksum(message_):
                # continue but log
                print(f'{rx_cmd}: error in checksum')
                return
            # combine parameter msb and lsb
            rx_param = hex_f.m_l_reg16(
                message_[self.P_M], message_[self.P_L])

            # check for specific messages that require action
            if rx_cmd == 0x41:  # ack
                self.ack_ev.set()
                return  # skip object update
            elif rx_cmd == 0x3d:  # sd_finish
                # self.current_track = rx_param  # uncomment if repeat used
                self.track_end_ev.set()
                self.playing_ev.clear()
            elif rx_cmd == 0x3f:  # q_init
                if rx_param & 0x0002 != 0x0002:
                    raise Exception('DFPlayer error: no TF-card?')
            elif rx_cmd == 0x40:  # error
                self.error_ev.set()  # not currently monitored
            elif rx_cmd == 0x43:  # q_vol
                self.volume = rx_param
            elif rx_cmd == 0x48:  # q_sd_files
                self.track_count = rx_param
            elif rx_cmd == 0x4c:  # q_sd_trk
                self.current_track = rx_param
            elif rx_cmd == 0x3a:  # media_insert
                print('TF-card inserted.')
            elif rx_cmd == 0x3b:  # media_remove
                raise Exception('DFPlayer error: TF-card removed!')

            self.rx_cmd = rx_cmd
            self.rx_param = rx_param

        # poll the Rx queue
        while True:
            await self.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = self.rx_queue.rmv_item()
            parse_rx_message(self.rx_word)


async def while_playing(playing, triggered):
    while playing.is_set():
        if triggered.is_set():
            print('loud')
            triggered.clear()
        else:
            print('not loud')
        await asyncio.sleep_ms(200)


async def main():
    """ test CommandHandler and UartTxRx """

    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTR(uart, buf_len=10)
    c_h = CommandHandler(stream_tr)
    adc = AdcReader(26, c_h)

    # start receive and send tasks
    asyncio.create_task(c_h.stream_tr.receiver())
    asyncio.create_task(c_h.consume_rx_data())
    # asyncio.create_task(adc.check_trigger())

    # (cmd: str, parameter: int) list for testing
    # 'zzz' is added for sleep calls
    commands = (('reset', 0), ('zzz', 3), ('vol_set', 15), ('zzz', 1), ('q_vol', 0),
                ('zzz', 1), ('track', 76), ('track', 15), ('track', 30),
                ('zzz', 1), ('track', 78), ('zzz', 1))

    for cmd in commands:
        print(cmd)
        command = cmd[0]
        parameter = cmd[1]
        if command == 'zzz':
            await asyncio.sleep(parameter)
        else:
            await c_h.send_command_str(command, parameter)
            c_h.print_rx_message()
            # if playing, wait for track end
            if command in c_h.play_set_str:
                await while_playing(c_h.playing_ev, adc.trigger_ev)
            else:
                # DFP recovery pause - required?
                await asyncio.sleep_ms(20)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
