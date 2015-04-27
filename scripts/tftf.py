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

import sys, os, argparse, struct, shutil
from string import rfind
from struct import *
from time import gmtime, strftime
import binascii  #*****

# TFTF section types
TFTF_SECTION_TYPE_END_OF_DESCRIPTORS    = 0x00
TFTF_SECTION_TYPE_RAW_CODE_BLOCK        = 0x01
TFTF_SECTION_TYPE_RAW_DATA_BLOCK        = 0x02
TFTF_SECTION_TYPE_COMPRESSED_CODE_BLOCK = 0x03
TFTF_SECTION_TYPE_COMPRESSED_DATA_BLOCK = 0x04
TFTF_SECTION_TYPE_MANIFEST              = 0x05
TFTF_SECTION_TYPE_SIGNATURE_BLOCK       = 0xff

# Other TFTF header constants (mostly field sizes)
TFTF_SENTINEL               = "TFTF"
TFTF_TIMESTAMP_LENGTH       = 16
TFTF_FW_PKG_NAME_LENGTH     = 48
TFTF_HDR_LENGTH             = 512
TFTF_MAX_SECTIONS           = 25
TFTF_PADDING                = 12
TFTF_SECTION_HDR_LENGTH     = 16

# Offsets into the TFTF header
TFTF_HDR_OFF_SENTINEL       = 0x00
TFTF_HDR_OFF_TIMESTAMP      = 0x04
TFTF_HDR_OFF_NAME           = 0x14
TFTF_HDR_OFF_LENGTH         = 0x44
TFTF_HDR_OFF_SECTIONS       = 0x64  # Start of sections array

TFTF_FILE_EXTENSION         = ".bin"

# TFTF validity assesments
TFTF_VALID                  = 0
TFTF_INVALID                = 1
TFTF_VALID_WITH_COLLISIONS  = 2


# TFTF Section representation
#
class TftfSection:

    # Constructor will set the section length to the length of the file
    #
    def __init__(self, prog, section_type, filename = None, copy_offset = 0):
        self.prog = prog
        self.section_length = 0
        self.expanded_length = 0
        self.copy_offset = copy_offset
        self.section_type = section_type
        self.filename = filename

        # Try to size the section length from the section input file
        if filename != None:
            try:
                statinfo = os.stat(filename)
                have_info = True
            except:
                print self.prog, "Error -", filename, " is invalid or missing"
                have_info = False
            else:
                if have_info:
                    # TODO: Lengths will be different if/when we support
                    # compression:
                    # - section_length will shrink to the compressed size
                    # - expanded_length will remain the input file length
                    self.section_length = statinfo.st_size
                    self.expanded_length = statinfo.st_size
 

    # Unpack a section header from a TFTF header buffer
    #
    # Returns False on section_end, True otherwise
    #
    def unpack(self, section_buf, section_offset):
        section_hdr = unpack_from("<LLLL", section_buf, section_offset)
        self.section_length = section_hdr[0]
        self.expanded_length = section_hdr[1]
        self.copy_offset = section_hdr[2]
        self.section_type = section_hdr[3]
        return self.section_type != TFTF_SECTION_TYPE_END_OF_DESCRIPTORS


    # Pack a section header into a TFTF header buffer
    #
    # Returns The section_offset for the next section
    #
    def pack(self, buf, offset):
        pack_into("<LLLL", buf, offset,
                  self.section_length,
                  self.expanded_length,
                  self.copy_offset,
                  self.section_type)
        return offset + TFTF_SECTION_HDR_LENGTH


    # Update a section header
    #
    # Use this to sweep through the list of sections and update the 
    # section copy_offsets to concatenate sections (except where the
    # user has specified an offset).
    #
    # Returns copy_offset + section length.
    #
    def update(self, copy_offset):
        if self.copy_offset == 0:
               self.copy_offset = copy_offset
        return self.section_length + self.copy_offset;


    # Convert a section type into textual form
    #
    def section_name(self, section_type):
        if section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
            name = "end of descriptors"
        elif section_type == TFTF_SECTION_TYPE_RAW_CODE_BLOCK:
            name = "code"
        elif section_type == TFTF_SECTION_TYPE_RAW_DATA_BLOCK:
            name = "data"
        elif section_type == TFTF_SECTION_TYPE_COMPRESSED_CODE_BLOCK:
            name = "compressed code"
        elif section_type == TFTF_SECTION_TYPE_COMPRESSED_DATA_BLOCK:
            name = "compressed data"
        elif section_type == TFTF_SECTION_TYPE_MANIFEST:
            name = "manifest"
        elif section_type == TFTF_SECTION_TYPE_SIGNATURE_BLOCK:
            name = "signature"
        else:
            name = "?"
        return name


    # Append a section's file to the output file
    #
    def write(self, writefile):
         if self.filename != None:
             with open(self.filename,'rb') as readfile:
                 shutil.copyfileobj(readfile, writefile, 1024*1024*10)
                 readfile.close()



    # Format the section table column names
    #
    # Returns the column header for the section table (no indentation)
    #
    def display_table_header(self):
        return "Length     Exp. Len   Offset     Type"




    # Format a section header in human-readable form
    #
    # Returns the column header for the section table (no indentation)
    def display(self, expand_type):
        section_string = "0x{0:08x}".format(self.section_length)
        section_string += " 0x{0:08x}".format(self.expanded_length)
        section_string += " 0x{0:08x}".format(self.copy_offset)
        section_string += " 0x{0:08x}".format(self.section_type)
        if expand_type:
            section_string += " ({0:s})".format(
                              self.section_name(self.section_type))
        return section_string



    # Display a section header in human-readable form
    #
    def display_mutli(self, section_num, collisions = None):
        if self.section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
            print "    Section [{0:2d}-{1:d}] (unused):".format(
                section_num, TFTF_MAX_SECTIONS)
        else:
            section_end = self.copy_offset + self.expanded_length - 1

            # Format the title line for the section...
            section_title ="    Section [{0:2d}] (0x{1:08x}..0x{2:08x}):".format(
                section_num,
                self.copy_offset,
                section_end)

            # ...and append any collisions
            if collisions != None and len(collisions) > 0:
                section_title += " Collides with:"
                for collision in collision_row:
                    section_title += " {0:d}".format(collisions)

            # Print the section title and details
            print section_title
            print "        section_length  0x{0:08x}".format(
                self.section_length)
            print "        expanded_length 0x{0:08x}".format(
                self.expanded_length)
            print "        copy_offset     0x{0:08x}".format(
                self.copy_offset)
            print "        section_type    0x{0:08x} ({1})".format(
                self.section_type,
                self.section_name(self.section_type))




# TFTF representation
#
class Tftf:
    def __init__(self, prog, filename = None):
        # Private fields
        self.prog = prog
        self.tftf_header_buf = bytearray(TFTF_HDR_LENGTH)
        self.collisions = []
        self.collisions_found = False
        self.header_validity = TFTF_INVALID

        # Header fields
        self.sentinel = 0
        self.timestamp = ""
        self.firmware_package_name = ""
        self.load_length = 0
        self.load_base = 0
        self.expanded_length = 0
        self.start_location = 0
        self.unipro_mfg_id = 0
        self.unipro_pid = 0
        self.ara_vid = 0
        self.ara_pid = 0
        self.sections = []

        if filename != None:
            self.load_tftf_file(filename)


    # Try to import a TFTF header and/or file
    #
    #  If "buf" is None, then we only import the TFTF header.  However, if
    #  buf is supplied (usually a memoryview into a larger buffer), the
    #  entire TFTF file is also imported into the buffer.  This is to allow
    #  for cases where the caller needs to determine the TFTF characteristics
    #  before creating their buffer.
    #
    def load_tftf_file(self, filename, buf = None, buf_size = 0, offset = 0):
        success = True
        if filename != None:
            # Try to open the file, and if that fails, try appending the
            # extension.
            names = (filename, filename + TFTF_FILE_EXTENSION)
            rf = None
            for i in range(len(names)):
                try:
                  rf = open(names[i], 'rb')
                  break
                except:
                  rf = None

            if rf == None:
                print self.prog, "can't find TFTF file", filename
                success = False
            else:
                # Determine the size of the TFTF file and ensure that it
                # fits in the available buffer
                rf.seek(0, 2)
                file_size = rf.tell()

                # Optionally read the entire TFTF blob into the caller's buffer
                if buf != None:
                    rf.seek(0, 0)
                    if (offset + file_size) >= buf_size:
                        print self.prog, \
                              "Error:", filename, "too big for buffer"
                        success = False
                    else:
                        # Read and display the TFTF file.
                        numread = rf.readinto(buf[offset:])

                # Read and display the TFTF header for local use.
                rf.seek(0, 0)
                self.tftf_header_buf = rf.read(TFTF_HDR_LENGTH)
                rf.close()
                self.unpack()
        return success


    # Unpack a TFTF header from a buffer
    #
    def unpack(self):
        tftf_hdr = unpack_from("<4s16s48sLLLLLLLL", self.tftf_header_buf)
        self.sentinel = tftf_hdr[0]
        self.timestamp = tftf_hdr[1]
        self.firmware_package_name = tftf_hdr[2]
        self.load_length = tftf_hdr[3]
        self.load_base = tftf_hdr[4]
        self.expanded_length = tftf_hdr[5]
        self.start_location = tftf_hdr[6]
        self.unipro_mfg_id = tftf_hdr[7]
        self.unipro_pid = tftf_hdr[8]
        self.ara_vid = tftf_hdr[9]
        self.ara_pid = tftf_hdr[10]

        # Parse the table of section headers
        section_offset = TFTF_HDR_OFF_SECTIONS
        copy_offset = tftf_hdr[4]
        for section_index in range(TFTF_MAX_SECTIONS):
            section = TftfSection(self.prog, 0, None, 0)
            if section.unpack(self.tftf_header_buf, section_offset):
                self.sections.append(section)
                section_offset += TFTF_SECTION_HDR_LENGTH
            else:
                # Stop on the first unused section
                break;
        self.sniff_test()


    # Pack the TFTF header into a buffer
    #
    # Pack the TFTF header members into a TFTF header buffer, prior
    # to writing the buffer out to a file.
    #
    def pack(self):
        # Populate the fixed part of the TFTF header.
        # (Note that we need to break up the packing because the "s" format
        # doesn't zero-pad a string shorter than the field width)
        timestamp = strftime("%Y%m%d %H%M%S", gmtime())
        pack_into("<4s16s", self.tftf_header_buf, 0,
             self.sentinel,
             timestamp)
        if self.firmware_package_name != None:
            pack_into("<48s", self.tftf_header_buf, TFTF_HDR_OFF_NAME,
                 self.firmware_package_name)
        pack_into("<LLLLLLLL", self.tftf_header_buf, TFTF_HDR_OFF_LENGTH,
             self.load_length,
             self.load_base,
             self.expanded_length,
             self.start_location,
             self.unipro_mfg_id,
             self.unipro_pid,
             self.ara_vid,
             self.ara_pid)

        # Pack the section headers into the TFTF header buffer
        offset = TFTF_HDR_OFF_SECTIONS
        for section in self.sections:
            offset = section.pack(self.tftf_header_buf, offset)


    # Add a new section to the section table
    #
    # (This would be called by "create-tftf" while/after parsing section
    # parameters)
    #
    # Returns True on success, False otherwise
    #
    def add_section(self, section_type, filename, copy_offset = 0):
        if len(self.sections) < TFTF_MAX_SECTIONS:
            self.sections.append(TftfSection(self.prog, section_type,
                                             filename, copy_offset))
            return True
        else:
            return False


    # Update the copy_offsets in the section table and the load_length
    #
    # (This would be called by "create-tftf" after parsing all of the
    # parameters)
    #
    def update_section_table_offsets(self):
        self.load_length = 0
        copy_offset = 0
        for section in self.sections:
            copy_offset = section.update(copy_offset)
            self.load_length += section.section_length;

        # Update the total length obtained from scanning the files above.
        # TODO: Change expanded_length if/when we support compression
        self.expanded_length = copy_offset;


    # Scan the TFTF section table for collisions
    #
    # This would be called by "create-ffff" after parsing all of the
    # parameters and calling update_ffff_sections().
    #
    # Returns True if collisions were detected, False otherwise
    #
    def check_for_collisions(self):
        # Only calculate the collisions once
        if self.collisions == []:
            for comp_a in range(len(self.sections)):
                collision = []
                # extract sections[comp_a]
                section_a = self.sections[comp_a]
                if section_a.section_type == \
                        TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                    break
                start_a = section_a.copy_offset
                end_a = start_a + section_a.section_length - 1
                for comp_b in range(len(self.sections)):
                    # skip checking one's self
                    if comp_a != comp_b:
                        # extract sections[comp_b]
                        section_b = self.sections[comp_b]
                        if section_b.section_type  == \
                                TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                            break
                        start_b = section_b.copy_offset
                        end_b = start_b + section_b.section_length - 1
                        if end_b >= start_a and \
                           start_b <= end_a:
                            self.collisions_found = True
                            collision += [comp_b]
                self.collisions += [collision]
        return self.collisions_found


    # Sniff-test the TFTF header
    #
    # Perform a quick validity check of the header.  Generally done wehn
    # importing an existing TFTF file.
    #
    def sniff_test(self):
        self.header_validity = TFTF_VALID

        # Valid sentinel? (This should also subsume the "erased block" test)
        if self.sentinel != TFTF_SENTINEL:
            self.header_validity = TFTF_INVALID
        else:
            # check for collisions
            if self.check_for_collisions():
                self.header_validity = TFTF_VALID_WITH_COLLISIONS

        return self.header_validity


    # Go/no-go decision on a TFTF header
    #
    def is_good(self):
        return self.header_validity != TFTF_INVALID


    # Post-process the TFTF header
    #
    # Process the TFTF header (called by "create-tftf" after processing all
    # arguments)
    #
    def post_process(self):
        """Post-process the TFTF header"""

        self.sentinel == TFTF_SENTINEL
            
        # Update the section table copy_offsets and check for collisions
        self.sentinel = TFTF_SENTINEL
        self.update_section_table_offsets()
        self.check_for_collisions()
        self.timestamp = strftime("%Y%m%d %H%M%S", gmtime())

        # Trim the name to length
        if self.firmware_package_name != None:
            self.firmware_package_name = \
                self.firmware_package_name[0:TFTF_FW_PKG_NAME_LENGTH]

        # Determine the validity
        self.sniff_test()




    # Create/write the TFTF file
    #
    #  Returns True on success, False on failure
    #
    def write(self, out_filename):
        """Create the TFTF file"""

        success = True
        # Prepare the output buffer
        self.pack()

        # Ensure the output file ends in the default TFTF file extension if
        # the user hasn't specified their own extension.
        if rfind(out_filename, ".") == -1:
            out_filename += TFTF_FILE_EXTENSION

        try:
            with open(out_filename, 'wb') as wf:
                # Write the TFTF header
                wf.write(self.tftf_header_buf)

                # Concatenate the input files
                for section in self.sections:
                    section.write(wf)


            # verify the file is the correct length
            try:
                statinfo = os.stat(out_filename)
                if statinfo.st_size != self.load_length + TFTF_HDR_LENGTH:
                    print self.prog, "Error -", out_filename ,"has wrong length"
            except:
                print self.prog, "Error - can't ge info on", out_filename

        except:
            print self.prog, "unable to write", out_filename
            success = False
        else:
            if success:
                print self.prog, "Wrote", out_filename
            else:
                print self.prog, "Failed to write", out_filename
            return success


    # Display a single TFTF header in human-readable form
    #
    def display(self, filename = None):
        """Display a single TFTF header"""

        # Dump the contents of the fixed part of the TFTF header
        if filename != None:
            print "TFTF Header for:", filename
        else:
            print "TFTF Header:"
        print "    sentinel:         ", self.sentinel
        print "    timestamp:         {0:16s}".format(self.timestamp)
        print "    fw_pkg_name:       {0:48s}".format(self.firmware_package_name)
        print "    load_length:       0x{0:08x}".format(self.load_length)
        print "    load_base:         0x{0:08x}".format(self.load_base)
        print "    expanded_length:   0x{0:08x}".format(self.expanded_length)
        print "    start_location:    0x{0:08x}".format(self.start_location)
        print "    unipro_mfg_id:     0x{0:08x}".format(self.unipro_mfg_id)
        print "    unipro_product_id: 0x{0:08x}".format(self.unipro_pid)
        print "    ara_vendor_id:     0x{0:08x}".format(self.ara_vid)
        print "    ara_product_id:    0x{0:08x}".format(self.ara_pid)

        # Dump the table of section headers
        section_offset = TFTF_HDR_OFF_SECTIONS  # offset within tftf_hdr
        copy_offset = self.load_base
        print "    Section Table:"
        print "      [] {0:s}".format(self.sections[0].display_table_header())
        for index in range(len(self.sections)):
            section = self.sections[index]
            print "      {0:2d} {1:s}".format(
                   index,
                   section.display(True))

            # Note any collisions on a separate line
            if len(self.collisions[index]) > 0:
                section_string = "           Collides with section(s):"
                for collision in self.collisions[index]:
                    section_string += " {0:s}".format(collision)
                print section_string
            if section.section_type == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS:
                break
        # Note any unused sections
        num_unused_sections = TFTF_MAX_SECTIONS - len(self.sections)
        if num_unused_sections > 1:
            print "      {0:2d} (unused)".format(len(self.sections))
            print "       :    :"
        if num_unused_sections > 0:
            print "      {0:2d} (unused)".format(TFTF_MAX_SECTIONS-1)
        print " "


