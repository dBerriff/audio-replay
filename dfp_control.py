# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin, UART
from uart_os_as import Queue, StreamTR
from c_h_as import CommandHandler


class DfPlayer:
    
    def __init__(self):
        uart = UART(0, 9600)
        uart.init(tx=Pin(0), rx=Pin(1))
        stream_tr = StreamTR(uart, 10, Queue(20))
        self.c_h = CommandHandler(stream_tr)

    async def reset(self):
        """ coro: reset the DFPlayer
            - with SD card response should be:
                Rx word: q_init 0x3f 0x0002
                -- signifies online storage: SD card
                -- not currently checked by software
        """
        await self.c_h.send_command('reset', 0)
        await self.c_h.ack_ev.wait()
        await asyncio.sleep_ms(2000)
        if self.c_h.rx_cmd != 0x3f:
            raise Exception('DFPlayer could not be reset')
        else:
            print('DFPlayer reset')

    async def next_trk(self):
        """ coro: play next track """
        await self.c_h.send_command('next', 0)
        await self.c_h.ack_ev.wait()
        self.c_h.current_track += 1
        print(f'Track: {self.c_h.current_track}')
        await self.c_h.track_end_ev.wait()

    async def prev_trk(self):
        """ coro: play previous track """
        await self.c_h.send_command('prev', 0)
        await self.c_h.ack_ev.wait()
        self.c_h.current_track -= 1
        print(f'Track: {self.c_h.current_track}')
        await self.c_h.track_end_ev.wait()

    async def track(self, track_=1):
        """ coro: play track n """
        await self.c_h.send_command('track', track_)
        await self.c_h.ack_ev.wait()
        self.c_h.current_track = track_
        print(f'Track: {track_}')
        await self.c_h.track_end_ev.wait()

    async def stop(self):
        """ coro: stop playing """
        await self.c_h.send_command('stop', 0)
        await self.c_h.ack_ev.wait()
        self.c_h.track_end_ev.set()
        print('DFPlayer stopped')

    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        level = min(30, level)
        await self.c_h.send_command('vol_set', level)
        await self.c_h.ack_ev.wait()
        self.c_h.volume_level = level

    async def q_vol(self):
        """ coro: query volume level """
        await self.c_h.send_command('q_vol')
        await self.c_h.ack_ev.wait()
        print(f'Volume level: {self.c_h.volume} (0-30)')

    async def q_sd_files(self):
        """ coro: query number of SD files (in root?) """
        await self.c_h.send_command('q_sd_files')
        await self.c_h.ack_ev.wait()
        print(f'Number of SD-card files: {self.c_h.track_count}')

    async def q_sd_trk(self):
        """ coro: query current track number """
        await self.c_h.send_command('q_sd_trk')
        await self.c_h.ack_ev.wait()
        print(f'Current track: {self.c_h.current_track}')

    async def track_sequence(self, sequence):
        """ coro: play sequence of tracks by number """
        for track_ in sequence:
            await self.c_h.send_command('track', track_)
            await self.c_h.ack_ev.wait()
            print(f'Track: {track_}')
            await self.c_h.track_end_ev.wait()

    async def play(self):
        """ replace 'play' command """
        await self.track(1)


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
            - format is cmd: str, parameters: (p0: str, ...)
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
            
            if cmd == 'trk':
                # parameters required as int
                params = [int(p) for p in params]
                await player.track_sequence(params)
            elif cmd == 'zzz':
                param = int(params[0])
                await asyncio.sleep(param)
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
