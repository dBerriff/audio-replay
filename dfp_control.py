# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin, UART
from uart_os_as import StreamTR
from c_h_as import CommandHandler


class DfPlayer:
    
    def __init__(self):
        uart = UART(0, 9600)
        uart.init(tx=Pin(0), rx=Pin(1))
        stream_tr = StreamTR(uart, buf_len=10)
        self.c_h = CommandHandler(stream_tr)
        self.track_min = 1
        self.track_max = 0
        self.track = 1

    async def reset(self):
        """ coro: reset the DFPlayer
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
        print(track)
        self.track = track
        self.c_h.current_track = track
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
    
    async def repeat_trks(self, start, end):
        """ coro: play range of tracks on repeat"""
        trk_c = start
        while trk_c <= end:
            await self.play_trk(trk_c)
            trk_c += 1
            if trk_c > end:
                trk_c = start

    async def stop(self):
        """ coro: stop playing """
        await self.c_h.send_command_str('stop', 0)
        self.c_h.track_end_ev.set()
        print('DFPlayer stopped')

    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        level = min(30, level)
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
        print(f'Current track: {self.c_h.current_track}')

    async def track_sequence(self, sequence):
        """ coro: play sequence of tracks by number """
        for track_ in sequence:
            await self.play_trk(track_)


async def main():
    """ test DFPlayer controller """
    
    def get_command_lines(filename):
        """ read in command-lines from a text file
            - work-in-progress! """
        with open(filename) as fp:
            commands_ = [line for line in fp]
        return commands_

    async def run_commands(commands_):
        """ control DFP from simple text commands
            - format is: "cmd parameter" or "cmd, parameter"
            - work-in-progress! """

        for line in commands_:
            line = line.strip()  # trim
            # print comment line
            if line[0] == '#':
                print(line)
                continue
            # remove commas; remove extra spaces
            line = line.replace(',', ' ')
            while '  ' in line:
                line = line.replace('  ', ' ')

            tokens = line.split(' ')
            cmd = tokens[0]
            params = tokens[1:]
            print(f'{cmd} {params}')
            
            if cmd == 'zzz':
                param = int(params[0])
                await asyncio.sleep(param)
            elif cmd == 'trk':
                # parameters required as int
                params = [int(p) for p in params]
                await player.track_sequence(params)
            elif cmd == 'nxt':
                await player.next_trk()
            elif cmd == 'prv':
                await player.prev_trk()
            elif cmd == 'rst':
                await player.reset()
            elif cmd == 'vol':
                param = int(params[0])
                await player.vol_set(param)
                await player.q_vol()
            elif cmd == 'stp':
                await player.stop()

    player = DfPlayer()
    
    asyncio.create_task(player.c_h.stream_tr.receiver())
    asyncio.create_task(player.c_h.consume_rx_data())
    
    print('Send commands')
    cmd_file = 'test.txt'
    commands = get_command_lines(cmd_file)
    await run_commands(commands)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
