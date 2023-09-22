# dfp_mini.py
"""
    DFPlayer Mini (DFP): device specific code
    See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for documentation.
    Some DFP mini commands do not work so are implemented in software.
"""

import uasyncio as asyncio
import struct
from dfp_support import ConfigFile


class CmdPackUnpack:
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
        self.tx_message = list(CmdPackUnpack.CMD_TEMPLATE)

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


class DfpMiniCh:
    """ formats, sends and receives command and query messages
        - N.B. 'reset' must be called to initialise object
        - tx messages are directly sent
        - rx messages are received through rx_queue
        - config is set from file config.json or _config
        - config.json must be explicitly saved if values are changed
    """

    _config = {'name': 'DFPlayer Mini',
               'vol_factor': 3,  # 0 - 30
               'vol': 15,
               'eq': 'normal'
               }
    qry_cmds = {'vol': 0x43,
                'eq': 0x44,
                'sd_files': 0x48,
                'sd_track': 0x4c
                }
    MESSAGE_SIZE = const(10)  # bytes
    # mutable message-byte indices
    CMD = const(3)
    P_M = const(5)
    P_L = const(6)
    C_M = const(7)
    C_L = const(8)

    VOL_MAX = const(30)
    CONFIG_FILENAME = const('config.json')

    # settings dictionaries
    eq_val = {'normal': 0, 'pop': 1, 'rock': 2, 'jazz': 3, 'classic': 4, 'bass': 5}
    val_eq = {value: key for key, value in eq_val.items()}

    def __init__(self, data_link_):
        # self._data_link = data_link_
        self.stream_tx_rx = data_link_.stream_tx_rx
        self.tx_queue = data_link_.tx_queue
        self.rx_queue = data_link_.rx_queue
        self.cmd_bytes = CmdPackUnpack()
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.cf = ConfigFile(self.CONFIG_FILENAME)
        self.config = self.get_config()
        self.track_count = 0
        self.track = 0
        self.ack_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored
        self.tx_lock = asyncio.Lock()
        asyncio.create_task(self.consume_rx_data())

    def get_config(self):
        """ initialise config from file or set to defaults
            - write config file if it does not exist
        """
        if self.cf.is_file():
            config = self.cf.read_file()
        else:
            config = DfpMiniCh._config
            self.cf.write_file(config)
        return config

    def save_config(self):
        """ save config settings """
        do_update = False
        if self.cf.is_file():
            prev_config = self.cf.read_file()
            if self.config != prev_config:
                do_update = True
        else:
            do_update = True
        if do_update:
            print(f'Saving config: {self.config}')
            self.cf.write_file(self.config)

    def player_config_str(self):
        """ return player config as str """
        result = f'player: {self.config["name"]}, '
        result += f'vol: {self.config["vol"]}, '
        result += f'eq: {self.config["eq"]}'
        return result

    async def _send_command(self, cmd_, param_=0):
        """ load tx bytearray word and send
            - lock against multiple attempts to send
        """
        async with self.tx_lock:
            self.ack_ev.clear()
            await self.tx_queue.put(self.cmd_bytes.pack_tx_ba(cmd_, param_))
            await self.ack_ev.wait()  # wait for DFPlayer ACK
            await asyncio.sleep_ms(20)  # DFP recovery time?

    async def send_query(self, query):
        """ send query """
        if query in self.qry_cmds:
            await self._send_command(self.qry_cmds[query])

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
            self.config['eq'] = self.val_eq[rx_param_]
        elif rx_cmd_ == 0x48:  # qry: sd_files
            self.track_count = rx_param_
        elif rx_cmd_ == 0x4c:  # qry: sd_trk
            self.track = rx_param_
        elif rx_cmd_ == 0x3a:  # media_insert
            print('SD-card inserted.')
        elif rx_cmd_ == 0x3b:  # media_remove
            raise Exception('DFPlayer error: SD-card removed!')

    async def consume_rx_data(self):
        """ get and evaluate received bytearray """
        while True:
            await self.rx_queue.is_data.wait()
            ba_ = await self.rx_queue.get()
            self.rx_cmd, self.rx_param = self.cmd_bytes.unpack_rx_ba(ba_)
            self.evaluate_rx_message(self.rx_cmd, self.rx_param)


class DfpMiniControl(DfpMiniCh):
    """ Extends DFPlayer Mini with control methods """

    def __init__(self, data_link_):
        super().__init__(data_link_)

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
        await self._send_command(0x03, track)
        self.track_end_ev.clear()
        self.track = track

    async def play(self):
        """ coro: resume/start playing """
        await self._send_command(0x0d, 0)

    async def pause(self):
        """ pause/stop playing """
        await self._send_command(0x0e, 0)

    async def set_vol(self):
        """ set volume 0 - VOL_MAX """
        await self._send_command(0x06, self.config['vol'])

    async def set_eq(self):
        """ set eq by name """
        await self._send_command(0x07, self.eq_val[self.config['eq']])
