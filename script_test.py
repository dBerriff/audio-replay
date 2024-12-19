# script_test.py
""" test class ScriptPlayer """

import asyncio
from dfp_mini import DfpMini
from script_player import ScriptPlayer

async def main():
    """ test DFPlayer controller """

    # UART pins
    tx_pin = 16
    rx_pin = 17

    cmds = [('vol', [5]), ('trk', [3]), ('trk', [2]), ('trk', [1])]
    player = ScriptPlayer(DfpMini(tx_pin, rx_pin), cmds)
    print(f'Player name: {player.name}')
    await player.reset()
    print(f"Level (1-10): {player.level} Eq: {player.eq}")
    print('Run commands')
    # player.read_command_file('test.txt')
    await player.run_commands()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
