# audio_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from random import randint
from dfp_mini import CommandHandler


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
    
    def __init__(self):
        self.cmd_h = CommandHandler()
        self.track_min = 1
        self.track_count = 0
        self.track = 0
        self.repeat_flag = False
        # self.track_playing = self.cmd_h.playing_ev
        self.track_end = self.cmd_h.track_end_ev
        self.track_end.set()
        
        # tasks to receive and process response words
        asyncio.create_task(self.cmd_h.stream_tr.receiver())
        asyncio.create_task(self.cmd_h.consume_rx_data())

    @property
    def volume(self):
        """ player volume setting """
        return self.cmd_h.vol

    # basic commands
    
    async def reset(self):
        """ coro: reset the DFPlayer """
        rx_cmd, rx_param = await self.cmd_h.reset()
        print(f'Reset returned: cmd: {rx_cmd:0x} param: {rx_param}')
        await self.cmd_h.q_sd_files()
        self.track_count = self.cmd_h.track_count
        print(f'Number of tracks: {self.track_count}')

    async def play_track(self, track):
        """ coro: play track n
            - does not wait for track_end: allows pause
        """
        if self.track_min <= track <= self.track_count:
            self.track = track
            print(f'Track: {track}')
            await self.cmd_h.play_track(track)

    async def play(self):
        """ coro: play or resume current track """
        print('Play')
        await self.cmd_h.play()

    async def pause(self):
        """ coro: pause playing current track """
        print('Pause')
        await self.cmd_h.pause()

    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        if level > 30:
            level = 30
        await self.cmd_h.vol_set(level)

    # query player attributes

    async def q_vol(self):
        """ coro: query volume level """
        await self.cmd_h.q_vol()
        print(f'DFPlayer volume: {self.cmd_h.vol} (0-30)')

    async def q_sd_files(self):
        """ coro: query number of SD files (in root?) """
        await self.cmd_h.q_sd_files()
        print(f'Number of SD-card files: {self.cmd_h.track_count}')

    async def q_sd_track(self):
        """ coro: query current track number """
        await self.cmd_h.q_sd_track()
        print(f'Current track: {self.cmd_h.track}')

    # additional play commands

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
        