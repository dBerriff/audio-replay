# dfp_mini.py
"""
    DFPlayer Mini (DFP): device specific code
    See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for documentation.
    Some DFP mini commands do not work so are implemented in software.
"""

import asyncio
import struct
from data_link import Buffer, DataLink


class MiniCmdPackUnpack:
    """ DFPlayer mini command pack/unpack: command values <-> message bytes
        - unsigned integers: B: 1 byte; H: 2 bytes
          command: start-B, ver-B, len-B, cmd-B, fb-B, param-H, csum-H, end-B
    """
    CMD_TEMPLATE = (0x7E, 0xFF, 0x06, 0x00, 0x01, 0x0000, 0x0000, 0xEF)
    CMD_FORMAT = const('>BBBBBHHB')  # > big-endian
    # command indices
    CMD_I = const(3)
    PRM_I = const(5)
    CSM_I = const(6)
    # message indices
    CSM_M = const(7)
    CSM_L = const(8)

    @classmethod
    def check_checksum(cls, bytes_):
        """ returns True if checksum is valid """
        checksum = sum(bytes_[1:cls.CSM_M])
        checksum += (bytes_[cls.CSM_M] << 8) + bytes_[cls.CSM_L]
        return checksum & 0xffff == 0

    def __init__(self):
        self.tx_message = list(MiniCmdPackUnpack.CMD_TEMPLATE)

    def pack_tx_ba(self, command, parameter):
        """ pack Tx DFPlayer mini command """
        self.tx_message[self.CMD_I] = command
        self.tx_message[self.PRM_I] = parameter
        bytes_ = struct.pack(self.CMD_FORMAT, *self.tx_message)
        # compute checksum
        self.tx_message[self.CSM_I] = -sum(bytes_[1:self.CSM_M]) & 0xffff
        return struct.pack(self.CMD_FORMAT, *self.tx_message)

    def unpack_rx_ba(self, bytes_):
        """ unpack Rx DFPlayer mini command """
        if self.check_checksum(bytes_):
            rx_msg = struct.unpack(self.CMD_FORMAT, bytes_)
            cmd_ = rx_msg[self.CMD_I]
            param_ = rx_msg[self.PRM_I]
        else:
            print('Error in checksum')
            cmd_ = 0
            param_ = 0
        return cmd_, param_


class DfpMini:
    """ formats, sends and receives command and query messages
        - N.B. reset() method must be called to initialise object
        - hex values are generally hard-coded as player-specific
        - messages are sent through Tx and Rx queues
        - config dict is set from file config.json or DfpMini._config
    """

    qry_cmds = {'vol': 0x43,
                'eq': 0x44,
                'sd_files': 0x48,
                'sd_track': 0x4c
                }
    qry_set = set(qry_cmds.keys())

    NAME = const('DFPlayer Mini')
    VOL_MAX = const(30)
    CONFIG = {'vol': 20, 'eq': 'bass'}
    START_TRACK = const(1)

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
        self.error_ev = asyncio.Event()  # not monitored by default
        self.q_response_ev = asyncio.Event()
        self.tx_lock = asyncio.Lock()
        # task to process returned data
        asyncio.create_task(self.consume_rx_data())
        self.config = DfpMini.CONFIG

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
        if query in self.qry_set:
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
            self.q_response_ev.set()
        elif rx_cmd_ == 0x44:  # qry: eq
            self.config['eq'] = self.eq_val_str[rx_param_]
            self.q_response_ev.set()
        elif rx_cmd_ == 0x48:  # qry: sd_files
            self.track_count = rx_param_
            self.q_response_ev.set()
        elif rx_cmd_ == 0x4c:  # qry: sd_trk
            self.track = rx_param_
            self.q_response_ev.set()
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
        await self.set_eq(self.eq_str_val[self.config['eq']])

    async def play_track(self, track):
        """ coro: play track n """
        self.track_end_ev.clear()
        await self.send_command(0x03, track)
        self.track = track

    async def play(self):
        """ coro: resume/start playing """
        await self.send_command(0x0d, 0)

    async def pause(self):
        """ coro: pause/stop playing """
        await self.send_command(0x0e, 0)

    async def set_vol(self, value):
        """ coro: set volume 0...self.VOL_MAX """
        await self.send_command(0x06, value)
        return value

    async def set_eq(self, value):
        """ coro: set eq by int value """
        await self.send_command(0x07, value)
        return value


async def main():
    """ test DFPlayer controller """

    # UART pins
    tx_pin = 16
    rx_pin = 17

    player = DfpMini(tx_pin, rx_pin)
    print("player.reset()")
    await player.reset()
    print("player.play_track(1)")
    await player.play_track(1)
    print("query vol and eq")
    await player.send_query("vol")
    await player.send_query("eq")
    print(player.config)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
