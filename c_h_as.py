# command_handler_as.py
"""
Control a DFPlayer Mini (DFP) from a Raspberry Pi Pico.
Requires modules hex_fns and uart_os_as to be loaded onto the Pico.
See https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for DFP documentation
Not all DFP commands are required or have been tested.

- TF-card is synonymous with microSD Card
- this version is for TF-cards only
- simplified: no folder-related commands

"""

from machine import UART, Pin
import uasyncio as asyncio
import hex_fns as hex_f
from uart_os_as import Queue, StreamTR


class CommandHandler:
    """ formats, sends and receives command and query messages
        - see Flyron Technology Co documentation for references
        - www.flyrontech.com
        - coro is short for coroutine
    """

    BUF_SIZE = const(10)
    # data-byte indices
    CMD = const(3)
    P_H = const(5)  # parameter
    P_L = const(6)
    C_H = const(7)  # checksum
    C_L = const(8)

    R_FB = const(1)  # require ACK feedback
    WAIT_MS = const(200)

    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}
    
    hex_str = {
        0x01: 'next',
        0x02: 'prev',
        0x03: 'track',  # 1-3000
        0x04: 'vol_inc',
        0x05: 'vol_dec',
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # 0:normal/1:pop/2:rock/3:jazz/4:classic/5:bass
        0x08: 'repeat_trk',  # track no. as parameter
        0x0c: 'reset',
        0x0e: 'stop',
        0x11: 'repeat_all',  # 0: stop; 1: start
        0x3a: 'media_insert',
        0x3b: 'media_remove',
        0x3d: 'sd_fin',
        0x3f: 'q_init',  # 02: TF-card
        0x40: 'error',
        0x41: 'ack',
        0x42: 'q_status',  # 0: stopped; 1: playing; 2: paused
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x48: 'q_sd_files',  # in root directory
        0x4c: 'q_sd_trk'
        }
    
    # inverse dictionary mapping
    str_hex = {value: key for key, value in hex_str.items()}

    # add Rx-only codes
    hex_str[0x3a] = 'media_insert'
    hex_str[0x3b] = 'media_remove'

    # build set of commands that play a track
    # required to clear the track_end_ev event
    play_set_str = {'next', 'prev', 'track', 'repeat_trk', 'repeat_all'}
    play_set = {0}
    # set comprehension raises an error so simple loop
    for element in play_set_str:
        play_set.add(str_hex[element])
    play_set.remove(0)

    def __init__(self, stream):
        self.stream_tr = stream
        self.sender = stream.sender
        self.rx_queue = stream.rx_queue
        self.tx_word = bytearray(self.BUF_SIZE)
        self.rx_word = bytearray(self.BUF_SIZE)
        # pre-load template fixed values
        for key in self.data_template:
            self.tx_word[key] = self.data_template[key]
        self.rx_cmd = 0x00
        self.rx_param = 0x0000
        self.volume = 0  # for info
        self.track_count = 0  # for info
        self.current_track = 0  # for info
        self.ack_ev = asyncio.Event()
        self.track_end_ev = asyncio.Event()
        self.error_ev = asyncio.Event()  # not currently monitored
        self.verbose = True

    def get_checksum(self):
        """ return the 2's complement checksum of:
            - bytes 1 to 6 """
        return hex_f.slice_reg16(-sum(self.tx_word[1:7]))

    def check_checksum(self, buf_):
        """ returns 0 for consistent checksum """
        byte_sum = sum(buf_[1:self.C_H])
        checksum_ = buf_[self.C_H] << 8  # msb
        checksum_ += buf_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    async def send_command(self, cmd_str, param=0):
        """ coro: set tx bytearray values and send
            - commands set own timing """
        self.ack_ev.clear()  # require ACK
        cmd_hex = self.str_hex[cmd_str]
        self.tx_word[self.CMD] = cmd_hex
        self.tx_word[self.P_H], self.tx_word[self.P_L] = \
            hex_f.slice_reg16(param)
        self.tx_word[self.C_H], self.tx_word[self.C_L] = \
            self.get_checksum()
        # if command plays a track, clear track_end_ev
        if cmd_hex in self.play_set:
            self.track_end_ev.clear()
        await self.sender(self.tx_word)
        # ack_ev is set in parse_rx_message()
        await self.ack_ev.wait()

    async def consume_rx_data(self):
        """ coro: parses and prints received data """

        def parse_rx_message(message_):
            """ parse incoming message_ parameters and
                set dependent attributes
                - continue following checksum error (non-zero)
                - partial implementation for known requirements """

            rx_cmd = message_[self.CMD]
            if self.check_checksum(message_):
                # continue but log
                print(f'{rx_cmd}: error in checksum')
                return
            rx_param = hex_f.set_reg16(
                message_[self.P_H], message_[self.P_L])

            # check for specific messages that require action
            if rx_cmd == 0x41:  # ack
                self.ack_ev.set()
            elif rx_cmd == 0x3d:  # sd_finish
                self.current_track = rx_param
                self.track_end_ev.set()
            elif rx_cmd == 0x3f:  # q_init
                if rx_param & 0x0002 != 0x0002:
                    raise Exception('DFPlayer error: no TF-card?')
            elif rx_cmd == 0x40:  # error
                self.error_ev.set()  # not currently monitored
            elif rx_cmd == 0x43:  # q_vol
                self.volume = rx_param
            elif rx_cmd == 0x48:  # q_sd_files
                self.track_count = rx_param
            elif rx_cmd == 0x4c:  # q_sd_trk
                self.current_track = rx_param
            elif rx_cmd == 0x3a:  # media_insert
                print('TF-card inserted.')
            elif rx_cmd == 0x3b:  # media_remove
                raise Exception('DFPlayer error: TF-card removed!')

            self.rx_cmd = rx_cmd
            self.rx_param = rx_param

        # poll the Rx queue
        while True:
            await self.rx_queue.is_data.wait()  # wait for data input
            self.rx_word = self.rx_queue.rmv_item()
            parse_rx_message(self.rx_word)


async def main():
    """ test CommandHandler and UartTxRx """
    
    async def reset():
        """ coro: reset the DFPlayer
            - with TF-card response should be:
                Rx word: q_init 0x3f 0x0002
                -- 0x0002: online storage is TF-card
        """
        print('Attempt DFPlayer reset...')
        await c_h.send_command('reset', 0)
        await c_h.ack_ev.wait()
        await asyncio.sleep_ms(2000)
        # require media online and TF-card present
        if c_h.rx_cmd == 0x3f and c_h.rx_param & 0x02:
            print('DFPlayer: reset succesful')
        else:
            raise Exception('DFPlayer: could not be reset')                
            
    async def next_trk():
        """ coro: play next track
            - track number is computed, not checked """
        await c_h.send_command('next', 0)
        await c_h.ack_ev.wait()
        c_h.current_track += 1
        print(f'Track: {c_h.current_track}')
        await c_h.track_end_ev.wait()

    async def prev_trk():
        """ coro: play previous track
            - track number is computed, not checked """
        await c_h.send_command('prev', 0)
        await c_h.ack_ev.wait()
        c_h.current_track -= 1
        print(f'Track: {c_h.current_track}')
        await c_h.track_end_ev.wait()

    async def track(track_i=1):
        """ coro: play track n """
        await c_h.send_command('track', track_i)
        await c_h.ack_ev.wait()
        c_h.current_track = track_i
        print(f'Track: {c_h.current_track}')
        await c_h.track_end_ev.wait()

    async def stop():
        """ coro: stop playing """
        await c_h.send_command('stop', 0)
        await c_h.ack_ev.wait()
        c_h.track_end_ev.set()

    async def vol_set(level):
        """ coro: set volume level 0-30 """
        level = min(30, level)
        await c_h.send_command('vol_set', level)
        await c_h.ack_ev.wait()

    async def q_vol():
        """ coro: query volume level """
        await c_h.send_command('q_vol')
        await c_h.ack_ev.wait()
        print(f'Volume level: {c_h.volume} (0-30)')

    async def q_sd_files():
        """ coro: query number of TF files (in root?) """
        await c_h.send_command('q_sd_files')
        await c_h.ack_ev.wait()
        print(f'Number of TF-card files: {c_h.track_count}')

    async def q_sd_trk():
        """ coro: query current track number """
        await c_h.send_command('q_sd_trk')
        await c_h.ack_ev.wait()
        print(f'Current track: {c_h.current_track}')

    async def track_sequence(sequence):
        """ coro: play sequence of tracks by number
            - sequence is a list or tuple """
        for track_ in sequence:
            await c_h.send_command('track', track_)
            await c_h.ack_ev.wait()
            print(f'Track: {track_}')
            await c_h.track_end_ev.wait()

    async def play():
        """ replace 'play' command """
        await track(1)

    # streaming object
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream_tr = StreamTR(uart, 10, Queue(20))
    c_h = CommandHandler(stream_tr)
    # tasks are non-blocking; the task is added to the scheduler
    asyncio.create_task(stream_tr.receiver())
    asyncio.create_task(c_h.consume_rx_data())
    
    # dictionary of tracks for selected phrases
    phrase_track = {'time_is': 76, 'midnight': 75}

    # awaited coros block; the coro is added to the scheduler
    print('Send commands')
    await reset()
    await vol_set(20)
    await q_vol()
    await q_sd_files()  # return number of files

    await track_sequence((phrase_track['time_is'], 9, 25))
    await asyncio.sleep(2)
    await track_sequence((phrase_track['time_is'], 13, 57))
    await asyncio.sleep(2)
    await track_sequence((phrase_track['time_is'], 65))
    await asyncio.sleep(2)    
    await track_sequence(
        (phrase_track['time_is'], phrase_track['midnight']))

    await play()
    await next_trk()
    await next_trk()
    await prev_trk()
    await track(61)
    await next_trk()
    await next_trk()
    await prev_trk()
    await asyncio.sleep_ms(1000)
    await stop()
    print('demo complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
