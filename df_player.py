# df_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_support import ConfigFile


class DfPlayer:
    """ implement high-level control of audio track player
        - tracks are referenced by number, counting from 1
        - volume is set in range 0 - 10 and scaled
    """

    START_TRACK = const(1)
    VOL_MAX = const(10)
    default_config = {'vol': 5, 'eq': 'normal'}

    def __init__(self, command_h_):
        self.command_h = command_h_
        self.cf = ConfigFile('config.json', self.default_config)
        self.name = command_h_.NAME
        self.config = self.cf.read_cf()
        self.vol_factor = command_h_.VOL_FACTOR
        self.vol = self.config['vol']
        self.eq = self.config['eq']
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self._track_index = 1
        self.track_end_ev = self.command_h.track_end_ev
        self.track_end_ev.set()  # no track playing yet

    async def reset(self):
        """ reset player including track_count """
        await self.command_h.reset()
        await self.send_query('sd_files')
        await asyncio.sleep_ms(200)
        self.vol = self.config['vol']
        await self.set_vol(self.vol)
        self.eq = self.config['eq']
        await self.set_eq(self.eq)

    def save_config(self):
        """ save self.config as JSON file """
        self.cf.write_cf(self.config)

    # player methods

    async def play_track(self, track):
        """ play track by number """
        if self.START_TRACK <= track <= self.command_h.track_count:
            await self.command_h.play_track(track)

    async def play_track_after(self, track):
        """ play track after current track finishes """
        await self.command_h.track_end_ev.wait()
        await self.play_track(track)

    async def set_vol(self, level_):
        """ set volume level """
        if level_ != self.vol:
            self.vol = await self.command_h.set_vol(
                level_ * self.vol_factor) // self.vol_factor
            self.config['vol'] = self.vol

    async def dec_vol(self):
        """ decrement volume by 1 unit """
        if self.vol > 0:
            self.vol -= 1
            await self.set_vol(self.vol)

    async def inc_vol(self):
        """ increment volume by 1 unit """
        if self.vol < self.VOL_MAX:
            self.vol += 1
            await self.set_vol(self.vol)

    async def set_eq(self, eq_name):
        """ set eq by type str """
        if eq_name != self.eq:
            eq_ = self.command_h.eq_str_val[eq_name]
            eq_ = await self.command_h.set_eq(eq_)
            self.eq = self.command_h.eq_val_str[eq_]
            self.config['eq'] = self.eq

    async def send_query(self, query):
        """ send query and wait for response event
            - 'vol', 'eq', 'sd_files', 'sd_track' """
        if query in self.command_h.qry_cmds:
            await self.command_h.send_query(query)
            if query == 'vol':
                print(f'Query vol: {self.command_h.cf["vol"] // self.vol_factor}')
            elif query == 'eq':
                print(f'Query eq: {self.command_h.cf["eq"]}')
            elif query == 'sd_files':
                print(f'Query track count: {self.command_h.track_count}')
            elif query == 'sd_track':
                print(f'Query current track: {self.command_h.track}')

    # playback methods

    async def play_trk_list(self, list_):
        """ coro: play sequence of tracks by number """
        for track_ in list_:
            await self.play_track_after(track_)

    async def next_track(self):
        """ coro: play next track """
        self._track_index += 1
        if self._track_index > self.command_h.track_count:
            self._track_index = self.START_TRACK
        await self.play_track_after(self._track_index)

    async def prev_track(self):
        """ coro: play previous track """
        self._track_index -= 1
        if self._track_index < self.START_TRACK:
            self._track_index = self.command_h.track_count
        await self.play_track_after(self._track_index)
