# motor_control.py
""" run dc motor(s) under PWM control """

import asyncio
from collections import namedtuple
from l298n import L298N


class MotorCtrl:
    """ control speed and direction of dc motor """
    
    Speed = namedtuple('Speed', ['f', 'r'])  # forward, reverse percentages
    
    @staticmethod
    def pc_u16(percentage):
        """ convert percentage to proportional 16-bit value"""
        return 0xffff * percentage // 100

    def __init__(self, channel, name, start_speed=25):
        self.channel = channel
        self.name = name  # for print or logging
        self.start_speed = start_speed
        self.state = ''
        self.speed_u16 = 0

    def set_state(self, state):
        """ set 'F' forward, 'R' reverse, or 'S' stop  """
        self.channel.set_state(state)
        self.state = state

    def rotate(self, dc_u16):
        """ rotate motor in state direction at u16 duty cycle """
        self.channel.set_dc_u16(dc_u16)
        self.speed_u16 = dc_u16

    async def accel(self, start_pc, target_pc, n_steps=25):
        """ accelerate from stop to target speed over n_steps """
        start_u16 = self.pc_u16(start_pc)
        target_u16 = self.pc_u16(target_pc)
        step = (target_u16 - start_u16) // n_steps
        sleep_ms = 5_000 // n_steps
        for speed in range(start_u16, target_u16, step):
            self.rotate(speed)
            await asyncio.sleep_ms(sleep_ms)
        self.rotate(target_u16)
        return target_pc

    async def halt(self):
        """ set speed to 0 but retain state """
        self.rotate(0)
        # allow some time to halt
        await asyncio.sleep_ms(500)

    async def stop(self):
        """ set state to 'S', halt the motor """
        self.set_state('S')
        await self.halt()

    def set_logic_off(self):
        """ turn off channel logic """
        self.channel.set_logic_off()

async def main():
    """ test of motor control """
    
    async def run_sequence(motor_, speed_, direction):
        """ run the locomotive """
        motor_.stop()
        hold_period = 10  # s : hold speed steady
        motor_.set_state(direction)
        for sequence in range(2):
            print(f'Sequence: {sequence + 1}')
            print(f'Accelerate from {direction} {motor_.start_speed}% to {speed_}%')
            current_speed = await motor_.accel(motor_.start_speed, speed_)
            print(f'Hold speed {direction} {current_speed}%')
            await asyncio.sleep(hold_period)
            print(f'Decelerate from {direction} {current_speed}% to {0}%')
            await motor_.accel(current_speed, 0)
            # pause movement
            print('Pause')
            await asyncio.sleep(30)


    # see PWM slice: frequency shared
    pwm_pins = (2, 3)
    motor_pins = (4, 5, 6, 7)
    pulse_f = 15_000  # adjust for physical motor and controller

    controller = L298N(pwm_pins, motor_pins, pulse_f)
    motor_a = MotorCtrl(controller.channel_a, 'A', 20)
    # establish initial state
    await motor_a.stop()

    motor_a_speed = MotorCtrl.Speed(f=75, r=50)

    await run_sequence(motor_a, motor_a_speed.f, 'F')

    motor_a.set_logic_off()
    await asyncio.sleep_ms(20)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
