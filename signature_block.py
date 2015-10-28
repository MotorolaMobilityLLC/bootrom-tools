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
from struct import pack_into, unpack_from
from util import display_binary_data, error
from signature_common import get_signature_algorithm_name, \
    TFTF_SIGNATURE_TYPE_UNKNOWN

# TFTF Signature Block layout
TFTF_SIGNATURE_KEY_NAME_LENGTH = 96
TFTF_SIGNATURE_OFF_LENGTH = 0x00
TFTF_SIGNATURE_OFF_TYPE = 0x04
TFTF_SIGNATURE_OFF_KEY_NAME = 0x08
TFTF_SIGNATURE_OFF_KEY_SIGNATURE = 0x68
# Size of the fixed portion of the signature block
TFTF_SIGNATURE_LEN_FIXED_PART = TFTF_SIGNATURE_OFF_KEY_SIGNATURE


def signature_block_write_map(wf, base_offset, prefix=""):
    """Display the field names and offsets of a single TFTF header"""
    # Add the symbol for the start of this header
    if prefix:
        wf.write("{0:s} {1:08x}\n".
                 format(prefix, base_offset))
        prefix += "."

    # Add the header fields
    wf.write("{0:s}length  {1:08x}\n".
             format(prefix, base_offset + TFTF_SIGNATURE_OFF_LENGTH))
    wf.write("{0:s}type  {1:08x}\n".
             format(prefix, base_offset + TFTF_SIGNATURE_OFF_TYPE))
    wf.write("{0:s}key_name  {1:08x}\n".
             format(prefix, base_offset + TFTF_SIGNATURE_OFF_KEY_NAME))
    wf.write("{0:s}key_signature  {1:08x}\n".
             format(prefix, base_offset + TFTF_SIGNATURE_OFF_KEY_SIGNATURE))


class SignatureBlock:
    """TFTF signature block representation"""

    def __init__(self, buf=None, signature_type=None, key_name=None,
                 signature=None):
        """Constructor

        Initialize the signature block from the supplied buf OR
        (signature_type + key_name + signature.)
        """
        if buf:
            self.unpack(buf)
        elif signature_type and key_name and signature:
            self.signature_type = signature_type
            self.key_name = key_name
            self.signature = signature
            self.length = TFTF_SIGNATURE_LEN_FIXED_PART + len(signature)
        else:
            error("Invalid SignatureBlock creation")
            self.signature_type = TFTF_SIGNATURE_TYPE_UNKNOWN
            self.key_name = None
            self.signature = None
            self.length = TFTF_SIGNATURE_LEN_FIXED_PART

    def pack(self):
        """Pack the signature data into a binary blob

        Returns a binary blob containing the packed signature block data
        """

        buf = bytearray(self.length)
        pack_into("<LL96s", buf, 0,
                  self.length,
                  self.signature_type,
                  self.key_name)
        buf[TFTF_SIGNATURE_LEN_FIXED_PART:self.length] = self.signature
        return buf

    def unpack(self, buf):
        """Unpack the signature block from a binary buffer"""

        sig_block = unpack_from("<LL96s", buf, 0)
        self.length = sig_block[0]
        self.signature_type = sig_block[1]
        self.key_name = sig_block[2]
        self.signature = \
            buf[TFTF_SIGNATURE_LEN_FIXED_PART:self.length]

    def display(self, indent=""):
        """Display the signature block"""

        signature_name = get_signature_algorithm_name(self.signature_type)
        print("{0:s}    Length:    {1:08x}".format(indent, self.length))
        print("{0:s}    Sig. type: {1:d} ({2:s})".format(
            indent, self.signature_type, signature_name))
        print("{0:s}    Key name:".format(indent))
        print("{0:s}        '{1:4s}'".format(indent, self.key_name))
        print("{0:s}    Signature:".format(indent))
        display_binary_data(self.signature, True, indent + "        ")
