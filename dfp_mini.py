# dfp_mini.py
"""
DFPlayer Mini (DFP): device specific code
See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for documentation.
Some DFP commands not supported or buggy - code alternatives implemented.
- this version is for SD-cards only
- no folder-related commands
"""

import uasyncio as asyncio
from data_link import DataLink
import hex_fns as hex_f


class CommandHandler:
    """ formats, sends and receives command and query messages
        - N.B. 'reset' must be called to initialise object
    """

    BA_SIZE = const(10)  # bytearray
    # data-byte indices
    CMD = const(3)
    P_M = const(5)  # parameter
    P_L = const(6)
    C_M = const(7)  # checksum
    C_L = const(8)
    R_FB = const(1)  # require ACK feedback
    # fixed bytearray elements by index
    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}

    VOL_MAX = const(30)
    VOL_MIN = const(0)

    Q_LEN = const(8)
    
    # command dictionary
    hex_str = {
        # commands
        0x03: 'track',  # 1-3000
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',
        0x0c: 'reset',
        0x0d: 'play',
        0x0e: 'pause',
        # information return
        0x3a: 'media_insert',
        0x3b: 'media_remove',
        0x3d: 'track_fin',  # sd track finished
        0x3f: 'qry_init',  # returns: 02 for TF-card
        0x40: 'error',
        0x41: 'ack',
        # query status
        0x42: 'qry_status',  # 0: stopped; 1: playing; 2: paused
        0x43: 'qry_vol',
        0x44: 'qry_eq',
        0x48: 'qry_sd_files',  # number of files, in root directory
        0x4c: 'qry_tf_trk'
        }

    # inverse dictionary mapping
    str_hex = {value: key for key, value in hex_str.items()}
    # eq dicts, and values as string
    eq_val = {'normal': 0, 'pop': 1, 'rock': 2, 'jazz': 3, 'classic': 4, 'bass': 5}
    val_eq = {value: key for key, value in eq_val.items()}
    eq_options = ''
    for key in eq_val:
        eq_options += f'{key}, '
    eq_options = eq_options[:-2]

    def __init__(self):
        self.data_link = DataLink(0, 1, 10)
        self.stream_tr = self.data_link.stream_tr
        self.sender = self.data_link.sender
        self.tx_word = bytearray(self.BA_SIZE)
        self.rx_queue = self.data_link.rx_queue
        self.rx_word = bytearray(self.BA_SIZE)
        self.rx_param = 0x0000
        self.rx_cmd = 0x00

        self.vol = 0
        self.vol_min = 0
        self.vol_max = 30
        self.eq = 'normal'
        self.track_count = 0
        self.track = 0
        self.ack_ev = asyncio.Event()
        self.playing_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored

        # pre-load template fixed values
        for key in self.data_template:
            self.tx_word[key] = self.data_template[key]

    def get_checksum(self, word_):
        """ 2's complement checksum of bytes 1 to 6 """
        return -sum(word_[1:self.C_M])

    def check_checksum(self, word_):
        """ returns 0 if checksum is valid """
        byte_sum = sum(word_[1:self.C_M])
        checksum_ = word_[self.C_M] << 8  # msb
        checksum_ += word_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    async def _send_command(self, cmd, param=0):
        """ coro: load tx bytearray word and send
            - call from player-specific methods
        """
        self.ack_ev.clear()  # require ACK
        self.tx_word[self.CMD] = cmd
        # slice and load (msb, lsb) for parameter
        self.tx_word[self.P_M], self.tx_word[self.P_L] = \
            hex_f.slice_reg16(param)
        # slice and load (msb, lsb) for checksum
        self.tx_word[self.C_M], self.tx_word[self.C_L] = \
            hex_f.slice_reg16(self.get_checksum(self.tx_word))
        await self.sender(self.tx_word)
        # require ACK (set in parse_rx_message() )
        await self.ack_ev.wait()

    def parse_rx_message(self, message):
        """ parse incoming message_ parameters,
            set any dependent attributes
        """
        self.rx_cmd = message[self.CMD]
        if self.check_checksum(message):
            print(f'{self.rx_cmd}: error in checksum')
            return
        self.rx_param = hex_f.m_l_reg16(
            message[self.P_M], message[self.P_L])
        rx_cmd = self.rx_cmd
        rx_param = self.rx_param

        # check for specific messages that require action
        if rx_cmd == 0x41:  # ack
            self.ack_ev.set()
        elif rx_cmd == 0x3d:  # tf track finished
            self.track_end_ev.set()
            self.playing_ev.clear()
        elif rx_cmd == 0x3f:  # q_init
            if (rx_param & 0x0002) != 0x0002:
                raise Exception('DFPlayer error: no TF-card?')
        elif rx_cmd == 0x40:  # error
            self.error_ev.set()  # not currently monitored
        elif rx_cmd == 0x43:  # qry_vol
            self.vol = rx_param
        elif rx_cmd == 0x44:  # qry_eq
            self.eq = self.val_eq[rx_param]
        elif rx_cmd == 0x48:  # qry_tf_files
            self.track_count = rx_param
        elif rx_cmd == 0x4c:  # qry_sd_trk
            self.track = rx_param
        elif rx_cmd == 0x3a:  # media_insert
            print('TF-card inserted.')
        elif rx_cmd == 0x3b:  # media_remove
            raise Exception('DFPlayer error: SD-card removed!')

    async def consume_rx_data(self):
        """ coro: consume and parse received data word """
        while True:
            await self.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = await self.rx_queue.get()
            self.parse_rx_message(self.rx_word)

    # DFPlayer mini control
    async def reset(self):
        """ coro: reset the DFPlayer
            - with SD card response should be: q_init 0x3f 0x0002
        """
        await self._send_command(0x0c, 0)
        await asyncio.sleep_ms(2000)
        if self.rx_cmd != 0x3f:
            if self.rx_cmd == 0x41:
                raise Exception(f'ACK but DFPlayer could not be reset: no SD card?')
            else:
                raise Exception('No ACK and DFPlayer could not be reset.')
        return self.rx_cmd, self.rx_param

    async def play_track(self, track):
        """ coro: play track n """
        self.track_end_ev.clear()
        self.playing_ev.set()
        await self._send_command(0x03, track)
        self.track = track

    async def play(self):
        """ coro: stop playing """
        await self._send_command(0x0d, 0)

    async def pause(self):
        """ coro: stop playing """
        await self._send_command(0x0e, 0)

    async def set_vol(self, level):
        """ coro: set volume level 0-30 """
        if level > 30:
            level = 30
        await self._send_command(0x06, level)
        self.vol = level

    async def set_eq(self, setting):
        """ set eq to preset setting
            - setting: 'normal', 'pop', 'rock', 'jazz', 'classic', 'bass'
        """
        if setting in self.eq_val:
            await self._send_command(0x07, self.eq_val[setting])
        else:
            await self._send_command(0x07, self.eq_val['normal'])

    async def qry_vol(self):
        """ coro: query volume level """
        await self._send_command(0x43)

    async def qry_eq(self):
        """ coro: query volume level """
        await self._send_command(0x44)

    async def qry_sd_files(self):
        """ coro: query number of TF/SD files (in root?) """
        await self._send_command(0x48)

    async def qry_sd_track(self):
        """ coro: query current track number """
        await self._send_command(0x4c)

    async def adjust_volume(self, delta):
        """ adjust volume up or down - must be run as task """
        await self.set_vol(self.vol + delta)
        await self.qry_vol()
        await asyncio.sleep_ms(1000)


async def main():
    """"""
    pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
