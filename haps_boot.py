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
import os
import subprocess
import threading
import Queue
import serial
import termios
import Adafruit_GPIO as GPIO
import Adafruit_GPIO.FT232H as FT232H

# haps_monitor class "monitor" status values
HAPS_MONITOR_TIMEOUT = 0
HAPS_MONITOR_STOP = 1
HAPS_MONITOR_PASS = 2
HAPS_MONITOR_FAIL = 3

# HAPS character timeout (1 second wait on characters, in 0.1 sec units)
HAPS_CHAR_TIMEOUT = 10

# HAPS boot timeout (~30 sec in character timeout counts)
HAPS_BOOT_TIMEOUT_COUNT = 30

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

# AdaFruit FT232H GPIO pins.
# Pins 0 to 7  = D0 to D7.
# Pins 8 to 15 = C0 to C7.
#
#                |<----- MPSSE ----->|
# Pin Signal GPIO UART  SPI     I2C
# --- ------ ---- ----  ---     ---
# J1.1  +5V  -    -     -       -
# J1.2  Gnd  -    -     -       -
# J1.3  D0   0    TxD   ClkOut  SCL
# J1.4  D1   1    RxD   MOSI    \_ SDA
# J1.5  D2   2    RTS#  MISO    /
# J1.6  D3   3    CTS#  SelOut
# J1.7  D4   4    DTR#
# J1.8  D5   5    DSR#
# J1.9  D6   6    DCD#
# J1.10 D7   7    RI#
#
# J2.1  C0   8
# J2.2  C1   9
# J2.3  C2   10
# J2.4  C3   11
# J2.5  C4   12
# J2.6  C5   13
# J2.7  C6   14
# J2.8  C7*  15
# J2.9  C8** -    -     -       -
# J2.10 C9** -    -     -       -
#
# * C7 connected to voltage divider
# ** C8, C9 drive red, green LEDs respectively

# The daughterboard reset line has a pull-up to 3v3. The "operate" position
# of switch DW1.4 is "ON" which shorts it to ground (i.e., "Run" = Low,
# "Reset" = high). Even though the FT232H can nominally drive the IO to 3v3,
# it would be better to instead simply tristate the IO and let the pull-up
# do the work.

# Daughterboard reset GPIO.
# Note: To simplify wiring, we use an IO pin on the connector having a
# ground pin
SPIROM_RESET_GPIO = 0

# Global to note that the Adafruit GPIO adapter has been initialized
adafruit_initialized = False

# Reset mechanisms
RESET_MANUAL = 0
RESET_FT232H = 1
reset_mode = RESET_FT232H

ft232h = None


def create_jlink_scripts(script_path, binfile, efuses):
    with open(os.path.join(script_path, JLINK_RESET_SCRIPT), "w") as fd:
        fd.write("w4 0xE000EDFC 0x01000001\n")
        fd.write("w4 0x40000100 0x1\n")
        fd.write("q\n")

    with open(os.path.join(script_path, JLINK_POST_RESET_SCRIPT), "w") as fd:
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


def remove_jlink_scripts(script_path):
    fname = os.path.join(script_path, JLINK_RESET_SCRIPT)
    if os.path.isfile(fname):
        os.remove(fname)
    fname = os.path.join(script_path, JLINK_POST_RESET_SCRIPT)
    if os.path.isfile(fname):
        os.remove(fname)


def haps_board_ready(chipit_name):
    # Wait for the HAPS board to finish initializing
    #
    # Monitor the ChipIT TTY and return when we see the "HAPS62>" prompt.
    # Will actively probe for the prompt after a while.
    # Returns True when synchronized, False if not
    have_prompt = False
    issued_boot_msg = False

    with serial.Serial(chipit_name, 230400, serial.EIGHTBITS,
                       serial.PARITY_NONE, serial.STOPBITS_ONE, 1) as chipit:
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
                        if "HAPS62>" in buffer:
                            have_prompt = True
                            break
                        if ch == "\n":
                            # We've already checked for the prompt, so just
                            # purge the buffer
                            buffer = ""
                            if not issued_boot_msg:
                                print("Waiting for HAPS...")
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
        return have_prompt


def init_adafruit_ft232h():
    # Apply or remove the reset from the SPIROM daughterboard
    # via a GPIO on the AdaFruit FT232H SPI/I2C/UART/GPIO breakout board.
    global ft232h, adafruit_initialized

    if not adafruit_initialized:
        # Temporarily disable the built-in FTDI serial driver on Mac & Linux
        # platforms.
        FT232H.use_FT232H()

        # Create an FT232H object that grabs the first available FT232H device
        # found.
        ft232h = FT232H.FT232H()

        # The daughterboard reset line has a pull-up to 3v3. The "operate"
        # position of switch DW1.4 is "ON" which shorts it to ground (i.e.,
        # "Run" = Low, "Reset" = high). Even though the FT232H can nominally
        # drive the IO to 3v3, it would be better to instead simply tristate
        # the IO and let the pull-up do the work.
        # For initialization, we'll drive it low.
        ft232h.setup(SPIROM_RESET_GPIO, GPIO.OUT)

        ft232h.output(SPIROM_RESET_GPIO, GPIO.LOW)

        # Note that we're now initialized
        adafruit_initialized = True


def reset_spirom_daughterboard_adafruit_ft232h(apply_reset):
    # Apply or remove the reset from the SPIROM daughterboard
    # via a GPIO on the AdaFruit FT232H SPI/I2C/UART/GPIO breakout board.
    global ft232h, adafruit_initialized
    if not adafruit_initialized:
        init_adafruit_ft232h()

    if apply_reset:
        # For "Reset", configure as input and let daughterboard pull-up
        # drive the line high.
        ft232h.setup(SPIROM_RESET_GPIO, GPIO.IN)
    else:
        # For "Run", configure as an output and drive low
        ft232h.setup(SPIROM_RESET_GPIO, GPIO.OUT)
        ft232h.output(SPIROM_RESET_GPIO, GPIO.LOW)


def reset_spirom_daughterboard_manual(apply_reset):
    # Apply or remove the reset from the SPIROM daughterboard
    # by prompting the user to manipulate the daughterboard
    # reset switch.
    if apply_reset:
        raw_input("set DW1.4 to the 'OFF' position and press Return")
    else:
        raw_input("set DW1.4 to the 'ON' position and press Return")


def reset_spirom_daughterboard(apply_reset, reset_mode):
    # Apply or remove the reset from the SPIROM daughterboard
    if reset_mode == RESET_MANUAL:
        reset_spirom_daughterboard_manual(apply_reset)
    elif reset_mode == RESET_FT232H:
        reset_spirom_daughterboard_adafruit_ft232h(apply_reset)
    else:
        raise ValueError("unknown daughterboard reset mode:", reset_mode)


def jtag_reset_phase(jlink_serial_no, script_path, reset_mode):
    # Apply the reset and run the "during-reset" JTAG script
    # (JLINK_RESET_SCRIPT)
    # Notes:
    #     1. Current version of JLinkExe doesn't return non-zero status on
    #        error, so "check_call" is there for future releases.
    #     2. We ues "check_output" to hide the debug spew from JLinkExe, but
    #        otherwise have no need for it.
    reset_spirom_daughterboard(True, reset_mode)
    subprocess.check_output(["JLinkExe", "-SelectEmuBySN", jlink_serial_no,
                            "-CommanderScript",
                            os.path.join(script_path, JLINK_RESET_SCRIPT)])


def jtag_post_reset_phase(jlink_serial_no, script_path, reset_mode):
    # Remove the reset and run the "post-reset" JTAG script
    # (JLINK_POST_RESET_SCRIPT)
    # NB: Current version of JLinkExe doesn't return non-zero status on error,
    # so "check_call" is there for future releases.
    reset_spirom_daughterboard(False, reset_mode)
    spew = subprocess.check_output(["JLinkExe", "-SelectEmuBySN",
                                   jlink_serial_no, "-CommanderScript",
                                   os.path.join(script_path,
                                                JLINK_POST_RESET_SCRIPT)])
    # Check the JLinkExe debug spew for errors
    if "WARNING: CPU could not be halted" in spew:
        raise IOError("CPU could not be halted")
    for line in spew.splitlines():
        if line.startswith("Downloading file ["):
            if not "]...O.K." in line:
                raise IOError("Unable to download [" + line.partition("[")[2])


def download_and_boot_haps(chipit_tty, script_path, jlink_sn, reset_mode,
                           bootrom_image_pathname, efuses):
    """ Wait for HAPS board readiness, then download and run a BootRom image.

    chipit_tty: typically "/dev/ttyUSBx"
    script_path: The path to where the JLink scripts will be written
    jlink_sn: The serial number of the JLink JTAG module (found on the bottom)
    bootrom_image_pathname: absolute or relative pathname to the BootRom.bin
                            file ("~" is not allowed)
    efuses: A list of eFuse names and values to write (see the global "efuses")

    Raises ValueError or IOError on failure, as appropriate
    """
    if '~' in bootrom_image_pathname:
        raise ValueError("BootRom pathanme cannot contain '~'")

    # Wait for the HAPS board to finish initializing
    if haps_board_ready(chipit_tty):
        # Create (scratch) JLink scripts from the efuse list and
        # bootrom_image file. (Required because JLink doesn't support
        # symbolic substitution in its script files
        create_jlink_scripts(script_path, bootrom_image_pathname, efuses)

        # Go through the JTAG download and boot sequence
        jtag_reset_phase(jlink_sn, script_path, reset_mode)
        jtag_post_reset_phase(jlink_sn, script_path, reset_mode)

        # Clean up the scratch JLink scripts
        remove_jlink_scripts(script_path)
    else:
        raise IOError("HAPS board unresponsive")


class WorkerThread(threading.Thread):
    """ A worker thread to read the daughterboard dbgserial in the background

        Output is done by placing captured lines into the Queue passed in
        result_q.

        Ask the thread to stop by calling its join() method.
    """
    def __init__(self, dbgser_tty_name, result_q, stop_strings=None):
        super(WorkerThread, self).__init__()
        self.dbgser_tty_name = dbgser_tty_name
        self.result_q = result_q
        self.stop_strings = stop_strings
        self.stoprequest = threading.Event()

    def run(self):
        if os.name != "posix":
            raise ValueError("Can only be run on Posix systems")
            return

        buffer = ""
        # While PySerial would be preferable and more machine-independant,
        # it does not support echo suppression
        with open(self.dbgser_tty_name, 'r+') as dbgser:
            # Config the debug serial port
            oldattrs = termios.tcgetattr(dbgser)
            newattrs = termios.tcgetattr(dbgser)
            newattrs[4] = termios.B115200  # ispeed
            newattrs[5] = termios.B115200  # ospeed
            newattrs[3] = newattrs[3] & ~termios.ICANON & ~termios.ECHO
            newattrs[6][termios.VMIN] = 0
            newattrs[6][termios.VTIME] = 10
            termios.tcsetattr(dbgser, termios.TCSANOW, newattrs)

            # As long as we weren't asked to stop, try to capture dbgserial
            # output and push each line up the result queue.
            try:
                while not self.stoprequest.isSet():
                    ch = dbgser.read(1)
                    if ch:
                        if ch == "\n":
                            # Push the line (sans newline) into our queue
                            # and clear the buffer for the next line.
                            self.result_q.put(buffer)
                            buffer = ""
                        elif ch != "\r":
                            buffer += ch
            except IOError:
                pass
            finally:
                # Restore previous settings
                termios.tcsetattr(dbgser, termios.TCSAFLUSH, oldattrs)
                # Flush any partial buffer
                if buffer:
                    self.result_q.put(buffer)

    def join(self, timeout=None):
        # Automatically stop our selves when the client joins to us
        self.stoprequest.set()
        super(WorkerThread, self).join(timeout)


def download_and_boot_haps_capture(chipit_tty, script_path, jlink_sn,
                                   reset_mode, bootrom_image_pathname, efuses,
                                   dbgser_tty_name, timeout,
                                   pass_strings, fail_strings, stop_strings):
    """Wait for HAPS board, then download/run a BootRom image, capturing output

    This is a superset of "download_and_boot_haps" that captures the debug
    serial output
    Arguments:
        chipit_tty:
            The TTY used by the HAPS board ChipIT supervisor (typically
            "/dev/ttyUSBx")
        script_path:
            The path to where the JLink scripts will be written
        jlink_sn:
            The serial number of the JLink JTAG module (found on the bottom
            of the JLink module)
        bootrom_image_pathname:
             Absolute or relative pathname to the BootRom.bin file ("~" is
             not allowed)
        efuses:
             A list of eFuse names and values to write (see the global
             "efuses")
        dbgser_tty_name:
             The TTY used by the daugherboard debug serial output
        timeout:
             How long, in seconds, to wait before concluding that serial
             output from the BootRom has ceased.
        stop_strings:
             (optional) List of strings to look for in the debug spew. If any
             are encountered, capture stops. (The stop string is retained/
             outputed)

    Returns: A list of the debug spew, one line per entry.
    """
    # Start the debug serial reader background thread
    result_q = Queue.Queue()
    dbgser_monitor = WorkerThread(dbgser_tty_name, result_q)
    dbgser_monitor.start()

    # Download and launch the test image
    download_and_boot_haps(chipit_tty, script_path, jlink_sn, reset_mode,
                           bootrom_image_pathname, efuses)

    # Harvest the debug serial until we see a stop string or it times out.
    stop = False
    capture = []
    while not stop:
        # Use a blocking 'get' from the queue
        try:
            result = result_q.get(True, timeout)
        except Queue.Empty:
            stop = True
        else:
            # Display/capture the line of debug spew
            capture.append(result)

            # Check for landmarks in the debug spew
            if fail_strings:
                # Stop on any failure string
                for term in fail_strings:
                    if term in result:
                        stop = True
                        break
            if stop_strings:
                # Stop on any stop string
                for term in stop_strings:
                    if term in result:
                        stop = True
                        break

    # Stop our worker thread
    dbgser_monitor.join()

    return capture


class haps_capture_monitor(object):
    """ Encapsulation of a HAPS download-boot-monitor-stop cycle
    """
    def __init__(self, chipit_tty, script_path, jlink_sn, reset_mode,
                 bootrom_image_pathname, efuses, dbgser_tty_name, timeout,
                 fail_strings, stop_strings):
        """Wait for HAPS board, then download/run a BootRom image

        Use "haps_capture_monitor.monitor to monitor the debug spew

        Arguments:
            chipit_tty:
                The TTY used by the HAPS board ChipIT supervisor (typically
                "/dev/ttyUSBx")
            script_path:
                The path to where the scratch JLink scripts will be written
            jlink_sn:
                The serial number of the JLink JTAG module (found on the bottom
                of the JLink module)
            bootrom_image_pathname:
                 Absolute or relative pathname to the BootRom.bin file ("~" is
                 not allowed)
            efuses:
                A list of eFuse names and values to write (see the global
                 "efuses")
            dbgser_tty_name:
                 The TTY used by the daugherboard debug serial output
            timeout:
                 How long, in seconds, to wait before concluding that serial
                 output from the BootRom has ceased. (This will result in a
                 "t"imeout status.)
            fail_strings:
                 List of failure strings to look for in the debug spew. If any
                 are encountered, capture stops.
            stop_strings:
                 List of strings to look for in the debug spew. If any
                 are encountered, capture stops.
        """
        self.chipit_tty = chipit_tty
        self.script_path = script_path
        self.jlink_sn = jlink_sn
        self.reset_mode = reset_mode
        self.bootrom_image_pathname = bootrom_image_pathname
        self.efuses = efuses
        self.dbgser_tty_name = dbgser_tty_name
        self.timeout = timeout
        self.fail_strings = fail_strings
        self.stop_strings = stop_strings
        self.result_q = None
        self.dbgser_monitor = None

        # Start the debug serial reader background thread
        self.result_q = Queue.Queue()
        self.dbgser_monitor = WorkerThread(self.dbgser_tty_name, self.result_q)
        self.dbgser_monitor.start()

        # Download and launch the test image
        download_and_boot_haps(self.chipit_tty, self.script_path,
                               self.jlink_sn, self.reset_mode,
                               self.bootrom_image_pathname, self.efuses)

    def __del__(self):
        """ Stop our worker thread """
        # Stop our worker thread
        if self.dbgser_monitor:
            self.dbgser_monitor.join()
            self.dbgser_monitor = None
        self.result_q = None

    def __enter__(self):
        """ Compatability with 'with' statement """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Compatability with 'with' statement """
        self.__del__()

    def monitor(self, pass_strings=None):
        """Capture output from HAPS board until encountering a landmark string

        Parameters:
            pass_strings An optional set of landmark strings to check for a
                "test passed" condition. Since the norm for pass strings is
                that all must be present for the test run to succeed, the
                caller typically removes strings from this list as we encounter
                them. Since the fail and stop strings operate on first-
                occurrance, they can be treated as static for the life of the
                test and are cached in the class.

        Returns: On encountering any landmark string, returns a 3-element
            tuple consisting of:
            - The reason the capture stopped (timeout, stop, pass or fail)
            - The index into the appropriate xxx_strings array for the matched
              string. (This will be zero in the case of a test timeout)
            - A list of the debug spew captured thus far, one line per entry.
        """
        # Harvest the debug serial until we see a landmark string or it
        # times out.
        stop = False
        capture = []
        status = HAPS_MONITOR_TIMEOUT
        index = 0
        while not stop:
            # Use a blocking 'get' from the queue
            try:
                result = self.result_q.get(True, self.timeout)
            except Queue.Empty:
                # Timeout - test died "silently"
                stop = True
            else:
                # Save the line of debug spew
                capture.append(result)

                # Check for landmarks in the debug spew
                if pass_strings:
                    # Stop on a pass string
                    for index, term in enumerate(pass_strings):
                        if term in result:
                            status = HAPS_MONITOR_PASS
                            stop = True
                            break
                elif self.fail_strings and not stop:
                    # Stop on any failure string
                    for index, term in enumerate(self.fail_strings):
                        if term in result:
                            status = HAPS_MONITOR_FAIL
                            stop = True
                            break
                elif self.stop_strings and not stop:
                    # Stop on any stop string
                    for index, term in enumerate(self.stop_strings):
                        if term in result:
                            status = HAPS_MONITOR_STOP
                            stop = True
                            break

        return [status, index, capture]
