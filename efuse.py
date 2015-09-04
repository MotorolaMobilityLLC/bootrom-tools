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

## Tool to automatically download an image into the HAPS board and boot it
#

# e-Fuse settings
efuses = {
    "VID": 0x00000000,
    "PID": 0x00000000,
    "SN0": 0x00000000,
    "SN1": 0x00000000,
    "IMS0": 0x00000000,
    "IMS1": 0x00000000,
    "IMS2": 0x00000000,
    "IMS3": 0x00000000,
    "IMS4": 0x00000000,
    "IMS5": 0x00000000,
    "IMS6": 0x00000000,
    "IMS7": 0x00000000,
    "IMS8": 0x00000000,
    "CMS0": 0x00000000,
    "CMS1": 0x00000000,
    "CMS2": 0x00000000,
    "CMS3": 0x00000000,
    "CMS4": 0x00000000,
    "CMS5": 0x00000000,
    "CMS6": 0x00000000,
    "SCR": 0x00000000,
    "JTAG_CONTROL": 0x00000000}


def set_efuse(reg, value):
    """ Set a named value in the efuses array

    reg The name of the value in the array
    value The value string to set
    """
    if reg in efuses:
        efuses[reg] = int(value, 16)
    else:
        raise ValueError("unknown e-Fuse:", reg)


def parse_efuse(efuse_filename):
    """ Parse the eFuse file to override the default eFuse values """
    if efuse_filename:
        with open(efuse_filename, "r") as fd:
            for line in fd:
                # lines are of the form: SN[63:0] = 41424344_45464748
                fields = line.split("=")
                if len(fields) == 2:
                    reg = fields[0].strip()
                    # remove the bitrange (e.g., PID[31:0])
                    i = reg.find('[')
                    if i > 0:
                        reg = reg[:i]
                    values = fields[1].strip().split('_')
                    max_index = len(values) - 1
                    if max_index == 0:
                        set_efuse(reg, values[0])
                    else:
                        for i, val in enumerate(values):
                            regname = "{0:s}{1:d}".format(reg, max_index - i)
                            set_efuse(regname, values[i])
