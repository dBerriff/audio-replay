# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from random import randint


def shuffle(tracks: list) -> tuple:
    """ return a shuffled tuple (or list)
        - Durstenfeld / Fisher-Yates shuffle algorithm """
    n = len(tracks)
    if n < 2:
        return tracks
    limit = n - 1
    for i in range(limit):  # exclusive range
        j = randint(i, limit)  # inclusive range
        tracks[i], tracks[j] = tracks[j], tracks[i]
    return tuple(tracks)


class DfPlayer:
    """ implement high-level control of the DFPlayer Mini
        - all replay is through command: 0x03 - play-track(n)
        - other commands have proved unnecessary or problematic
        - tracks are referenced by number counting from 1 """
    
    bytearray_len = 10  # correct for DfPlayer Mini
    max_q_len = 16
    
    def __init__(self, ch_tr_):
        self.ch_tr = ch_tr_
        self.track_min = 1
        self.track_count = 0
        self.track = 0
        self.repeat_flag = False

    async def reset(self):
        """ coro: reset the DFPlayer """
        rx_cmd, rx_param = await self.ch_tr.reset()
        print(f'Reset returned: cmd: {rx_cmd:0x} param: {rx_param}')
        await self.ch_tr.q_tf_files()
        self.track_count = self.ch_tr.track_count
        print(f'Number of tracks: {self.track_count}')

    async def play_trk(self, track):
        """ coro: play track n """
        if track < self.track_min or track > self.track_count:
            return
        print(f'play_track: {track}')
        self.track = track
        await self.ch_tr.play_trk(track)

    async def next_trk(self):
        """ coro: play next track """
        self.track += 1
        if self.track > self.track_count:
            self.track = self.track_min
        await self.play_trk(self.track)

    async def prev_trk(self):
        """ coro: play previous track """
        self.track -= 1
        if self.track < self.track_min:
            self.track = self.track_count
        await self.play_trk(self.track)
    
    async def stop(self):
        """ coro: stop playing """
        await self.ch_tr.stop()
        print('DFPlayer stopped')

    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        if level > 30:
            level = 30
        await self.ch_tr.vol_set(level)

    async def q_vol(self):
        """ coro: query volume level """
        await self.ch_tr.q_vol()
        print(f'Volume level: {self.ch_tr.volume} (0-30)')

    async def q_fd_files(self):
        """ coro: query number of FD files (in root?) """
        await self.ch_tr.q_sd_files()
        print(f'Number of SD-card files: {self.ch_tr.track_count}')

    async def q_fd_trk(self):
        """ coro: query current track number """
        await self.ch_tr.q_tf_trk()
        print(f'Current track: {self.ch_tr.track}')

    async def track_sequence(self, sequence):
        """ coro: play sequence of tracks by number """
        for track_ in sequence:
            await self.play_trk(track_)

    async def repeat_tracks(self, start, end):
        """ coro: play a range of tracks from start to end inclusive
            then repeat
            - run as a task: non-blocking so repeat_flag can be set
            - should be the final command in a script list
            - to enable: must set repeat_flag True
            - to stop: set repeat_flag False
        """
        if end > start:
            inc = +1
        elif end < start:
            inc = -1  # count down through tracks
        else:
            return
        rewind = end + inc
        trk_counter = start
        while self.repeat_flag:
            await self.play_trk(trk_counter)
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
        