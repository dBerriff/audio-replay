# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_support import Led, ConfigFile, shuffle


class DfPlayer:
    """ implement high-level control of audio track player
        - tracks are referenced by number counting from 1
        - volume is set in range 0 - 10 and scaled
        - print() statements are minimised except for qry methods;
          add to calling script if required
    """

    VOL_MAX = 10
    VOL_MIN = 0

    def __init__(self, command_h_):
        self.cmd_h = command_h_
        self.eq_settings = list(self.cmd_h.eq_val.keys())
        self.config_file = ConfigFile('config.json')
        self.config = {}
        self.init_config()
        self.track_count = 0
        self.track_min = 1
        self._track_index = 1
        self.repeat_flag = False
        self.track_end_ev = self.cmd_h.track_end_ev
        self.track_end_ev.set()
        self.led = Led('LED')

    # config methods
    
    @property
    def track_number(self):
        return self._track_index
    
    def init_config(self):
        """ initialise config from file or set to defaults """
        if self.config_file.is_file():
            self.config = self.config_file.read_file()
        else:
            self.config = self.cmd_h.config
            self.config_file.write_file(self.config)

    def save_config(self):
        """ save config settings """
        self.config_file.write_file(self.config)
        asyncio.create_task(self.led.blink(self.config['vol']))

    async def startup(self):
        """ player startup sequence """
        response = await self.reset()
        await self.set_vol(self.config['vol'])
        await self.set_eq(self.config['eq'])
        await self.cmd_h.qry_sd_files()
        self.track_count = self.cmd_h.track_count
        return response

    # player methods

    async def reset(self):
        """ coro: reset the DFPlayer """
        return await self.cmd_h.reset()

    async def play_track(self, track):
        """ coro: play track n - allows pause """
        if self.track_min <= track <= self.track_count:
            self._track_index = track
            await self.cmd_h.play_track(track)

    async def play(self):
        """ coro: play or resume (after pause) current track """
        await self.cmd_h.play()

    async def pause(self):
        """ coro: pause playing current track """
        await self.cmd_h.pause()
    
    async def set_ch_vol(self):
        """ set command handler volume """
        await self.cmd_h.set_vol(self.config['vol'] * self.config['vol_factor'])

    async def set_vol(self, level):
        """ coro: set volume level 0-10 """
        if self.VOL_MIN <= level <= self.VOL_MAX:
            self.config['vol'] = level
            await self.set_ch_vol()
    
    async def dec_vol(self):
        """ increase volume by 1 unit """
        if self.config['vol'] > self.VOL_MIN:
            self.config['vol'] -= 1
            await self.set_ch_vol()

    async def inc_vol(self):
        """ increase volume by 1 unit """
        if self.config['vol'] < self.VOL_MAX:
            self.config['vol'] += 1
            await self.set_ch_vol()

    async def set_eq(self, setting):
        """ coro: set eq to preset """
        if setting in self.eq_settings:
            self.config['eq'] = setting
            await self.cmd_h.set_eq(self.config['eq'])

    # query methods

    async def qry_vol(self):
        """ coro: query volume level """
        ch_vol = await self.cmd_h.qry_vol()
        self.config['vol'] = ch_vol // self.config['vol_factor']
        print(f"Volume: {self.config['vol']}")

    async def qry_eq(self):
        """ coro: query volume level """
        eq = await self.cmd_h.qry_eq()
        self.config['eq'] = eq
        print(f"Eq: {self.config['eq']}")

    async def qry_sd_files(self):
        """ coro: query number of SD files (in root?) """
        tc = await self.cmd_h.qry_sd_files()
        self.track_count = tc
        print(f'Number of SD-card files: {self.track_count}')

    async def qry_sd_track(self):
        """ coro: query current track number """
        trk = await self.cmd_h.qry_sd_track()
        self._track_index = trk
        print(f'Current track: {self._track_index}')

    # additional play methods

    async def play_track_next(self, track):
        """ coro: play track in sequence """
        await self.track_end_ev.wait()
        await self.play_track(track)

    async def play_trk_list(self, list_):
        """ coro: play sequence of tracks by number """
        for track_ in list_:
            await self.play_track_next(track_)

    async def next_track(self):
        """ coro: play next track """
        self._track_index += 1
        if self._track_index > self.track_count:
            self._track_index = self.track_min
        await self.play_track_next(self._track_index)

    async def prev_track(self):
        """ coro: play previous track """
        self._track_index -= 1
        if self._track_index < self.track_min:
            self._track_index = self.track_count
        await self.play_track_next(self._track_index)


class PlPlayer(DfPlayer):
    """ play tracks in a playlist
        - playlist interface: index tracks from 1 to match DFPlayer
    """
    
    START_TRACK = const(1)

    def __init__(self, command_h_):
        super().__init__(command_h_)
        self._playlist = []
        self._pl_track_index = self.START_TRACK
    
    @property
    def playlist(self):
        return self._playlist

    def build_playlist(self, shuffled=False):
        """ shuffle playlist track sequence """
        self._playlist = [i + 1 for i in range(self.track_count)]
        if shuffled:
            self._playlist = shuffle(self._playlist)
        self._playlist.insert(0, 0)

    async def play_pl_track(self, track_index_):
        """ play current playlist track
            - offset by -1 to match list index
        """
        await self.track_end_ev.wait()
        self._pl_track_index = track_index_
        await self.play_track(self._playlist[track_index_])

    async def next_pl_track(self):
        """ coro: play next track """
        self._pl_track_index += 1
        if self._pl_track_index > self.track_count:
            self._pl_track_index = self.START_TRACK
        await self.play_pl_track(self._pl_track_index)

    async def prev_pl_track(self):
        """ coro: play previous track """
        self._pl_track_index -= 1
        if self._pl_track_index < self.START_TRACK:
            self._pl_track_index = self.track_count
        await self.play_pl_track(self._pl_track_index)

    async def play_playlist(self):
        """ play playlist """
        await self.play_pl_track(self.START_TRACK)
        while True:
            await self.next_pl_track()


async def main():
    """"""
    pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
        