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
    xstr = chr(ord('A') + system.x.index(self.x))
    ystr = str(len(system.y) - system.y.index(self.y))

    return xstr + ystr

# Monkey-patch automatic stringification into Coord
system.Coord.__str__ = stringify_coord

coord_regex = re.compile('^([A-E])(\d{1,2})$')

def parse_coord(coord):
    coord_match = coord_regex.match(coord)

    if coord_match is None:
        return None

    x, y = coord_match.group(1, 2)

    x = system.x[ord(x) - ord('A')]
    y = system.y[-int(y)]

    return system.Coord(x, y)

# Stuff for dealing with the message syntax for movements
movement_re = re.compile('^\s*(\w+)\s+(\w+)\s+(\d)\s+'
                         '(move|win|loss|tie|flag)\s*$')

def parse_movement(board, move):
    move_match = movement_re.match(move)

    if move_match is None:
        return None

    start, end, player, outcome = move_match.group(1, 2, 3, 4)
    start = parse_coord(start)
    end = parse_coord(end)
    player = int(player)

    if outcome == 'move':
        outcome = None
    elif outcome == 'flag':
        outcome = 'win'

    piece = board.get(start)
    if piece is None:
        return None

    return Movement(board, board.get(start), end, outcome)

invalid_move = re.compile('^Invalid\s+Board\s+Move\s+(.*)$')
flag_pos = re.compile('^F\s+(\w+)$')
victory = re.compile('(1|2|No)\s+Victory')

def write(message):
    message = str(message)
    print(message)
    sys.stdout.flush()

    logging.info('sent: "' + message + '"')

def receive_message(game):
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

    if False:
        logging.basicConfig(filename='log.{0}.txt'.format(player),
                            level=logging.DEBUG)
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
    if False:
        cProfile.run('main()', 'profile.{0}'.format(os.getpid()))
    else:
        main()
