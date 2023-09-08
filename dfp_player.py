# dfp_player.py
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
    VOL_MIN = const(0)

    def __init__(self, command_h_):
        self.cmd_h = command_h_
        self.vol = 0
        self.vol_factor = 1
        self.eq = 0
        self.eq_settings = list(self.cmd_h.eq_val.keys())
        self.config_file = ConfigFile('config.json')
        self.config = {}
        self.init_config()
        self.track_count = 0
        self._track_index = 1

        # map unmodified methods
        self.reset = self.cmd_h.reset
        self.play = self.cmd_h.play
        self.pause = self.cmd_h.pause
        self.track_end_ev = self.cmd_h.track_end_ev
        self.track_end_ev.set()

    # config methods
    
    @property
    def track(self):
        """ set by qry_sd_track() """
        return self._track_index
    
    def init_config(self):
        """ initialise config from file or set to defaults
            - write config file if it does not exist
        """
        if self.config_file.is_file():
            self.config = self.config_file.read_file()
        else:
            self.config = self.cmd_h.config
            self.config_file.write_file(self.config)
        self.vol = self.config['vol']
        self.vol_factor = self.config['vol_factor']
        self.eq = self.config['eq']

    def save_config(self):
        """ update and save config dictionary """
        self.config['vol'] = self.vol
        self.config['eq'] = self.eq
        self.config_file.write_file(self.config)

    async def startup(self):
        """ player startup sequence
            - response should be: (0x3f, 0x02)
        """
        response = await self.reset()
        await self.set_vol(self.config['vol'])
        await self.set_eq(self.config['eq'])
        await self.qry_sd_files()
        return response

    # player methods

    async def play_track(self, track):
        """ coro: play track n - allows pause """
        if self.START_TRACK <= track <= self.track_count:
            self._track_index = track
            await self.cmd_h.play_track(track)

    async def set_ch_vol(self):
        """ set command handler volume """
        await self.cmd_h.set_vol(self.vol * self.vol_factor)

    async def set_vol(self, level):
        """ coro: set volume level 0-10 """
        if self.VOL_MIN <= level <= self.VOL_MAX:
            self.config['vol'] = level
            await self.set_ch_vol()
    
    async def dec_vol(self):
        """ increase volume by 1 unit """
        if self.vol > self.VOL_MIN:
            self.vol -= 1
            await self.set_ch_vol()

    async def inc_vol(self):
        """ increase volume by 1 unit """
        if self.vol < self.VOL_MAX:
            self.vol += 1
            await self.set_ch_vol()

    async def set_eq(self, setting):
        """ coro: set eq to preset """
        if setting in self.eq_settings:
            self.eq = setting
            await self.cmd_h.set_eq(setting)

    # query methods

    async def qry_vol(self):
        """ coro: query volume level """
        ch_vol = await self.cmd_h.qry_vol()
        self.vol = ch_vol // self.vol_factor
        print(f'Volume: {self.vol}')

    async def qry_eq(self):
        """ coro: query volume level """
        eq = await self.cmd_h.qry_eq()
        self.eq = eq
        print(f'Eq: {self.eq}')

    async def qry_sd_files(self):
        """ coro: query number of SD files (in root?) """
        self.track_count = await self.cmd_h.qry_sd_files()
        print(f'Number of SD-card files: {self.track_count}')

    async def qry_sd_track(self):
        """ coro: query current track number """
        self._track_index = await self.cmd_h.qry_sd_track()
        print(f'Current track: {self.track}')


async def main():
    """"""
    print('In main()')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
        