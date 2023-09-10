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

    @classmethod
    def get_checksum(cls, word_):
        """ 2's comp. checksum of bytes 1 to parameter-bytes inclusive """
        return -sum(word_[1:cls.P_L + 1]) & 0xffff

    @classmethod
    def check_checksum(cls, word_):
        """ returns True if checksum is valid """
        byte_sum = sum(word_[1:cls.P_L + 1])
        checksum = (word_[cls.C_M] << 8) + word_[cls.C_L]
        return (byte_sum + checksum) & 0xffff == 0

    def __init__(self, data_link_):
        self._data_link = data_link_
        self.stream_tx_rx = self._data_link.stream_tx_rx
        self.tx_ba = bytearray(self.BA_TEMPLATE)
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
        asyncio.create_task(self.consume_rx_data())

    async def _send_command(self, cmd, param=0):
        """ coro: load tx bytearray word and send
            - lock against multiple attempts to send
        """
        async with self.tx_lock:
            self.ack_ev.clear()
            self.tx_ba[self.CMD] = cmd
            self.tx_ba[self.P_M], self.tx_ba[self.P_L] = hex_f.slice_reg16(param)
            self.tx_ba[self.C_M], self.tx_ba[self.C_L] = hex_f.slice_reg16(self.get_checksum(self.tx_ba))
            await self.tx_queue.put(self.tx_ba)
            await self.ack_ev.wait()  # wait for DFPlayer ACK
            await asyncio.sleep_ms(20)  # DFP recovery time?

    async def send_query(self, query):
        """ send query and wait for response event
            - 'vol', 'eq', 'sd_files', 'sd_track' """
        self.query_rx_ev.clear()
        await self._send_command(self.qry_cmds[query])
        await self.query_rx_ev.wait()

    def parse_rx_message(self, message):
        """ parse incoming message to cmd and params """
        rx_cmd = message[self.CMD]
        rx_param = hex_f.m_l_reg16(message[self.P_M], message[self.P_L])
        return rx_cmd, rx_param

    def evaluate_rx_message(self, rx_cmd, rx_param):
        """ evaluate incoming command for required action or errors """
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

    async def consume_rx_data(self):
        """ coro: consume, parse and evaluate received bytearray """
        while True:
            await self.rx_queue.is_data.wait()
            rx_ba = await self.rx_queue.get()
            if not self.check_checksum(rx_ba):
                print(f'{hex_f.byte_array_str(rx_ba)}: checksum error')
                continue
            self._rx_cmd, self._rx_param = self.parse_rx_message(rx_ba)
            self.evaluate_rx_message(self._rx_cmd, self._rx_param)

    # DFPlayer mini control
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

    # query methods
    



async def main():
    """"""
    from data_link import DataLink
    from queue import Buffer

    tx_queue = Buffer()
    rx_queue = Buffer()
    data_link = DataLink(0, 1, 9600, 10, tx_queue, rx_queue)
    cmd_handler = CommandHandler(data_link)
    print(cmd_handler)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
