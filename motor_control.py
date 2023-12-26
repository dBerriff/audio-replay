# motor_control.py
""" run dc motor(s) under PWM control """

import asyncio
from collections import namedtuple
from time import sleep
from l298n import L298N


class Motor:
    """ control speed and direction of dc motor """
    
    Speed = namedtuple('Speed', ['f', 'r'])  # forward, reverse percentages
    
    def __init__(self, channel, name):
        self.channel = channel
        self.name = name  # for print or logging
        self.state = None
        self.speed_pc = None

    def rotate(self, dc_u16):
        """ rotate motor in self.state direction at u16 duty cycle """
        self.channel.set_state(self.state)
        self.channel.set_dc_u16(dc_u16)

    def run_pc(self, percent):
        """ run the motor in the set direction at percent duty-cycle """
        print(f'Motor {self.name}: {self.state} {percent}%')
        self.rotate(0xffff * percent // 100)
        self.speed_pc = percent
    
    async def accel(self, target_pc):
        """ accelerate from stop to target speed over 10 steps """ 
        step = target_pc // 10
        for speed in range(0, target_pc, step):
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

async def main():
    """ basic test of motor control """
    # a PWM slice comprises consecutive even and odd pins
    # slice pins share the same frequency
    pwm_pins = (2, 3)  # consecutive even & odd pins
    motor_pins = (4, 5, 6, 7)
    pulse_f = 15000  # adjust for physical motor and controller
    controller = L298N(pwm_pins, motor_pins, pulse_f)
    motor_a = Motor(controller.channel_a, name='A')
    motor_b = Motor(controller.channel_b, name='B')
    # establish initial state
    await motor_a.stop()
    await motor_b.stop()
    
    motor_a_speed = Motor.Speed(f=75, r=50)
    motor_b_speed = Motor.Speed(f=75, r=50)
    for _ in range(4):
        if motor_a.state != 'F':
            motor_a.state = 'F'
            motor_b.state = 'R'
            asyncio.create_task(motor_a.accel(motor_a_speed.f))
            asyncio.create_task(motor_b.accel(motor_b_speed.r))
        else:
            motor_a.state = 'R'
            motor_b.state = 'F'
            asyncio.create_task(motor_a.accel(motor_a_speed.r))
            asyncio.create_task(motor_b.accel(motor_b_speed.f))
        await asyncio.sleep_ms(30_000)
        asyncio.create_task(motor_a.decel())
        asyncio.create_task(motor_b.decel())
        await asyncio.sleep_ms(10_000)

    motor_a.set_logic_off()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
