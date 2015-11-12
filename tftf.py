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
import os
from struct import pack_into, unpack_from
from string import rfind
from time import gmtime, strftime
from util import display_binary_data, error
from signature_block import signature_block_write_map

# TFTF section types
TFTF_SECTION_TYPE_RESERVED = 0x00
TFTF_SECTION_TYPE_RAW_CODE = 0x01
TFTF_SECTION_TYPE_RAW_DATA = 0x02
TFTF_SECTION_TYPE_COMPRESSED_CODE = 0x03
TFTF_SECTION_TYPE_COMPRESSED_DATA = 0x04
TFTF_SECTION_TYPE_MANIFEST = 0x05
TFTF_SECTION_TYPE_SIGNATURE = 0x80
TFTF_SECTION_TYPE_CERTIFICATE = 0x81
TFTF_SECTION_TYPE_END_OF_DESCRIPTORS = 0xfe  # (File End)

# These types are considered valid
valid_tftf_types = \
    (TFTF_SECTION_TYPE_RAW_CODE,
     TFTF_SECTION_TYPE_RAW_DATA,
     TFTF_SECTION_TYPE_COMPRESSED_CODE,
     TFTF_SECTION_TYPE_COMPRESSED_DATA,
     TFTF_SECTION_TYPE_MANIFEST,
     TFTF_SECTION_TYPE_SIGNATURE,
     TFTF_SECTION_TYPE_CERTIFICATE,
     TFTF_SECTION_TYPE_END_OF_DESCRIPTORS)

# These types contribute to the TFTF load_length and extended_length
# calculation.
# NB. any certificates located after the first signature block are
# excluded from the calculations
countable_tftf_types = \
    (TFTF_SECTION_TYPE_RAW_CODE,
     TFTF_SECTION_TYPE_RAW_DATA,
     TFTF_SECTION_TYPE_COMPRESSED_CODE,
     TFTF_SECTION_TYPE_COMPRESSED_DATA,
     TFTF_SECTION_TYPE_MANIFEST,
     TFTF_SECTION_TYPE_CERTIFICATE)


# Other TFTF header constants (mostly field sizes)
TFTF_HEADER_SIZE_MIN = 512
TFTF_HEADER_SIZE_MAX = 4096
TFTF_HEADER_SIZE_DEFAULT = 512
TFTF_SENTINEL = "TFTF"
TFTF_TIMESTAMP_LENGTH = 16
TFTF_FW_PKG_NAME_LENGTH = 48
TFTF_HDR_NUM_RESERVED_MIN = 4
TFTF_RSVD_SIZE = 4      # Size of each reserved item

# TFTF section field lengths
TFTF_SECTION_LEN_TYPE = 1
TFTF_SECTION_LEN_CLASS = 3
TFTF_SECTION_LEN_ID = 4
TFTF_SECTION_LEN_LENGTH = 4
TFTF_SECTION_LEN_LOAD_ADDRESS = 4
TFTF_SECTION_LEN_EXPANDED_LENGTH = 4
TFTF_SECTION_LEN = (TFTF_SECTION_LEN_TYPE +
                    TFTF_SECTION_LEN_CLASS +
                    TFTF_SECTION_LEN_ID +
                    TFTF_SECTION_LEN_LENGTH +
                    TFTF_SECTION_LEN_LOAD_ADDRESS +
                    TFTF_SECTION_LEN_EXPANDED_LENGTH)

# TFTF section field offsets
TFTF_SECTION_OFF_TYPE = 0
TFTF_SECTION_OFF_CLASS = (TFTF_SECTION_OFF_TYPE + TFTF_SECTION_LEN_TYPE)
TFTF_SECTION_OFF_ID = (TFTF_SECTION_OFF_CLASS + TFTF_SECTION_LEN_CLASS)
TFTF_SECTION_OFF_LENGTH = (TFTF_SECTION_OFF_ID + TFTF_SECTION_LEN_ID)
TFTF_SECTION_OFF_LOAD_ADDRESS = (TFTF_SECTION_OFF_LENGTH +
                                 TFTF_SECTION_LEN_LENGTH)
TFTF_SECTION_OFF_EXPANDED_LENGTH = (TFTF_SECTION_OFF_LOAD_ADDRESS +
                                    TFTF_SECTION_LEN_LOAD_ADDRESS)

# TFTF header field lengths
TFTF_HDR_LEN_SENTINEL = 4
TFTF_HDR_LEN_HEADER_SIZE = 4
TFTF_HDR_LEN_TIMESTAMP = 16
TFTF_HDR_LEN_NAME = 48
TFTF_HDR_LEN_PACKAGE_TYPE = 4
TFTF_HDR_LEN_START_LOCATION = 4
TFTF_HDR_LEN_UNIPRO_MFGR_ID = 4
TFTF_HDR_LEN_UNIPRO_PRODUCT_ID = 4
TFTF_HDR_LEN_ARA_VENDOR_ID = 4
TFTF_HDR_LEN_ARA_PRODUCT_ID = 4
TFTF_HDR_LEN_MIN_RESERVED = (TFTF_HDR_NUM_RESERVED_MIN * TFTF_RSVD_SIZE)
TFTF_HDR_LEN_FIXED_PART = (TFTF_HDR_LEN_SENTINEL +
                           TFTF_HDR_LEN_HEADER_SIZE +
                           TFTF_HDR_LEN_TIMESTAMP +
                           TFTF_HDR_LEN_NAME +
                           TFTF_HDR_LEN_PACKAGE_TYPE +
                           TFTF_HDR_LEN_START_LOCATION +
                           TFTF_HDR_LEN_UNIPRO_MFGR_ID +
                           TFTF_HDR_LEN_UNIPRO_PRODUCT_ID +
                           TFTF_HDR_LEN_ARA_VENDOR_ID +
                           TFTF_HDR_LEN_ARA_PRODUCT_ID)
TFTF_HDR_NUM_SECTIONS = \
    ((TFTF_HEADER_SIZE_DEFAULT - TFTF_HDR_LEN_FIXED_PART) // TFTF_SECTION_LEN)
TFTF_HDR_LEN_SECTION_TABLE = (TFTF_HDR_NUM_SECTIONS * TFTF_SECTION_LEN)
# (The reserved array is made up of what's left over after creating the
# section array.)
TFTF_HDR_LEN_RESERVED = \
    (TFTF_HEADER_SIZE_DEFAULT -
     (TFTF_HDR_LEN_FIXED_PART + TFTF_HDR_LEN_SECTION_TABLE))
TFTF_HDR_NUM_RESERVED = (TFTF_HDR_LEN_RESERVED / TFTF_RSVD_SIZE)

# TFTF header field offsets
TFTF_HDR_OFF_SENTINEL = 0
TFTF_HDR_OFF_HEADER_SIZE = (TFTF_HDR_OFF_SENTINEL +
                            TFTF_HDR_LEN_SENTINEL)
TFTF_HDR_OFF_TIMESTAMP = (TFTF_HDR_OFF_HEADER_SIZE +
                          TFTF_HDR_LEN_HEADER_SIZE)
TFTF_HDR_OFF_NAME = (TFTF_HDR_OFF_TIMESTAMP +
                     TFTF_HDR_LEN_TIMESTAMP)
TFTF_HDR_OFF_PACKAGE_TYPE = (TFTF_HDR_OFF_NAME +
                             TFTF_HDR_LEN_NAME)
TFTF_HDR_OFF_START_LOCATION = (TFTF_HDR_OFF_PACKAGE_TYPE +
                               TFTF_HDR_LEN_PACKAGE_TYPE)
TFTF_HDR_OFF_UNIPRO_MFGR_ID = (TFTF_HDR_OFF_START_LOCATION +
                               TFTF_HDR_LEN_START_LOCATION)
TFTF_HDR_OFF_UNIPRO_PRODUCT_ID = (TFTF_HDR_OFF_UNIPRO_MFGR_ID +
                                  TFTF_HDR_LEN_UNIPRO_MFGR_ID)
TFTF_HDR_OFF_ARA_VENDOR_ID = (TFTF_HDR_OFF_UNIPRO_PRODUCT_ID +
                              TFTF_HDR_LEN_UNIPRO_PRODUCT_ID)
TFTF_HDR_OFF_ARA_PRODUCT_ID = (TFTF_HDR_OFF_ARA_VENDOR_ID +
                               TFTF_HDR_LEN_ARA_VENDOR_ID)
TFTF_HDR_OFF_RESERVED = (TFTF_HDR_OFF_ARA_PRODUCT_ID +
                         TFTF_HDR_LEN_ARA_PRODUCT_ID)
TFTF_HDR_OFF_SECTIONS = (TFTF_HDR_OFF_RESERVED +
                         TFTF_HDR_LEN_RESERVED)


# TFTF Signature Block layout
TFTF_SIGNATURE_KEY_NAME_LENGTH = 96
TFTF_SIGNATURE_SIGNATURE_LENGTH = 256

# TFTF signature block field lengths
TFTF_SIGNATURE_LEN_LENGTH = 4
TFTF_SIGNATURE_LEN_TYPE = 4
TFTF_SIGNATURE_LEN_KEY_NAME = TFTF_SIGNATURE_KEY_NAME_LENGTH
TFTF_SIGNATURE_LEN_KEY_SIGNATURE = TFTF_SIGNATURE_SIGNATURE_LENGTH
TFTF_SIGNATURE_LEN_FIXED_PART = (TFTF_SIGNATURE_LEN_LENGTH +
                                 TFTF_SIGNATURE_LEN_TYPE +
                                 TFTF_SIGNATURE_LEN_KEY_NAME)

# TFTF signature block field offsets
TFTF_SIGNATURE_OFF_LENGTH = 0
TFTF_SIGNATURE_OFF_TYPE = (TFTF_SIGNATURE_OFF_LENGTH +
                           TFTF_SIGNATURE_LEN_LENGTH)
TFTF_SIGNATURE_OFF_KEY_NAME = (TFTF_SIGNATURE_OFF_TYPE +
                               TFTF_SIGNATURE_LEN_TYPE)
TFTF_SIGNATURE_OFF_KEY_SIGNATURE = (TFTF_SIGNATURE_OFF_KEY_NAME +
                                    TFTF_SIGNATURE_LEN_KEY_NAME)

# TFTF Signature Types and associated dictionary of types and names
# NOTE: When adding new types, both the "define" and the dictionary
# need to be updated.
TFTF_SIGNATURE_TYPE_UNKNOWN = 0x00
TFTF_SIGNATURE_TYPE_RSA_2048_SHA_256 = 0x01
tftf_signature_types = {"rsa2048-sha256": TFTF_SIGNATURE_TYPE_RSA_2048_SHA_256}
tftf_signature_names = {TFTF_SIGNATURE_TYPE_RSA_2048_SHA_256: "rsa2048-sha256"}

TFTF_FILE_EXTENSION = ".bin"

# TFTF validity assesments
TFTF_VALID = 0
TFTF_INVALID = 1
TFTF_VALID_WITH_COLLISIONS = 2

# Size of the blob to copy each time
copy_blob_size = 1024*1024*10

section_type_names = {
    TFTF_SECTION_TYPE_RESERVED: "Reserved",
    TFTF_SECTION_TYPE_RAW_CODE: "Code",
    TFTF_SECTION_TYPE_RAW_DATA: "Data",
    TFTF_SECTION_TYPE_COMPRESSED_CODE: "Compressed code",
    TFTF_SECTION_TYPE_COMPRESSED_DATA: "Compressed data",
    TFTF_SECTION_TYPE_MANIFEST: "Manifest",
    TFTF_SECTION_TYPE_SIGNATURE: "Signature",
    TFTF_SECTION_TYPE_CERTIFICATE: "Certificate",
    TFTF_SECTION_TYPE_END_OF_DESCRIPTORS: "End of descriptors",
}

section_type_short_names = {
    TFTF_SECTION_TYPE_RESERVED: "reserved",
    TFTF_SECTION_TYPE_RAW_CODE: "code",
    TFTF_SECTION_TYPE_RAW_DATA: "data",
    TFTF_SECTION_TYPE_COMPRESSED_CODE: "compressed_code",
    TFTF_SECTION_TYPE_COMPRESSED_DATA: "compressed_data",
    TFTF_SECTION_TYPE_MANIFEST: "manifest",
    TFTF_SECTION_TYPE_SIGNATURE: "signature",
    TFTF_SECTION_TYPE_CERTIFICATE: "certificate",
    TFTF_SECTION_TYPE_END_OF_DESCRIPTORS: "eot",
}


class TftfSection:
    """TFTF Section representation"""
    def __init__(self, section_type, section_class=0, section_id=0,
                 section_length=0, load_address=0, extended_length=0,
                 filename=None):
        """Constructor

        If filename is specified, this reads in the file and sets the section
        length to the length of the file.
        """
        self.section_type = section_type
        self.section_class = section_class
        self.section_id = section_id
        self.section_length = section_length
        if (section_type == TFTF_SECTION_TYPE_SIGNATURE) or \
           (section_type == TFTF_SECTION_TYPE_CERTIFICATE):
            self.load_address = 0xffffffff
        else:
            self.load_address = load_address
        self.expanded_length = extended_length
        self.filename = filename

        # Try to size the section length from the section input file
        if filename:
            try:
                statinfo = os.stat(filename)
                # TODO: Lengths will be different if/when we support
                # compression:
                # - section_length will shrink to the compressed size
                # - expanded_length will remain the input file length
                self.section_length = statinfo.st_size
                self.expanded_length = statinfo.st_size
            except:
                error("file", filename, " is invalid or missing")

    def unpack(self, section_buf, section_offset):
        # Unpack a section header from a TFTF header buffer, and return
        # a flag indicating if the section was a section-end
        section_hdr = unpack_from("<LLLLL", str(section_buf), section_offset)
        type_class = section_hdr[0]
        self.section_type = type_class & 0x000000ff
        self.section_class = (type_class >> 8) & 0x00ffffff
        self.section_id = section_hdr[1]
        self.section_length = section_hdr[2]
        self.load_address = section_hdr[3]
        self.expanded_length = section_hdr[4]
        return self.section_type in valid_tftf_types

    def pack(self, buf, offset):
        # Pack a section header into a TFTF header buffer at the specified
        # offset, returning the offset of the next section.
        type_class = (self.section_class << 8) | self.section_type
        pack_into("<LLLLL", buf, offset,
                  type_class,
                  self.section_id,
                  self.section_length,
                  self.load_address,
                  self.expanded_length)
        return offset + TFTF_SECTION_LEN

    def section_name(self, section_type):
        # Convert a section type into textual form

        if section_type in section_type_names:
            return section_type_names[section_type]
        else:
            return "?"

    def section_short_name(self, section_type):
        # Convert a section type into a short textual form
        if section_type in section_type_short_names:
            return section_type_short_names[section_type]
        else:
            return "?"

    def display_table_header(self, indent):
        # Print the section table column names, returning the column
        # header for the section table (no indentation)

        print("{0:s}     Type Class  ID       Length   Load     Exp.Len".
              format(indent))

    def display(self, indent, index, expand_type):
        # Print a section header
        section_string = "{0:s}  {1:2d} {2:02x}   {3:06x} {4:08x} " \
                         "{5:08x} {6:08x} {7:08x}".format(indent, index,
                                                          self.section_type,
                                                          self.section_class,
                                                          self.section_id,
                                                          self.section_length,
                                                          self.load_address,
                                                          self.expanded_length)

        if expand_type:
            section_string += " ({0:s})".format(
                              self.section_name(self.section_type))
        print(section_string)

    def display_data(self, blob, title=None, indent=""):
        """Display the payload referenced by a single TFTF header"""
        # Print the title line
        title_string = indent
        if title:
            title_string += title
        title_string += "({0:d} bytes): {1:s}".format(
                        self.section_length,
                        self.section_name(self.section_type))
        print(title_string)

        # Print the data blob
        if self.section_type == TFTF_SECTION_TYPE_SIGNATURE:
            # Signature blocks have a known format which we can break down
            # for the user
            sig_block = unpack_from("<LL64s", blob, 0)
            sig_type = tftf_signature_names[sig_block[1]]
            if not sig_type:
                sig_type = "UNKNOWN"
            print("{0:s}  Length:    {1:08x}".format(indent, sig_block[0]))
            print("{0:s}  Sig. type: {1:d} ({2:s})".
                  format(indent, sig_block[1], sig_type))
            print("{0:s}  Key name:".format(indent))
            print("{0:s}      '{1:4s}'".format(indent, sig_block[2]))
            print("{0:s}  Signature:".format(indent))
            display_binary_data(blob[TFTF_SIGNATURE_OFF_KEY_SIGNATURE:],
                                True, indent + "       ")
        else:
            # The default is to show the blob as a binary dump.
            display_binary_data(blob, False, indent + " ")
        print("")


class Tftf:
    """TFTF representation"""
    def __init__(self, header_size, filename=None):
        """ TFTF constructor

        Basically, there are 2 logical constructor forms:
            - Tftf(header_size) # create a blank TFTF with a given header size
            - Tftf(filename)    # read an existing TFTF file into memory
        But, because Python doesn't allow polymorphism, these take the
        following forms:
            - Tftf(header_size, None) # create a blank TFTF
            - Tftf(0, filename)       # read an existing TFTF
        """
        # Size the buffer: if we're creating a blank TFTF use the supplied
        # header_size. If we're loading it from a file, (header_size = 0 and
        # a valid filename), allocate a default one and replace it with the
        # one from the file

        if (header_size != 0) and \
            ((header_size < TFTF_HEADER_SIZE_MIN) or
             (header_size > TFTF_HEADER_SIZE_MAX)):
            raise ValueError("TFTF header size is out of range")

        # Private fields
        if (header_size == 0):
            self.tftf_buf = bytearray(TFTF_HEADER_SIZE_DEFAULT)
        else:
            self.tftf_buf = bytearray(header_size)
        self.collisions = []
        self.collisions_found = False
        self.header_validity = TFTF_INVALID
        self.tftf_length = 0  # length of the whole blob

        # Header fields
        self.sentinel = 0
        self.header_size = header_size
        self.timestamp = ""
        self.firmware_package_name = ""
        self.package_type = 0
        self.start_location = 0
        self.unipro_mfg_id = 0
        self.unipro_pid = 0
        self.ara_vid = 0
        self.ara_pid = 0
        self.reserved = [0] * TFTF_HDR_NUM_RESERVED
        self.sections = []

        if filename:
            # Load the TFTF buffer and parse it for the TFTF header and
            # section list
            self.load_tftf_file(filename)
        else:
            # Salt the list with the end-of-table, because we will be
            # adding sections manually later
            eot = TftfSection(TFTF_SECTION_TYPE_END_OF_DESCRIPTORS)
            self.sections.append(eot)

        # Validate the header size (via parameter or the file)
        if self.header_size != 0:
            if (self.header_size < TFTF_HEADER_SIZE_MIN) or \
               (self.header_size > TFTF_HEADER_SIZE_MAX):
                raise ValueError("TFTF header size is out of range")
            self.recalculate_header_offsets()

    def recalculate_header_offsets(self):
        """ Recalculate section table size and offsets from header_size

        Because we have variable-size TFTF headers, we need to recalculate the
        number of entries in the section table, and the offsets to all fields
        which follow.
        """
        global TFTF_HDR_NUM_SECTIONS, TFTF_HDR_LEN_SECTION_TABLE, \
            TFTF_HDR_LEN_RESERVED, TFTF_HDR_OFF_RESERVED, \
            TFTF_HDR_OFF_SECTIONS, TFTF_HDR_NUM_RESERVED
        # TFTF section table and derived lengths
        TFTF_HDR_NUM_SECTIONS = \
            ((self.header_size -
             (TFTF_HDR_LEN_FIXED_PART + TFTF_HDR_LEN_MIN_RESERVED)) //
             TFTF_SECTION_LEN)
        TFTF_HDR_LEN_SECTION_TABLE = (TFTF_HDR_NUM_SECTIONS * TFTF_SECTION_LEN)

        # (The reserved array is made up of what's left over after creating the
        # section array.)
        TFTF_HDR_LEN_RESERVED = \
            self.header_size - \
            (TFTF_HDR_LEN_FIXED_PART + TFTF_HDR_LEN_SECTION_TABLE)
        TFTF_HDR_NUM_RESERVED = TFTF_HDR_LEN_RESERVED / TFTF_RSVD_SIZE

        # DO NOT CLEAR RESERVED - IT IS USED FOR TFTF VERSION
        #self.reserved = [0] * TFTF_HDR_NUM_RESERVED
        # Offsets to fields following the first variable-length table
        # (Reserved)
        TFTF_HDR_OFF_SECTIONS = (TFTF_HDR_OFF_RESERVED +
                                 TFTF_HDR_LEN_RESERVED)

    def load_tftf_file(self, filename):
        """Try to import a TFTF header and/or file

        If "buf" is None, then we only import the TFTF header.  However, if
        buf is supplied (typically a memoryview into a larger buffer), the
        entire TFTF file is also imported into the buffer.  This is to allow
        for cases where the caller needs to determine the TFTF characteristics
        before creating their buffer.
        """
        success = True
        if filename:
            # Try to open the file, and if that fails, try appending the
            # extension.
            names = (filename, filename + TFTF_FILE_EXTENSION)
            rf = None
            for name in names:
                try:
                    rf = open(name, 'rb')
                    break
                except:
                    print("can't find TFTF file"), filename
                    success = False

            if success:
                # Record the length of the entire TFTF blob (this will be
                # longer than the header's load_length)
                rf.seek(0, 2)
                self.tftf_length = rf.tell()

                rf.seek(0, 0)
                # (Display-tftf case) Read the entire TFTF file into
                # a local buffer
                self.tftf_buf = bytearray(self.tftf_length)
                rf.readinto(self.tftf_buf)
                rf.close()
                self.unpack()
                self.post_process()
        return success

    def load_tftf_from_buffer(self, buf):
        """Import a TFTF blob from a memory buffer"""
        self.tftf_buf = buf
        self.unpack()

    def unpack(self):
        # Unpack a TFTF header from a buffer
        fmt_string = "<4sL16s48sLLLLLL" + "L" * TFTF_HDR_NUM_RESERVED
        tftf_hdr = unpack_from(fmt_string, str(self.tftf_buf))
        self.sentinel = tftf_hdr[0]
        self.header_size = tftf_hdr[1]
        self.timestamp = tftf_hdr[2]
        self.firmware_package_name = tftf_hdr[3]
        self.package_type = tftf_hdr[4]
        self.start_location = tftf_hdr[5]
        self.unipro_mfg_id = tftf_hdr[6]
        self.unipro_pid = tftf_hdr[7]
        self.ara_vid = tftf_hdr[8]
        self.ara_pid = tftf_hdr[9]

        # Since the imported header_size may be different from our 512-byte
        # default, we need to recalculate the size of the reserved and
        # section tables and their offsets
        self.recalculate_header_offsets()

        for i in range(TFTF_HDR_NUM_RESERVED):
            self.reserved[i] = tftf_hdr[10+i]

        # Purge (the EOT from) the list because we're populating the entire
        # list from the file
        self.sections = []

        # Parse the table of section headers
        section_offset = TFTF_HDR_OFF_SECTIONS
        for section_index in range(TFTF_HDR_NUM_SECTIONS):
            section = TftfSection(0)
            if section.unpack(self.tftf_buf, section_offset):
                self.sections.append(section)
                section_offset += TFTF_SECTION_LEN

                if section.section_type == \
                   TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                    break
            else:
                error("Invalid section type {0:02x} "
                      "at [{1:d}]".format(section.section_type,
                                          section_index))
                break
        self.sniff_test()

    def pack(self):
        # Pack the TFTF header members into the TFTF header buffer, prior
        # to writing the buffer out to a file.

        # Populate the fixed part of the TFTF header.
        # (Note that we need to break up the packing because the "s" format
        # doesn't zero-pad a string shorter than the field width)
        pack_into("<4sL16s", self.tftf_buf, 0,
                  self.sentinel,
                  self.header_size,
                  self.timestamp)
        if self.firmware_package_name:
            pack_into("<48s", self.tftf_buf, TFTF_HDR_OFF_NAME,
                      self.firmware_package_name)
        pack_into("<LLLLLL", self.tftf_buf, TFTF_HDR_OFF_PACKAGE_TYPE,
                  self.package_type,
                  self.start_location,
                  self.unipro_mfg_id,
                  self.unipro_pid,
                  self.ara_vid,
                  self.ara_pid)
        for i in range(TFTF_HDR_NUM_RESERVED):
            pack_into("<L", self.tftf_buf,
                      TFTF_HDR_OFF_RESERVED + (TFTF_RSVD_SIZE * i),
                      self.reserved[i])

        # Pack the section headers into the TFTF header buffer
        offset = TFTF_HDR_OFF_SECTIONS
        for section in self.sections:
            offset = section.pack(self.tftf_buf, offset)

    def add_section(self, section_type, section_class, section_id,
                    section_data, load_address=0):
        # Add a new section to the section table and return a success flag
        #
        # (This would be called by "sign-tftf" to add signature and
        # certificate blocks.)
        num_sections = len(self.sections)
        if num_sections < TFTF_HDR_NUM_SECTIONS:
            # Insert the section to the section list, just in front of
            # the end-of-table marker.
            #
            # Notes:
            #   1. We assume this is an uncompressable section
            #   2. We defer pushing the new section into the buffer until
            #      the write stage or someone explicitly calls "pack".)
            self.sections.insert(num_sections - 1,
                                 TftfSection(section_type,
                                             section_class,
                                             section_id,
                                             len(section_data),
                                             load_address,
                                             len(section_data),
                                             None))

            # Append the section data blob to our TFTF buffer
            self.tftf_buf += section_data

            # Record the length of the entire TFTF blob (this will be longer
            # than the header's load_length)
            self.tftf_length = len(self.tftf_buf)
            return True
        else:
            error("Section table full")
            return False

    def add_section_from_file(self, section_type, section_class, section_id,
                              filename, load_address=0):
        # Add a new section from a file and return a success flag
        #
        # (This would be called by "create-tftf" while/after parsing section
        # parameters)
        if len(self.sections) < TFTF_HDR_NUM_SECTIONS:
            try:
                with open(filename, 'rb') as readfile:
                    section_data = readfile.read()

                return self.add_section(section_type, section_class,
                                        section_id, section_data,
                                        load_address)
            except:
                error("Unable to read", filename)
                return False
        else:
            error("Section table full")
            return False

    def check_for_collisions(self):
        # Scan the TFTF section table for collisions
        #
        # This would be called by "create-ffff" after parsing all of the
        # parameters and calling update_ffff_sections().

        for comp_a, section_a in enumerate(self.sections):
            collision = []
            # extract sections[comp_a]
            if section_a.section_type == TFTF_SECTION_TYPE_SIGNATURE or \
               section_a.section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                break

            start_a = section_a.load_address
            end_a = start_a + section_a.expanded_length - 1
            for comp_b, section_b in enumerate(self.sections):
                # skip checking one's self
                if comp_a != comp_b:
                    # extract sections[comp_b]
                    if section_b.section_type == \
                       TFTF_SECTION_TYPE_SIGNATURE or \
                       section_b.section_type == \
                       TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                        break

                    start_b = section_b.load_address
                    end_b = start_b + section_b.expanded_length - 1
                    if end_b >= start_a and \
                       start_b <= end_a:
                        self.collisions_found = True
                        collision += [comp_b]
            self.collisions += [collision]
        return self.collisions_found

    def sniff_test(self):
        # Perform a quick validity check of the TFTF header.  Generally
        # done when importing an existing TFTF file.

        self.header_validity = TFTF_VALID

        # Valid sentinel? (This should also subsume the "erased block" test)
        if self.sentinel != TFTF_SENTINEL:
            self.header_validity = TFTF_INVALID
        else:
            # check for collisions
            if self.check_for_collisions():
                self.header_validity = TFTF_VALID_WITH_COLLISIONS

        return self.header_validity

    def is_good(self):
        # Go/no-go decision on a TFTF header

        return self.header_validity != TFTF_INVALID

    def post_process(self):
        """Post-process the TFTF header

        Process the TFTF header (called by "create-tftf" after processing all
        arguments)
        """
        self.sentinel == TFTF_SENTINEL

        # Check for collisions
        self.sentinel = TFTF_SENTINEL
        self.check_for_collisions()
        if self.timestamp == "":
            self.timestamp = strftime("%Y%m%d %H%M%S", gmtime())

        # Trim the name to length
        if self.firmware_package_name:
            self.firmware_package_name = \
                self.firmware_package_name[0:TFTF_FW_PKG_NAME_LENGTH]

        # Determine the validity
        self.sniff_test()

    def write(self, out_filename):
        """Create the TFTF file and return a success flag

        Create the TFTF file (appending the default extension if omitted)
        and write the TFTF buffer to it.
        """
        success = True
        # Prepare the output buffer
        self.pack()

        # Record the length of the entire TFTF blob (this will be longer
        # than the header's load_length)
        self.tftf_length = len(self.tftf_buf)

        # Ensure the output file ends in the default TFTF file extension if
        # the user hasn't specified their own extension.
        if rfind(out_filename, ".") == -1:
            out_filename += TFTF_FILE_EXTENSION

        try:
            with open(out_filename, 'wb') as wf:
                # Write the TFTF header
                wf.write(self.tftf_buf)

            # verify the file is the correct length
            try:
                statinfo = os.stat(out_filename)
                if statinfo.st_size != self.tftf_length:
                    error(out_filename, "has wrong length")
            except:
                error("Can't get info on", out_filename)

        except:
            error("Unable to write", out_filename)
            success = False
        else:
            if success:
                print("Wrote", out_filename)
            else:
                error("Failed to write", out_filename)
            return success

    def display(self, title=None, indent=""):
        """Display a single TFTF header"""
        # 1. Dump the contents of the fixed part of the TFTF header
        if title:
            print("{0:s}TFTF Header for {1:s} ({2:d} bytes)".format(
                indent, title, self.tftf_length))
        else:
            print("{0:s}TFTF Header ({1:d} bytes)".format(
                indent, self.tftf_length))
        print("{0:s}  Sentinel:         '{1:4s}'".format(
            indent, self.sentinel))
        print("{0:s}  Header size:       0x{1:08x} ({2:d})".format(
            indent, self.header_size, self.header_size))
        print("{0:s}  Timestamp:        '{1:16s}'".format(
            indent, self.timestamp))
        print("{0:s}  Fw. pkg name:     '{1:48s}'".format(
            indent, self.firmware_package_name))
        print("{0:s}  Package type:      0x{1:08x}".format(
            indent, self.package_type))
        print("{0:s}  Start location:    0x{1:08x}".format(
            indent, self.start_location))
        print("{0:s}  Unipro mfg ID:     0x{1:08x}".format(
            indent, self.unipro_mfg_id))
        print("{0:s}  Unipro product ID: 0x{1:08x}".format(
            indent, self.unipro_pid))
        print("{0:s}  Ara vendor ID:     0x{1:08x}".format(
            indent, self.ara_vid))
        print("{0:s}  Ara product ID:    0x{1:08x}".format(
            indent, self.ara_pid))
        for i, rsvd in enumerate(self.reserved):
            print("{0:s}  Reserved [{1:d}]:      0x{2:08x}".
                  format(indent, i, rsvd))

        # 2. Dump the table of section headers
        print("{0:s}  Section Table (all values in hex):".format(indent))
        self.sections[0].display_table_header(indent)
        for index, section in enumerate(self.sections):
            section.display(indent, index, True)

            # Note any collisions on a separate line
            # NB. the end-of-table section does not have a collisions list.
            if index < len(self.collisions) and \
               len(self.collisions[index]) > 0:
                section_string = \
                    "{0:s}     Collides with section(s):".format(indent)
                for collision in self.collisions[index]:
                    section_string += " {0:d}".format(collision)
                print(section_string)

        # Note any unused sections
        num_unused_sections = TFTF_HDR_NUM_SECTIONS - len(self.sections)
        if num_unused_sections > 1:
            print("{0:s}  {1:2d} (unused)".format(indent, len(self.sections)))
        if num_unused_sections > 2:
            print("{0:s}   :    :".format(indent))
        if num_unused_sections > 0:
            print("{0:s}  {1:2d} (unused)".
                  format(indent, TFTF_HDR_NUM_SECTIONS-1))
        print(" ")

    def display_data(self, title=None, indent=""):
        """Display the payload referenced by a single TFTF header"""
        # 1. Print the title line
        title_string = "{0:s}TFTF contents".format(indent)
        if title:
            title_string += " for {0:s}".format(title)
        title_string += " ({0:d} bytes)".format(self.tftf_length)
        print(title_string)

        # 2. Print the associated data blobs
        offset = self.header_size
        for index, section in enumerate(self.sections):
            if section.section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                break
            end = offset + section.section_length - 1
            section.display_data(self.tftf_buf[offset:end],
                                 "section [{0:d}] ".format(index),
                                 indent + "  ")
            offset += section.section_length

    def find_first_section(self, section_type):
        """Find the index of the first section of the specified type

        Return the index of the first section in the section table matching
        the specified type. Returns the index of the first end-of-table
        marker if not found.

        (Typically used to find the first signature section as part of the
        signing operation.)
        """
        for index, section in enumerate(self.sections):
            if section.section_type == section_type or \
               section.section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                return index
        return len(self.sections)

    def get_header_up_to_section(self, section_index):
        """Return the head of the header buffer up to section_table[index]

        Returns a (binary) string consisting of the first N bytes of the
        header buffer up to the start of the Ith entry in the section
        descriptor table.

        (Typically used to obtain the first part of the blob to be signed.)
        """
        if section_index > len(self.sections):
            return None

        # Flush any changes out to the buffer and return the substring
        self.pack()
        slice_end = TFTF_HDR_OFF_SECTIONS + \
            section_index * TFTF_SECTION_LEN
        return self.tftf_buf[0:slice_end]

    def get_section_data_up_to_section(self, section_index):
        """Return the section info for the first N sections

        Returns a (binary) string consisting of the first N bytes of the
        section data up to the start of the Ith entry in the section
        table.

        (Typically used to obtain the second part of the blob to be signed.)
        """
        if section_index > len(self.sections):
            return None

        # Flush any changes out to the buffer and return the substring
        self.pack()
        slice_end = self.header_size
        for index, section in enumerate(self.sections):
            if index >= section_index:
                break
            slice_end += section.section_length
        return self.tftf_buf[self.header_size:slice_end]

    def create_map_file(self, base_name, base_offset, prefix=""):
        """Create a map file from the base name

        Create a map file from the base name substituting or adding ".map"
        as the file extension, and write out the offsets for the TFTF fields.
        """
        index = base_name.rindex(".")
        if index != -1:
            base_name = base_name[:index]
        map_name = base_name + ".map"
        try:
            with open(map_name, 'w') as mapfile:
                self.write_map(mapfile, base_offset, prefix)
        except:
            error("Unable to write", map_name)
            return False

    def write_map(self, wf, base_offset, prefix=""):
        """Display the field names and offsets of a single TFTF header"""
        # Add the symbol for the start of this header
        if prefix:
            wf.write("{0:s} {1:08x}\n".format(prefix, base_offset))
            prefix += "."

        # Add the header fields
        wf.write("{0:s}sentinel  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_SENTINEL))
        wf.write("{0:s}header_size  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_HEADER_SIZE))
        wf.write("{0:s}timestamp  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_TIMESTAMP))
        wf.write("{0:s}firmware_name  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_NAME))
        wf.write("{0:s}package_type  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_PACKAGE_TYPE))
        wf.write("{0:s}start_location  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_START_LOCATION))
        wf.write("{0:s}unipro_mfgr_id  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_UNIPRO_MFGR_ID))
        wf.write("{0:s}unipro_product_id  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_UNIPRO_PRODUCT_ID))
        wf.write("{0:s}ara_vendor_id  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_ARA_VENDOR_ID))
        wf.write("{0:s}ara_product_id  {1:08x}\n".
                 format(prefix, base_offset + TFTF_HDR_OFF_ARA_PRODUCT_ID))
        for i in range(len(self.reserved)):
            wf.write("{0:s}reserved[{1:d}]  {2:08x}\n".
                     format(prefix, i,
                            base_offset + TFTF_HDR_OFF_RESERVED +
                            (TFTF_RSVD_SIZE * i)))

        # Dump the section descriptors (used and free)
        section_offset = base_offset + TFTF_HDR_OFF_SECTIONS
        for index in range(TFTF_HDR_NUM_SECTIONS):
            wf.write("{0:s}section[{1:d}].type  {2:08x}\n".
                     format(prefix, index,
                            section_offset + TFTF_SECTION_OFF_TYPE))
            wf.write("{0:s}section[{1:d}].class  {2:08x}\n".
                     format(prefix, index,
                            section_offset + TFTF_SECTION_OFF_CLASS))
            wf.write("{0:s}section[{1:d}].id  {2:08x}\n".
                     format(prefix, index,
                            section_offset + TFTF_SECTION_OFF_ID))
            wf.write("{0:s}section[{1:d}].section_length  {2:08x}\n".
                     format(prefix, index,
                            section_offset + TFTF_SECTION_OFF_LENGTH))
            wf.write("{0:s}section[{1:d}].load_address  {2:08x}\n".
                     format(prefix, index,
                            section_offset + TFTF_SECTION_OFF_LOAD_ADDRESS))
            wf.write("{0:s}section[{1:d}].expanded_length  {2:08x}\n".
                     format(prefix, index,
                            section_offset + TFTF_SECTION_OFF_EXPANDED_LENGTH))
            section_offset += TFTF_SECTION_LEN

        # Dump the section starts
        base_offset += self.header_size
        for index, section in enumerate(self.sections):
            sn_name = "{0:s}section[{1:d}].{2:s}".\
                      format(prefix, index,
                             section.section_short_name(section.section_type))
            # If we know the structure of the section, dump the map for that
            if section.section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                break
            elif section.section_type == TFTF_SECTION_TYPE_SIGNATURE:
                signature_block_write_map(wf, base_offset, sn_name)
            else:
            # Otherwise, just describe it generically
                wf.write("{0:s}  {1:08x}\n".format(sn_name, base_offset))
            base_offset += section.section_length
