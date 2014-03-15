#! /usr/bin/python3

import argparse
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

if __name__ == '__main__':
    # If init_argparser() returns, the command line arguments were correct
    player, time = init_argparser()

    if False:
        logfile = open('log.txt', mode='a')
    else:
        logfile = None

    def log_write(message):
        if logfile:
            logfile.write(message + '\n')

    game = LuzhanqiBoard()
    game.setup()

    invalid_move = re.compile('^Invalid\s+Board\s+Move\s+(.*)$')
    flag_pos = re.compile('^F\s+(\w+)$')
    victory = re.compile('(1|2|No)\s+Victory')

    def write(message):
        message = str(message)
        print(message)

        log_write('sent: "' + message + '"')

    def receive_move():
        while True:
            message = input()

            log_write('received: "' + message + '"')

            if invalid_move.match(message) or victory.match(message):
                sys.exit()

            if flag_pos.match(message):
                continue

            move = Movement.from_string(game, message)
            if move is not None:
                game.add_move(move)
                return

            log_write('parsing failed for "' + message + '"')

    def do_move():
        moves = set(game.valid_moves())
        move = random.sample(moves, 1)[0]
        write(move)

        receive_move()

    def mark():
        log_write('---')

    atexit.register(mark)

    write('(' +
          ' '.join('({0} {1})'.format(piece.initial, piece.spec.symbol)
                   for piece in game.get_living_pieces()) +
          ')')

    if player == 1:
        do_move()

    while True:
        receive_move()
        do_move()
