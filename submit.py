#!/usr/bin/python3

import subprocess
import argparse
import errno
import os

parser = argparse.ArgumentParser(
            description='Automated assignment submission script'
         )
parser.add_argument('email', help='email address to submit with')
parser.add_argument('assignment', type=int,
                    help='assignment that you are submitting')
args = parser.parse_args()

file_format = "tgz"
directory = "play4500-assignment" + str(args.assignment)
file_name = directory + '.' + file_format

def run_command(*command):
    print('Running command:', ' '.join(command))

    result = subprocess.call(command)
    if result != 0:
        raise RuntimeError('Command failed with exit status ' + str(result))

try:
    os.remove(file_name)
except OSError as e:
    if e.errno != errno.ENOENT:
        raise e

run_command('git', 'archive', '--format', file_format,
                              '--prefix', directory + '/',
                              '--output', file_name,
                              '-v', 'HEAD')

run_command('/course/cs4500sp14/submit', args.email,
                                         str(args.assignment),
                                         file_name)
