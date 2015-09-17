#! /usr/bin/python

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
from struct import unpack_from, pack_into
from tftf import Tftf
from util import error, block_aligned


# TFTF Sentinel value.
FFFF_SENTINEL = "FlashFormatForFW"

# FFFF header & field sizes
FFFF_SENTINEL_LENGTH_IN_BYTES = 16
FFFF_TIMESTAMP_LENGTH = 16
FFFF_FLASH_IMAGE_NAME_LENGTH = 48
FFFF_HDR_LENGTH = 512
FFFF_MAX_ELEMENTS = 19
FFFF_PADDING = 16

# Maximum possible size for a header block
FFFF_MAX_HEADER_BLOCK_SIZE = (64 * 1024)
FFFF_MAX_HEADER_BLOCK_OFFSET = (512 * 1024)

# Special element index denoting header (for collisions)
FFFF_HEADER_COLLISION = -1

# FFFF Element types (see: ffff_element.element_type)
FFFF_ELEMENT_STAGE2_FIRMWARE_PACKAGE = 0x01
FFFF_ELEMENT_STAGE3_FIRMWARE_PACKAGE = 0x02
FFFF_ELEMENT_IMS_CERTIFICATE = 0x03
FFFF_ELEMENT_CMS_CERTIFICATE = 0x04
FFFF_ELEMENT_DATA = 0x05
FFFF_ELEMENT_END_OF_ELEMENT_TABLE = 0xfe

# FFFF signature block field sizes
FFFF_SIGNATURE_KEY_NAME_LENGTH = 64
FFFF_SIGNATURE_KEY_HASH_LENGTH = 32

# FFFF element offsets
FFFF_ELT_OFF_TYPE = 0x00
FFFF_ELT_OFF_ID = 0x04
FFFF_ELT_OFF_GENERATION = 0x08
FFFF_ELT_OFF_LOCATION = 0x0c
FFFF_ELT_OFF_LENGTH = 0x10
FFFF_ELT_LENGTH = 0x14

# FFFF header offsets
FFFF_HDR_OFF_SENTINEL = 0x0000
FFFF_HDR_OFF_TIMESTAMP = 0x0010
FFFF_HDR_OFF_FLASH_IMAGE_NAME = 0x0020
FFFF_HDR_OFF_FLASH_CAPACITY = 0x0050
FFFF_HDR_OFF_ERASE_BLOCK_SIZE = 0x0054
FFFF_HDR_OFF_HDR_BLOCK_SIZE = 0x0058
FFFF_HDR_OFF_FLASH_IMAGE_LENGTH = 0x005c
FFFF_HDR_OFF_HEADER_GENERATION_NUM = 0x0060
FFFF_HDR_OFF_ELEMENT_TBL = 0x0064  # Start of elements array
FFFF_HDR_OFF_PADDING = 0x01e0  # 12-byte padding
FFFF_HDR_OFF_TAIL_SENTINEL = 0x01f0

FFFF_FILE_EXTENSION = ".ffff"

# TFTF validity assesments
FFFF_HDR_VALID = 0
FFFF_HDR_ERASED = 1
FFFF_HDR_INVALID = 2

element_short_names = {
    FFFF_ELEMENT_END_OF_ELEMENT_TABLE: "eot",
    FFFF_ELEMENT_STAGE2_FIRMWARE_PACKAGE: "2fw",
    FFFF_ELEMENT_STAGE3_FIRMWARE_PACKAGE: "3fw",
    FFFF_ELEMENT_IMS_CERTIFICATE: "ims_cert",
    FFFF_ELEMENT_CMS_CERTIFICATE: "cms_cert",
    FFFF_ELEMENT_DATA: "data",
}


# FFFF Element representation
#
class FfffElement:
    """Defines the contents of a Flash Format for Firmware (FFFF) element table

    Each element describes a region of flash memory, its type and the
    corresponding blob stored there (typically a TFTF "file").
    """

    def __init__(self, index, buf, buf_size, erase_block_size,
                 element_type, element_id, element_generation,
                 element_location, element_length, filename=None):
        """Constructor

        Note: The optional filename is merely stored here.  It is used
        later in init()
        """

        # Private vars
        self.filename = filename
        self.tftf_blob = None
        self.buf = buf
        self.buf_size = buf_size
        self.index = index
        self.erase_block_size = erase_block_size
        self.collisions = []
        self.duplicates = []
        self.in_range = False
        self.aligned = False
        self.valid_type = False

        # Element fields
        self.element_type = element_type
        self.element_id = element_id
        self.element_generation = element_generation
        self.element_location = element_location
        self.element_length = element_length

    def init(self):
        """FFFF Element post-constructor initializer

        Loads the element from TFTF file, setting the element length to
        that of the file.  Returns a success flag if the file was loaded
        (no file is treated as success).
        """
        success = True
        # Try to size it from the TFTF file
        if self.filename and not self.tftf_blob:
            # Create a TFTF blob and load the contents from the specified
            # TFTF file
            self.tftf_blob = Tftf(self.filename)
            success = self.tftf_blob.load_tftf_file(self.filename)
            if success and self.tftf_blob.is_good():
                # element_length must be that of the entire TFTF blob,
                # not just the TFTF's "load_length" or "expanded_length".
                self.element_length = self.tftf_blob.tftf_length
            else:
                raise ValueError("Bad TFTF file:", self.filename)
        return True

    def unpack(self, buf, offset):
        """Unpack an element header from an FFFF header buffer

        Unpacks an element header from an FFFF header buffer at the specified
        offset.  Returns a flag indicating if the unpacked element is an
        end-of-table marker
        """
        element_hdr = unpack_from("<LLLLL", buf, offset)
        self.element_type = element_hdr[0]
        self.element_id = element_hdr[1]
        self.element_generation = element_hdr[2]
        self.element_location = element_hdr[3]
        self.element_length = element_hdr[4]

        # Get the element data into our tftf_blob
        if self.element_type != FFFF_ELEMENT_END_OF_ELEMENT_TABLE:
            # Create a TFTF blob and load the contents from the specified
            # TFTF file
            span_start = self.element_location
            span_end = span_start + self.element_length
            self.tftf_blob = Tftf(None)
            span_start = self.element_location
            span_end = span_start + self.element_length
            self.tftf_blob.load_tftf_from_buffer(buf[span_start:span_end])
            return False
        else:
            return True

    def pack(self, buf, offset):
        """Pack an element header into an FFFF header

        Packs an element header into into the FFFF header buffer at the
        specified offset and returns the offset for the next element
        """
        pack_into("<LLLLL", buf, offset,
                  self.element_type,
                  self.element_id,
                  self.element_generation,
                  self.element_location,
                  self.element_length)
        return offset + FFFF_ELT_LENGTH

    def validate(self, address_range_low, address_range_high):
        # Validate an element header
        #
        # Returns True if valid, False otherwise

        # EOT is always valid
        if self.element_type == FFFF_ELEMENT_END_OF_ELEMENT_TABLE:
            return True

        # Do we overlap the header
        self.in_range = self.element_location >= address_range_low and\
                        self.element_location < address_range_high
        if not self.in_range:
            error("Element location " + format(self.element_location, "#x") + \
            " falls outside address range " + format(address_range_low, "#x") + \
            "-" + format(address_range_high, "#x"))

        # check for alignment and type
        self.aligned = block_aligned(self.element_location,
                                     self.erase_block_size)
        if not self.aligned:
            error("Element location " + format(self.element_location, "#x") + \
            " unaligned to block size " + format(self.erase_block_size, "#x"))
        self.valid_type = self.element_type >= \
            FFFF_ELEMENT_STAGE2_FIRMWARE_PACKAGE and \
            self.element_type <= FFFF_ELEMENT_DATA
        return self.in_range and self.aligned and self.valid_type

    def validate_against(self, other):
        # Validate an element header against another element header

        # Check for collision
        start_a = self.element_location
        end_a = start_a + self.element_length - 1
        start_b = other.element_location
        end_b = start_b + other.element_length - 1
        if end_b >= start_a and start_b <= end_a:
            self.collisions += [other.index]

        # Check for other duplicate entries per the specification:
        # "At most, one element table entry with a particular element
        # type, element ID, and element generation may be present in
        # the element table."
        if self.element_type == other.element_type and \
           self.element_id == other.element_id and \
           self.element_generation == other.element_generation:
            self.duplicates += [other.index]

    def same_as(self, other):
        """Determine if this TFTF is identical to another"""

        return self.element_type == other.element_type and \
            self.element_id == other.element_id and \
            self.element_generation == other.element_generation and \
            self.element_location == other.element_location and \
            self.element_length == other.element_length

    def write(self, filename):
        """Write an element to a file

        Write the FFFF element from the FFFF buffer as a binary blob to
        the specified file.
        """

        # Output the entire FFFF element blob (less padding)
        with open(filename, 'wb') as wf:
            wf.write(self.buf[self.element_location:
                              self.element_location +
                              self.element_length])
            print("Wrote", filename)

    def element_name(self, element_type):
        # Convert an element type into textual form

        if element_type == FFFF_ELEMENT_END_OF_ELEMENT_TABLE:
            name = "end of elements"
        elif element_type == FFFF_ELEMENT_STAGE2_FIRMWARE_PACKAGE:
            name = "stage 2 firmware"
        elif element_type == FFFF_ELEMENT_STAGE3_FIRMWARE_PACKAGE:
            name = "stage 3 firmware"
        elif element_type == FFFF_ELEMENT_IMS_CERTIFICATE:
            name = "IMS certificate"
        elif element_type == FFFF_ELEMENT_CMS_CERTIFICATE:
            name = "CMS certificate"
        elif element_type == FFFF_ELEMENT_DATA:
            name = "data"
        else:
            name = "?"
        return name

    def element_short_name(self, element_type):
        # Convert an element type into textual form
        if element_type in element_short_names:
            return element_short_names[element_type]

    def display_table_header(self):
        # Print the element table column names
        print("     Type       ID         Generation Location   Length")

    def display(self, expand_type):
        """Print an element header

        Print an element header in numeric form, optionally expanding
        the element type into a textual form
        """
        # Print the element data
        element_string = "  {0:2d}".format(self.index)
        element_string += " 0x{0:08x}".format(self.element_type)
        element_string += " 0x{0:08x}".format(self.element_id)
        element_string += " 0x{0:08x}".format(self.element_generation)
        element_string += " 0x{0:08x}".format(self.element_location)
        element_string += " 0x{0:08x}".format(self.element_length)
        if expand_type:
            element_string += \
                " ({0:s})".format(self.element_name(self.element_type))
        print(element_string)

        # Note any collisions and duplicates on separate lines
        if len(self.collisions) > 0:
            element_string = "           Collides with element(s):"
            for collision in self.collisions[self.index]:
                element_string += " {0:d}".format(collision)
            print(element_string)

        if len(self.duplicates) > 0:
            element_string = "           Duplicates element(s):"
            for duplicate in self.duplicates[self.index]:
                element_string += " {0:d}".format(duplicate)
            print(element_string)

        # Note any other errors
        element_string = ""
        if not self.in_range:
            element_string += "Out-of-range "
        if not self.aligned:
            element_string += "Misaligned "
        if not self.valid_type:
            element_string += "Invalid-type "
        if len(element_string) > 0:
            error(element_string)

    def display_element_data(self, header_index):
        """Print the data blob associated with this element

        Print an element header's TFTF info
        """
        if self.element_type != FFFF_ELEMENT_END_OF_ELEMENT_TABLE: 
            self.tftf_blob.display("element [{0:d}]".format(self.index), "  ")
            self.tftf_blob.display_data("element [{0:d}]".format(self.index), "  ")

    def write_map_payload(self, wf,  base_offset, prefix=""):
        """Display the field names and offsets of a single FFFF header"""
        elt_name = "{0:s}element[{1:d}].{2:s}".\
                   format(prefix, self.index,
                          self.element_short_name(self.element_type))

        # Dump the element starts
        if self.tftf_blob:
            # We've got a TFTF, pass that on to TFTF to display
            self.tftf_blob.write_map(wf, self.element_location, elt_name)
        elif self.element_type != FFFF_ELEMENT_END_OF_ELEMENT_TABLE:
            # Just print the element payload location
            wf.write("{0:s}  {1:08x}\n".
                     format(prefix, self.element_location))
