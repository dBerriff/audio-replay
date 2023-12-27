# motor_control.py
""" run dc motor(s) under PWM control """

import asyncio
from collections import namedtuple
from l298n import L298N
from buttons import Button


class MotorCtrl:
    """ control speed and direction of dc motor """
    
    Speed = namedtuple('Speed', ['f', 'r'])  # forward, reverse percentages
    
    def __init__(self, channel, name, start_pc=0):
        self.channel = channel
        self.name = name  # for print or logging
        self.start_pc = start_pc
        self.state = None
        self.speed_pc = None
        # y = m.x + C | C = start_pc
        self.m = (100 - start_pc) // 100

    def rotate(self, dc_u16):
        """ rotate motor in self.state direction at u16 duty cycle """
        self.channel.set_state(self.state)
        self.channel.set_dc_u16(dc_u16)

    def run_pc(self, percent):
        """ run the motor in the set direction at percent duty-cycle """
        print(f'Motor {self.name}: {self.state} {percent}%')
        if percent == 0:
            self.rotate(0)
        else: 
            self.rotate(0xffff * percent * self.m // 100)
        self.speed_pc = percent
    
    async def accel(self, target_pc):
        """ accelerate from stop to target speed over 10 steps """ 
        step = (target_pc - self.start_pc) // 10
        for speed in range(self.start_pc, target_pc, step):
            self.run_pc(speed)
            await asyncio.sleep_ms(500)  # period // 10
        self.run_pc(target_pc)

    async def decel(self):
        """ decelerate from current speed to stop over 5000 ms """
        step = self.speed_pc // 10
        for speed in range(self.speed_pc, 0, -step):
            self.run_pc(speed)
            await asyncio.sleep_ms(500)  # period // 10
        await self.halt()

    async def halt(self):
        """ set speed to 0 but retain state """
        self.run_pc(0)
        # allow some time to halt
        await asyncio.sleep_ms(500)

    async def stop(self):
        """ set state to 'S', halt the motor """
        self.state = 'S'
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
                out_state = 'F'
                motor_a_.state = 'F'
                motor_b_.state = 'R'
                await asyncio.gather(
                    motor_a_.accel(motor_a_speed_.f),
                    motor_b_.accel(motor_b_speed_.r))
                await asyncio.sleep_ms(hold_period)
                await asyncio.gather(
                    motor_a_.decel(),
                    motor_b_.decel())
            else:
                out_state = 'R'
                motor_a_.state = 'R'
                motor_b_.state = 'F'
                await asyncio.gather(
                    motor_a_.accel(motor_a_speed_.r),
                    motor_b_.accel(motor_b_speed_.f))
                await asyncio.sleep_ms(hold_period)
                await asyncio.gather(
                    motor_a_.decel(),
                    motor_b_.decel())

            # block button response 
            await asyncio.sleep_ms(20_000)
            demand_btn_.press_ev.clear()


    # see PWM slice: frequency shared
    pwm_pins = (2, 3)
    motor_pins = (4, 5, 6, 7)
    pulse_f = 15_000  # adjust for physical motor and controller

    controller = L298N(pwm_pins, motor_pins, pulse_f)
    motor_a = MotorCtrl(controller.channel_a, name='A', start_pc=25)
    motor_b = MotorCtrl(controller.channel_b, name='B', start_pc=25)
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
