#! /usr/bin/python

import argparse
import re


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

    # Initial map
    # (
    #     ( A1 1 ) ( B1 F ) ( C1 2 ) ( D1 L ) ( E1 5 )
    #     ( A2 L ) ( B2 4 ) ( C2 7 ) ( D2 6 ) ( E2 L )
    #     ( A3 1 ) ( C3 6 ) ( E3 1 )
    #     ( A4 7 ) ( B4 B ) ( D4 B ) ( E4 3 )
    #     ( A5 2 ) ( C5 3 ) ( E5 5 )
    #     ( A6 8 ) ( B6 4 ) ( C6 9 ) ( D6 2 ) ( E6 3 )
    # )

    print '( ( A1 1 ) ( B1 F ) ( C1 2 ) ( D1 L ) ( E1 5 ) ( A2 L ) ( B2 4 ) ( C2 7 ) ( D2 6 ) ( E2 L ) ( A3 1 ) ( C3 6 ) ( E3 1 ) ( A4 7 ) ( B4 B ) ( D4 B ) ( E4 3 ) ( A5 2 ) ( C5 3 ) ( E5 5 ) ( A6 8 ) ( B6 4 ) ( C6 9 ) ( D6 2 ) ( E6 3 ) )'
    if player == 1:
        print '( A6 A7 )'
