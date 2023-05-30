import uasyncio as asyncio
from machine import UART, Pin
from command_handler_as import Queue, StreamTR, CommandHandler
import _thread as thread


class Controller:
    """ control DFPlayer"""

    def __init__(self, uart):
        self.uart = uart
        self.uart_tr = StreamTR(uart, 10, Queue(20))
        self.c_h = CommandHandler(self.uart_tr)
        self.playing = self.c_h.track_playing_ev
        self.folder = None

    # DFPlayer commands

    async def play_next(self):
        """ play next track """
        await self.c_h.send_command('next')
        self.playing.set()
        await self.play_wait()

    async def play_prev(self):
        """ play next track """
        await self.c_h.send_command('prev')
        self.playing.set()
        await self.play_wait()

    async def play_track(self, track_number: int):
        """ play track by number; 1-2999 (docs show 0-2999) """
        track_number = max(1, track_number)
        await self.c_h.send_command('track', track_number)
        self.playing.set()
        await self.play_wait()

    async def inc_volume(self):
        """ increase volume by one unit """
        await self.c_h.send_command('vol_inc')
        await asyncio.sleep_ms(200)
    
    async def dec_volume(self):
        """ decrease volume by one unit """
        await self.c_h.send_command('vol_dec')
        await asyncio.sleep_ms(200)

    async def set_volume(self, level: int):
        """ set volume in range 0-30  """
        level = max(0, level)
        level = min(30, level)
        await self.c_h.send_command('vol_set', level)
        await asyncio.sleep_ms(200)

    async def set_eq(self, mode: int):
        """ set eq type in range 0-5
            - normal, pop, rock, jazz, classic, bass """
        mode = max(0, mode)
        mode = min(5, mode)
        await self.c_h.send_command('eq_set', mode)
        await asyncio.sleep_ms(200)

    async def set_pb_mode(self, mode: int):
        """ set playback mode in range 0-3
            - repeat, folder_repeat, single_repeat, random
            - 0: repeat tracks
            - 1: repeat tracks (in folder?)
            - as for rest, do not seem to work
        """
        mode = max(0, mode)
        mode = min(3, mode)
        await self.c_h.send_command('playback_mode', mode)
        await asyncio.sleep_ms(200)

    async def standby(self):
        """ set to low-power standby
            - appears to get 'stuck' in this mode
            - power off-wait-and-on is required """
        pass

    async def normal(self):
        """ set to normal operation (from standby?) """
        await self.c_h.send_command('normal')
        await asyncio.sleep_ms(200)

    async def reset(self):
        """ reset device
            - power-on requires 1.5 to 3.0 s
              so play safe """
        await self.c_h.send_command('reset')
        self.playing.clear()
        await asyncio.sleep_ms(3000)  # ZG

    async def playback(self):
        """ start/resume playback """
        await self.c_h.send_command('playback')
        self.playing.set()
        await self.play_wait()

    async def pause(self):
        """ pause playback """
        await self.c_h.send_command('pause')
        await asyncio.sleep_ms(200)

    async def set_folder(self, folder: int):
        """ set playback folder in range 1-10
            - for efficient playback do not use """
        folder = max(1, folder)
        folder = min(10, folder)
        self.folder = folder
        await self.c_h.send_command('folder', folder)
        await asyncio.sleep_ms(200)
        
    async def repeat_play(self, start: int):
        """ control repeat play:
            - 0: stop - does not work!
            - 1: start
        """
        await self.c_h.send_command('repeat_play', start)
        if start == 1:
            self.c_h.play_flag = True
        else:
            self.c_h.play_flag = False
        await asyncio.sleep_ms(200)

    # support methods
    
    async def play_wait(self):
        """ wait for current track to complete """
        while self.playing.is_set():
            await asyncio.sleep_ms(20)

    async def dfp_init(self, vol):
        """ initialisation commands """
        await self.reset()
        await self.c_h.send_command('q_tf_files')
        await self.set_volume(vol)
        await self.c_h.send_command('q_vol')
        self.playing.clear()


async def blink():
    """ blink onboard LED """
    from machine import Pin
    led = Pin(16, Pin.OUT)
    while True:
        led.value(1)
        await asyncio.sleep_ms(1000)
        led.value(0)
        await asyncio.sleep_ms(1000)


async def main():
    """ test Controller, CommandHandler and UartTxRx """

    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    controller = Controller(uart)
    asyncio.create_task(controller.c_h.consume_rx_data())
    asyncio.create_task(controller.c_h.stream_tr.read_rx_data())
    thread.start_new_thread(asyncio.create_task(blink()), ())
    asyncio.create_task(blink())
    await controller.dfp_init(15)
    await controller.playback()
    for i in range(1):
        await controller.play_next()
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
