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
        self.track_end = self.ch_tr.track_end_ev

    async def reset(self):
        """ coro: reset the DFPlayer """
        rx_cmd, rx_param = await self.ch_tr.reset()
        print(f'Reset returned: cmd: {rx_cmd:0x} param: {rx_param}')
        await self.ch_tr.q_tf_files()
        self.track_count = self.ch_tr.track_count
        print(f'Number of tracks: {self.track_count}')

    async def play_track(self, track):
        """ coro: play track n
            - does not wait for track_end: allows pause
        """
        if self.track_min <= track <= self.track_count:
            self.track = track
            await self.ch_tr.play_track(track)

    async def play_full_track(self, track):
        """ coro: play track n
            - waits for track_end; no pause allowed
        """
        if self.track_min <= track <= self.track_count:
            await self.play_track(track)
            await self.track_end.wait()
        

    async def next_track(self):
        """ coro: play next track """
        self.track += 1
        if self.track > self.track_count:
            self.track = self.track_min
        await self.play_full_track(self.track)

    async def prev_track(self):
        """ coro: play previous track """
        self.track -= 1
        if self.track < self.track_min:
            self.track = self.track_count
        await self.play_full_track(self.track)
    
    async def play(self):
        """ coro: play or resume current track """
        await self.ch_tr.play()
        print('DFPlayer play')

    async def pause(self):
        """ coro: pause playing current track """
        await self.ch_tr.pause()
        print('DFPlayer pause')

    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        if level > 30:
            level = 30
        await self.ch_tr.vol_set(level)

    async def q_vol(self):
        """ coro: query volume level """
        await self.ch_tr.q_vol()
        print(f'Volume level: {self.ch_tr.vol} (0-30)')

    async def q_fd_files(self):
        """ coro: query number of FD files (in root?) """
        await self.ch_tr.q_sd_files()
        print(f'Number of SD-card files: {self.ch_tr.track_count}')

    async def q_fd_track(self):
        """ coro: query current track number """
        await self.ch_tr.q_tf_track()
        print(f'Current track: {self.ch_tr.track}')

    async def track_sequence(self, sequence):
        """ coro: play sequence of tracks by number """
        for track_ in sequence:
            await self.play_full_track(track_)

    async def repeat_tracks(self, start, end):
        """ coro: play a range of tracks from start to end inclusive
            then repeat
            - run as a task: non-blocking so repeat_flag can be set
            - should be the final command in a script list
            - to enable: must set repeat_flag True
            - to stop: set repeat_flag False
        """
        inc = -1 if end < start else 1
        rewind = end + inc
        trk_counter = start
        while self.repeat_flag:
            await self.play_full_track(trk_counter)
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
        