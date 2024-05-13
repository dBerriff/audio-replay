# df_player.py
"""
    Control DFPlayer Mini over UART
    Class PlPlayer plays tracks in a playlist
"""

import asyncio
from df_player import DfPlayer
from dfp_support import shuffle, Led
from buttons import Button, HoldButton


class PlPlayer(DfPlayer):
    """ play tracks in a playlist
        - hw_player: example: DfpMini
        - playlist interface: track_index tracks from 1 to match DFPlayer
    """

    def __init__(self, hw_player, btn_pins_):
        super().__init__(hw_player)
        self.buttons = DfpButtons(self, btn_pins_)
        self._playlist = []
        self._track_count = 0
        self.track_index = self.START_TRACK
        self.list_index = 0
        self.led = Led('LED')
        asyncio.create_task(self.buttons.poll_buttons())
    
    @property
    def playlist(self):
        return self._playlist

    def build_playlist(self, shuffled=False):
        """ shuffle playlist track sequence """
        self._track_count = self.hw_player.track_count
        playlist = []
        for i in range(self._track_count):
            playlist.append(i + 1)
        self._playlist = playlist
        print(self._track_count)
        if shuffled:
            self._playlist = shuffle(self._playlist)
        print(self._playlist)

    async def play_pl_track(self, list_index_):
        """ play playlist track by list track_index """
        self.track_index = self._playlist[list_index_]
        await self.play_track(self.track_index)

    async def next_pl_track(self):
        """ coro: play next track by list track_index """
        self.list_index += 1
        if self.list_index == self._track_count:
            self.list_index = 0
        self.track_index = self._playlist[self.list_index]
        await self.play_track(self.track_index)

    async def play_playlist(self):
        """ play playlist """
        await self.play_pl_track(0)
        while True:
            await self.next_pl_track()

    async def dec_level(self):
        """ decrement volume by 1 unit and blink value """
        if self.level > 1:
            level = self.level - 1
            await self.set_level(level)
            asyncio.create_task(self.led.blink(level))

    async def inc_level(self):
        """ increment volume by 1 unit and blink value """
        if self.level < self.LEVEL_SCALE:
            level = self.level + 1
            await self.set_level(level)
            asyncio.create_task(self.led.blink(level))


class DfpButtons:
    """
        player buttons
        - play_btn waits for any current track-play to complete
    """

    def __init__(self, player_, buttons_):
        self.player = player_
        self.play_btn = Button(buttons_["play"])
        self.v_dec_btn = HoldButton(buttons_["v_dec"])
        self.v_inc_btn = HoldButton(buttons_["v_inc"])
        self.led = Led('LED')

    async def play_btn_pressed(self):
        """ play next playlist track """
        button = self.play_btn
        self.player.list_index = -1
        while True:
            await button.press_ev.wait()
            await self.player.next_pl_track()
            await self.player.hw_player.track_end_ev.wait()
            button.clear_state()

    async def dec_btn_pressed(self):
        """ decrement player volume setting """
        button = self.v_dec_btn
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                await self.player.dec_level()
            elif button.state == 2:
                self.player.save_config()
                asyncio.create_task(self.led.show(1000))
            button.clear_state()

    async def inc_btn_pressed(self):
        """ increment player volume setting """
        button = self.v_inc_btn
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                await self.player.inc_level()
            elif button.state == 2:
                self.player.save_config()
                asyncio.create_task(self.led.show(1000))
            button.clear_state()

    async def poll_buttons(self):
        """ start button polling """
        # buttons: self poll to set state
        asyncio.create_task(self.play_btn.poll_state())
        asyncio.create_task(self.v_dec_btn.poll_state())
        asyncio.create_task(self.v_inc_btn.poll_state())
        # buttons: respond to press or hold state
        asyncio.create_task(self.play_btn_pressed())
        asyncio.create_task(self.dec_btn_pressed())
        asyncio.create_task(self.inc_btn_pressed())
