# cmd_test.py
""" Control DFPlayer Mini over UART from text-file commands
    - command format is: cmd parameter-list, space (or comma) delimited
    - cmd is 3-letter string; parameters are list of int
"""

import uasyncio as asyncio
from dfp_support import LedFlash
from dfp_mini import DfpMini
from df_player import DfPlayer


def get_command_script(filename):
    """ read in command-lines from a text file """
    with open(filename) as fp:
        commands_ = [line for line in fp]
    return commands_


def parse_command(cmd_line):
    """ parse command line to cmd and param-list
        - space (or comma) delimiter """
    cmd_line = cmd_line.strip()  # trim start/end white space
    if cmd_line == '':
        cmd_, params = '', []
    elif cmd_line.startswith('#'):
        print(cmd_line)
        cmd_, params = '', []
    else:
        cmd_line = cmd_line.replace(',', ' ')
        while '  ' in cmd_line:
            cmd_line = cmd_line.replace('  ', ' ')
        tokens = cmd_line.split(' ')
        cmd_ = tokens[0]
        params = [int(p) for p in tokens[1:]]
    return cmd_, params


async def run_commands(player_, commands_):
    """ control DFP from simple text commands
        - format is: 'cmd p0 p1 ...' or 'cmd, p0, p1, ...'
    """
    cmd_set = {'zzz', 'trk', 'nxt', 'prv', 'rst', 'vol', 'stp', 'ply'}
    for line in commands_:
        await player_.command_h.track_end_ev.wait()
        cmd_, params = parse_command(line)
        if cmd_ in cmd_set:
            print(cmd_, params)
            if cmd_ == 'zzz':
                await player_.track_end_ev.wait()
                await asyncio.sleep(params[0])
            elif cmd_ == 'trk':
                await player_.play_trk_list(params)
            elif cmd_ == 'nxt':
                await player_.next_track()
            elif cmd_ == 'prv':
                await player_.prev_track()
            elif cmd_ == 'rst':
                await player_.reset()
            elif cmd_ == 'vol':
                await player_.set_vol(params[0])
            elif cmd_ == 'stp':
                await player_.command_h.pause()
            elif cmd_ == 'ply':
                await player_.command_h.ch_play()


async def main():
    """ test DFPlayer controller """

    # pins
    # UART
    tx_pin = 0
    rx_pin = 1
    # ADC
    adc_pin = 26
    led_pin = 'LED'
    adc = LedFlash(adc_pin, led_pin)
    asyncio.create_task(adc.poll_input())

    player = DfPlayer(DfpMini(tx_pin, rx_pin))
    print(f'Player name: {player.name}')
    await player.reset()
    print(f'Config: {player.config}')
    print(player.vol, player.eq)
    print('Run commands')
    commands = get_command_script('test.txt')
    await run_commands(player, commands)
    player.save_config()
    print(f'Config: {player.config}')
    # adc.led.turn_off()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
