# dfp_mini.py
"""
    DFPlayer Mini (DFP): device specific code
    See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for documentation.
    Some DFP mini commands do not work so are implemented in software.
"""

import asyncio
from dfpm_codec import MiniCmdPackUnpack
from data_link import Buffer, DataLink


class DfpMini:
    """ formats, sends and receives command and query messages
        - N.B. reset() method must be called to initialise object
        - hex values are generally hard-coded as player-specific
        - messages are sent through Tx and Rx queues
        - config dict is set from file config.json or DfpMini._config
    """

    config = {'vol': 5, 'eq': 'bass'}
    qry_cmds = {'vol': 0x43,
                'eq': 0x44,
                'sd_files': 0x48,
                'sd_track': 0x4c
                }

    NAME = const('DFPlayer Mini')
    VOL_MAX = const(30)
    CONFIG_FILENAME = const('config.json')

    # eq dictionary for decoding eq query response
    eq_val_str = {0: 'normal', 1: 'pop', 2: 'rock', 3: 'jazz', 4: 'classic', 5: 'bass'}
    eq_str_val = {'normal': 0, 'pop': 1, 'rock': 2, 'jazz': 3, 'classic': 4, 'bass': 5}
    eq_set = set(eq_val_str.keys())

    def __init__(self, tx_p, rx_p):
        # self._data_link = data_link_
        data_link = DataLink(tx_p, rx_p, 9600, 10, Buffer(), Buffer())
        self.stream_tx_rx = data_link.stream_tx_rx
        self.tx_queue = data_link.tx_queue
        self.rx_queue = data_link.rx_queue
        self.cmd_codec = MiniCmdPackUnpack()
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.track_count = 0
        self.track = 0
        self.ack_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored
        self.tx_lock = asyncio.Lock()
        # task to process returned data
        asyncio.create_task(self.consume_rx_data())
        self.config = DfpMini.config

    async def send_command(self, cmd_, param_=0):
        """ coro: load tx bytearray word and send
            - lock against multiple attempts to send
        """
        async with self.tx_lock:
            self.ack_ev.clear()
            await self.tx_queue.put(self.cmd_codec.pack_tx_ba(cmd_, param_))
            await self.ack_ev.wait()  # wait for DFPlayer ACK
            await asyncio.sleep_ms(20)  # DFP recovery time?

    async def send_query(self, query):
        """ coro: send query """
        if query in self.qry_cmds:
            await self.send_command(self.qry_cmds[query])

    def evaluate_rx_message(self, rx_cmd_, rx_param_):
        """ evaluate incoming command for required action or errors """
        if rx_cmd_ == 0x41:  # ack
            self.ack_ev.set()
        elif rx_cmd_ == 0x3d:  # sd track finished
            self.track_end_ev.set()
        elif rx_cmd_ == 0x3f:  # qry: init
            if (rx_param_ & 0x0002) != 0x0002:
                raise Exception('DFPlayer error: no SD-card?')
        elif rx_cmd_ == 0x40:  # error
            self.error_ev.set()  # not currently monitored
        elif rx_cmd_ == 0x43:  # qry: vol
            self.config['vol'] = rx_param_
        elif rx_cmd_ == 0x44:  # qry: eq
            self.config['eq'] = self.eq_val_str[rx_param_]
        elif rx_cmd_ == 0x48:  # qry: sd_files
            self.track_count = rx_param_
        elif rx_cmd_ == 0x4c:  # qry: sd_trk
            self.track = rx_param_
        elif rx_cmd_ == 0x3a:  # media_insert
            print('SD-card inserted.')
        elif rx_cmd_ == 0x3b:  # media_remove
            raise Exception('DFPlayer error: SD-card removed!')

    async def consume_rx_data(self):
        """ coro: get and evaluate received bytearray """
        while True:
            await self.rx_queue.is_data.wait()
            ba_ = await self.rx_queue.get()
            self.rx_cmd, self.rx_param = self.cmd_codec.unpack_rx_ba(ba_)
            self.evaluate_rx_message(self.rx_cmd, self.rx_param)

    # DFPlayer Mini control methods

    async def reset(self):
        """ coro: reset the DFPlayer
            - with SD card response should be: 0x3f 0x0002
        """
        await self.send_command(0x0c, 0)
        await asyncio.sleep_ms(2000)  # allow time for the DFPlayer reset
        if self.rx_cmd != 0x3f:
            if self.rx_cmd == 0x41:
                raise Exception(f'DFPlayer ACK with error: no SD card?')
            else:
                raise Exception('DFPlayer no ACK.')
        await self.set_vol(self.config['vol'])
        await self.set_eq(self.config['eq'])

    async def play_track(self, track):
        """ coro: play track n """
        await self.send_command(0x03, track)
        self.track_end_ev.clear()
        self.track = track

    async def play(self):
        """ coro: resume/start playing """
        await self.send_command(0x0d, 0)

    async def pause(self):
        """ coro: pause/stop playing """
        await self.send_command(0x0e, 0)

    async def set_vol(self, value):
        """ set volume VOL_MIN - VOL_MAX """
        if not 0 <= value <= self.VOL_MAX:
            value = self.VOL_MAX // 2
        await self.send_command(0x06, value)
        return value

    async def set_eq(self, value):
        """ set eq by int value """
        if value not in self.eq_set:
            value = 0
        await self.send_command(0x07, value)
        return value
