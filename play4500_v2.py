#!/usr/bin/python3
from collections import namedtuple, defaultdict
import itertools

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

class CenteredOriginAxis:
    def __init__(self, symbol, num_vals):
        self.symbol = symbol
        self.num_vals = num_vals

    def __len__(self):
        return self.num_vals

    def __getitem__int(self, i):
        abs_max = self.num_vals // 2

        if not -self.num_vals <= i < self.num_vals:
            raise IndexError()

        if i < 0:
            i = self.num_vals + i

        if i < abs_max:
            return -abs_max + i

        i -= abs_max

        if self.num_vals % 2 != 0:
            if i == 0:
                return 0

            i -= 1

        if i < abs_max:
            return i + 1

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.__getitem__int(key)
        elif isinstance(key, slice):
            return [self[i] for i in range(*key.indices(self.num_vals))]
        else:
            raise TypeError()

    def match(self, matchval):
        return (component for component in self
                          if match(component, matchval))

class LuzhanqiBoard:
    Space = namedtuple_with_defaults('Space', 'name', initial_placement=True, safe=False, 
                                     diagonals=False, quagmire=False)
    spaces = {
        'station': Space('Soldier Station'),
        'camp': Space('Camp', safe=True, diagonals=True, initial_placement=False),
        'headquarters': Space('Headquarters', quagmire=True)
    }

    x, y = CenteredOriginAxis('x', 5), CenteredOriginAxis('y', 12)
    axes = (x, y)
    Coord = coordtuple('Coord', axes)

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
            for components in self._positions_matching(('*', '*'))
        }

    def _initial_piece_counts():
        return {key: val.initial_count for key, val in pieces.items()}

    def _reflect_along_axes(reflection_axes, positions):
        def position_with_negatives(position):
            for axis, component in zip(axes, position):
                if axis.symbol in reflection_axes:
                    yield (component, -component)
                else:
                    yield (component,)

        for position in positions:
            for new_position in product(*position_with_negatives(position)):
                yield new_position

    def _space_positions(self, space):
        return _reflect_along_axes(('Y'), (key for key, val in board_spec
                                               if val == spec))

    def _positions_matching(self, spec):
        matches = (axis.match(axis_range) for axis, axis_range in zip(axes, spec))

        return itertools.product(*matches)

    def _placement_steps(self):
        keyfunc = lambda pair: pair[1].placement_step

        for step, pairs in groupby(sorted(self.piece_strategies.items(), key=keyfunc), keyfunc):
            yield (piece for piece, strategy in pairs)







