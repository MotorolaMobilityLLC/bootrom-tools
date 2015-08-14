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

from __future__ import print_function
import sys
import os
import termios
import fcntl
import subprocess
from util import error

# Program return values
PROGRAM_SUCCESS = 0
PROGRAM_WARNINGS = 1
PROGRAM_ERRORS = 2

# HAPS character timeout (1 second wait on characters, in 0.1 sec units)
HAPS_CHAR_TIMEOUT = 10

# HAPS boot timeout (~30 sec in character timeout counts)
HAPS_BOOT_TIMEOUT_COUNT = 300

JLINK_RESET_SCRIPT = "cmd-jlink-start-1"  # "cmd-jlink-start-1"
JLINK_POST_RESET_SCRIPT = "cmd-jlink-start-2"  # "cmd-jlink-start-2"

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
    "IMS8": 0x00000000}


def create_jlink_scripts(script_path, binfile, efuses):
    if script_path[-1] != "/":
        script_path += "/"

    with open(script_path + JLINK_RESET_SCRIPT, "w") as fd:
        fd.write("w4 0xE000EDFC 0x01000001\n")
        fd.write("w4 0x40000100 0x1\n")
        fd.write("q\n")

    with open(script_path + JLINK_POST_RESET_SCRIPT, "w") as fd:
        fd.write("halt\n")
        fd.write("loadbin {0:s} 0x00000000\n".format(binfile))
        fd.write("w4 0xE000EDFC 0x01000000\n")

        # Set ARA_VID:
        fd.write("w4 0x40000700 0x{0:08x}\n".format(efuses["VID"]))

        # Set ARA_PID:
        fd.write("w4 0x40000704 0x{0:08x}\n".format(efuses["PID"]))

        # Set Serial No (SN0, SN1):
        fd.write("w4 0x40084300 0x{0:08x}\n".format(efuses["SN0"]))
        fd.write("w4 0x40084304 0x{0:08x}\n".format(efuses["SN1"]))

        # Set IMS (IMS0..IMS8):
        fd.write("w4 0x40084100 0x{0:08x}\n".format(efuses["IMS0"]))
        fd.write("w4 0x40084104 0x{0:08x}\n".format(efuses["IMS1"]))
        fd.write("w4 0x40084108 0x{0:08x}\n".format(efuses["IMS2"]))
        fd.write("w4 0x4008410C 0x{0:08x}\n".format(efuses["IMS3"]))
        fd.write("w4 0x40084110 0x{0:08x}\n".format(efuses["IMS4"]))
        fd.write("w4 0x40084114 0x{0:08x}\n".format(efuses["IMS5"]))
        fd.write("w4 0x40084118 0x{0:08x}\n".format(efuses["IMS6"]))
        fd.write("w4 0x4008411c 0x{0:08x}\n".format(efuses["IMS7"]))
        fd.write("w4 0x40084120 0x{0:08x}\n".format(efuses["IMS8"]))

# Pulse the Cortex reset
        fd.write("w4 0x40000000 0x1\n")
        fd.write("w4 0x40000100 0x1\n")
        fd.write("q\n")


def hit_any_key(prompt):
    oldterm = termios.tcgetattr(sys.stdin)
    newattr = termios.tcgetattr(sys.stdin)
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(sys.stdin, termios.TCSANOW, newattr)

    oldflags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

    sys.stdout.write(prompt)
    try:
        while 1:
            try:
                sys.stdin.read(1)
                break
            except IOError:
                pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, oldterm)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, oldflags)


def haps_board_ready(chipit_name):
    # Wait for the HAPS board to finish initializing
    #
    # Monitor the ChipIT TTY and return when we see the "HAPS62>" prompt.
    # Will actively probe for the prompt after a while.
    # Returns True when synchronized, False if not
    have_prompt = False
    issued_boot_msg = False
    with open(chipit_name, 'r+') as chipit:
        # Config the ChipIt serial port
        oldattrs = termios.tcgetattr(chipit)
        newattrs = termios.tcgetattr(chipit)
        # Apply new settings

        newattrs[4] = termios.B230400  # ispeed
        newattrs[5] = termios.B230400  # ospeed
        newattrs[3] = newattrs[3] & ~termios.ICANON & ~termios.ECHO
        newattrs[6][termios.VMIN] = 0
        newattrs[6][termios.VTIME] = 10
        termios.tcsetattr(chipit, termios.TCSANOW, newattrs)

        # Scan TTY for the "HAPS62>" prompt
        num_timeouts = 0
        num_attempts = 0
        buffer = ""
        try:
            while (not have_prompt) and (num_attempts < 2):
                # Poke HAPS.
                # If it's already booted, it'll issue a prompt which we'll
                # capture immediately. If not, the poke gets lost in the
                # aether while the HAPS boots up. The boot sequence ends in
                # the HAPS prompt
                chipit.write("\r\n")

                # Look for the prompt, waiting through the bootup sequence
                # as needed
                while not have_prompt:
                    ch = chipit.read(1)
                    if ch:
                        buffer += ch
                        num_timeouts = 0
                        if buffer.find("HAPS62>") != -1:
                            have_prompt = True
                            break
                        if ch == "\n":
                            # We've already checked for the prompt, so just
                            # purge the buffer
                            buffer = ""
                            if not issued_boot_msg:
                                print("HAPS is booting...")
                                issued_boot_msg = True
                    else:
                        # Read timed out
                        num_timeouts += 1
                        if num_timeouts > HAPS_BOOT_TIMEOUT_COUNT:
                            print("No response from HAPS, retrying...")
                            # set up for the next attempt
                            print("Please ensure the HAPS board is powered")
                            num_attempts += 1
                            num_timeouts = 0
                            break
        except IOError:
            pass
        finally:
            # Restore previous settings
            termios.tcsetattr(chipit, termios.TCSAFLUSH, oldattrs)
        return have_prompt


def reset_spirom_daughterboard(apply_reset):
    # Apply or remove the reset from the SPIROM daughterboard
    # NOTE: Manual version
    if apply_reset:
        print("set DW1.4 to the 'OFF' position")
    else:
        print("set DW1.4 to the 'ON' position")
    hit_any_key("Press any key when done")


def jtag_reset_phase(jlink_serial_no, script_path):
    # JTAG sequence to be applied to the SPIROM daugherboard (reset)
    script_path += JLINK_RESET_SCRIPT

    # Apply the reset and run the JTAG script
    reset_spirom_daughterboard(True)
    subprocess.call(["JLinkExe", "-SelectEmuBySN", jlink_serial_no,
                     "-CommanderScript", script_path])


def jtag_post_reset_phase(jlink_serial_no, script_path):
    # JTAG sequence to be applied to the SPIROM daugherboard (no reset)
    script_path += JLINK_POST_RESET_SCRIPT

    # Remove the reset and run the JTAG script
    reset_spirom_daughterboard(False)
    subprocess.call(["JLinkExe", "-SelectEmuBySN", jlink_serial_no,
                     "-CommanderScript", script_path])


def download_and_boot_haps(chipit_tty, script_path, jlink_sn,
                           bootrom_image_pathname, efuses):
    """ Wait for HAPS board readiness, then download and run a BootRom image.

    chipit_tty: typically "/dev/ttyUSBx"
    script_path: The path to where the JLink scripts will be written (ideally
                 ending in a "/")
    jlink_sn: The serial number of the JLink JTAG module (found on the bottom)
    bootrom_image_pathname: absolute or relative pathname to the BootRom.bin
                            file ("~" is not allowed)
    efuses: A list of eFuse names and values to write (see the global "efuses")

    Returns True on success, False on failure
    """
    if bootrom_image_pathname.find("~") != -1:
        error("BootRom pathanme cannot contain '~'")
        return False

    if script_path[-1] != "/":
        script_path += "/"

    # Create (scratch) JLink scripts from the efuse list and bootrom_image
    # file. (Required because JLink doesn't support symbolic substitution
    # in its script files
    create_jlink_scripts(script_path, bootrom_image_pathname, efuses)

    # Wait for the HAPS board to finish initializing
    if haps_board_ready(chipit_tty):
        # Go through the JTAG download and boot sequence
        jtag_reset_phase(jlink_sn, script_path)
        jtag_post_reset_phase(jlink_sn, script_path)
        return True
    return False

