# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from dfp_control import DfPlayer


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

    player = DfPlayer(0, 1)
    command_handler = player.c_h
    # task to receive response words
    asyncio.create_task(command_handler.stream_tr.receiver())
    # task to read and parse the response words
    asyncio.create_task(command_handler.consume_rx_data())

    print('Run commands')
    commands = get_command_lines('test.txt')
    # repeat_flag is initialised False
    player.repeat_flag = True  # allow repeat 
    await run_commands(commands)
    await asyncio.sleep(15)
    print('set repeat_flag False')
    player.repeat_flag = False
    await command_handler.track_end_ev.wait()
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
