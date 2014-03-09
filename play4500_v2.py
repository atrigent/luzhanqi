#!/usr/bin/python3
from collections import namedtuple, defaultdict
from itertools import product, groupby

def namedtuple_with_defaults(typename, *args, **kwargs):
    extra_args = {}
    for arg in 'verbose', 'rename':
        if arg in kwargs:
            extra_args[arg] = kwargs[arg]
            del kwargs[arg]

    kwargs = tuple(kwargs.items())
    field_names = list(args) + [key for key, val in kwargs]
    defaults = tuple(val for key, val in kwargs)

    T = namedtuple(typename, field_names, **extra_args)
    T.__new__.__defaults__ = defaults
    return T

def match(val, matchval):
    if matchval == '*':
        return True
    elif callable(matchval):
        return matchval(val)
    elif isinstance(matchval, list):
        return val in matchval
    else:
        raise ValueError()

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

        def match(self, spec):
            return all(match(component, matchval)
                       for component, matchval in zip(self, spec))

    T.__name__ = name

    return T

class SequenceMixin:
    def __getitem__(self, key):
        if isinstance(key, int):
            if -len(self) <= key <= -1:
                key = len(self) + key
            elif key < 0:
                raise IndexError()

            return super().__getitem__(key)
        elif isinstance(key, slice):
            return [self[i] for i in range(*key.indices(len(self)))]
        else:
            raise TypeError()

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

        if self.num_vals % 2 != 0:
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

    def match(self, matchval):
        return (component for component in self
                          if match(component, matchval))

class CenteredOriginAxis(SequenceMixin, CenteredOriginAxisBase):
    pass

class CoordinateSystem:
    def __init__(self, *axes):
        self.axes = axes

        self.Coord = coordtuple('Coord', axes)

        for axis in axes:
            setattr(self, axis.symbol, axis)

    def coords_matching(self, *spec):
        matches = (axis.match(axis_range) for axis, axis_range in zip(self.axes, spec))

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
                yield self.Coord(*new_coord)

class LuzhanqiBoard:
    Space = namedtuple_with_defaults('Space', 'name', initial_placement=True, safe=False, 
                                     diagonals=False, quagmire=False)
    spaces = {
        'station': Space('Soldier Station'),
        'camp': Space('Camp', safe=True, diagonals=True, initial_placement=False),
        'headquarters': Space('Headquarters', quagmire=True)
    }

    system = CoordinateSystem(CenteredOriginAxis('x', 5), CenteredOriginAxis('y', 12))
    Coord = system.Coord

    board_spec = defaultdict(lambda: LuzhanqiBoard.spaces['station'], {
        Coord(1, 2): spaces['camp'],
        Coord(0, 3): spaces['camp'],
        Coord(1, 4): spaces['camp'],
        Coord(1, 6): spaces['headquarters']
    })

    Piece = namedtuple_with_defaults('Piece', 'name', 'initial_count',
                                     order=None, sessile=False, bomb=False,
                                     defeats_sessile_bombs=False,
                                     railroad_corners=False,
                                     reveal_flag_on_defeat=False,
                                     initial_placement=None,
                                     lose_on_defeat=False)
    # initial_counts should add up to 25
    pieces = {
        '9': Piece('Field Marshal', 1, order=9,
                   reveal_flag_on_defeat=True),
        '8': Piece('General', 1, order=8),
        '7': Piece('Lieutenant General', 2, order=7),
        '6': Piece('Brigadier General', 2, order=6),
        '5': Piece('Colonel', 2, order=5),
        '4': Piece('Major', 2, order=4),
        '3': Piece('Captain', 3, order=3),
        '2': Piece('Commander', 3, order=2),
        '1': Piece('Engineer', 3, order=1,
                   defeats_sessile_bombs=True,
                   railroad_corners=True),
        'B': Piece('Bomb', 2, bomb=True,
                   initial_placement=('*', lambda y: y > 1)),
        'L': Piece('Landmine', 3, sessile=True, bomb=True,
                   initial_placement=('*', lambda y: y > 4)),
        'F': Piece('Flag', 1, sessile=True, lose_on_defeat=True,
                   initial_placement=spaces['headquarters'])
    }

    PieceStrategy = namedtuple_with_defaults('PieceStrategy', 'placement_step')
    piece_strategies = {
        pieces['9']: PieceStrategy(3),
        pieces['8']: PieceStrategy(3),
        pieces['7']: PieceStrategy(3),
        pieces['6']: PieceStrategy(3),
        pieces['5']: PieceStrategy(3),
        pieces['4']: PieceStrategy(3),
        pieces['3']: PieceStrategy(3),
        pieces['2']: PieceStrategy(3),
        pieces['1']: PieceStrategy(3),
        pieces['B']: PieceStrategy(2),
        pieces['L']: PieceStrategy(1),
        pieces['F']: PieceStrategy(0)
    }

    def __init__(self):
        self.board_state = {
            Coord(*components): None
            for components in self.system.coords_matching('*', '*')
        }

    def _initial_piece_counts():
        return {key: val.initial_count for key, val in pieces.items()}

    def _position_spec(self, position):
        return self.board_spec[abs(position)]

    def _space_positions(self, space, positions):
        return filter(lambda position: self._position_spec(position) == space, positions)

    def _placement_steps(self):
        keyfunc = lambda pair: pair[1].placement_step

        for step, pairs in groupby(sorted(self.piece_strategies.items(), key=keyfunc), keyfunc):
            yield (piece for piece, strategy in pairs)







