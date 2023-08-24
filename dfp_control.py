# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin
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


class HwSwitch:
    """
        input pin class for hardware switch or button
        - PULL_UP logic
        - returned states: 0 for off (open), 1 for on (closed)
        - this inverts pull-up logic
    """

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)

    @property
    def state(self):
        """ get switch state off (0) or on (1) """
        return 0 if self._hw_in.value() == 1 else 1


class DfPlayer:
    """ implement high-level control of the DFPlayer Mini
        - all replay is through command: 0x03 - play-track(n)
        - other commands have proved unnecessary or problematic
        - tracks are referenced by number counting from 1 """
    
    bytearray_len = 10  # correct for DfPlayer Mini
    max_q_len = 16
    
    def __init__(self, c_h):
        self.c_h = c_h
        self.track_min = 1
        self.track_max = 0
        self.track = 0
        self.repeat_flag = False

    async def reset(self):
        """ coro: reset the DFPlayer
            N.B. this coro must be run to set object attributes
            - with SD card response should be:
                Rx word: q_init 0x3f 0x0002
                -- signifies online storage, SD card
        """
        await self.c_h.send_command_str('reset', 0)
        await asyncio.sleep_ms(2000)
        if self.c_h.rx_cmd == 0x3f:
            print(f'DFPlayer reset with code: {self.c_h.rx_param}')
        else:
            raise Exception('DFPlayer could not be reset')
        # get number of TF-card files for track_max
        await self.c_h.send_command_str('q_tf_files')
        await asyncio.sleep_ms(200)
        self.track_max = self.c_h.track_count
        print(f'Number of TF-card files: {self.track_max}')

    async def play_trk(self, track):
        """ coro: play track n """
        if track < self.track_min or track > self.track_max:
            return
        print(f'play_track: {track}')
        self.track = track
        await self.c_h.send_command_str('track', track)
        await self.c_h.track_end_ev.wait()

    async def next_trk(self):
        """ coro: play next track """
        self.track += 1
        if self.track > self.track_max:
            self.track = self.track_min
        await self.play_trk(self.track)

    async def prev_trk(self):
        """ coro: play previous track """
        self.track -= 1
        if self.track < self.track_min:
            self.track = self.track_max
        await self.play_trk(self.track)
    
    async def stop(self):
        """ coro: stop playing """
        await self.c_h.send_command_str('stop', 0)
        self.c_h.track_end_ev.set()
        print('DFPlayer stopped')

    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        if level > 30:
            level = 30
        await self.c_h.send_command_str('vol_set', level)
        self.c_h.volume_level = level

    async def q_vol(self):
        """ coro: query volume level """
        await self.c_h.send_command_str('q_vol')
        print(f'Volume level: {self.c_h.volume} (0-30)')

    async def q_sd_files(self):
        """ coro: query number of SD files (in root?) """
        await self.c_h.send_command_str('q_sd_files')
        await self.c_h.ack_ev.wait()
        print(f'Number of SD-card files: {self.c_h.track_count}')

    async def q_sd_trk(self):
        """ coro: query current track number """
        await self.c_h.send_command_str('q_sd_trk')
        print(f'Current track: {self.c_h.track}')

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
        sequence = list(range(self.track_min, self.track_max + 1))
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
        