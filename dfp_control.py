# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin, UART
from uart_os_as import StreamTR
from c_h_as import CommandHandler, AdcReader
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
        - other commands have proved unnecessary or problematic """
    
    def __init__(self):
        uart = UART(0, 9600)
        # UART Tx, Rx on pins 0 and 1
        uart.init(tx=Pin(0), rx=Pin(1))
        # ADC input on pin 26
        self.c_h = CommandHandler(StreamTR(uart, buf_len=10), AdcReader(26))
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
        while self.repeat_flag:
            for track_ in sequence:
                await self.play_trk(track_)

    async def repeat_tracks(self, start, end):
        """ coro: play a range of tracks from start to end inclusive
            then repeat
            - run as a task so is non-blocking:
                -- must be the final command in a set
            - set repeat_flag True to enable (initialised False)
            - to stop: set repeat_flag False
            - end == start repeats a single track
            - end can be less than the start track (count down) """
        if end > start:
            inc = +1
        elif end < start:
            inc = -1
        else:
            return
        rewind = end + inc
        trk_counter = start
        while self.repeat_flag:
            await self.play_trk(trk_counter)
            trk_counter += inc
            if trk_counter == rewind:
                trk_counter = start

    def play_all(self, do_shuffle=True):
        """ play all tracks on repeat, optionally shuffled """
        sequence = list(range(self.track_min, self.max + 1))
        if do_shuffle:
            sequence = shuffle(sequence)
        self.repeat_flag = True
        self.track_sequence(sequence)


async def main():
    """ test DFPlayer controller """
    
    async def while_playing(playing, trigger):
        """ check for 'loud' Event being triggered
            - test function to demonstrate operation """
        while True:
            await playing.wait()
            while playing.is_set():
                if trigger.is_set():
                    print('loud!')
                    # clear to catch next loud event
                    trigger.clear()
                await asyncio.sleep_ms(200)

    def get_command_lines(filename):
        """ read in command-lines from a text file
            - work-in-progress! """
        with open(filename) as fp:
            commands_ = [line for line in fp]
        return commands_

    async def run_commands():
        """ control DFP from simple text commands
            - format is: "cmd parameter" or "cmd, parameter"
            - work-in-progress! """

        nonlocal commands
        for line in commands:
            line = line.strip()  # trim
            if line == '':  # skip empty line
                continue
            if line[0] == '#':  # print comment line then skip
                print(line)
                continue
            # remove commas; remove extra spaces
            line = line.replace(',', ' ')
            while '  ' in line:
                line = line.replace('  ', ' ')

            tokens = line.split(' ')
            cmd = tokens[0]
            params = [int(p) for p in tokens[1:]]
            print(f'{cmd} {params}')
            # all commands block except 'rpt'
            if cmd == 'zzz':
                await asyncio.sleep(params[0])
            elif cmd == 'trk':
                # parameters required as int
                await player.track_sequence(params)
            elif cmd == 'nxt':
                await player.next_trk()
            elif cmd == 'prv':
                await player.prev_trk()
            elif cmd == 'rst':
                await player.reset()
            elif cmd == 'vol':
                await player.vol_set(params[0])
                await player.q_vol()
            elif cmd == 'stp':
                await player.stop()
            elif cmd == 'rpt':
                # to stop: set repeat_flag False
                asyncio.create_task(player.repeat_tracks(params[0], params[1]))

    player = DfPlayer()
    # task to receive response words
    asyncio.create_task(player.c_h.stream_tr.receiver())
    # task to read and parse the response words
    asyncio.create_task(player.c_h.consume_rx_data())
    # task to monitor ADC input and set a trigger Event above a threshold
    asyncio.create_task(player.c_h.check_vol_trigger())
    # test task to print a line if the ADC trigger Event has been set
    asyncio.create_task(while_playing(player.c_h.playing_ev, player.c_h.trigger_ev))
    
    print('Send commands')
    cmd_file = 'test.txt'
    commands = get_command_lines(cmd_file)
    # repeat_flag is initialised False
    player.repeat_flag = True
    await run_commands()
    # let final 'rpt' command in test.txt run for 15s then stop
    await asyncio.sleep(15)
    print('set repeat_flag False')
    player.repeat_flag = False
    await asyncio.sleep(2)
    # additional commands can now be run, including run_commands()
    track_seq = [76, 75]
    print(f'trk {track_seq}')
    await player.track_sequence(track_seq)
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
