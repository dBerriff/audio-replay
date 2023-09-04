# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_player import DfPlayer
from dfp_support import Led, DfpButtons


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
    
    async def loop():
        """"""
        while True:
            # await buttons.inc_vol()
            await asyncio.sleep_ms(1000)


    onboard = Led('LED')
    asyncio.create_task(onboard.blink(10))
    # allow for player power-up
    await asyncio.sleep_ms(2000)

    player = DfPlayer()
    buttons = DfpButtons(20, 21, 22)
    buttons.next_track = player.next_track
    buttons.dec_vol = player.dec_vol
    buttons.inc_vol = player.inc_vol
    buttons.poll_buttons()
    await player.startup()
    await player.qry_vol()
    # asyncio.create_task(player.repeat_tracks(1, player.track_count))
    await player.next_track()
    await player.next_track()
    await loop()



if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
