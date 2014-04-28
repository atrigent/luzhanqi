#!/usr/bin/python3

import play4500
from luzhanqi import LuzhanqiBoard as L
import logging
import coordinates
import sys

board = coordinates.CoordinateSystemState(L.system)

for i, pos in enumerate(L.initial_positions()):
    board[pos] = '+' + str(i)

for i, pos in enumerate(L.initial_enemy_positions()):
    board[pos] = '-' + str(i)

logging.basicConfig(level=logging.DEBUG,
                    stream=sys.stdout)

for line in open(sys.argv[1]):
    match = play4500.movement_re.match(line)
    if not match:
        print(line, end='')
        continue

    start = play4500.parse_coord(match.group(1))
    end = play4500.parse_coord(match.group(2))

    enemy_move = False
    if match.group(3) == sys.argv[2]:
        enemy_move = True
        start = -start
        end = -end

    mtype = match.group(4)
    if mtype == 'move' or mtype == 'win':
        board[end] = board[start]
        board[start] = None
    elif mtype == 'loss':
        board[start] = None
    elif mtype == 'tie':
        board[start] = None
        board[end] = None

    print('{} {} {} {}'.format(start, end, match.group(3), match.group(4)))
    markers = {pos: board[pos] for pos in board
                               if board[pos] is not None}

    L.log_board_with_markers(markers)
