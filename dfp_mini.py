# dfp_mini.py
"""
    DFPlayer Mini (DFP): device specific code
    See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for documentation.
    Some DFP mini commands do not work, so not included.
"""

import uasyncio as asyncio
import struct


class CmdPackUnpack:
    """ DFPlayer mini command pack/unpack
        - see Python struct documentation for 'format' characters
        - command format:
          start-B, ver-B, len-B, cmd-B, fb-B, param-H, csum-H, end-B
    """
    CMD_TEMPLATE = (0x7E, 0xFF, 0x06, 0x00, 0x01, 0x0000, 0x0000, 0xEF)
    CMD_FORMAT = const('>BBBBBHHB')  # > big-endian
    # command indices
    CMD_I = const(3)
    PRM_I = const(5)
    CSM_I = const(6)
    # byte-array indices
    CSM_M = const(7)
    CSM_L = const(8)

    @classmethod
    def get_checksum(cls, message_):
        """ 2's comp. checksum of bytes 1 to parameter inclusive """
        tx_bytes = struct.pack(cls.CMD_FORMAT, *message_)
        return -sum(tx_bytes[1:cls.CSM_M]) & 0xffff

    @classmethod
    def check_checksum(cls, bytes_):
        """ returns True if checksum is valid """
        checksum = sum(bytes_[1:cls.CSM_M])
        checksum += (bytes_[cls.CSM_M] << 8) + bytes_[cls.CSM_L]
        return checksum & 0xffff == 0

    def __init__(self):
        self.tx_message = list(CmdPackUnpack.CMD_TEMPLATE)

    def pack_tx_ba(self, command, parameter):
        """ pack Tx DFPlayer mini command """
        self.tx_message[self.CMD_I] = command
        self.tx_message[self.PRM_I] = parameter
        self.tx_message[self.CSM_I] = self.get_checksum(self.tx_message)
        return struct.pack(self.CMD_FORMAT, *self.tx_message)
    
    def unpack_rx_ba(self, byte_array):
        """ unpack Rx DFPlayer mini command """
        if self.check_checksum(byte_array):
            rx_message = struct.unpack(self.CMD_FORMAT, byte_array)
            cmd_ = rx_message[self.CMD_I]
            param_ = rx_message[self.PRM_I]
        else:
            print('Error in checksum')
            cmd_ = 0
            param_ = 0
        return cmd_, param_


class DfpMiniCh:
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
    CS_U = const(P_L + 1)
    C_M = const(7)  # checksum
    C_L = const(8)
    VOL_MAX = const(30)
    # settings dictionaries
    eq_val = {'normal': 0, 'pop': 1, 'rock': 2, 'jazz': 3, 'classic': 4, 'bass': 5}
    val_eq = {value: key for key, value in eq_val.items()}

    def __init__(self, data_link_):
        self._data_link = data_link_
        self.stream_tx_rx = self._data_link.stream_tx_rx
        self.tx_queue = self._data_link.tx_queue
        self.rx_queue = self._data_link.rx_queue
        self._rx_cmd = 0x00  # for testing
        self._rx_param = 0x0000  # for testing
        self.vol = 0
        self.eq = 'normal'
        self.track_count = 0
        self.track = 0
        self.ack_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored
        self.query_rx_ev = asyncio.Event()
        self.tx_lock = asyncio.Lock()
        
        self.cmd_ba = CmdPackUnpack()
        asyncio.create_task(self.consume_rx_data())

    async def _send_command(self, cmd_, param_=0):
        """ coro: load tx bytearray word and send
            - lock against multiple attempts to send
        """
        async with self.tx_lock:
            self.ack_ev.clear()
            await self.tx_queue.put(self.cmd_ba.pack_tx_ba(cmd_, param_))
            await self.ack_ev.wait()  # wait for DFPlayer ACK
            await asyncio.sleep_ms(20)  # DFP recovery time?

    async def send_query(self, query):
        """ send query and wait for response event
            - 'vol', 'eq', 'sd_files', 'sd_track' """
        self.query_rx_ev.clear()
        await self._send_command(self.qry_cmds[query])
        await self.query_rx_ev.wait()

    def evaluate_rx_message(self, rx_cmd, rx_param):
        """ evaluate incoming command for required action or errors """
        if rx_cmd == 0x41:  # ack
            self.ack_ev.set()
        elif rx_cmd == 0x3d:  # sd track finished
            self.track_end_ev.set()
        elif rx_cmd == 0x3f:  # qry_init
            if (rx_param & 0x0002) != 0x0002:
                raise Exception('DFPlayer error: no SD-card?')
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
            print('SD-card inserted.')
        elif rx_cmd == 0x3b:  # media_remove
            raise Exception('DFPlayer error: SD-card removed!')

    async def consume_rx_data(self):
        """ coro: consume, parse and evaluate received bytearray """
        while True:
            await self.rx_queue.is_data.wait()
            ba_ = await self.rx_queue.get()
            self._rx_cmd, self._rx_param = self.cmd_ba.unpack_rx_ba(ba_)
            self.evaluate_rx_message(self._rx_cmd, self._rx_param)

    def print_player_settings(self):
        """ print selected player settings """
        result = f'player: {self.config["name"]}, '
        result += f'track: {self.track}, '
        result += f'vol: {self.vol}, '
        result += f'vol_factor: {self.config["vol_factor"]}, '
        result += f'eq: {self.eq}'
        print(result)


class DfpMiniControl(DfpMiniCh):
    """ DFPlayer Mini control methods """

    def __init__(self, data_link_):
        super().__init__(data_link_)

    async def reset(self):
        """ coro: reset the DFPlayer
            - with SD card response should be: 0x3f 0x0002
        """
        await self._send_command(0x0c, 0)
        await asyncio.sleep_ms(2000)  # allow time for the DFPlayer reset
        if self._rx_cmd != 0x3f:
            if self._rx_cmd == 0x41:
                raise Exception(f'DFPlayer ACK with error: no SD card?')
            else:
                raise Exception('DFPlayer no ACK.')

    async def play_track(self, track):
        """ coro: play track n """
        await self._send_command(0x03, track)
        self.track_end_ev.clear()
        self.track = track

    async def play(self):
        """ coro: start playing; after pause? """
        await self._send_command(0x0d, 0)

    async def pause(self):
        """ coro: stop playing """
        await self._send_command(0x0e, 0)

    async def set_vol(self, level):
        """ coro: set volume level 0-VOL_MAX """
        await self._send_command(0x06, level)
        self.vol = level

    async def set_eq(self, eq_key):
        """ set eq to key in:
            'normal', 'pop', 'rock', 'jazz', 'classic', 'bass'
        """
        await self._send_command(0x07, self.eq_val[eq_key])
        self.eq = eq_key
    

async def main():
    """"""
    from data_link import DataLink
    from uqueue import Buffer

    tx_queue = Buffer()
    rx_queue = Buffer()
    data_link = DataLink(0, 1, 9600, 10, tx_queue, rx_queue)
    cmd_handler = DfpMiniControl(data_link)
    print(cmd_handler)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
