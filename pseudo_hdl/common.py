"""Commonly available functions."""
from inspect import currentframe


def _find_outer_name(obj):
    outer_frame = currentframe().f_back.f_back
    for outer_name, outer_obj in outer_frame.f_locals.items():
        if id(obj) == id(outer_obj):  # "==" may be overloaded
            return outer_name
    return None


def _find_module_from_path(hw_module_path):
    hier_list = hw_module_path.strip('/').split('/')
    frame = currentframe().f_back.f_back
    hw_module = frame.f_locals.get(hier_list[0], None)
    return _find_module_by_hier_list(hw_module, hier_list)


def _find_module_by_hier_list(hw_module, hier_list):
    hw_module_name = hier_list.pop(0)
    if not hw_module:
        raise ValueError('Can\'t find hw_module "{0}".'.format(
            hw_module_name))
    for sub_module_name in hier_list:
        sub_module = hw_module.module_dict.get(sub_module_name, None)
        if sub_module:
            hw_module = sub_module
        else:
            raise ValueError('Can\'t find hw_module "{0}".'.format(
                sub_module_name))
    return hw_module


def mirror_signal(signal_path):
    """Make a mirror signal of the signal specified by the path."""
    hier_list = signal_path.strip('/').split('/')
    signal_name = hier_list.pop()
    hw_module = _find_module_from_path('/'.join(hier_list))
    signal = hw_module.signal_dict.get(signal_name, None)
    if signal is None:
        raise ValueError('Can\'t find signal "{0}".'.format(signal_name))
    else:
        return signal