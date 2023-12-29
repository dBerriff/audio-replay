# motor_control.py
""" run dc motor(s) under PWM control """

import asyncio
from collections import namedtuple
from micropython import const
from l298n import L298N
from buttons import Button


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


class Buttons:
    """ input buttons """

    def __init__(self, pins_):
        self.demand_btn = Button(pins_[0])

    async def poll_buttons(self):
        """ start button polling """
        # buttons: self poll to set state
        asyncio.create_task(self.demand_btn.poll_state())


async def main():
    """ test of motor control """
    
    async def run_incline(
        demand_btn_, motor_a_, motor_b_, motor_a_speed_, motor_b_speed_):
        """ run the incline motors """

        hold_period = 5_000  # hold speed steady
        out_state = 'S'
        while True:
            print('Waiting for button press...')
            await demand_btn_.press_ev.wait()
            if out_state != 'F':
                print('Move forward')
                out_state = 'F'
                motor_a_.set_state('F')
                motor_b_.set_state('R')
                print('Accelerate')
                await asyncio.gather(
                    motor_a_.accel(motor_a_.start_speed, motor_a_speed_.f),
                    motor_b_.accel(motor_b_.start_speed, motor_b_speed_.r))
                print('Hold')
                await asyncio.sleep_ms(hold_period)
                print('Decelerate')
                await asyncio.gather(
                    motor_a_.accel(motor_a_speed_.f, 0),
                    motor_b_.accel(motor_a_speed_.f, 0))
            else:
                out_state = 'R'
                print('Move in reverse')
                motor_a_.set_state('R')
                motor_b_.set_state('F')
                print('Accelerate')
                await asyncio.gather(
                    motor_a_.accel(motor_a_.start_speed, motor_a_speed_.f),
                    motor_b_.accel(motor_b_.start_speed, motor_b_speed_.r))
                print('Hold')
                await asyncio.sleep_ms(hold_period)
                print('Decelerate')
                await asyncio.gather(
                    motor_a_.accel(motor_a_speed_.f, 0),
                    motor_b_.accel(motor_a_speed_.f, 0))

            # block button response 
            await asyncio.sleep_ms(5_000)
            demand_btn_.press_ev.clear()


    # see PWM slice: frequency shared
    pwm_pins = (2, 3)
    motor_pins = (4, 5, 6, 7)
    pulse_f = 15_000  # adjust for physical motor and controller

    controller = L298N(pwm_pins, motor_pins, pulse_f)
    motor_a = MotorCtrl(controller.channel_a, name='A', start_speed=25)
    motor_b = MotorCtrl(controller.channel_b, name='B', start_speed=25)
    # establish initial state
    await motor_a.stop()
    await motor_b.stop()

    ctrl_buttons = Buttons([20])
    asyncio.create_task(ctrl_buttons.poll_buttons())  # buttons self-poll
    demand_btn = ctrl_buttons.demand_btn

    motor_a_speed = MotorCtrl.Speed(f=75, r=50)
    motor_b_speed = MotorCtrl.Speed(f=75, r=50)

    await run_incline(demand_btn, motor_a, motor_b, motor_a_speed, motor_b_speed)

    motor_a.set_logic_off()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
