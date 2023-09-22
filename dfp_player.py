# dfp_player.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio


class DfPlayer:
    """ implement high-level control of audio track player
        - tracks are referenced by number, counting from 1
        - volume is set in range 0 - 10 and scaled
    """

    START_TRACK = const(1)
    VOL_MAX = const(10)

    def __init__(self, command_h_):
        self.command_h = command_h_
        self.vol_factor = command_h_.config['vol_factor']
        self.vol = command_h_.config['vol'] // self.vol_factor
        self.track_end_ev = self.command_h.track_end_ev
        self.track_end_ev.set()  # no track playing yet
        self.rx_cmd = 0x00
        self.rx_param = 0x0000

    async def reset(self):
        """ reset player including track_count """
        await self.command_h.reset()
        await self.send_query('sd_files')
        await asyncio.sleep_ms(200)

    # player methods

    async def play_track(self, track):
        """ play track by number """
        if self.START_TRACK <= track <= self.track_count:
            await self.command_h.play_track(track)

    async def play_track_after(self, track):
        """ play track after current track finishes """
        await self.command_h.track_end_ev.wait()
        await self.play_track(track)

    async def set_vol(self, level):
        """ set volume level """
        vol = min(self.VOL_MAX, level)
        vol = max(0, vol)
        await self.command_h.set_vol(vol * self.vol_factor)
    
    async def dec_vol(self):
        """ decrement volume by 1 unit """
        if self.vol > 0:
            self.vol -= 1
            await self.command_h.set_vol(self.vol * self.vol_factor)

    async def inc_vol(self):
        """ increment volume by 1 unit """
        if self.vol < self.VOL_MAX:
            self.vol += 1
            await self.command_h.set_vol(self.vol * self.vol_factor)

    async def set_eq(self, eq_type):
        """ set eq by type str """
        await self.command_h.set_eq(eq_type)

    async def send_query(self, query):
        """ send query and wait for response event
            - 'vol', 'eq', 'sd_files', 'sd_track' """
        if query in self.command_h.qry_cmds:
            await self.command_h.send_query(query)
            if query == 'vol':
                print(f'Query vol: {self.command_h.config["vol"] // self.vol_factor}')
            elif query == 'eq':
                print(f'Query eq: {self.command_h.config["eq"]}')
            elif query == 'sd_files':
                print(f'Query track count: {self.command_h.track_count}')
            elif query == 'sd_track':
                print(f'Query current track: {self.command_h.track}')
