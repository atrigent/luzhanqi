from collections import namedtuple, defaultdict
from itertools import groupby
from functools import reduce
import logging
import random

from misc import namedtuple_with_defaults, match_sequence
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

class Movement:
    def __init__(self, board, piece, end, outcome=None):
        self.board = board
        self.piece = piece
        self.start = piece.position
        self.end = end
        self.turn = board.turn

        if (self.start is None) != (self.turn == 0):
            raise ValueError()

        if not self.board.verify_move(self.piece, self.end):
            raise ValueError()

        end_piece = board.get(end)
        if end_piece is not None:
            self.attack = AttackInfo(end_piece, outcome)
        else:
            if outcome is not None:
                raise ValueError('This is not an attack!')

            self.attack = None

class BoardPiece:
    def __init__(self, spec=None):
        self.events = []
        self.movements = []
        self.attacks = []
        self.spec = spec

    def __hash__(self):
        if self.initial is None:
            raise TypeError()

        return hash(self.initial)

    def __eq__(self, other):
        if self.initial is None:
            return False

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
        if len(self.movements) == 0:
            return None

        return self.movements[0].end

    @property
    def friendly(self):
        return self.spec is not None

    @property
    def dead(self):
        if len(self.events) == 0:
            return False

        return bool(self._fatal_event(self.events[-1]))

    @property
    def position(self):
        if self.dead or not self.initial:
            return None

        return self.movements[-1].end

    @property
    def died_at(self):
        if not self.dead:
            return None

        last_move = self.movements[-1]
        if self._fatal_event(last_move):
            return last_move.start
        else:
            return last_move.end

class LuzhanqiBoard:
    STATION = Space('Soldier Station')
    CAMP = Space('Camp', safe=True, diagonals=True,
                         initial_placement=False)
    HEADQUARTERS = Space('Headquarters', quagmire=True)

    system = CoordinateSystem(CenteredOriginAxis('x', 5),
                              CenteredOriginAxis('y', 12))
    Coord = system.Coord

    board_spec = defaultdict(lambda: LuzhanqiBoard.STATION, {
        Coord(1, 2): CAMP,
        Coord(0, 3): CAMP,
        Coord(1, 4): CAMP,
        Coord(1, 6): HEADQUARTERS
    })

    # initial_counts should add up to 25
    MARSHAL = Piece('Field Marshal', '9', 1, order=9,
                    reveal_flag_on_defeat=True)
    GENERAL = Piece('General', '8', 1, order=8)
    LIEUT_GENERAL = Piece('Lieutenant General', '7', 2, order=7)
    BRIG_GENERAL = Piece('Brigadier General', '6', 2, order=6)
    COLONEL = Piece('Colonel', '5', 2, order=5)
    MAJOR = Piece('Major', '4', 2, order=4)
    CAPTAIN = Piece('Captain', '3', 3, order=3)
    COMMANDER = Piece('Commander', '2', 3, order=2)
    ENGINEER = Piece('Engineer', '1', 3, order=1,
                     defeats_sessile_bombs=True,
                     railroad_corners=True)
    BOMB = Piece('Bomb', 'B', 2, bomb=True,
                 initial_placement=('*', lambda y: y > 1))
    LANDMINE = Piece('Landmine', 'L', 3, sessile=True, bomb=True,
                     initial_placement=('*', lambda y: y > 4))
    FLAG = Piece('Flag', 'F', 1, sessile=True, lose_on_defeat=True,
                 initial_placement=HEADQUARTERS)

    pieces = {
        MARSHAL, GENERAL, LIEUT_GENERAL, BRIG_GENERAL,
        COLONEL, MAJOR, CAPTAIN, COMMANDER, ENGINEER,
        BOMB, LANDMINE, FLAG
    }

    piece_strategies = {
        MARSHAL: PieceStrategy(3),
        GENERAL: PieceStrategy(3),
        LIEUT_GENERAL: PieceStrategy(3),
        BRIG_GENERAL: PieceStrategy(3),
        COLONEL: PieceStrategy(3),
        MAJOR: PieceStrategy(3),
        CAPTAIN: PieceStrategy(3),
        COMMANDER: PieceStrategy(3),
        ENGINEER: PieceStrategy(3),
        BOMB: PieceStrategy(2),
        LANDMINE: PieceStrategy(1),
        FLAG: PieceStrategy(0)
    }

    def __init__(self):
        self.board = CoordinateSystemState(self.system)

        self.friendly_pieces = set()
        self.friendly_pieces_dead = set()

        self.enemy_pieces = set()
        self.enemy_pieces_dead = set()

        self.turn = 0

    def _position_spec(self, position):
        return self.board_spec[abs(position)]

    def _position_match(self, position, matchval):
        if isinstance(matchval, Space):
            return self._position_spec(position) == matchval
        else:
            return match_sequence(position, matchval)

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

    def _verify_attack(self, piece, end):
        if self.board[end] is not None:
            # no friendly fire and no attacking a safe space
            return (piece.friendly != self.board[end].friendly and
                    not self._position_spec(end).safe)

        return True

    def _can_move(self, piece):
        # can't move a sessile piece
        if piece.spec is not None and piece.spec.sessile:
            return False

        # can't move off a quagmire space
        if self._position_spec(piece.position).quagmire:
            return False

        return True

    def _railroad_moves(self, piece):
        if match_sequence(abs(piece.position), ((0, 2), 1)):
            yield self.Coord(piece.position.x, -piece.position.y)

    def _valid_moves_for_piece(self, piece):
        position = piece.position

        if not self._can_move(piece):
            return set()

        either_side = lambda axis, i: (i - 1, i + 1)
        valid_moves = set(self.system.map_coord_components_separately(
                                          [position],
                                          x=either_side,
                                          y=either_side
                                      ))

        diagonals = set(self.system.map_coord_components([position],
                                                         x=either_side,
                                                         y=either_side))
        if self._position_spec(position).diagonals:
            valid_moves |= diagonals
        else:
            valid_moves |= {diagonal for diagonal in diagonals
                                     if self._position_spec(diagonal).diagonals}

        valid_moves |= set(self._railroad_moves(piece))

        valid_moves = {move for move in valid_moves
                            if self._verify_attack(piece, move)}

        return valid_moves

    def verify_move(self, piece, end):
        start = piece.position

        if start is None:
            if self.board[end] is not None:
                return False

            if not self._position_spec(end).initial_placement:
                return False

            if piece.spec and piece.spec.initial_placement:
                return self._position_match(end, piece.spec.initial_placement)

            return True

        if (start == end or
            not self._can_move(piece) or
            not self._verify_attack(piece, end)):
            return False

        # horizontal/vertical move
        if sum(abs(start - end) for start, end in zip(start, end)) == 1:
            return True

        # diagonal move
        if (all(abs(start - end) == 1 for start, end in zip(start, end)) and
            (self._position_spec(start).diagonals or
             self._position_spec(end).diagonals)):
            return True

        if end in self._railroad_moves(piece):
            return True

        return False

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
                    new_piece = BoardPiece(piece)
                    new_piece.add_event(Movement(self, new_piece, choice))
                    self.friendly_pieces.add(new_piece)
                    self.board[choice] = new_piece

                positions -= set(chosen)

    def _check_pulse(self, piece):
        if not piece.dead:
            return

        self.board[piece.died_at] = None

        if piece.friendly:
            living_set = self.friendly_pieces
            dead_set = self.friendly_pieces_dead
        else:
            living_set = self.enemy_pieces
            dead_set = self.enemy_pieces_dead

        living_set.remove(piece)
        dead_set.add(piece)

    def _move_on_board(self, movement):
        if self.board[movement.end] is not None:
            raise RuntimeError('Cannot move onto an occupied space')

        self.board[movement.start] = None
        self.board[movement.end] = movement.piece

    def setup(self):
        if self.turn != 0:
            raise RuntimeError('Cannot setup while a game is in progress!')

        self._do_initial_placement()

        for position in self._initial_enemy_positions():
            new_piece = BoardPiece()
            new_piece.add_event(Movement(self, new_piece, position))
            self.enemy_pieces.add(new_piece)
            self.board[position] = new_piece

        self.turn = 1

    def valid_moves(self):
        for piece in self.friendly_pieces:
            for move in self._valid_moves_for_piece(piece):
               yield Movement(self, piece, move)

    def get_living_pieces(self):
        return self.friendly_pieces

    def get(self, position):
        return self.board[position]

    def add_move(self, movement):
        moved = movement.piece
        attacked = movement.attack.piece if movement.attack else None

        moved.add_event(movement)

        if attacked is not None:
            attacked.add_event(movement)

            self._check_pulse(moved)
            self._check_pulse(attacked)

        if not moved.dead:
            self._move_on_board(movement)

        self.turn += 1

    def _layout_markers(self):
        def piece_display(piece):
            if piece is None:
                return '  '

            if piece.friendly:
                return '+' + piece.spec.symbol
            else:
                return '-?'

        return {piece.position: piece_display(piece)
                for piece in self.friendly_pieces | self.enemy_pieces}

    def log_board_layout(self, level=logging.DEBUG):
        self.log_board_with_markers(self._layout_markers(), level=level)

    def log_board_with_markers(self, *marks_dicts, level=logging.DEBUG):
        all_marks = {}
        for marks_dict in marks_dicts:
            for position, mark in marks_dict.items():
                if position in all_marks:
                    all_marks[position] += ',' + mark
                else:
                    all_marks[position] = mark

        col_widths = [reduce(max,
                             (len(mark) for position, mark in all_marks.items()
                                        if position.x == col),
                             len(str(col)))
                      for col in self.system.x]
        horizontal_pad_size = 2
        horizontal_pad = ' ' * horizontal_pad_size

        vertical_pad_size = 1

        def grid_line(edge='|', sep='|', row=None, dashes=False, marks={}):
            if row:
                line = str(row).rjust(2) + ' '
            else:
                line = '   '

            line += edge

            if dashes:
                displays = ('-' * (horizontal_pad_size * 2 + width)
                            for width in col_widths)
            else:
                displays = (horizontal_pad +
                            str(marks.get(col, '')).center(width) +
                            horizontal_pad
                            for col, width in zip(self.system.x, col_widths))

            line += sep.join(displays)

            line += edge

            logging.log(level, line)

        def pad_vertical():
            for _ in range(vertical_pad_size):
                grid_line()

        def sep_line():
            grid_line(edge='+', sep='+', dashes=True)

        grid_line(edge=' ', sep=' ', marks={x: x for x in self.system.x})

        for row in self.system.y:
            sep_line()
            pad_vertical()

            pieces = {x: mark for (x, y), mark in all_marks.items()
                              if y == row}

            grid_line(row=row, marks=pieces)

            pad_vertical()

        sep_line()
