# df_player.py
""" Control DFPlayer Mini over UART """

import asyncio
from dfp_support import ConfigFile


class DfPlayer:
    """
        implement high-level control of audio track player
            device-specific module: dfp_mini.py
        - tracks are referenced by number, counting from 1
        - volume is set in range 0 - 10 and scaled
    """

    START_TRACK = const(1)
    VOL_SCALE = const(10)
    default_config = {'vol': 3, 'eq': 'bass'}

    def __init__(self, cmd_handler_):
        self.cmd_handler = cmd_handler_
        self.cf = ConfigFile('config.json', self.default_config)
        self.name = cmd_handler_.NAME
        self.config = self.cf.read_cf()
        self.cmd_vol_max = cmd_handler_.VOL_MAX
        self.vol = self.config['vol']
        self.eq = self.config['eq']
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.track_index = self.START_TRACK
        self.track_count = 0
        self.track_end_ev = self.cmd_handler.track_end_ev
        self.track_end_ev.set()  # no track playing yet

    async def reset(self):
        """ reset player including track_count """
        await self.cmd_handler.reset()
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
        if self.START_TRACK <= track <= self.cmd_handler.track_count:
            await self.cmd_handler.play_track(track)

    async def play_track_after(self, track):
        """ play track after current track finishes """
        print('df_player waiting to play track after...')
        await self.cmd_handler.track_end_ev.wait()
        print('df_player waiting done.')
        await self.play_track(track)

    async def set_vol(self, level_):
        """ set volume level """
        if level_ != self.vol:
            level = level_ * self.cmd_vol_max // self.VOL_SCALE
            self.vol = await self.cmd_handler.set_vol(level)
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
            eq_ = self.cmd_handler.eq_str_val[eq_name]
            eq_ = await self.cmd_handler.set_eq(eq_)
            self.eq = self.cmd_handler.eq_val_str[eq_]
            self.config['eq'] = self.eq

    async def send_query(self, query):
        """ send query and wait for response event
            - 'vol', 'eq', 'sd_files', 'sd_track' """
        if query in self.cmd_handler.qry_cmds:
            await self.cmd_handler.send_query(query)
            if query == 'vol':
                print(f'Query vol: {self.cmd_handler.cf["vol"] // self.vol_factor}')
            elif query == 'eq':
                print(f'Query eq: {self.cmd_handler.cf["eq"]}')
            elif query == 'sd_files':
                print(f'Query track count: {self.cmd_handler.track_count}')
            elif query == 'sd_track':
                print(f'Query current track: {self.cmd_handler.track}')

    # playback methods

    async def play_trk_list(self, list_):
        """ coro: play sequence of tracks by number """
        for track_ in list_:
            await self.play_track_after(track_)

    async def play_next_track(self):
        """ coro: play next track """
        self.track_index += 1
        if self.track_index > self.cmd_handler.track_count:
            self.track_index = self.START_TRACK
        await self.play_track_after(self.track_index)

    async def play_prev_track(self):
        """ coro: play previous track """
        self.track_index -= 1
        if self.track_index < self.START_TRACK:
            self.track_index = self.cmd_handler.track_count
        await self.play_track_after(self.track_index)
