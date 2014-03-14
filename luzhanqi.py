from collections import namedtuple, defaultdict
from itertools import groupby
import random

from misc import namedtuple_with_defaults
from coordinates import (CenteredOriginAxis, CoordinateSystem,
                         CoordinateSystemState)

Space = namedtuple_with_defaults('Space', 'name',
                                 initial_placement=True, safe=False,
                                 diagonals=False, quagmire=False)

Piece = namedtuple_with_defaults('Piece', 'name', 'symbol', 'initial_count',
                                 order=None, sessile=False, bomb=False,
                                 defeats_sessile_bombs=False,
                                 railroad_corners=False,
                                 reveal_flag_on_defeat=False,
                                 initial_placement=None,
                                 lose_on_defeat=False)

PieceStrategy = namedtuple_with_defaults('PieceStrategy', 'placement_step')

AttackInfo = namedtuple('AttackInfo', 'piece outcome')
Movement = namedtuple_with_defaults('Movement', 'start', 'end',
                                    'piece', 'turn', attack=None)

class BoardPiece:
    def __init__(self, initial, spec=None):
        self.events = []
        self.movements = []
        self.attacks = []
        self.spec = spec

        self.add_event(Movement(None, initial, self, 0))

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

class LuzhanqiBoard:
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

    def _position_match(self, position, matchval):
        if isinstance(matchval, Space):
            return self._position_spec(position) == matchval
        else:
            return position.match(matchval)

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
                    choices = (position
                               for position in positions
                               if self._position_match(position, placement))

                choices = list(choices)
                if len(choices) < piece.initial_count:
                    raise RuntimeError("Not enough choices to place piece!")

                random.shuffle(choices)

                chosen = choices[:piece.initial_count]
                for choice in chosen:
                    new_piece = BoardPiece(choice, piece)
                    self.friendly_pieces.add(new_piece)
                    self.board[choice] = new_piece

                positions -= set(chosen)

    def setup(self):
        self._do_initial_placement()

        for position in self._initial_enemy_positions():
            new_piece = BoardPiece(position)
            self.enemy_pieces.add(new_piece)
            self.board[position] = new_piece

    def get_living_pieces(self):
        return self.friendly_pieces

    def get(self, position):
        return self.board[position]
