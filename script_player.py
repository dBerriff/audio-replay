# script_player.py
""" Control DFPlayer Mini over UART from text-file commands
    - command format is: cmd parameter-list, space (or comma) delimited
    - cmd is 3-letter string; parameters are list of int
"""

import asyncio
from df_player import DfPlayer
from dfp_support import Led, LedFlash


class ScriptPlayer(DfPlayer):
    """
        set player and play tracks from script
    """

    cmd_set = {'zzz', 'trk', 'nxt', 'prv', 'rst', 'vol', 'stp', 'ply'}

    def __init__(self, cmd_handler, commands=[]):
        super().__init__(cmd_handler)
        self.commands = commands
        self.led = Led('LED')

    def read_command_file(self, filename):
        """ read in command-lines from a text file """
        commands = []
        with open(filename) as fp:
            for line in fp:
                command, params = self.parse_command(line)
                if command in self. cmd_set:
                    commands.append((command, params))
        self.commands = commands

    async def run_commands(self):
        """ coro: control DFP from simple text commands
            - format is: 'cmd p0 p1 ...' or 'cmd, p0, p1, ...'
        """
        for command in self.commands:
            await self.cmd_handler.track_end_ev.wait()
            cmd_, params = command
            if cmd_ in self.cmd_set:
                print(cmd_, params)
                if cmd_ == 'zzz':
                    await self.track_end_ev.wait()
                    await asyncio.sleep(params[0])
                elif cmd_ == 'trk':
                    await self.play_trk_list(params)
                elif cmd_ == 'nxt':
                    await self.play_next_track()
                elif cmd_ == 'prv':
                    await self.play_prev_track()
                elif cmd_ == 'rst':
                    await self.reset()
                elif cmd_ == 'vol':
                    await self.set_vol(params[0])
                elif cmd_ == 'stp':
                    await self.cmd_handler.pause()
                elif cmd_ == 'ply':
                    await self.cmd_handler.ch_play()

    @staticmethod
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


