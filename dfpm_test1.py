# audio_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from audio_player import DfPlayer
from dfp_support import Led, VolButtons


async def main():
    """ test DFPlayer controller """

    def get_command_lines(filename):
        """ read in command-lines from a text file """
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
                await player.qry_vol()
            elif cmd == 'stp':
                await player.pause()
            elif cmd == 'rpt':
                # to stop: set repeat_flag False
                asyncio.create_task(player.repeat_tracks(params[0], params[1]))

    async def startup(player_):
        """ player startup sequence """
        print('Starting...')
        await player_.reset()
        await player_.set_vol(4)
        await player_.qry_vol()
        print(f'Player eq options: {player_.eq_options}')
        await player_.set_eq('bass')
        await player.qry_eq()

    onboard = Led('LED')
    asyncio.create_task(onboard.blink(10))
    # allow for player power-up
    await asyncio.sleep_ms(2000)

    player = DfPlayer()
    await startup(player)
    await player.repeat_tracks(1, player.track_count)



if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
