# audio_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from audio_player import DfPlayer
from ap_support import Led


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
                await player.next_track()
            elif cmd == 'prv':
                await player.prev_track()
            elif cmd == 'rst':
                await player.reset()
            elif cmd == 'vol':
                await player.vol_set(params[0])
                await player.q_vol()
            elif cmd == 'stp':
                await player.pause()
            elif cmd == 'rpt':
                # to stop: set repeat_flag False
                asyncio.create_task(player.repeat_tracks(params[0], params[1]))

    onboard = Led('LED')
    asyncio.create_task(onboard.blink(10))
    # allow for player power-up
    await asyncio.sleep_ms(2000)
    print('Starting...')

    player = DfPlayer()
    await player.reset()
    await player.vol_set(15)
    await player.q_vol()
    await player.q_sd_track()  # query current track
    print('Run commands')

    commands = get_command_lines('test.txt')
    player.repeat_flag = True  # allow repeat 
    await run_commands(commands)
    await asyncio.sleep(5)
    print('set repeat_flag False')
    player.repeat_flag = False
    await player.track_end.wait()  # blocking must be in this task

    # additional commands can now be run
    await player.play_track_seq(79)
    await player.play_track_seq(1)
    await asyncio.sleep_ms(1000)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
