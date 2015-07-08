#! /usr/bin/env python

#
# Copyright (c) 2015 Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import print_function
import sys
import binascii

# Program return values
PROGRAM_SUCCESS = 0
PROGRAM_WARNINGS = 1
PROGRAM_ERRORS = 2


def warning(*objs):
    """Print a warning message to stderr, prefixed with 'WARNING'"""
    print("WARNING:", *objs, file=sys.stderr)


def error(*objs):
    """Print an error message to stderr, prefixed with 'ERROR'"""
    print("ERROR:", *objs, file=sys.stderr)


def print_to_error(*objs):
    """Print a message to stderr, unadorned"""
    print(*objs, file=sys.stderr)


def is_power_of_2(x):
    """Determine if a number is a power of 2"""
    return ((x != 0) and not(x & (x - 1)))


def block_aligned(location, block_size):
    """Determine if a location is block-aligned"""
    return (location & (block_size - 1)) == 0


def next_boundary(location, block_size):
    """Round up to the next block"""
    return (location + (block_size - 1)) & ~(block_size - 1)


def is_constant_fill(bytes, fill_byte):
    """Check a range of bytes for a constant fill"""
    return all(b == fill_byte for b in bytes)


def display_binary_data(blob, show_all, indent=""):
    """Display a binary blob

    Display a binary blob in 32-byte lines. If show_all is
    True, then the entire blob is displayed. Otherwise, up to 3 lines
    are displayed, and if the blob is more than 96 bytes long, only the
    first and last 32 bytes are displayed, with a ":" between them.
    """
    # Print the data blob
    length = len(blob)
    max_on_line = 32

    if length <= (3 * max_on_line) or show_all:
        # Nominally a small blob
        for start in range(0, length, max_on_line):
            num_bytes = min(length, max_on_line)
            print("{0:s}{1:s}".format(
                  indent,
                  binascii.hexlify(blob[start:start+num_bytes])))
    else:
        # Blob too long, so print the first and last lines with a ":"
        # spacer between
        print("{0:s}{1:s}".format(
              indent,
              binascii.hexlify(blob[0:max_on_line])))
        print("{0:s}  :".format(indent))
        start = length - max_on_line
        print("{0:s}{1:s}".format(
              indent,
              binascii.hexlify(blob[start:length])))
