"""For VCD file creation."""
import time
from .common import _find_outer_name
from .common import _find_module_from_path

__version__ = '17.1'


class _VcdInfo:
    def __init__(self, filename):
        self.filename = filename
        self.hw_module = None
        self.hw_module_name = None

    def create_header(self):
        _set_up_vcd_id(self.hw_module)

        header = ''
        header += '$date\n'
        header += '    {0}\n'.format(time.asctime())
        header += '$end\n'
        header += '$version\n'
        header += '    {0} version {1}\n'.format(__name__, __version__)
        header += '$end\n'
        header += '$timescale\n'
        header += '    1ns\n'
        header += '$end\n'

        def add_definition(hw_module_name, hw_module, header):
            header += '$scope module {0} $end\n'.format(hw_module_name)
            for signal_name, signal in hw_module.signal_dict.items():
                if signal._vcd_id:
                    header += '$var reg {0} {1} {2} $end\n'.format(
                        signal._numbits, signal._vcd_id, signal_name)
            for sub_module_name, sub_module in hw_module.module_dict.items():
                header = add_definition(sub_module_name, sub_module, header)
            header += '$upscope $end\n'
            return header

        header += add_definition(self.hw_module_name, self.hw_module, '')

        header += '$enddefinitions $end\n'
        header += '$dumpvars\n'
        for signal in _collect_vcd_signals(self.hw_module, []):
            if (signal._numbits == 1):
                header += '{0}{1}\n'.format(
                    int(signal._value), signal._vcd_id)
            else:
                header += 'b{0:b} {1}\n'.format(
                    int(signal._value), signal._vcd_id)
        header += '$end\n'
        return header


def _set_up_vcd_id(hw_module):
    vcd_id_generator = _vcd_id_genfunc()

    def set_vcd_id(hw_module):
        if hw_module.vcd_flag:
            for signal in hw_module.signal_dict.values():
                if not signal._vcd_id:
                    signal._vcd_id = next(vcd_id_generator)
        for sub_module in hw_module.module_dict.values():
            set_vcd_id(sub_module)

    set_vcd_id(hw_module)


def _vcd_id_genfunc():
    chars = [chr(i) for i in range(33, 127)]
    chars = ''.join(chars)
    num_chars = len(chars)
    n = 0
    while True:
        q, r = divmod(n, num_chars)
        id = chars[r]
        while q > 0:
            q, r = divmod(q-1, num_chars)
            id += chars[r]
        yield id
        n += 1


def _collect_vcd_signals(hw_module, signals):
    if hw_module.vcd_flag:
        for signal in hw_module.signal_dict.values():
            if id(signal) not in [id(s) for s in signals]:  # '==' overloaded
                signals.append(signal)
    for sub_module in hw_module.module_dict.values():
        signals = _collect_vcd_signals(sub_module, signals)
    return signals


def vcd_dump(hw_module, filename):
    """
    Set to dump signals under specified hw_module and submodules.
    Create a vcd_info object, set the properties and return it.
    """
    _include_vcd_module(hw_module)
    vcd_info = _VcdInfo(filename)
    vcd_info.hw_module = hw_module
    vcd_info.hw_module_name = _find_outer_name(hw_module)
    return vcd_info


def _include_vcd_module(hw_module):
    hw_module.vcd_flag = True
    for sub_module in hw_module.module_dict.values():
        _include_vcd_module(sub_module)


def _exclude_vcd_module(hw_module):
    hw_module.vcd_flag = False
    for sub_module in hw_module.module_dict.values():
        _exclude_vcd_module(sub_module)


def include_vcd_path(hw_module_path):
    """
    Set to dump signals under hw_module and submodules specified
    by hierarchical path. Use slashes to separate names.
    """
    return _include_vcd_module(_find_module_from_path(hw_module_path))


def exclude_vcd_path(hw_module_path):
    """
    Set not to dump signals under hw_module and submodules specified
    by hierarchical path. Use slashes to separate names.
    """
    return _exclude_vcd_module(_find_module_from_path(hw_module_path))
