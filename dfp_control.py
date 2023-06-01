#dfp_control.py
""" Control DFPlayer Mini """

import uasyncio as asyncio
from machine import Pin, UART
from uart_os_as import Queue, StreamTR
from c_h_as import CommandHandler

class DfPlayer:
    
    def __init__(self):
        uart = UART(0, 9600)
        uart.init(tx=Pin(0), rx=Pin(1))
        stream_tr = StreamTR(uart, 10, Queue(20))
        self.c_h = CommandHandler(stream_tr)
 
        
    async def reset(self):
        """ coro: reset the DFPlayer
            - with SD card response should be:
                Rx word: q_init 0x3f 0x0002
                -- signifies online storage: SD card
                -- not currently checked by software
        """
        await self.c_h.send_command('reset', 0)
        await self.c_h.ack_ev.wait()
        await asyncio.sleep_ms(2000)
        if self.c_h.rx_cmd != 0x3f:
            raise Exception('DFPlayer could not be reset')
        else:
            print('DFPlayer reset')


    async def next_trk(self, n=1):
        """ coro: play n next tracks """
        for _ in range(n):
            await self.c_h.send_command('next', 0)
            await self.c_h.ack_ev.wait()
            await self.c_h.track_end_ev.wait()


    async def prev_trk(self, n=1):
        """ coro: play n previous tracks """
        for _ in range(n):
            await self.c_h.send_command('prev', 0)
            await self.c_h.ack_ev.wait()
            await self.c_h.track_end_ev.wait()


    async def track(self, track_=1):
        """ coro: play track n """
        await self.c_h.send_command('track', track_)
        await self.c_h.ack_ev.wait()
        print(f'Track: {track_}')
        await self.c_h.track_end_ev.wait()


    async def stop(self):
        """ coro: stop playing """
        await self.c_h.send_command('stop', 0)
        await self.c_h.ack_ev.wait()
        self.c_h.track_end_ev.set()


    async def vol_set(self, level):
        """ coro: set volume level 0-30 """
        level = min(30, level)
        await self.c_h.send_command('vol_set', level)
        await self.c_h.ack_ev.wait()


    async def q_vol(self):
        """ coro: query volume level """
        await self.c_h.send_command('q_vol')
        await self.c_h.ack_ev.wait()
        print(f'Volume level: {self.c_h.volume} (0-30)')


    async def q_sd_files(self):
        """ coro: query number of SD files (in root?) """
        await self.c_h.send_command('q_sd_files')
        await self.c_h.ack_ev.wait()
        print(f'Number of SD-card files: {self.c_h.track_count}')


    async def q_sd_trk(self):
        """ coro: query current track number """
        await self.c_h.send_command('q_sd_trk')
        await self.c_h.ack_ev.wait()
        print(f'Current track: {self.c_h.current_track}')


    async def track_sequence(self, sequence):
        """ coro: play sequence of tracks by number """
        for track_ in sequence:
            await self.c_h.send_command('track', track_)
            await self.c_h.ack_ev.wait()
            print(f'Track: {track_}')
            await self.c_h.track_end_ev.wait()

    async def play(self):
        """ replace 'play' command """
        await self.track(1)


async def main():
    """ test CommandHandler and UartTxRx """
    
    player = DfPlayer()
    # tasks are non-blocking; the task is added to the scheduler
    asyncio.create_task(player.c_h.stream_tr.receiver())
    asyncio.create_task(player.c_h.consume_rx_data())
    
    # dictionary of tracks for selected phrases
    phrase_track = {'time_is': 76, 'midnight': 75}

    # awaited coros block; the coro is added to the scheduler
    print('Send commands')
    await player.reset()
    await player.vol_set(20)
    await player.q_vol()
    await player.q_sd_files()  # return number of files

    await player.track_sequence(
        (phrase_track['time_is'], 9, 25))
    await asyncio.sleep(2)
    await player.track_sequence(
        (phrase_track['time_is'], 13, 57))
    await asyncio.sleep(2)
    await player.track_sequence(
        (phrase_track['time_is'], 65))
    await asyncio.sleep(2)    
    await player.track_sequence(
        (phrase_track['time_is'], phrase_track['midnight']))

    await player.play()
    await player.next_trk()
    await player.next_trk()
    await player.prev_trk()
    await player.track(61)
    await player.next_trk()
    await player.next_trk()
    await player.prev_trk()
    await asyncio.sleep_ms(1000)
    await player.stop()
    print('demo complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
