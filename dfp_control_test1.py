# dfp_control.py
""" Control DFPlayer Mini over UART """

import uasyncio as asyncio
from machine import Pin, UART
from uart_ba_as import StreamTR, Queue
from dfp_app_as import CommandHandler
from dfp_control import DfPlayer, HwSwitch


async def main():
    """ test DFPlayer controller """
    
    def get_command_lines(filename):
        """ read in command-lines from a text file
            - work-in-progress! """
        with open(filename) as fp:
            commands_ = [line for line in fp]
        return commands_
    
    async def adjust_volume(c_h_, button_0, button_1):
        """ adjust volume up or down
            - need to check for command conflict """
        while True:
            if button_0.state:
                await player.vol_set(c_h_.volume + 1)
                await player.q_vol()
            elif button_1.state:
                await player.vol_set(c_h_.volume - 1)
                await player.q_vol()
            await asyncio.sleep_ms(1000)

    async def run_commands(commands_):
        """ control DFP from simple text commands
            - format is: "cmd parameter" or "cmd, parameter"
            - work-in-progress! """

        for line in commands_:
            line = line.strip()  # trim
            if line == '':  # skip empty line
                continue
            if line[0] == '#':  # print comment line then skip
                print(line)
                continue
            # remove commas; remove extra spaces
            line = line.replace(',', ' ')
            while '  ' in line:
                line = line.replace('  ', ' ')

            tokens = line.split(' ')
            cmd = tokens[0]
            params = [int(p) for p in tokens[1:]]
            print(f'{cmd} {params}')
            # all commands block except 'rpt'
            if cmd == 'zzz':
                await asyncio.sleep(params[0])
            elif cmd == 'trk':
                # parameters required as int
                await player.track_sequence(params)
            elif cmd == 'nxt':
                await player.next_trk()
            elif cmd == 'prv':
                await player.prev_trk()
            elif cmd == 'rst':
                await player.reset()
            elif cmd == 'vol':
                await player.vol_set(params[0])
                await player.q_vol()
            elif cmd == 'stp':
                await player.stop()
            elif cmd == 'rpt':
                # to stop: set repeat_flag False
                asyncio.create_task(player.repeat_tracks(params[0], params[1]))

    bytearray_len = 10  # property of command set
    q_item = bytearray(bytearray_len)
    max_q_len = 16
    queue = Queue(q_item, max_q_len)
    
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))
    stream = StreamTR(uart, bytearray_len, queue)
    command_handler = CommandHandler(stream)
    player = DfPlayer(command_handler)
    switch_0 = HwSwitch(16)
    switch_1 = HwSwitch(17)
    # tasks to receive and process response words
    asyncio.create_task(command_handler.stream_tr.receiver())
    asyncio.create_task(command_handler.consume_rx_data())

    asyncio.create_task(adjust_volume(command_handler, switch_0, switch_1))
    print('Run commands')
    commands = get_command_lines('test.txt')
    # repeat_flag is initialised False
    player.repeat_flag = True  # allow repeat 
    await run_commands(commands)
    await asyncio.sleep(30)
    print('set repeat_flag False')
    player.repeat_flag = False
    await command_handler.track_end_ev.wait()
    # additional commands can now be run
    track_seq = [76, 75]
    print(f'trk {track_seq}')
    await player.track_sequence(track_seq)
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('test complete')
