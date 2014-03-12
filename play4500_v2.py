#!/usr/bin/python3
from collections import namedtuple, defaultdict
from itertools import product, groupby
import random

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

def coordtuple(name, axes, strfunc=None):
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

        def __str__(self):
            if strfunc is not None:
                return strfunc(*zip(axes, self))
            else:
                return super().__str__()

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
    def __init__(self, *axes, strfunc=None):
        self.axes = axes

        self.Coord = coordtuple('Coord', axes, strfunc)

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
            raise KeyError()

        self.state[position] = value

class LuzhanqiBoard:
    Space = namedtuple_with_defaults('Space', 'name',
                                     initial_placement=True, safe=False,
                                     diagonals=False, quagmire=False)
    spaces = {
        'station': Space('Soldier Station'),
        'camp': Space('Camp', safe=True, diagonals=True,
                              initial_placement=False),
        'headquarters': Space('Headquarters', quagmire=True)
    }

    def stringify_coord(x, y):
        xaxis, xval = x
        xstr = chr(ord('A') + xaxis.index(xval))

        yaxis, yval = y
        ystr = str(yaxis.index(yval) + 1)

        return xstr + ystr

    system = CoordinateSystem(CenteredOriginAxis('x', 5),
                              CenteredOriginAxis('y', 12),
                              strfunc=stringify_coord)
    Coord = system.Coord

    board_spec = defaultdict(lambda: LuzhanqiBoard.spaces['station'], {
        Coord(1, 2): spaces['camp'],
        Coord(0, 3): spaces['camp'],
        Coord(1, 4): spaces['camp'],
        Coord(1, 6): spaces['headquarters']
    })

    Piece = namedtuple_with_defaults('Piece', 'name', 'symbol', 'initial_count',
                                     order=None, sessile=False, bomb=False,
                                     defeats_sessile_bombs=False,
                                     railroad_corners=False,
                                     reveal_flag_on_defeat=False,
                                     initial_placement=None,
                                     lose_on_defeat=False)
    # initial_counts should add up to 25
    pieces = {
        '9': Piece('Field Marshal', '9', 1, order=9,
                   reveal_flag_on_defeat=True),
        '8': Piece('General', '8', 1, order=8),
        '7': Piece('Lieutenant General', '7', 2, order=7),
        '6': Piece('Brigadier General', '6', 2, order=6),
        '5': Piece('Colonel', '5', 2, order=5),
        '4': Piece('Major', '4', 2, order=4),
        '3': Piece('Captain', '3', 3, order=3),
        '2': Piece('Commander', '2', 3, order=2),
        '1': Piece('Engineer', '1', 3, order=1,
                   defeats_sessile_bombs=True,
                   railroad_corners=True),
        'B': Piece('Bomb', 'B', 2, bomb=True,
                   initial_placement=('*', lambda y: y > 1)),
        'L': Piece('Landmine', 'L', 3, sessile=True, bomb=True,
                   initial_placement=('*', lambda y: y > 4)),
        'F': Piece('Flag', 'F', 1, sessile=True, lose_on_defeat=True,
                   initial_placement=spaces['headquarters'])
    }

    AttackInfo = namedtuple('AttackInfo', 'piece outcome')
    Movement = namedtuple_with_defaults('Movement', 'start', 'end',
                                        'piece', 'turn', attack=None)

    class BoardPiece:
        def __init__(self, initial, spec=None):
            self.events = []
            self.movements = []
            self.attacks = []
            self.spec = spec

            self.add_event(LuzhanqiBoard.Movement(None, initial, self, 0))

        def __hash__(self):
            return hash(self.initial)

        def __eq__(self, other):
            return self.initial == other.initial

        def _fatal_event(self, event):
            if event.attack is None:
                return None

            if event.piece is self:
                safe_outcome = 'win'
            elif event.attack.piece is self:
                safe_outcome = 'loss'
            else:
                return None

            return event.attack.outcome != safe_outcome

        def add_event(self, event):
            if self.dead:
                raise RuntimeError('This piece is dead - nothing further '
                                   'can happen to it')

            if event.piece is self:
                self.movements.append(event)
            elif event.attack is not None and event.attack.piece is self:
                self.attacks.append(event)
            else:
                raise RuntimeError('This event is not relevant to this piece')

            self.events.append(event)

        @property
        def initial(self):
            return self.movements[0].end

        @property
        def friendly(self):
            return self.initial.y > 0

        @property
        def dead(self):
            if len(self.events) == 0:
                return False

            return bool(self._fatal_event(self.events[-1]))

        @property
        def position(self):
            if self.dead:
                return None

            return self.movements[-1].end

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
        self.board = CoordinateSystemState(self.system)

        self.friendly_pieces = set()
        self.friendly_pieces_dead = set()

        self.enemy_pieces = set()
        self.enemy_pieces_dead = set()

    def _initial_piece_counts(self):
        return {key: val.initial_count for key, val in self.pieces.items()}

    def _position_spec(self, position):
        return self.board_spec[abs(position)]

    def _space_positions(self, space, positions):
        return filter(lambda position: self._position_spec(position) == space,
                      positions)

    def _initial_positions(self):
        nonneg = lambda i: i >= 0

        absolutes = (position
                     for position in self.system.coords_matching(nonneg, nonneg)
                     if self._position_spec(position).initial_placement)

        x_map = lambda axis, x: axis.original_and_reflection(x)
        return self.system.map_coord_components(absolutes, x=x_map)

    def _initial_enemy_positions(self):
        initials = self._initial_positions()

        y_reflect = lambda axis, y: axis.reflection(y)
        return self.system.map_coord_components(initials, y=y_reflect)

    def _placement_steps(self):
        keyfunc = lambda pair: pair[1].placement_step

        for step, pairs in groupby(sorted(self.piece_strategies.items(),
                                          key=keyfunc),
                                   keyfunc):
            yield (piece for piece, strategy in pairs)

    def _do_initial_placement(self):
        positions = set(self._initial_positions())

        for step in self._placement_steps():
            for piece in step:
                placement = piece.initial_placement
                choices = positions

                if placement is not None:
                    if isinstance(placement, self.Space):
                        choices = self._space_positions(placement, positions)
                    else:
                        choices = (position for position in positions
                                            if position.match(placement))

                choices = list(choices)
                if len(choices) < piece.initial_count:
                    raise RuntimeError("Not enough choices to place piece!")

                random.shuffle(choices)

                chosen = choices[:piece.initial_count]
                for choice in chosen:
                    new_piece = self.BoardPiece(choice, piece)
                    self.friendly_pieces.add(new_piece)
                    self.board[choice] = new_piece

                positions -= set(chosen)

    def setup(self):
        self._do_initial_placement()

        for position in self._initial_enemy_positions():
            new_piece = self.BoardPiece(position)
            self.enemy_pieces.add(new_piece)
            self.board[position] = new_piece

    def get_living_pieces(self):
        return self.friendly_pieces

if __name__ == '__main__':
    game = LuzhanqiBoard()
    game.setup()

    print('(' +
          ' '.join('({0} {1})'.format(piece.initial, piece.spec.symbol)
                   for piece in game.get_living_pieces()) +
          ')')
