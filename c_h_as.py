# c_h_as.py
"""
Control a DFPlayer Mini (DFP) from a Raspberry Pi Pico.
Requires modules hex_fns and uart_os_as to be loaded onto the Pico.
See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for DFP documentation
Most DFP commands are not supported as not required or problematical.

- TF-card is synonymous with microSD Card
- this version is for TF-cards only
- simplified: no folder-related commands

"""

from machine import UART, Pin, ADC
import uasyncio as asyncio
import hex_fns as hex_f


class AdcReader:
    """ return ADC input as u16 property """
    def __init__(self, pin):
        self.adc = ADC(Pin(pin))

    @property
    def input(self):
        """ ADC reading """
        return self.adc.read_u16()


class CommandHandler:
    """ formats, sends and receives command and query messages
        - see Flyron Technology Co documentation for references
        - www.flyrontech.com
        - coro is short for coroutine
        - N.B. 'reset' must be called to initialise object
            -- cannot do this from __init__()
    """

    BUF_SIZE = const(10)
    # data-byte indices
    CMD = const(3)
    P_M = const(5)  # parameter
    P_L = const(6)
    C_M = const(7)  # checksum
    C_L = const(8)

    R_FB = const(1)  # require ACK feedback

    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}
    
    # repeat and sleep commands removed as problematic
    # use software to emulate
    hex_str = {
        # commands
        0x03: 'track',  # 1-3000
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # 0:normal/1:pop/2:rock/3:jazz/4:classic/5:bass
        0x0c: 'reset',
        0x0e: 'stop',
        # information return
        0x3a: 'media_insert',
        0x3b: 'media_remove',
        0x3d: 'tf_fin',  # sd track finished
        0x3f: 'q_init',  # returns: 02 for TF-card
        0x40: 'error',
        0x41: 'ack',
        # query status
        0x42: 'q_status',  # 0: stopped; 1: playing; 2: paused
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x48: 'q_tf_files',  # number of files, in root directory
        0x4c: 'q_tf_trk'
        }
    
    # inverse dictionary mapping
    str_hex = {value: key for key, value in hex_str.items()}

    def __init__(self, stream, adc):
        self.stream_tr = stream
        self.adc = adc
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
        self.track_count = 0
        self.track = 0
        self.threshold = 28_000
        self.ack_ev = asyncio.Event()
        self.playing_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored
        self.trigger_ev = asyncio.Event()

    def print_rx_message(self):
        """ for testing """
        print('Latest Rx message:', hex_f.byte_str(self.rx_cmd),
              hex_f.byte_str(self.rx_param), self.rx_param)

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
        """ coro: send command word with string command """
        await self.send_command(self.str_hex[cmd_str], param)

    async def send_command(self, cmd, param=0):
        """ coro: load tx bytearray word and send """
        self.ack_ev.clear()  # require ACK
        self.tx_word[self.CMD] = cmd
        # slice msb and lsb for parameter and checksum
        self.tx_word[self.P_M], self.tx_word[self.P_L] = \
            hex_f.slice_reg16(param)
        self.tx_word[self.C_M], self.tx_word[self.C_L] = \
            self.get_checksum()
        # play track
        if cmd == 0x03:
            self.track = param
            self.track_end_ev.clear()
            self.playing_ev.set()
        await self.sender(self.tx_word)
        # ack_ev is set in parse_rx_message()
        await self.ack_ev.wait()

    async def consume_rx_data(self):
        """ coro: consume and parse received data word """

        def parse_rx_message(message_):
            """ parse incoming message_ parameters and
                set dependent attributes
                - on checksum error (non-zero): print but continue
                - known requirements only; other responses ignored """
            rx_cmd = message_[self.CMD]
            if self.check_checksum(message_):
                # print then continue
                print(f'{rx_cmd}: error in checksum')
                return
            # combine parameter msb and lsb
            rx_param = hex_f.m_l_reg16(
                message_[self.P_M], message_[self.P_L])

            # check for specific messages that require action
            if rx_cmd == 0x41:  # ack
                self.ack_ev.set()
                return  # skip object update
            elif rx_cmd == 0x3d:  # tf track finished
                self.track_end_ev.set()
                self.playing_ev.clear()
            elif rx_cmd == 0x3f:  # q_init
                if rx_param & 0x0002 != 0x0002:
                    raise Exception('DFPlayer error: no TF-card?')
            elif rx_cmd == 0x40:  # error
                self.error_ev.set()  # not currently monitored
            elif rx_cmd == 0x43:  # q_vol
                self.volume = rx_param
            elif rx_cmd == 0x48:  # q_tf_files
                self.track_count = rx_param
            elif rx_cmd == 0x4c:  # q_tf_trk
                self.track = rx_param
            elif rx_cmd == 0x3a:  # media_insert
                print('TF-card inserted.')
            elif rx_cmd == 0x3b:  # media_remove
                raise Exception('DFPlayer error: TF-card removed!')

            self.rx_cmd = rx_cmd
            self.rx_param = rx_param

        # parse queued data
        while True:
            await self.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = self.rx_queue.rmv_item()
            parse_rx_message(self.rx_word)

    async def check_vol_trigger(self):
        """ read ADC input while track playing
            set trigger if volume threshold exceeded """
        while True:
            await self.playing_ev.wait()
            while self.playing_ev.is_set():
                if self.adc.input > self.threshold:
                    self.trigger_ev.set()
                await asyncio.sleep_ms(20)


async def main():
    """ test CommandHandler and UartTxRx
        - can be removed when testing has been completed """
    pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
