#!/usr/bin/python3
from luzhanqi import LuzhanqiBoard

if __name__ == '__main__':
    game = LuzhanqiBoard()
    game.setup()

    print('(' +
          ' '.join('({0} {1})'.format(piece.initial, piece.spec.symbol)
                   for piece in game.get_living_pieces()) +
          ')')
