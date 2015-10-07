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

## Tool to compare a log file against a response file
#

from __future__ import print_function


def load_file(filename):
    """ Load a file into a list """
    with open(filename, "r") as f:
        return f.readlines()


def compare_log_to_resp(log, resp):
    """ Search the log list for the responses in the response list

    Search through the log list for the lines in the response list. The
    response list may contain substrings found in the log list lines. The
    response list lines must be found in the log list in the order they
    are specified in the response list (the log list may have extra lines
    which are ignored).

    Returns None if all the strings in the response list were found in the
    log list. Otherwise, returns the first missing response line.
    """
    response_line_no = 0
    response_line = resp[response_line_no].rstrip()

    for log_line in log:
        log_line = log_line.rstrip()
        if response_line in log_line:
            # Found a match, step to the next non-blank line in the response
            # list
            while True:
                response_line_no += 1
                if response_line_no >= len(resp):
                    # We ran through all of our respones lines, success!
                    return None
                else:
                    response_line = resp[response_line_no].rstrip()
                    if len(response_line) > 0:
                        break
    #print("Log missing '{0:s}'".format(response_line))
    return response_line
