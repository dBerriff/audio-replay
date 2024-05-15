# df_player.py
""" Control DFPlayer Mini over UART """

import asyncio
from dfp_support import ConfigFile
from dfp_mini import DfpMini


class DfPlayer:
    """
        implement high-level control of audio track player
            - devices
                -- dfp_mini - serial commands over UART
                -- ??? - serial AT commands (module not yet written)
        - tracks are referenced by number, counting from 1
        - volume is set from 0...10 and scaled to device range
    """

    LEVEL_SCALE = const(10)
    default_config = {'level': 3, 'eq': 'bass'}

    def __init__(self, hw_player_):
        self.hw_player = hw_player_
        self.cf = ConfigFile('config.json', self.default_config)
        self.name = hw_player_.NAME
        self.config = self.cf.read_cf()
        self.vol_factor = hw_player_.VOL_MAX // self.LEVEL_SCALE
        self.level = self.config['level']
        self.eq = self.config['eq']
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.start_track = hw_player_.START_TRACK
        self.track_index = self.start_track
        hw_player_.track_end_ev.set()  # no track playing yet

    async def reset(self):
        """ reset player including track_count """
        await self.hw_player.reset()
        await self.send_query('sd_files')
        await asyncio.sleep_ms(200)
        self.level = self.config['level']
        await self.set_level(self.level)
        self.eq = self.config['eq']
        await self.set_eq(self.eq)

    def save_config(self):
        """ save self.config as JSON file """
        self.cf.write_cf(self.config)

    # player methods

    async def play_track(self, track):
        """ play track by number """
        await self.hw_player.play_track(track)

    async def play_track_after(self, track):
        """ play track after current track finishes """
        await self.hw_player.track_end_ev.wait()
        await self.hw_player.play_track(track)

    async def set_level(self, level_):
        """ set audio output level  """
        if level_ != self.level:
            level_ = max(level_, 0)
            level_ = min(level_, self.LEVEL_SCALE)
            await self.hw_player.set_vol(level_ * self.vol_factor)
            self.level = level_
            self.config['level'] = level_

    async def set_eq(self, eq_name):
        """ set eq by type str """
        if eq_name != self.eq:
            eq_ = self.hw_player.eq_str_val[eq_name]
            eq_ = await self.hw_player.set_eq(eq_)
            self.eq = self.hw_player.eq_val_str[eq_]
            self.config['eq'] = self.eq

    async def send_query(self, query):
        """ send query and wait for response event
            - 'vol', 'eq', 'sd_files', 'sd_track' """
        if query in self.hw_player.qry_cmds:
            await self.hw_player.send_query(query)
            await self.hw_player.q_response_ev.wait()
            if query == 'vol':
                print(f'Query level: {self.hw_player.config["vol"] // self.vol_factor}')
            elif query == 'eq':
                print(f'Query eq: {self.hw_player.config["eq"]}')
            elif query == 'sd_files':
                print(f'Query track count: {self.hw_player.track_count}')
            elif query == 'sd_track':
                print(f'Query current track: {self.hw_player.track}')
            self.hw_player.q_response_ev.clear()

    # playback methods

    async def play_trk_list(self, list_):
        """ coro: play sequence of tracks by number """
        for track_ in list_:
            await self.play_track_after(track_)

    async def play_next_track(self):
        """ coro: play next track """
        self.track_index += 1
        if self.track_index > self.hw_player.track_count:
            self.track_index = self.start_track
        await self.play_track_after(self.track_index)

    async def play_prev_track(self):
        """ coro: play previous track """
        self.track_index -= 1
        if self.track_index < self.start_track:
            self.track_index = self.hw_player.track_count
        await self.play_track_after(self.track_index)


async def main():
    """ test DFPlayer controller """

    # UART pins
    tx_pin = 16
    rx_pin = 17

    player = DfpMini(tx_pin, rx_pin)
    v_player = DfPlayer(player)
    print("player.reset()")
    await v_player.reset()
    await v_player.set_level(3)
    await v_player.send_query("vol")
    await v_player.send_query("eq")

    tracks = player.track_count
    print(f"Track count: {tracks}")
    for i in range(tracks):
        track = i + 1
        print(f"player.play_track({track})")
        await v_player.play_track_after(track)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
