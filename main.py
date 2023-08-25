# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin
from dfp_player import DfPlayer
from dfp_mini import CommandHandler


async def main():
    """ test DFPlayer controller """

    async def blink(led, period=1000):
        """ coro: blink the onboard LED
            - earlier versions of MicroPython require
              25 rather than 'LED' if not Pico W
        """
        # flash LED every period ms approx.
        on_time = 100
        off_ms = period - on_time
        while True:
            led.on()
            await asyncio.sleep_ms(on_time)  # allow other tasks to run
            led.off()
            await asyncio.sleep_ms(off_ms)


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


    onboard = Pin('LED', Pin.OUT, value=0)
    asyncio.create_task(blink(onboard))  # scheduled but does not block locally
    await asyncio.sleep_ms(2000)
    print('Starting...')
    ch_tr = CommandHandler()
    player = DfPlayer(ch_tr)
    # tasks to receive and process response words
    asyncio.create_task(ch_tr.stream_tr.receiver())
    asyncio.create_task(ch_tr.consume_rx_data())
    await player.reset()
    print('Run commands')
    commands = get_command_lines('test.txt')
    player.repeat_flag = True  # allow repeat 
    await run_commands(commands)
    await asyncio.sleep(15)
    print('set repeat_flag False')
    player.repeat_flag = False
    await player.q_fd_trk()
    await ch_tr.track_end_ev.wait()
    # additional commands can now be run
    track_seq = [76, 75]
    print(f'trk {track_seq}')
    await player.track_sequence(track_seq)

    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
