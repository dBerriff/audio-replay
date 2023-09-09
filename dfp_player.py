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

    def __init__(self, command_h_):
        self.cmd_h = command_h_
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.vol = 0
        self.vol_factor = 1
        self.eq = 0
        self.eq_val = self.cmd_h.eq_val
        self.config_file = ConfigFile('config.json')
        self.config = {}
        self.init_config()
        self.track_count = 0
        self.track_end_ev = self.cmd_h.track_end_ev
        self.track_end_ev.set()  # no track playing yet
        self.send_query = self.cmd_h.send_query

    async def reset(self):
        """ reset player including track_count """
        await self.cmd_h.reset()
        await self.cmd_h.send_query('sd_files')
        self.track_count = self.cmd_h.track_count
    
    # config methods

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
        await self.reset()
        await asyncio.sleep_ms(200)
        await self.set_vol(self.config['vol'])
        await self.set_eq(self.config['eq'])
        await self.send_query('sd_files')

    # player methods

    async def play_track_after(self, track):
        """ coro: play track after previous track """
        await self.cmd_h.track_end_ev.wait()
        if self.START_TRACK <= track <= self.track_count:
            await self.cmd_h.play_track(track)

    async def set_vol(self, level):
        """ coro: set volume level """
        self.vol = min(self.VOL_MAX, level)
        self.vol = max(0, level)
        await self.cmd_h.set_vol(self.vol * self.vol_factor)
    
    async def dec_vol(self):
        """ decrement volume by 1 unit """
        if self.vol > 0:
            self.vol -= 1
            await self.cmd_h.set_vol(self.vol * self.vol_factor)

    async def inc_vol(self):
        """ increment volume by 1 unit """
        if self.vol < self.VOL_MAX:
            self.vol += 1
            await self.cmd_h.set_vol(self.vol * self.vol_factor)

    async def set_eq(self, setting):
        """ coro: set eq to preset """
        if setting in self.eq_val:
            self.eq = setting
            await self.cmd_h.set_eq(self.eq)

    def print_player_settings(self):
        """ print selected player settings """
        result = f'track: {self.cmd_h.track}, '
        result += f'vol: {self.cmd_h.vol // self.vol_factor}, '
        result += f'eq: {self.cmd_h.eq}'
        print(result)


async def main():
    """"""
    print('In main()')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
        