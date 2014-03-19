from collections import namedtuple
from itertools import product

from misc import match, SequenceMixin

def coordtuple(name, axes):
    fields = [axis.symbol for axis in axes]

    class T(namedtuple(name, fields)):
        def __new__(cls, *args):
            for axis, component in zip(axes, args):
                if component not in axis:
                    raise ValueError()

            return super(T, cls).__new__(cls, *args)

        def _map_vals(self, func):
            return T(*map(func, self))

        def __abs__(self):
            return self._map_vals(lambda val: abs(val))

        def __neg__(self):
            return self._map_vals(lambda val: -val)

    T.__name__ = name

    return T

class CenteredOriginAxisBase:
    def __init__(self, symbol, num_vals):
        self.symbol = symbol
        self.num_vals = num_vals

    def __len__(self):
        return self.num_vals

    def __getitem__(self, i):
        if not 0 <= i < self.num_vals:
            raise IndexError()

        abs_max = self.num_vals // 2

        if i < abs_max:
            return -abs_max + i

        i -= abs_max

        if 0 in self:
            if i == 0:
                return 0

            i -= 1

        if i < abs_max:
            return i + 1

    def __contains__(self, val):
        if val == 0:
            return self.num_vals % 2 != 0

        abs_max = self.num_vals // 2

        return val in range(-abs_max, abs_max + 1)

    def index(self, val):
        if val not in self:
            raise ValueError()

        abs_max = self.num_vals // 2

        if val == 0:
            return abs_max
        elif val < 0:
            return abs_max + val
        else:
            ret = abs_max + val
            if 0 not in self:
                ret -= 1

            return ret

    def match(self, matchval):
        return (component for component in self
                          if match(component, matchval))

    def original_and_reflection(self, val):
        if val not in self:
            raise ValueError()

        if val == 0:
            return (val,)
        else:
            return val, -val

    def reflection(self, val):
        if val not in self:
            raise ValueError()

        if val == 0:
            return (val,)
        else:
            return (-val,)

class CenteredOriginAxis(SequenceMixin, CenteredOriginAxisBase):
    pass

class CoordinateSystem:
    def __init__(self, *axes):
        self.axes = axes

        self.Coord = coordtuple('Coord', axes)

        for axis in axes:
            setattr(self, axis.symbol, axis)

    def coords_matching(self, *spec):
        matches = (axis.match(axis_range)
                   for axis, axis_range in zip(self.axes, spec))

        return (self.Coord(*match) for match in product(*matches))

    def map_coord_components(self, coords, **maps):
        def component_values(coord):
            for axis, component in zip(self.axes, coord):
                if axis.symbol in maps:
                    yield maps[axis.symbol](axis, component)
                else:
                    yield (component,)

        for coord in coords:
            for new_coord in product(*component_values(coord)):
                try:
                    yield self.Coord(*new_coord)
                except ValueError:
                    pass

    def map_coord_components_separately(self, coords, **maps):
        for symbol in maps:
            for coord in self.map_coord_components(coords,
                                                   **{symbol: maps[symbol]}):
                yield coord

class CoordinateSystemState:
    def __init__(self, system):
        self.system = system

        self.state = {
            system.Coord(*components): None
            for components in system.coords_matching('*', '*')
        }

    def __getitem__(self, position):
        return self.state[position]

    def __setitem__(self, position, value):
        if position not in self.state:
            raise KeyError(position)

        self.state[position] = value
