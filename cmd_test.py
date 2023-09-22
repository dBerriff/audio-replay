# cmd_test.py
""" Control DFPlayer Mini over UART from text-file commands
    - command format is: cmd parameter-list, space (or comma) delimited
    - cmd is 3-letter string; parameters are list of int
"""

import uasyncio as asyncio
import machine
from dfp_support import Led
from data_link import DataLink
from dfp_mini import DfpMiniControl
from dfp_player import DfPlayer
from uqueue import Buffer


class LedFlash:
    """ flash LED if ADC threshold exceeded """
    
    def __init__(self, adc_pin_, led_pin_):
        self.adc = machine.ADC(adc_pin_)
        self.led = Led(led_pin_)

    async def poll_input(self):
        """ """
        ref_u16 = 25_400
        while True:
            await asyncio.sleep_ms(100)
            level_ = self.adc.read_u16()
            if level_ > ref_u16:
                asyncio.create_task(self.led.flash(min((level_ - ref_u16), 200)))


async def main():
    """ test DFPlayer controller """

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

    async def run_commands(commands_):
        """ control DFP from simple text commands
            - format is: 'cmd p0 p1 ...' or 'cmd, p0, p1, ...'
        """
        cmd_set = {'zzz', 'trk', 'nxt', 'prv', 'rst', 'vol', 'stp', 'ply'}
        for line in commands_:
            await player.command_h.track_end_ev.wait()
            cmd_, params = parse_command(line)
            if cmd_ in cmd_set:
                print(cmd_, params)
                if cmd_ == 'zzz':
                    await player.track_end_ev.wait()
                    await asyncio.sleep(params[0])
                elif cmd_ == 'trk':
                    await player.play_trk_list(params)
                elif cmd_ == 'nxt':
                    await player.next_track()
                elif cmd_ == 'prv':
                    await player.prev_track()
                elif cmd_ == 'rst':
                    await player.reset()
                elif cmd_ == 'vol':
                    await player.set_vol(params[0])
                elif cmd_ == 'stp':
                    await player.command_h.pause()
                elif cmd_ == 'ply':
                    await player.command_h.ch_play()

    def build_player(tx_p, rx_p):
        """ build player from components """
        data_link = DataLink(tx_p, rx_p, 9600, 10, Buffer(), Buffer())
        cmd_handler = DfpMiniControl(data_link)
        return DfPlayer(cmd_handler)

    # pins
    # UART
    tx_pin = 0
    rx_pin = 1
    # ADC
    adc_pin = 26
    led_pin = 'LED'
    
    adc = LedFlash(adc_pin, led_pin)
    asyncio.create_task(adc.poll_input())

    player = build_player(tx_pin, rx_pin)
    await player.reset()
    await player.send_query('vol')
    await player.send_query('eq')
    print('Run commands')
    commands = get_command_script('test.txt')
    await run_commands(commands)
    await player.track_end_ev.wait()
    player.save_config()
    # adc.led.turn_off()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
