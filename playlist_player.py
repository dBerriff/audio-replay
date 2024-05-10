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
        - playlist interface: index tracks from 1 to match DFPlayer
    """
    
    START_TRACK = 1

    def __init__(self, cmd_handler, btn_pins_):
        super().__init__(cmd_handler)
        self.buttons = DfpButtons(self, *btn_pins_)
        self._playlist = []
        self._track_count = 0
        self._index = self.START_TRACK
        self.led = Led('LED')
        asyncio.create_task(self.buttons.poll_buttons())
    
    @property
    def playlist(self):
        return self._playlist

    def build_playlist(self, shuffled=False):
        """ shuffle playlist track sequence """
        self._track_count = self.cmd_handler.track_count
        self._playlist = [i + 1 for i in range(self._track_count)]
        if shuffled:
            self._playlist = shuffle(self._playlist)
        self._playlist.insert(0, 0)

    async def play_pl_track(self, track_index_):
        """ play playlist track by index """
        self._index = track_index_
        await self.play_track_after(self._playlist[track_index_])
        print(f"Playing track: {self._index}")

    async def next_pl_track(self):
        """ coro: play next track """
        self._index += 1
        if self._index > self._track_count:
            self._index = self.START_TRACK
        await self.play_pl_track(self._index)

    async def play_playlist(self):
        """ play playlist """
        await self.play_pl_track(self.START_TRACK)
        while True:
            await self.next_pl_track()

    async def dec_vol(self):
        """ decrement volume by 1 unit and blink value """
        if self.vol > 0:
            vol = self.vol - 1
            await self.set_vol(vol)
            asyncio.create_task(self.led.blink(vol))

    async def inc_vol(self):
        """ increment volume by 1 unit and blink value """
        if self.vol < self.VOL_MAX:
            vol = self.vol + 1
            await self.set_vol(vol)
            asyncio.create_task(self.led.blink(vol))


class DfpButtons:
    """ player buttons """

    def __init__(self, player_, play_pin, v_dec_pin, v_inc_pin):
        self.player = player_
        self.play_btn = Button(play_pin)
        self.v_dec_btn = HoldButton(v_dec_pin)
        self.v_inc_btn = HoldButton(v_inc_pin)
        self.led = Led('LED')

    async def play_btn_pressed(self):
        """ play next playlist track """
        button = self.play_btn
        while True:
            await button.press_ev.wait()
            await self.player.next_pl_track()
            button.press_ev.clear()

    async def dec_btn_pressed(self):
        """ decrement player volume setting """
        button = self.v_dec_btn
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                await self.player.dec_vol()
            elif button.state == 2:
                self.player.save_config()
                asyncio.create_task(self.led.flash(1000))
            button.press_ev.clear()

    async def inc_btn_pressed(self):
        """ increment player volume setting """
        button = self.v_inc_btn
        while True:
            await button.press_ev.wait()
            if button.state == 1:
                await self.player.inc_vol()
            elif button.state == 2:
                self.player.save_config()
                asyncio.create_task(self.led.flash(1000))
            button.press_ev.clear()

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
    """ test playlist player controller
        - playlist interface indexes tracks from 1
    """
    print('In main()')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
