#! /usr/bin/python3

import cProfile
import os

import traceback
import argparse
import logging
import atexit
import random
import sys
import re

from luzhanqi import LuzhanqiBoard, Movement

# Time Regex: ^(\d+)(?:\.(\d+))?(s|ms)$
# Starts with one or more digits. May be followed by a decimal point ('.')
# and one or more digits. Must end with a unit ('s'/'ms').
def valid_time(time):
    """
    Parses the time/move command line argument to make sure it passes a
    correctly formatted time. Acceptable times match any of these formats:
        2s
        2.0s
        2000ms
        2000.0ms

    Passing an invalid time format will result in an ArgumentTypeError.
    Passing a correct format will return the time string.

    """
    p = re.compile('^(\d+)(?:\.(\d+))?(s|ms)$')
    if p.match(time):
        return time
    else:
        raise argparse.ArgumentTypeError('is not a correct format')


def init_argparser():
    """
    Initializes the ArgumentParser. Allows the two arguments:
        --go <n>
        --time/move <t>

    Parses the arguments to match all required software specifications,
    and prints error messages to standard out.

    """
    parser = argparse.ArgumentParser(
        usage='./%(prog)s --go <n> --time/move <t>',
        description='Luzhanqi.'
    )
    parser.add_argument(
        '--go',
        type=int,
        choices=[1, 2],
        required=True,
        help='Whether the player goes first or second',
        dest='player'
    )
    parser.add_argument(
        '--time/move',
        type=valid_time,
        required=True,
        help='Time alloted per turn',
        dest='time'
    )

    args = parser.parse_args()
    return args.player, args.time

# Stuff for dealing with the message syntax for coordinates
system = LuzhanqiBoard.system

def stringify_coord(self):
    """Stringify a Coord object as defined by the message syntax.

    The stringification will consist of a letter (A through E) followed
    by a number (1 through 12).

    Examples: A1, E12, B7, C3, etc
    """

    xstr = chr(ord('A') + system.x.index(self.x))
    ystr = str(len(system.y) - system.y.index(self.y))

    return xstr + ystr

# Monkey-patch automatic stringification into Coord
system.Coord.__str__ = stringify_coord

coord_regex = re.compile('^([A-E])(\d{1,2})$')

def parse_coord(coord):
    """Form a Coord object from a message syntax representation of a coordinate.

    See stringify_coord for a description of the syntax.
    """

    coord_match = coord_regex.match(coord)

    if coord_match is None:
        return None

    x, y = coord_match.group(1, 2)

    x = system.x[ord(x) - ord('A')]
    y = system.y[-int(y)]

    return system.Coord(x, y)

# Stuff for dealing with the message syntax for movements
movement_re = re.compile('^\s*(\w+)\s+(\w+)\s+(\d)\s+'
                         '(move|win|loss|tie)\s*$')

def parse_movement(board, move):
    """Form a Movement object from a message syntax representation of a move.

    This function accepts a LuzhanqiBoard object and a
    string containing information about a move. The string
    shall use the syntax that the referee uses when
    communicating moves to the players. This syntax consists
    of four elements, separated by whitespace: the first two
    elements are coordinates (see above), the third is a
    player number, and the fourth is a move outcome which
    shall be one of move, win, loss, or tie.

    For the purposes of this function, the player value is
    ignored. The corresponding Movement object is returned.
    """

    move_match = movement_re.match(move)

    if move_match is None:
        return None

    start, end, player, outcome = move_match.group(1, 2, 3, 4)
    start = parse_coord(start)
    end = parse_coord(end)
    player = int(player)

    if outcome == 'move':
        outcome = None

    piece = board.get(start)
    if piece is None:
        return None

    return Movement(board, piece, end, outcome)

invalid_move = re.compile('^Invalid\s+Board\s+Move\s+(.*)$')
flag_pos = re.compile('^F\s+(\w+)$')
victory = re.compile('(1|2|No)\s+Victory')

def write(message):
    """Send a message to the referee.

    This function also takes care of output flushing and logging.
    """

    message = str(message)
    print(message)
    sys.stdout.flush()

    logging.info('sent: "' + message + '"')

def receive_message(game):
    """Receive messages from the referee until a move message is received.

    See parse_movement for a description of the syntax used for moves.

    Other types of messages that this function knows about include:

    - Invalid Board Move <error string>
        For when the player makes an error.
    - F <coordinate>
        For notifying of the location of the opponent's flag. Sent
        when the opponent's field marshal is defeated.
    - 1, 2, or No Victory
        Sent when the game is over and a player has won or
        there was a tie.
    """

    while True:
        message = input()

        logging.info('received: "' + message + '"')

        if invalid_move.match(message):
            raise RuntimeError(message)

        if victory.match(message):
            sys.exit()

        if flag_pos.match(message):
            continue

        move = parse_movement(game, message)
        if move is not None:
            game.add_move(move)
            return

        logging.error('parsing failed for "' + message + '"')

def do_move(game):
    """Picks a move to make and sends it to the referee.

    Moves are currently chosen randomly.

    The format for moves is:

    (<start> <end>)

    Where start and end are coordinates (see the stringify_coord
    function).

    If there are no moves to make, the "forfeit" message is sent
    in place of a move message. This message causes this player's
    opponent to immediately win the game.

    This function also handles receiving the response from the
    referee that tells us the outcome of the move.
    """

    moves = set(game.valid_moves())
    if len(moves) == 0:
        write('forfeit')
        return

    move = random.sample(moves, 1)[0]
    write('({0} {1})'.format(move.start, move.end))

    receive_message(game)

def main():
    # If init_argparser() returns, the command line arguments were correct
    player, time = init_argparser()
    game = None

    log_level = os.environ.get('PLAY4500_LOGGING', None)
    if log_level is not None:
        logging.basicConfig(filename='log.{0}.txt'.format(player),
                            format='[%(asctime)s] %(levelname)s: %(message)s',
                            level=log_level.upper())
    else:
        logging.disable(logging.CRITICAL)

    def mark():
        logging.info('---')

    atexit.register(mark)

    def log_traceback(*info):
        logging.critical('Unhandled exception!', exc_info=info)

        if game:
            game.log_board_layout()

    sys.excepthook = log_traceback

    placement_order = [LuzhanqiBoard.FLAG,
                       LuzhanqiBoard.LANDMINE,
                       LuzhanqiBoard.BOMB]

    def get_placements(piece, choices):
        return random.sample(choices, piece.initial_count)

    game = LuzhanqiBoard()
    game.setup(placement_order, get_placements)

    write('(' +
          ' '.join('({0} {1})'.format(piece.initial, piece.spec.symbol)
                   for piece in game.get_living_pieces()) +
          ')')

    if player == 1:
        do_move(game)

    while True:
        receive_message(game)
        do_move(game)

if __name__ == '__main__':
    if os.environ.get('PLAY4500_PROFILING', None) == '1':
        cProfile.run('main()', 'profile.{0}'.format(os.getpid()))
    else:
        main()
