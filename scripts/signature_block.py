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
from util import display_binary_data
from tftf import error

# TFTF Signature Block layout
TFTF_SIGNATURE_KEY_NAME_LENGTH = 96
TFTF_SIGNATURE_OFF_LENGTH = 0x00
TFTF_SIGNATURE_OFF_TYPE = 0x04
TFTF_SIGNATURE_OFF_KEY_NAME = 0x08
TFTF_SIGNATURE_OFF_KEY_SIGNATURE = 0x68
# Size of the fixed portion of the signature block
TFTF_SIGNATURE_BLOCK_SIZE = TFTF_SIGNATURE_OFF_KEY_SIGNATURE

# TFTF Signature Types and associated dictionary of types and names
# NOTE: When adding new types, both the "define" and the dictionary
# need to be updated.
TFTF_SIGNATURE_TYPE_UNKNOWN = 0x00
TFTF_SIGNATURE_TYPE_RSA_2048_SHA_256 = 0x01
tftf_signature_types = {"rsa2048-sha256":
                        TFTF_SIGNATURE_TYPE_RSA_2048_SHA_256}
tftf_signature_names = {TFTF_SIGNATURE_TYPE_RSA_2048_SHA_256:
                        "rsa2048-sha256"}


def get_key_type(key_type_string):
    """convert a string into a key_type

    returns a numeric key_type, or None if invalid
    """

    return tftf_signature_types[key_type_string]


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
            self.length = TFTF_SIGNATURE_BLOCK_SIZE + len(signature)
        else:
            error("Invalid SignatureBlock creation")
            self.signature_type = TFTF_SIGNATURE_TYPE_UNKNOWN
            self.key_name = None
            self.signature = None
            self.length = TFTF_SIGNATURE_BLOCK_SIZE

    def pack(self):
        """Pack the signature data into a binary blob

        Returns a binary blob containing the packed signature block data
        """

        buf = bytearray(self.length)
        pack_into("<LL96s", buf, 0,
                  self.length,
                  self.signature_type,
                  self.key_name)
        buf[TFTF_SIGNATURE_BLOCK_SIZE:self.length] = self.signature
        return buf

    def unpack(self, buf):
        """Unpack the signature block from a binary buffer"""

        sig_block = unpack_from("<LL96s", buf, 0)
        self.length = sig_block[0]
        self.signature_type = sig_block[1]
        self.key_name = sig_block[2]
        self.signature = \
            buf[TFTF_SIGNATURE_BLOCK_SIZE:self.length]

    def display(self, indent=""):
        """Display the signature block"""

        try:
            signature_name = tftf_signature_names[self.signature_type]
        except:
            signature_name = "INVALID"

        print("{0:s}    Length:    {1:08x}".format(indent, self.length))
        print("{0:s}    Sig. type: {1:d} ({2:s})".format(
            indent, self.signature_type, signature_name))
        print("{0:s}    Key name:".format(indent))
        print("{0:s}        '{1:4s}'".format(indent, self.key_name))
        print("{0:s}    Signature:".format(indent))
        display_binary_data(self.signature, True, indent + "        ")
