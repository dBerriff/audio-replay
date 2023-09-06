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
        self.track_min = 1
        self.track_count = 0
        self.track = 0
        self.play_list = []
        self.repeat_flag = False
        self.track_end = self.cmd_h.track_end_ev
        self.track_end.set()
        self.led = Led('LED')

    # config methods
    
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
        await self.reset()
        await self.set_vol(self.config['vol'])
        await self.set_eq(self.config['eq'])
        await self.cmd_h.qry_sd_files()
        self.track_count = self.cmd_h.track_count
                           
    # player methods

    async def reset(self):
        """ coro: reset the DFPlayer """
        rx_cmd, rx_param = await self.cmd_h.reset()

    async def play_track(self, track):
        """ coro: play track n - allows pause """
        if self.track_min <= track <= self.track_count:
            self.track = track
            await self.cmd_h.play_track(track)

    async def play(self):
        """ coro: play or resume current track """
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
        await self.cmd_h.qry_vol()
        print(f'Volume: {self.cmd_h.vol // self.config['vol_factor']} (0-10)')

    async def qry_eq(self):
        """ coro: query volume level """
        await self.cmd_h.qry_eq()
        print(f'Eq: {self.cmd_h.eq}')

    async def qry_sd_files(self):
        """ coro: query number of SD files (in root?) """
        await self.cmd_h.qry_sd_files()
        print(f'Number of SD-card files: {self.cmd_h.track_count}')

    async def qry_sd_track(self):
        """ coro: query current track number """
        await self.cmd_h.qry_sd_track()
        print(f'Current track: {self.cmd_h.track}')

    # additional play methods

    async def next_track(self):
        """ coro: play next track """
        self.track += 1
        if self.track > self.track_count:
            self.track = self.track_min
        await self.play_track_seq(self.track)

    async def prev_track(self):
        """ coro: play previous track """
        self.track -= 1
        if self.track < self.track_min:
            self.track = self.track_count
        await self.play_track_seq(self.track)
    
    async def play_track_seq(self, track):
        """ coro: play track n
            - waits for previous track_end
        """
        await self.track_end.wait()
        await self.play_track(track)

    async def track_sequence(self, sequence):
        """ coro: play sequence of tracks by number """
        for track_ in sequence:
            await self.play_track_seq(track_)

    async def repeat_tracks(self, start, end):
        """ coro: play a range of tracks from start to end inclusive
            then repeat
            - run as a task: non-blocking so repeat_flag can be set
            - should be the final command in a script list
            - to enable: must set repeat_flag True
            - to stop: set repeat_flag False
        """
        self.repeat_flag = True
        inc = -1 if end < start else 1
        rewind = end + inc
        trk_counter = start
        while self.repeat_flag:
            await self.play_track_seq(trk_counter)
            trk_counter += inc
            if trk_counter == rewind:  # end of list
                trk_counter = start

    def play_all(self, do_shuffle=True):
        """ play all tracks on repeat, optionally shuffled """
        sequence = list(range(self.track_min, self.track_count + 1))
        if do_shuffle:
            sequence = shuffle(sequence)
        self.repeat_flag = True
        self.track_sequence(sequence)


async def main():
    """"""
    pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
        