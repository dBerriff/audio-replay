# df_player.py
"""
    Control DFPlayer Mini over UART
    Class PlPlayer plays tracks in a playlist
"""

import asyncio
from random import randint
from dfp_mini import DfpMini
from df_player import DfPlayer
from led import Led
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
        self.track_index = hw_player.START_TRACK
        self.list_index = 0
        self.led = Led('LED')
        self.ch_l_lock = asyncio.Lock()
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
            self._playlist = self.shuffle(self._playlist)
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
        async with self.ch_l_lock:
            if self.level > 1:
                level = self.level - 1
                await self.set_level(level)
                print(f"Output level: {level}")
                await self.led.blink(level)

    async def inc_level(self):
        """ increment volume by 1 unit and blink value """
        async with self.ch_l_lock:
            if self.level < self.LEVEL_SCALE:
                level = self.level + 1
                await self.set_level(level)
                print(f"Output level: {level}")
                await self.led.blink(level)

    @staticmethod
    def shuffle(list_):
        """ return a shuffled list
            - Durstenfeld / Fisher-Yates shuffle algorithm """
        n = len(list_)
        if n < 2:
            return list_
        limit = n - 1
        for i in range(limit):  # exclusive range
            j = randint(i, limit)  # inclusive range
            # list_[j], list_[i] = list_[i], list_[j]
            t = list_[j]
            list_[j] = list_[i]
            list_[i] = t
        return list_


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


async def main():
    """ test playlist player controller """

    # pins
    # - UART
    tx_pin = 16
    rx_pin = 17
    # - ADC
    # adc_pin = 26
    # led_pin = 'LED'

    # play_pin, v_dec_pin, v_inc_pin
    button_pins = {"play": 2, "v_dec": 3, "v_inc": 4}

    player = PlPlayer(DfpMini(tx_pin, rx_pin), button_pins)
    led = Led('LED')
    await player.reset()
    player.build_playlist(shuffled=False)
    print(f'Config: {player.config}')
    asyncio.create_task(led.show(2000))
    
    while True:
        await asyncio.sleep_ms(1000)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
    