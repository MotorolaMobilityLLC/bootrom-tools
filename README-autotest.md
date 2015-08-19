# bootrom-tools (Test Automation)
## Python scripts for testing BootRom images, logging results, determining pass-fail
This describes the Python scripts for loading and testing BootRom images with
a HAPS-62 board.  Each script will list its parameters if it is called with
the flag `--help`.

The scripts are:

* **autoboot** Loads and runs a BootRom image and displays the debug output on
stdout, or optionally saves it in a log file.
* **run-bootrom-tests** Executes a set of tests from a simple script file,
validating whether each test passed of failed. Output is sent to stdout or
optionally to a log file
* **create-bootrom-test-suite** Creates a folder containing a test script and
optionally a series of altered binary images. This folder becomes a
self-contained run-bootrom-tests test suite.
* **hexpatch** A general-purpose (binary) file patching tool. (Used by
create-bootrom-test-suite to create known-defective binary images for
testing).

### Dependencies
The *autoboot* script supports the Adafruit FT232H USB->GPIO adapter for
controlling the reset on the HAPS-62 SPIROM daughterboard. While its use is
optional, you must install their drivers to keep Python happy. See Appendix A
for installation instructions.

The HAPS-2 *ChipIT* supervisor/monitor is one of the 4 USB serial ports on the
*Future Devices FT232R USB UART*, which appears as /dev/ttyUSBx. In local
testing, this has consistently been /dev/ttyUSB4. However, adding the Adafruit
adapter changed the enumeration order. You will need to do some investigation
with *putty* or other comm. application to determine how things are connected
on your system. The HAPS-2 supervisor monitor is configured 230400-8-n-1.


### Hardware Configuration
    +------+                         +-----------+
    | Host |                         |  HAPS-62  |
    |      |                         |           |
    |      |---(usb)-----------------| (monitor) |
    |      |                         |           |
    |      |           +--------+    |           |
    |      |---(usb)---| J-Link |    |           |
    |      |           +--------+    |           |
    |      |              |||        |           |
    |      |           +-----------+ |           |
    |      |---(usb)---| "GPB" d.b |=|           |
    |      |           |           |=|           |
    |      |           | DW1.4     |=|           |
    |      |           +-----------+ |           |
    |      |               ^         |           |
    |      |               |         |           |
    |      |           +----------+  |           |
    |      |           |  GPIO0   |  |           |
    |      |---(usb)---| Adafruit |  |           |
    |      |           |  GPIO1   |  |           |
    |      |           +---------+|  |           |
    |      |               |         |           |
    |      |               v         |           | -----
    |      |           +-----------+ |           |   ^
    |      |           | DW1.4     |=|           |   |
    |      |           |           |=|           |  (Not
    |      |---(usb)---| "APB" d.b |=|           |  needed
    |      |           +-----------+ |           |  for
    |      |              |||        |           |  GPB-only
    |      |           +--------+    |           |  tests)
    |      |---(usb)---| J-Link |    |           |   |
    |      |           +--------+    |           |   v
    |      |                         |           | -----
    +------+                         +-----------+

#File Formats
Both *run-bootrom-tests* and *create-bootrom-test-suite* take script files
as an input. Two script files are very similar, consisting of a series of
one-line entries for each test. Each line resembles a  Linux command-line
without the command.

## Test Script
Below is an example of the test script, used by *run-bootrom-tests*:

    -t BadSentinel -d "#1, of items" -b ./bootrom-BadSentinel.bin \
      -f "Hello world from 2nd stage FW"
    -t BadTailSentinel -b ./test/bootrom-BadTailSentinel.bin \
      -f "Hello world from 2nd stage FW" -f yabba -f dabba -f do

Where:

* `-t <test name>`: Each test must have a name (preferably unique, since
it is used to log which tests pass or fail).
* `-d <test description>`: Optional description (quote if multi word)
Can use "--description" instead.
* `-b <bin_file>`: Pathname to the BootRom image to load
* `-p <pass_string>`: A pass-condition string to look for in the debug
output (quote if multi word)
* `-f <fail_string>`: A fail-condition string to look for in the debug
output (quote if multi word)

You can have multiple pass_strings or fail_strings, but you cannot mix
pass and fail strings. If there are multiple pass strings, all must be
present for the test to pass. If there are multiple fail strings, any
must be present for the test to fail


## Test Suite Script
The test suite script is the input to *create-bootrom-test-suite*, from
which it creates the test script and set of binary files. Syntactically,
it is a superset of the test script, with one test per line.

The following parameters are passed through to the test script:

* `-t <test name>`: Each test must have a name (preferably unique, since it
is used to log which tests pass or fail).
* `-d <test description>`: Optional description (quote if multi word)
Can use "--description" instead.
* `-p <pass_string>`: A pass-condition string to look for in the debug
output (quote if multi word)
* `-f <fail_string>`: A fail-condition string to look for in the debug
output (quote if multi word)

These additional parameters are used to generate the modified binaries:

* `-b <bin_file>`: Pathname to the original BootRom image, from which the
modified versions will be patched. The modified binary images' names are a
concatenation of this name and the test name.
* `-z <offset>`: Patch the byte(s) at the specified offset. The offset
from start-of-file can be expressed as any of the following 4 forms:
    * **hex_number**: Absolute offset
    * **hex_number+hex_number**: Relative offset from an absolute base
    * **symbol**: Absolute offset, using symbol from map file (see *hexpatch*)
    * **symbol+hex_number**: Relative offset from an absolute symbolic base
* `-r|-o|-x|-a <hex_byte_value>...`: **R**eplace/**O**R/**X**OR/**A**ND
the byte(s) at `<offset>` with the supplied replacement byte(s)

# Workflow
This set of tools is intended for batch operation of test suites, as
typically found with a Build Verification Test (BVT), and for providing
a set of test logs to Toshiba which validate the supplied code.

The typical work flow for this would be to first define a suite of tests,
and creating a test suite script file. Then feed this and the candidate binary
to *create-bootrom-test-suite*, to create the test suite folder. One then
runs *run-bootrom-tests* on that test suite to run the tests in sequence
and gather the test result log.

One can also manually generate individual test scripts for *run-bootrom-tests*
for specific tests or as a means of prototyping the script parameters for
inclusion in a test suite script.

## Example 1: Autoboot (debug output to stdout)
While *autoboot* was designed primarily as a framework for testing the
underlying autoboot libarary, it can be used as a standalone tool for
downloading and running a BootRom image. A typical invocation would be:

    autoboot --jlinksn 504302001 --chipit /dev/ttyUSB5 \
      --efuse ~/jgdb/efuse --capture /dev/ttyUSB3  --reset adafruit \
      --bin ~/work/bootrom/build/bootrom.bin

* `--jlinksn`: The serial number of the J-Link JTAG interface.
* `--chipit`: The serial port used by the HAPS-62 *ChipIt* supervisor.
* `--efuse`: The e-Fuse settings file (see: *Appendix B*)
* `--capture`: The daughterboard's debug serial port
* `--reset adafruit | manual`: (optional) The daughterboard reset mechanism.
Adafruit will use the Adafruit USB-GPIO adapter to control the reset
line. Manual will prompt you to manipulate the reset DIP switch. If
`--reset` is omitted, it defaults to manual.
* `--bin`: The FFFF image to download to the daughterboard

## Example 2: Autoboot (debug output to a log file)
You can also have autoboot log the debug output to a log file
by adding the `--log` parameter:

    autoboot --jlinksn 504302001 --chipit /dev/ttyUSB5 \
      --efuse ~/jgdb/efuse --capture /dev/ttyUSB3  --reset adafruit \
      --bin ~/work/bootrom/build/bootrom.bin \
      --log foo.log

* `--log`: The pathname to the log file

## Example 3: Creating a test suite

### 1. Create the Test Suite Script
Create a file (e.g., test.tss) with the following content on each line:

    -t BadSentinel -d "#1, of items" -f "Hello world from 2nd stage FW" \
      -z ffff[0].sentinel+1 -x 05
    -t BadTailSentinel  -f "Hello world from 2nd stage FW" -f "yabba" \
      -f dabba -f do -z ffff[0].tail_sentinel+1 -x 05 #comment

This test suite script has 2 tests (one per line) which test whether or not the
BootRom will detect corrupted FFFF sentinels. The first line checks for a bad
sentinel at the start of the FFFF header:

* `-t BadSentinel`: The test name
* `-d "#1, of items"` Supplies a description for the BadSentinel test
* `-f "Hello world from 2nd stage FW"`: Since the BootRom should fail with a
bad sentinel, we set a failure string to be the successfully-booted string
* `-z ffff[0].sentinel+1`: Patch the 2nd byte of the sentile by...
* `-x 05`: ...XORing it with 0x05.
* `#comment`: Everything from the '#' to the end of the line is ignored.

The second line tests a corrupted tail sentinel. In real life it would be
identical to the first, except for a different test name and a different
patch offset (tail_sentinel vs. sentinel). For illustration, it has 3
additional failure strings ("yabba", "dabba" and "do"), and the presence of
any of them will cause the test to fail.

### 2. Create FFFF Image and Map files
If your test suite script is using symbolic (highly-recommended), you need to
create your FFFF image with the --map parameter to generate the matching .map
file:

    create-ffff **--map** --out build/foo.ffff ...

### 3. Create the Test Suite
Use *create-bootrom-test-suite* to generate your test suite file.

    create-bootrom-test-suite --bin build/foo.ffff --map build/foo.map \
      --desc test.tss --out_folder ./Test2 --test test.ts
* `--bin`: The FFFF file created in step 2.
* `--map`: The map file created in step 2.
* `--desc`: The test script script created in step 1.
* `--out_folder`: The test suite folder to create/populate.
* `--test`: The name of the test suite file to generate in the test
suite folder.

This creates the test suite folder (./Test2) and the test script (./Test2/test.ts),
which was covered in the *File Format* section above.

## Example 4: Running the tests in a test suite
Use *run-bootrom-tests* to execute the test suite:

    run-bootrom-tests --test Test2/test.ts --jlinksn 504302001 \
      --chipit /dev/ttyUSB4 --efuse ~/jgdb/efuse --dbgser /dev/ttyUSB2 \
      --stop "Hello world from 2nd stage FW" \
      --stop "failed to load image, entering infinite loop" \
      --timeout 5

* `--test`: The test script (in this case, generated by
*create-bootrom-test-suite* in example 1.
* `--jlinksn`: The serial number of the J-Link JTAG interface.
* `--chipit`: The serial port used by the HAPS-62 *ChipIt* supervisor.
* `--efuse`: The e-Fuse settings
* `--dbgser`: The daughterboard's debug serial port
* `--stop`: If this string is encountered in the debug stream, the test
is concluded. You may specify multiple stop strings if desired.
* `--timeout`: The number of seconds of debug output inactivity before
concluding that the test has run its course. This is in lieu of any of
the `--stop` parameters and is a backstop for images that silently fail.


# Appendix A: Adafruit FT232H Installation
The `autoboot` script supports the Adafruit FT232H USB->GPIO adapter for
controlling the reset on the HAPS-62 SPIROM daughterboard. While its use is
optional, you must install their drivers to keep Python happy.

The information in this appendix comes from the FT232H [product page](https://learn.adafruit.com/adafruit-ft232h-breakout/overview).

## Linux Installation
Follow the steps to
[install](https://learn.adafruit.com/adafruit-ft232h-breakout/linux-setup)
**MPSSE** and the **Adafruit Python GPIO library**.

## Changing the IO Drive Current (Windows Installation)
As shipped, the GPIO drive current is to low to overpower the pull-up on the
daugherboard, and must be reprogrammed to use a higher drive current to be
usefull. This can be done simply via the FT_Prog utility, but getting that to
work requires a Windows machine and several steps because it won't find the
chip.

Adafruit's
[More Info](https://learn.adafruit.com/adafruit-ft232h-breakout/more-info)
page instructions and links to most of what you need.

1. Install [FT_Prog](http://www.ftdichip.com/Support/Utilities.htm#FT_PROG)
from FTDI's website.
2. Plug in your FT232H board and let Windows enumerate it.
3. Launch FT_Prog and click the *magnifying glass* or press *F5* to search
for devices. If none show up, you'll need to install the libusb driver and
erase the device:
    1 Exit FT_Prog
    2 Scroll down Adafruits *More Info* page and follow the steps in
**Erase EEPROM For Programming With FT_PROG**
4. Reaunch FT_Prog and click the magnifying glass or press F5 to search for
devices. The device should now appear.
    1. (Optional) restore default values (See: below)
    2. Change the IO pin drive strength:
        1. FT EEPROM > Hardware Specific > IO Pins > Group AD
        2. Change Drive from 4mA to 8mA
        3. (Optional) repeat for Group AC

    3. Program the new settings:
        1 Click on the lightning bolt icon or press ^P to program the FT232H

## Adafruit FT232H Default Values
While not essential to restore any of the default values after erasing the
chip, you may wish to do so.

Attribute | Value
--------- | -----
Data.Signature1 | 0x00000000
Data.Signature2 | 0xffffffff
Data.VendorId | 0x0403
Data.ProductId | 0x6014
Data.Manufacturer | "Adafruit"
Data.ManufacturerId | "FT"
Data.Description | "FT232H"
Data.SerialNumber | "FTQTRXJL"
Data.MaxPower | 90
Data.PnP | 1
Data.SelfPowered | 0
Data.RemoteWakeup | 0
Data.PullDownEnableH | 0
Data.SerNumEnableH | 1
Data.ACSlowSlewH | 0
Data.ACSchmittInputH | 0
Data.ACDriveCurrentH | 4 (Change to 8)
Data.ADSlowSlewH | 0
Data.ADSchmittInputH | 0
Data.ADDriveCurrentH | 4
Data.Cbus0H | 0
Data.Cbus1H | 0
//Data.Cbus2H | 0
Data.Cbus3H | FT_232H_CBUS_TXLED
//Data.Cbus3H | 0
Data.Cbus4H | FT_232H_CBUS_RXLED
Data.Cbus4H | 0
Data.Cbus5H | 0
Data.Cbus6H | 0
Data.Cbus7H | 0
Data.Cbus8H | 0
Data.Cbus9H | 0
Data.IsFifoH | 0
Data.IsFifoTarH | 0
Data.IsFastSerH | 0
Data.IsFT1248H | 0
Data.FT1248CpolH | 0
Data.FT1248LsbH | 0
Data.FT1248FlowControlH | 0
Data.IsVCPH | 0
Data.PowerSaveEnableH | 0

# Appendix B efuse file
The *run-bootrom-tests* tool requires a file of keyword-value pairs describing the
various e-Fuse settings. On a real ES3, these would be defined by the hardware,
but on the HAPS-62, they must be preloaded before the BootRom image runs.
Listed below is the full set of keywords, and some stand-in values.

    VID   55555555
    PID   6A6A6A6A
    SN0   3C3C3C3C
    SN1   5A5A5A5A
    IMS0  33333333
    IMS1  55555555
    IMS2  66666666
    IMS3  99999999
    IMS4  AAAAAAAA
    IMS5  CCCCCCCC
    IMS6  33335555
    IMS7  69696969
    IMS8  0069AC35

Note that, to be valid, VID, PID, and SN (SN0 + SN1) must have equal numbers of
zero and one bits. The IMS (IMS0..IMS8) have no such restriction.

