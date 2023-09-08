# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_player import DfPlayer
from dfp_support import Led, ConfigFile, shuffle


class ExtPlayer(DfPlayer):
    """ play tracks in a playlist
        - playlist interface: index tracks from 1 to match DFPlayer
    """

    def __init__(self, command_h_):
        super().__init__(command_h_)
    
    async def play_next(self, track):
        """ coro: play track in sequence """
        await self.track_end_ev.wait()
        await self.play_track(track)

    async def play_trk_list(self, list_):
        """ coro: play sequence of tracks by number """
        for track_ in list_:
            await self.play_next(track_)

    async def next_track(self):
        """ coro: play next track """
        self._track_index += 1
        if self._track_index > self.track_count:
            self._track_index = self.START_TRACK
        await self.play_next(self._track_index)

    async def prev_track(self):
        """ coro: play previous track """
        self._track_index -= 1
        if self._track_index < self.START_TRACK:
            self._track_index = self.track_count
        await self.play_next(self._track_index)


async def main():
    """"""
    print('In main()')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
        