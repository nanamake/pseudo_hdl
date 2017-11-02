#!/usr/bin/env python
from pseudo_hdl import Signal, Delay, Always, HwBlock, HwModule
from pseudo_hdl import simulate, now, finish, vcd_dump


def timer(clock, reset, pulse):

    count = Signal(0, n=4)
    count_eq9 = Signal(0)

    @Always(clock.posedge)
    def count_LOGIC():
        if reset or count_eq9:
            count.next = 0
        else:
            count.next = count + 1

    @Always(count)
    def count_eq9_LOGIC():
        count_eq9.next = (count == 9)

    @Always(clock.posedge)
    def pulse_LOGIC():
        pulse.next = count_eq9

    return HwModule()


def timer_tb():

    clock = Signal(0)
    reset = Signal(0)
    pulse = Signal(0)

    u_timer = timer(clock, reset, pulse)
    vcd_info = vcd_dump(u_timer, 'timer.vcd')

    @HwBlock
    def clock_GEN():
        while True:
            clock.next = 0; yield Delay(10)
            clock.next = 1; yield Delay(10)

    @HwBlock
    def reset_GEN():
        reset.next = 0
        for i in range (5):
            yield clock.posedge
        reset.next = 1
        for i in range (5):
            yield clock.posedge
        reset.next = 0

    @HwBlock
    def reset_MON():
        while True:
            yield reset
            print('reset={0} at time {1}'.format(int(reset), now()))

    @HwBlock
    def pulse_MON():
        while True:
            yield pulse
            print('pulse={0} at time {1}'.format(int(pulse), now()))

    @HwBlock
    def finish_simulation():
        yield Delay(700)
        finish('Simulation finished.')

    return HwModule()


tb = timer_tb()
simulate(tb)
