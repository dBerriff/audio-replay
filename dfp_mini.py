# dfp_mini.py
"""
    DFPlayer Mini (DFP): device specific code
    See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for documentation.
    Some DFP commands not supported or buggy - code alternatives implemented.
"""

import uasyncio as asyncio
import hex_fns as hex_f


class CommandHandler:
    """ formats, sends and receives command and query messages
        - N.B. 'reset' must be called to initialise object
        - tx messages are directly sent
        - rx messages are received through rx_queue
    """

    config = {'name': 'DFPlayer Mini',
              'vol_factor': 3,
              'vol': 5,
              'eq': 'normal'
              }

    qry_cmds = {'vol': 0x43,
                'eq': 0x44,
                'sd_files': 0x48,
                'sd_track': 0x4c
                }

    BA_SIZE = const(10)  # bytearray
    # data-byte indices
    CMD = const(3)
    P_M = const(5)  # parameter
    P_L = const(6)
    C_M = const(7)  # checksum
    C_L = const(8)
    VOL_MAX = const(30)
    # bytearray template: set to require ACK response
    BA_TEMPLATE = [0x7E, 0xFF, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0xEF]

    # settings dictionaries
    eq_val = {'normal': 0, 'pop': 1, 'rock': 2, 'jazz': 3, 'classic': 4, 'bass': 5}
    val_eq = {value: key for key, value in eq_val.items()}

    def __init__(self, data_link_):
        self.data_link = data_link_
        self.stream_tx_rx = self.data_link.stream_tx_rx
        self.sender = self.data_link.sender
        self.tx_word = bytearray(self.BA_TEMPLATE)
        self.rx_word = bytearray(self.BA_TEMPLATE)
        self.rx_queue = self.data_link.rx_queue
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.vol = 0
        self.vol_min = 0
        self.eq = 'normal'
        self.track_count = 0
        self.track = 0
        self.ack_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored
        self.tx_lock = asyncio.Lock()
        self.query_rx_ev = asyncio.Event()
        self.query_lock = asyncio.Lock()

        asyncio.create_task(self.stream_tx_rx.receiver())
        asyncio.create_task(self.consume_rx_data())

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
            - lock against multiple attempts to send
        """
        async with self.tx_lock:
            self.ack_ev.clear()
            self.tx_word[self.CMD] = cmd
            self.tx_word[self.P_M], self.tx_word[self.P_L] = hex_f.slice_reg16(param)
            self.tx_word[self.C_M], self.tx_word[self.C_L] = hex_f.slice_reg16(self.get_checksum(self.tx_word))
            await self.sender(self.tx_word)
            await self.ack_ev.wait()  # wait for DFPlayer ACK

    def parse_rx_message(self, message):
        """ parse and act on incoming message parameters """
        if self.check_checksum(message):
            print(f'{message}: error in checksum')
            return
        rx_cmd = message[self.CMD]
        rx_param = hex_f.m_l_reg16(message[self.P_M], message[self.P_L])
        # check for specific messages that require action
        if rx_cmd == 0x41:  # ack
            self.ack_ev.set()
        elif rx_cmd == 0x3d:  # sd track finished
            self.track_end_ev.set()
        elif rx_cmd == 0x3f:  # qry_init
            if (rx_param & 0x0002) != 0x0002:
                raise Exception('DFPlayer error: no TF-card?')
        elif rx_cmd == 0x40:  # error
            self.error_ev.set()  # not currently monitored
        elif rx_cmd == 0x43:  # qry_vol
            self.vol = rx_param
            self.query_rx_ev.set()
        elif rx_cmd == 0x44:  # qry_eq
            self.eq = self.val_eq[rx_param]
            self.query_rx_ev.set()
        elif rx_cmd == 0x48:  # qry_sd_files
            self.track_count = rx_param
            self.query_rx_ev.set()
        elif rx_cmd == 0x4c:  # qry_sd_trk
            self.track = rx_param
            self.query_rx_ev.set()
        elif rx_cmd == 0x3a:  # media_insert
            print('TF-card inserted.')
        elif rx_cmd == 0x3b:  # media_remove
            raise Exception('DFPlayer error: SD-card removed!')
        return rx_cmd, rx_param

    async def consume_rx_data(self):
        """ coro: consume and parse received data word """
        while True:
            await self.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = await self.rx_queue.get()
            self.rx_cmd, self.rx_param = self.parse_rx_message(self.rx_word)

    # DFPlayer mini control
    async def reset(self):
        """ coro: reset the DFPlayer
            - with SD card response should be: 0x3f 0x0002
        """
        await self._send_command(0x0c, 0)
        await asyncio.sleep_ms(2000)  # allow time for the DFPlayer reset
        if self.rx_cmd != 0x3f:
            if self.rx_cmd == 0x41:
                raise Exception(f'DFPlayer ACK with error: no SD card?')
            else:
                raise Exception('DFPlayer no ACK.')

    async def play_track(self, track):
        """ coro: play track n """
        await self.track_end_ev.wait()
        self.track_end_ev.clear()
        await self._send_command(0x03, track)
        self.track = track

    async def play(self):
        """ coro: start playing; after pause? """
        await self._send_command(0x0d, 0)

    async def pause(self):
        """ coro: stop playing """
        await self._send_command(0x0e, 0)

    async def set_vol(self, level):
        """ coro: set volume level 0-VOL_MAX """
        level = min(self.VOL_MAX, level)
        level = max(self.vol_min, level)
        await self._send_command(0x06, level)
        self.vol = level

    async def set_eq(self, eq_key):
        """ set eq to key in:
            'normal', 'pop', 'rock', 'jazz', 'classic', 'bass'
        """
        if eq_key in self.eq_val:
            param = self.eq_val[eq_key]
        else:
            param = self.eq_val['normal']
        await self._send_command(0x07, param)

    # query methods
    
    async def send_query(self, query):
        """ send and wait for query response """
        async with self.query_lock:
            self.query_rx_ev.clear()
            await self._send_command(self.qry_cmds[query])
            await self.query_rx_ev.wait()


async def main():
    """"""
    from data_link import DataLink
    from queue import Buffer

    rx_queue = Buffer()
    data_link = DataLink(0, 1, 9600, 10, rx_queue)
    cmd_handler = CommandHandler(data_link)
    print(cmd_handler)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
