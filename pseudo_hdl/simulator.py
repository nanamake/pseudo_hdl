"""Simulate pseudo HDL written in Python."""
from collections import namedtuple
from inspect import currentframe
from .vcd_info import _VcdInfo


class Signal:
    def __init__(self, value, n=1):
        """
        Create a signal object and set the initial value.
        To dump a multi-bit signal, specify the number of bits.
        Properties "next", "posedge" and "negedge" are available.
        """
        self._value = value
        self._next = value
        self._waiters = []
        self._posedge = None
        self._negedge = None
        self._numbits = n
        self._vcd_id = None
        if (self._numbits == 1):
            self._vcd_write = self._vcd_write_bit
        else:
            self._vcd_write = self._vcd_write_vec

    @property
    def next(self):
        return self._next

    @next.setter
    def next(self, other):
        if isinstance(other, Signal):
            self._next = other._value
        else:
            self._next = other
        _next_signals.append(self)

    @property
    def posedge(self):
        if self._posedge is None:
            self._posedge = _Edge()
        return self._posedge

    @property
    def negedge(self):
        if self._negedge is None:
            self._negedge = _Edge()
        return self._negedge

    def _update(self):
        if self._value == self._next:
            return []
        if self._posedge and (not self._value) and self._next:
            self._waiters += self._posedge._waiters
            del self._posedge._waiters[:]
        if self._negedge and self._value and (not self._next):
            self._waiters += self._negedge._waiters
            del self._negedge._waiters[:]
        self._value = self._next
        if self._vcd_id:
            self._vcd_write()
        return self._waiters

    def _vcd_write_bit(self):
        _vcd.write('{0}{1}\n'.format(int(self._value), self._vcd_id))

    def _vcd_write_vec(self):
        _vcd.write('b{0:b} {1}\n'.format(int(self._value), self._vcd_id))

    def __str__(self):
        return str(int(self._value))

    def __int__(self):
        return int(self._value)

    def __bool__(self):
        return bool(self._value)

    def __eq__(self, other):
        return self._value == other

    def __ne__(self, other):
        return self._value != other

    def __lt__(self, other):
        return self._value < other

    def __le__(self, other):
        return self._value <= other

    def __gt__(self, other):
        return self._value > other

    def __ge__(self, other):
        return self._value >= other

    def __add__(self, other):
        if isinstance(other, Signal):
            return self._value + other._value
        else:
            return self._value + other

    def __sub__(self, other):
        if isinstance(other, Signal):
            return self._value - other._value
        else:
            return self._value - other


class _Edge:
    def __init__(self):
        self._waiters = []


class Delay:
    def __init__(self, value):
        """
        Create a delay object and set the delay value.
        """
        self._value = value


class _HwBlock:
    def __init__(self, generator):
        self.generator = generator


class _HwModule:
    def __init__(self, signal_dict, block_dict, module_dict):
        self.signal_dict = signal_dict
        self.block_dict = block_dict
        self.module_dict = module_dict
        self.vcd_info = None
        self.vcd_flag = False


def Always(*signal_or_edges):
    """
    Convert a function to generator function with loop and convert it
    to hw_block object.
    Generator is set as property of the object.
    """
    def deco(func):
        logic_func = func
        def gen_func():
            while True:
                yield signal_or_edges
                logic_func()
        func = gen_func()
        return _HwBlock(func)
    return deco


def HwBlock(func):
    """
    Convert a generator function to hw_block object.
    Generator is set as property of the object.
    """
    func = func()
    return _HwBlock(func)


def HwModule():
    """
    Collect objects and their names from stack frame.
    Set object name dictionary to new hw_module and return it.
    """
    signal_dict = {}
    block_dict = {}
    module_dict = {}
    vcd_info = None
    frame = currentframe().f_back
    for name, obj in frame.f_locals.items():
        if isinstance(obj, Signal):
            signal_dict[name] = obj
        elif isinstance(obj, _HwBlock):
            block_dict[name] = obj
        elif isinstance(obj, _HwModule):
            module_dict[name] = obj
        elif isinstance(obj, _VcdInfo):
            vcd_info = obj
    hw_module = _HwModule(signal_dict, block_dict, module_dict)
    hw_module.vcd_info = vcd_info
    return hw_module


# Outline of simulate()
#
# 1) For each Always and HwBlock, execute up to the first yield statement.
#   If the event indicated by the yield statement is a signal change,
#   register the generator of the block into the waiting list of the signal.
#   If the event is a time delay, register the generator into time event list.
#
# 2) By executing each block, the next values are set to the signals.
#   If there is a change in value when updating the signal, execute each block
#   up to the next yield statement using the generator in the waiting list.
#   Also, a new event corresponding to the yield statement is registered.
#   This step is repeated until no signal change.
#
# 3) Advance the simulation time to the next event time.
#   For each event waiting for the same simulation time, execute the block
#   up to the next yield statement using the corresponding generator.
#   Also, a new event corresponding to the yield statement is registered.
#
# 4) Repeat steps 2 and 3 until signal change and time event disappear.

_now = 0
_next_signals = []
_vcd = None


def simulate(hw_module):
    """
    Execute simulation until finish() is called or no more events.
    """
    vcd_info = _find_vcd_info(hw_module)
    if vcd_info:
        print('Create VCD file "{0}".'.format(vcd_info.filename))
        global _vcd
        _vcd = open(vcd_info.filename, 'wt')
        _vcd.write(vcd_info.create_header())

    time_pair = namedtuple('time_pair', ('time', 'generator'))
    time_pairs = []

    def schedule_next(generators):
        for generator in generators:
            obj = next(generator, None)
            if isinstance(obj, Signal) or isinstance(obj, _Edge):
                obj = obj,
            if isinstance(obj, tuple):
                for signal_or_edge in obj:
                    signal_or_edge._waiters.append(generator)
            elif isinstance(obj, Delay):
                schedule(_now + obj._value, generator)

    def schedule(time, generator):
        new_pair = time_pair(time, generator)
        inserted = False
        for i, existing_pair in enumerate(time_pairs):
            if time < existing_pair.time:
                time_pairs.insert(i, new_pair)
                inserted = True
                break
        if not inserted:
            time_pairs.append(new_pair)

    schedule_next(_collect_generators(hw_module, []))

    while _next_signals or time_pairs:
        try:
            while _next_signals:
                all_signal_waiters = []
                for signal in _next_signals:
                    signal_waiters = signal._update()
                    for waiter in signal_waiters:
                        if waiter not in all_signal_waiters:
                            all_signal_waiters.append(waiter)
                    del signal_waiters[:]
                del _next_signals[:]
                schedule_next(all_signal_waiters)

        except _FinishSimulation as exc:
            _finish(str(exc))
            return 0

        global _now
        try:
            if time_pairs:
                _now = time_pairs[0].time
                if _vcd:
                    _vcd.write('#{0}\n'.format(_now))
            time_waiters = []
            while time_pairs:
                if _now == time_pairs[0].time:
                    time_waiters.append(time_pairs.pop(0).generator)
                else:
                    break
            schedule_next(time_waiters)

        except _FinishSimulation as exc:
            _finish(str(exc))
            return 0

    _finish('No more events.')
    return 0


def _find_vcd_info(hw_module):
    if hw_module.vcd_info:
        return hw_module.vcd_info
    else:
        for sub_module in hw_module.module_dict.values():
            return _find_vcd_info(sub_module)
    return None


def _collect_generators(hw_module, generators):
    for hw_block in hw_module.block_dict.values():
        generators.append(hw_block.generator)
    for sub_module in hw_module.module_dict.values():
        generators = _collect_generators(sub_module, generators)
    return generators


def now():
    """Return current simulation time."""
    return _now


class _FinishSimulation(Exception):
    pass


def finish(message):
    """Display the message and finish simulation."""
    raise _FinishSimulation(message)


def _finish(message):
    if _vcd:
        _vcd.close()
    print('Time {0}:'.format(_now), message)
