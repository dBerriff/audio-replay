# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from data_link import DataLink
from dfp_mini import CommandHandler
from dfp_player import DfPlayer
from dfp_support import Led, DfpButtons
from queue import Buffer, Queue


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
        single_space = ' '
        double_space = '  '

        for line in commands_:
            line = line.strip()  # trim
            if line == '':  # skip empty line
                continue
            if line.startswith('#'):  # print comment line then skip
                print(line)
                continue
            # remove commas; remove extra spaces
            line = line.replace(',', single_space)
            while double_space in line:
                line = line.replace(double_space, single_space)

            tokens = line.split(single_space)
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
                await player.set_vol(params[0])
                await player.qry_vol()
            elif cmd == 'stp':
                await player.pause()
            elif cmd == 'rpt':
                # to stop: set repeat_flag False
                asyncio.create_task(player.repeat_tracks(params[0], params[1]))
    
    async def loop():
        """ do nothing loop """
        while True:
            await asyncio.sleep_ms(1000)

    onboard = Led('LED')
    asyncio.create_task(onboard.blink(10))
    # allow for player power-up
    await asyncio.sleep_ms(2000)

    # instantiate rx queue and app layers
    rx_queue = Buffer()
    data_link = DataLink(0, 1, 9600, 10, rx_queue)
    cmd_handler = CommandHandler(data_link)
    player = DfPlayer(cmd_handler)
    # link button action methods
    buttons = DfpButtons(20, 21, 22)
    buttons.next_track = player.next_track
    buttons.dec_vol = player.dec_vol
    buttons.inc_vol = player.inc_vol
    # start button-polling tasks
    buttons.poll_buttons()

    await player.startup()
    print(f'{player.config['name']}: configuration file loaded')
    print(f'Number of SD tracks: {player.track_count}')
    await player.qry_vol()
    await player.qry_eq()

    commands = get_command_lines('test.txt')
    await run_commands(commands)
    # await player.next_track()
    # await player.next_track()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
