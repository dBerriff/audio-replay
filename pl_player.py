# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_player import DfPlayer
from dfp_support import shuffle, Led


class PlPlayer(DfPlayer):
    """ play tracks in a playlist
        - playlist interface: index tracks from 1 to match DFPlayer
    """

    def __init__(self, command_h_):
        super().__init__(command_h_)
        self._playlist = []
        self._pl_track_index = self.START_TRACK
        self.led = Led('LED')
    
    @property
    def playlist(self):
        return self._playlist

    def save_config(self):
        """ save config settings """
        self.config['vol'] = self.vol
        self.config['eq'] = self.eq
        self.config_file.write_file(self.config)
        asyncio.create_task(self.led.blink(self.config['vol']))

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
        self._pl_track_index = track_index_
        await self.play_track_after(self._playlist[track_index_])

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

    async def dec_vol(self):
        """ decrement volume """
        if self.vol > 1:
            self.vol -= 1
            await self.set_vol(self.vol)
            asyncio.create_task(self.led.blink(self.vol))

    async def inc_vol(self):
        """ increment volume """
        if self.vol < self.VOL_MAX:
            self.vol += 1
            await self.set_vol(self.vol)
            asyncio.create_task(self.led.blink(self.vol))


async def main():
    """ test playlist player controller
        - playlist interface indexes tracks from 1
    """
    print('In main()')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
