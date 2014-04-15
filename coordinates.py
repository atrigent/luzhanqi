from collections import namedtuple
from itertools import product
import math

from misc import match, sequence_getitem

def coordtuple(name, axes):
    """Create a namedtuple which verifies that it is a valid coordinate.

    Accepts a name and a list of axes (such as CenteredOriginAxis). When
    an instance is created, an exception is raised if the coordinate is
    not on these axes.

    Instances can also be used with the - operator (returns a new coordinate
    where all components are negated) and the abs() functions (does the same
    but all components are absolute valued).
    """

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

        def distance(self, other):
            return math.sqrt(sum((a - b)**2 for a, b in zip(self, other)))

    T.__name__ = name

    return T

class CenteredOriginAxis:
    """Represents an axis with 0 in the center.

    This class is essentially a sequence of a specified length where
    the values go from -x to x and where x is floor(length / 2). 0 may or
    may not be included depending on whether there are an even or odd
    number of elements in the sequence.
    """

    def __init__(self, symbol, num_vals):
        """Initialize an axis with a given symbol and number of elements.

        The symbol should be x, y, etc.
        """

        self.symbol = symbol
        self.num_vals = num_vals

    def __len__(self):
        return self.num_vals

    @sequence_getitem
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
        """Return the index of val in this axis."""

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
        """Return the values in the axis that match the given matchval.

        See match.
        """

        return (component for component in self
                          if match(component, matchval))

    def original_and_reflection(self, val):
        """Return the given value and its reflection over the origin.

        Also checks that the value is on the axis and only returns
        a single value if the given value is 0.
        """

        if val not in self:
            raise ValueError()

        if val == 0:
            return (val,)
        else:
            return val, -val

    def reflection(self, val):
        """Return the reflection of the given value over the origin.

        Also checks that the given value is on the axis.
        """

        if val not in self:
            raise ValueError()

        if val == 0:
            return (val,)
        else:
            return (-val,)

class CoordinateSystem:
    """A representation of a coordinate system consisting of one or more axes.

    This is essentially just a wrapper around a list of axes with
    some useful functions related to those axes.
    """

    def __init__(self, *axes):
        """Initialize the coordinate system with the given axes."""

        self.axes = axes

        self.Coord = coordtuple('Coord', axes)

        for axis in axes:
            setattr(self, axis.symbol, axis)

    def __contains__(self, coord):
        return all(component in axis
                   for component, axis in zip(coord, self.axes))

    def coords_matching(self, *spec):
        """Get Coords on this coordinate system that match the given matchvals.

        This function uses match to return Coord objects for all of the
        coordinates on this coordinate system where each matchval passed
        matches the cooresponding component in the coordinate.
        """

        matches = (axis.match(axis_range)
                   for axis, axis_range in zip(self.axes, spec))

        return (self.Coord(*match) for match in product(*matches))

    def map_coord_components(self, coords, **maps):
        """Flexibly maps a set of coordinates to another set.

        This function accepts a set of coordinates and a set of component
        maps to perform on those coordinates. The maps are passed in as
        keyword arguments, where the keyword is the name of an axis and
        the value is a function that takes an axis and an axis value and
        returns a tuple of new values.

        Example (assuming all of these Coords are in the CoordinateSystem):

        >>> either_side = lambda axis, i: (i - 1, i + 1)
        >>> list(system.map_coord_components([system.Coord(0, 0)],
                                             x=either_side,
                                             y=either_side))
        [Coord(-1, -1), Coord(1, 1), Coord(-1, 1), Coord(1, -1)]
        """

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
        """Like map_coord_components, but map the components separately.

        Example (assuming all of these Coords are in the CoordinateSystem):

        >>> either_side = lambda axis, i: (i - 1, i + 1)
        >>> list(system.map_coord_components_separately([system.Coord(0, 0)],
                                                        x=either_side,
                                                        y=either_side))
        [Coord(0, -1), Coord(0, 1), Coord(-1, 0), Coord(1, 0)]
        """

        for symbol in maps:
            for coord in self.map_coord_components(coords,
                                                   **{symbol: maps[symbol]}):
                yield coord

class CoordinateSystemState:
    """For storing an object at each point described by a CoordinateSystem.

    The objects at each position can be accessed and set using the subscript
    operator.
    """

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
