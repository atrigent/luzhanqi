from collections import namedtuple, defaultdict
from itertools import product
from functools import reduce
import logging

from misc import (namedtuple_with_defaults, match_sequence,
                  find_connected_component)
from coordinates import (CenteredOriginAxis, CoordinateSystem,
                         CoordinateSystemState)

# Represents spaces on the board.
Space = namedtuple_with_defaults('Space', 'name',
                                 initial_placement=True, safe=False,
                                 diagonals=False, quagmire=False)

# Represents the types of pieces that can go on the board.
Piece = namedtuple_with_defaults('Piece', 'name', 'symbol', 'initial_count',
                                 order=None, sessile=False, bomb=False,
                                 defeats_sessile_bombs=False,
                                 railroad_corners=False,
                                 reveal_flag_on_defeat=False,
                                 initial_placement=None,
                                 lose_on_defeat=False)

# Represents an attack - the attacked piece, whether we know the winner,
# and the winning piece (which will only be meaningful if we know it)
AttackInfo = namedtuple('AttackInfo', 'piece theoretical winner')

class Movement:
    """Represents a movement of a piece to a position on a board.

    The following attributes are available (but shouldn't be manually
    changed):

    - board: the board that this movement is on
    - piece: the piece being moved
    - start: where the move is being made from
        (can be None for an initial placement)
    - end: the destination position of the move
    - turn: the turn on which the move was made
        (0 means initial placement)
    - attack: an AttackInfo if this is an attack move
    - move_type: the strings INITIAL, ROAD, RAILROAD,
        or RAILROAD_CORNER, depending on how the move was made
    """

    def __init__(self, board, piece, end, outcome=None):
        """Initialize the movement.

        board is the LuzhanqiBoard on which the movement is to be
        made, piece is the piece being moved, end is where the piece
        is being moved to, and outcome is an attack outcome or None
        if this is not an attack or if the outcome is unknown.
        """

        self.board = board
        self.piece = piece
        self.start = piece.position
        self.end = end
        self.turn = board.turn

        if (self.start is None) != (self.turn == 0):
            raise ValueError()

        self.move_type = self.board.verify_move(self.piece, self.end)
        if self.move_type is None:
            raise ValueError()

        end_piece = board.get(end)
        if end_piece is not None:
            theoretical = False
            if outcome == 'win':
                winner = piece
            elif outcome == 'loss':
                winner = end_piece
            elif outcome == 'tie':
                winner = None
            elif outcome == None:
                theoretical = True
                winner = None
            else:
                raise ValueError('Invalid outcome value!')

            self.attack = AttackInfo(end_piece, theoretical, winner)
        else:
            if outcome is not None:
                raise ValueError('This is not an attack!')

            self.attack = None

class BoardPiece:
    """Represents a piece on the board with a type and an event history.

    This class encapsulates a piece type and a list of events that have
    happened to the piece during the game. The piece type may be None
    if we don't actually know what type of piece it is.
    """

    def __init__(self, spec=None):
        """Initialize a BoardPiece with an optional piece type."""

        self.events = []
        self.movements = []
        self.attacks = []
        self.spec = spec
        self.maybies = None

        if not spec:
            self.maybies = LuzhanqiBoard.pieces.copy()

    def __str__(self):
        if self.friendly:
            return '+' + self.spec.symbol
        else:
            return '-' + ','.join(sorted(maybe.symbol
                                         for maybe in self.maybies))

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

        return event.attack.winner is not self

    def _event_possible_for_type(self, event, spec):
        if event.start is None:
            initial = spec.initial_placement

            if initial and not LuzhanqiBoard.position_match(abs(event.end),
                                                            initial):
                return False
        elif spec.sessile and event.piece is self:
            return False
        elif (not spec.railroad_corners and event.piece is self and
              event.move_type == 'RAILROAD_CORNER'):
            return False
        elif event.attack is not None:
            attacker_type, attacked_type = None, None
            if event.piece is self:
                attacker_type = spec
            else:
                attacked_type = spec

            simulated = LuzhanqiBoard.simulate_attack(event.piece,
                                                      attacker_type,
                                                      event.attack.piece,
                                                      attacked_type)

            if simulated is not event.attack.winner:
                return False

        return True

    def add_event(self, event):
        """Add the given event to this piece's event history."""

        if self.dead:
            raise RuntimeError('This piece is dead - nothing further '
                               'can happen to it')

        if event.piece is self:
            self.movements.append(event)
        elif event.attack is not None and event.attack.piece is self:
            if event.attack.theoretical:
                raise RuntimeError('A theoretical attack cannot be an event!')

            self.attacks.append(event)
        else:
            raise RuntimeError('This event is not relevant to this piece')

        self.events.append(event)

        if self.maybies is not None:
            to_remove = set()
            for piece in self.maybies:
                if not self._event_possible_for_type(event, piece):
                    to_remove.add(piece)

            self.maybies -= to_remove

    @property
    def initial(self):
        """Get this piece's initial position.

        Returns None if the piece has not yet been placed.
        """

        if len(self.movements) == 0:
            return None

        return self.movements[0].end

    @property
    def friendly(self):
        """Determine whether this is a friendly piece or not."""

        return self.spec is not None

    @property
    def dead(self):
        """Determine whether this piece is dead or not."""

        if len(self.events) == 0:
            return False

        return bool(self._fatal_event(self.events[-1]))

    @property
    def position(self):
        """Get this piece's current position.

        Returns None if the piece is dead or has not yet been placed.
        """

        if self.dead or not self.initial:
            return None

        return self.movements[-1].end

    @property
    def died_at(self):
        """Return the position where the piece died, if it is dead.

        Returns None if the piece is not dead.
        """

        if not self.dead:
            return None

        last_move = self.movements[-1]
        if self._fatal_event(last_move):
            return last_move.start
        else:
            return last_move.end

class LuzhanqiBoard:
    """A complete description of the Luzhanqi board and game.

    This class contains a bunch of information about the game (as class
    attributes) and instances of this class are capable of keeping
    track of the game board and implementing the rules of the game.
    """

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

    railroads = {
        # the railroad from (0, 5) to (2, 5)
        ((0, 1, 2), 5),
        # the railroad from (0, 1) to (2, 1)
        ((0, 1, 2), 1),
        # the railroad from (2, 0) to (2, 5)
        (2, (0, 1, 2, 3, 4, 5)),
        # the railroad from (0, 0) to (0, 1)
        (0, (0, 1))
    }

    @classmethod
    def simulate_attack(cls, attacker, attacker_type, attacked, attacked_type):
        def get_type(piece, spec):
            if spec:
                if piece.spec:
                    raise ValueError('This piece already has a spec!')

                return spec
            else:
                return piece.spec

        attacker_type = get_type(attacker, attacker_type)
        attacked_type = get_type(attacked, attacked_type)

        if attacker_type.sessile:
            raise RuntimeError('Sessile pieces cannot attack!')

        if attacker_type.order and attacked_type.order:
            if attacker_type.order > attacked_type.order:
                return attacker
            elif attacked_type.order > attacker_type.order:
                return attacked

            return None

        if attacker_type.bomb:
            return None
        elif attacked_type.bomb:
            if attacked_type.sessile and attacker_type.defeats_sessile_bombs:
                return attacker

            return None

        # special case - anything wins against the flag
        if attacked_type == cls.FLAG:
            return attacker

        raise RuntimeError('Cannot determine winner???')

    @classmethod
    def position_spec(cls, position):
        """Get the Space object that corresponds to the given position."""

        return cls.board_spec[abs(position)]

    @classmethod
    def position_match(cls, position, matchval):
        """Check whether a position matches a given matchval.

        This supports both match_sequence based matching and matching based
        on the Space object at the given position.
        """

        if isinstance(matchval, Space):
            return cls.position_spec(position) == matchval
        else:
            return match_sequence(position, matchval)

    @classmethod
    def initial_positions(cls):
        """Return the initial placement positions for a player."""

        nonneg = lambda i: i >= 0

        absolutes = (position
                     for position in cls.system.coords_matching(nonneg, nonneg)
                     if cls.position_spec(position).initial_placement)

        x_map = lambda axis, x: axis.original_and_reflection(x)
        return cls.system.map_coord_components(absolutes, x=x_map)

    @classmethod
    def initial_enemy_positions(cls):
        """Return the initial placement positions for a player's opponent."""

        initials = cls.initial_positions()

        y_reflect = lambda axis, y: axis.reflection(y)
        return cls.system.map_coord_components(initials, y=y_reflect)

    @classmethod
    def can_move(cls, piece):
        """Determine whether the given piece can move.

        This is based both on the piece's type and on the space where it is
        currently located.
        """

        # can't move a sessile piece
        if piece.spec is not None and piece.spec.sessile:
            return False

        # can't move off a quagmire space
        if cls.position_spec(piece.position).quagmire:
            return False

        return True

    @classmethod
    def nonabsolute_railroad_lines(cls):
        """Return matchvals for the straight railroad lines on the board.

        The naming of this function is based on the fact that it takes the
        "absolute" railroad information in LuzhanqiBoard.railroads and
        "de-absolutizes" it to describe the actual railroad lines on the
        complete board.
        """

        def nonabsolute_matchvals(matchval):
            for component in matchval:
                if not isinstance(component, tuple):
                    component = (component,)

                reflection = tuple(-val for val in component if val != 0)

                if 0 in component:
                    yield (component + reflection,)
                else:
                    yield (component, reflection)

        for line in cls.railroads:
            for nonabsolute in product(*nonabsolute_matchvals(line)):
                yield nonabsolute

    @classmethod
    def log_board_with_markers(cls, *marks_dicts, level=logging.DEBUG):
        """Log the board with the given marks and log level or DEBUG.

        The arguments to this function should be dicts which map between
        positions on the board and a string to put at that position. If
        multiple dicts are passed, they are merged into one with values
        with the same keys joined with commas. The level argument is
        keyword-only.
        """

        all_marks = {}
        for marks_dict in marks_dicts:
            for position, mark in marks_dict.items():
                if position in all_marks:
                    all_marks[position] += ';' + mark
                else:
                    all_marks[position] = mark

        col_widths = [reduce(max,
                             (len(mark) for position, mark in all_marks.items()
                                        if position.x == col),
                             len(str(col)))
                      for col in cls.system.x]
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
                            for col, width in zip(cls.system.x, col_widths))

            line += sep.join(displays)

            line += edge

            logging.log(level, line)

        def pad_vertical():
            for _ in range(vertical_pad_size):
                grid_line()

        def sep_line():
            grid_line(edge='+', sep='+', dashes=True)

        grid_line(edge=' ', sep=' ', marks={x: x for x in cls.system.x})

        for row in cls.system.y:
            sep_line()
            pad_vertical()

            pieces = {x: mark for (x, y), mark in all_marks.items()
                              if y == row}

            grid_line(row=row, marks=pieces)

            pad_vertical()

        sep_line()

    def __init__(self):
        self.board = CoordinateSystemState(self.system)

        self.friendly_pieces = set()
        self.friendly_pieces_dead = set()

        self.enemy_pieces = set()
        self.enemy_pieces_dead = set()

        self.turn = 0

    def _verify_attack(self, piece, end):
        if self.board[end] is not None:
            # no friendly fire and no attacking a safe space
            return (piece.friendly != self.board[end].friendly and
                    not self.position_spec(end).safe)

        return True

    @classmethod
    def adjacent_railroad_moves(cls, spec, orig_position, position, corner):
        def component_values(line):
            for position_component, line_component in zip(position, line):
                values = (position_component - 1,
                          position_component,
                          position_component + 1)

                yield tuple(val for val in values
                                if val in line_component)

        for line in cls.nonabsolute_railroad_lines():
            if (match_sequence(position, line) and
                (not spec or
                 spec.railroad_corners or
                 match_sequence(orig_position, line))):
                new_corner = corner
                if new_corner is False:
                    new_corner = not match_sequence(orig_position, line)

                for components in product(*component_values(line)):
                    if components != position:
                        yield components, new_corner

    def _railroad_moves(self, piece):
        def adjacent(position, corner):
            if (position in self.system and
                self.board[position] is not None and
                self.board[position] != piece):
                return

            for adj, adj_corner in self.adjacent_railroad_moves(piece.spec,
                                                                piece.position,
                                                                position,
                                                                corner):
                yield adj, adj_corner

        moves = find_connected_component(piece.position, False, adjacent)

        def to_result(moves):
            for move, corner in moves.items():
                if move != piece.position:
                    try:
                        yield self.Coord(*move), corner
                    except ValueError:
                        pass

        return dict(to_result(moves))

    @classmethod
    def _road_moves(cls, position):
        either_side = lambda axis, i: (i - 1, i + 1)
        for end in cls.system.map_coord_components_separately([position],
                                                              x=either_side,
                                                              y=either_side):
            yield end

        all_diagonals = cls.position_spec(position).diagonals
        for end in cls.system.map_coord_components([position],
                                                   x=either_side,
                                                   y=either_side):
            if all_diagonals or cls.position_spec(end).diagonals:
                yield end

    def _valid_moves_for_piece(self, piece):
        position = piece.position

        if not self.can_move(piece):
            return set()

        valid_moves = set(self._road_moves(position))

        valid_moves |= set(self._railroad_moves(piece))

        valid_moves = {move for move in valid_moves
                            if self._verify_attack(piece, move)}

        return valid_moves

    def verify_move(self, piece, end):
        """Verify that the given piece can move to the given end position.

        Returns the strings INITIAL, ROAD, or RAILROAD if the move is a
        valid move. This string indicates how the move was made. Returns
        None if the move is invalid.
        """

        start = piece.position

        if start is None:
            if self.board[end] is not None:
                return None

            if not self.position_spec(end).initial_placement:
                return None

            if piece.spec and piece.spec.initial_placement:
                if self.position_match(end, piece.spec.initial_placement):
                    return 'INITIAL'
                else:
                    return None

            return 'INITIAL'

        if (start == end or
            not self.can_move(piece) or
            not self._verify_attack(piece, end)):
            return None

        if end in self._road_moves(start):
            return 'ROAD'

        railroad_moves = self._railroad_moves(piece)
        if end in railroad_moves:
            if railroad_moves[end]: # if it is a corner move
                return 'RAILROAD_CORNER'
            else:
                return 'RAILROAD'

        return None

    def _placement_order(self, order):
        for piece in order:
            yield piece

        for piece in self.pieces:
            if piece not in order:
                yield piece

    def _do_initial_placement(self, placement_order, get_placements):
        positions = set(self.initial_positions())

        for piece in self._placement_order(placement_order):
            placement = piece.initial_placement
            choices = positions

            if placement is not None:
                choices = (position
                           for position in positions
                           if self.position_match(position, placement))

            choices = list(choices)
            if len(choices) < piece.initial_count:
                raise RuntimeError("Not enough choices to place piece!")

            chosen = set(get_placements(piece, choices))
            for choice in chosen:
                new_piece = BoardPiece(piece)
                new_piece.add_event(Movement(self, new_piece, choice))
                self.friendly_pieces.add(new_piece)
                self.board[choice] = new_piece

            positions -= chosen

    def setup(self, placement_order, get_placements):
        """Set up the board, placing our own pieces in the specified way.

        placement_order should be a list of Piece objects. This method
        will guarantee that it will start placing types of pieces in that
        order - after the pieces in that list have been placed, no
        guarantees are made.

        get_placements should be a function which takes a piece and a list
        of potential placement positions and returns an iterable of chosen
        placement positions. It should return piece.initial_count chosen
        positions.
        """

        if self.turn != 0:
            raise RuntimeError('Cannot setup while a game is in progress!')

        self._do_initial_placement(placement_order, get_placements)

        for position in self.initial_enemy_positions():
            new_piece = BoardPiece()
            new_piece.add_event(Movement(self, new_piece, position))
            self.enemy_pieces.add(new_piece)
            self.board[position] = new_piece

        self.turn = 1

    def valid_moves(self):
        """Returns an iterable of valid moves as Movement objects."""

        for piece in self.friendly_pieces:
            for move in self._valid_moves_for_piece(piece):
               yield Movement(self, piece, move)

    def get_living_pieces(self):
        """Returns the set of our pieces that are still alive."""

        return self.friendly_pieces

    def get(self, position):
        """Get a piece on the board at the given position."""

        return self.board[position]

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

    def add_move(self, movement):
        """Add a move (a Movement object) to the board."""

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
        return {piece.position: str(piece)
                for piece in self.friendly_pieces | self.enemy_pieces}

    def log_board_layout(self, level=logging.DEBUG):
        """Log the board layout with the given log level or DEBUG."""

        self.log_board_with_markers(self._layout_markers(), level=level)

    def log_defeated_pieces(self):
        for piece in self.enemy_pieces_dead:
            logging.debug('{} ({}): {}'.format(piece.initial, piece.died_at,
                                               piece))
