# bootrom-tools
## Python scripts for building images for the Trusted Firmware Transfer Format and Flash Format for Firmware
The scripts/ directory in this repository contains Python scripts for packaging firmware images into Project Ara's
TFTF and FFFF image formats.  Each script will list its parameters if it is called with the flag `--help`.

## Example 1: packaging a [nuttx](https://github.com/projectara/nuttx) firmware into a TFTF image
The following command, executes from within scripts/, will package a nuttx firmware specified in two raw-binary parts,
one of which has a nontrivial linking offset, into a TFTF image.  Assume that `~/nuttx-es2-debug-apbridgea.text`
contains the `.text` section of the firmware (with an offset of 0), and that `~/nuttx-es2-debug-apbridgea.data`
contains the `.data` section of the firmware (which begins 0x1e6e8 after the base loading address in memory).  We want to load the firmware as a whole to the base address 0x10000000, and the `.text` section's entry-point is at 0x10000ae4.

The Unipro and Ara VID/PID values are specific to the chip on which we intend to run the firmware.

All numerical parameters can be passed in decimal or hexadecimal form, and are here given in hex for convenience.

    ./create-tftf -v --code ~/nuttx-es2-debug-apbridgea.text --out ~/nuttx-es2-debug-apbridgea.tftf \
    --data ~/nuttx-es2-debug-apbridgea.data --offset 0x1e6e8 \
    --load 0x10000000 --start 0x10000ae4 \
    --unipro-mfg 0x126 --unipro-pid 0x1000 --ara-vid 0x0 --ara-pid 0x1

The flags can be understood as follows:

* `-v`: Verbose mode, in which the script will dump the contents of the resultant TFTF headers to stdout when finished.
* `--code`: Specifies the filename in which the raw binary for a code section can be found.  This should be
the Ara firmware's `.text` section.
* `--out`: Specifies the filename to which the TFTF image should be written.
* `--data`: Specifies the filename in which the raw binary for a data section can be found.  This should be
the Ara firmware's `.data` section.
* `--offset`: An offset to be added to the loading address (see below) to find where to load the immediately preceding
section (which must be one of: `--code`, `--data`, or `--manifest`) when loading its contents to memory at boot-time.
* `--load`: The base address in memory to which the firmware sections packaged in the TFTF should be loaded at
boot-time, as obtained from a disassembler or linker.
* `--start`: The absolute memory address of the firmware's entry-point, as obtained from a disassembler or linker.
* `--unipro-mfg`: The Unipro Manufacturer ID (MID)/Vendor ID (VID) (these are two different phrasings for talking about the same number).  The specific value is obtained from the relevant hardware.
* `--unipro-pid`: The Unipro Product ID (PID).  The specific value is obtained from the relevant hardware.
* `--ara-vid`: The Project Ara Vendor ID (VID).  The specific value is obtained from the relevant hardware.
* `--ara-pid`: The Project Ara Product ID (PID).  The specific value is obtained from the relevant hardware.

At least one section must be given via `--code`, `--data`, or `--manifest`, and an output filename via `--out` is also mandatory.

## Example 2: packaging [nuttx](https://github.com/projectara/nuttx) TFTF into an FFFF image
The following command, executed within scripts/, will package the TFTF image from Example 1 into an FFFF image,
designated for a flashrom with 2 MB (megabytes) of capacity and considered to be a first-generation FFFF header.

The `--flash-capacity` and `--erase-size` parameters take values specific to the hardware for which we are building
firmware.

All numerical parameters can be passed in decimal or hexadecimal form, and are here given in hex for convenience.

    ./create-ffff -v --flash-capacity 0x200000 --image-length 0x28000 --erase-size 0x1000 \
    --name "nuttx" --generation 0x1 \
    --s2f ~/nuttx-es2-debug-apbridgea.tftf --eloc 0x2000 --eid 0x1 \
    --out ~/nuttx-es2-debug-apbridgea.ffff

The flags can be understood as follows:

* `-v`: Verbose mode, in which the script will dump the contents of the resultant FFFF and TFTF headers when finished.
* `--flash-capacity`: The total capacity of the target flashrom, in bytes.
* `--image-length`: The length of the output FFFF image, in bytes.
* `--erase-size`: The length of an erase-block in the target flashrom device, in bytes.
* `--name`: The name being given to the FFFF firmware package.
* `--generation`: The per-device FFFF generation of the output image.  Used to version firmware images.
* `--s2f`: Specifies the filename of a TFTF package for Ara "*S*tage *2* *F*irmware".
* `--eloc`: The absolute address, within the FFFF image and flashrom address-space, at which the preceding element (here the `--s2f` element) is to be located, in bytes.  `--eloc` should be read as "Element Location".
* `--eid`: The *e*lement *id*entifier, one-indexed.
* `--out`: Specifies the filename to which to write the resultant FFFF image.

## Example 3: packaging a [nuttx](https://github.com/projectara/nuttx) ELF binary into a TFTF image

This example proceeds in exactly the same way as Example 1, except that instead
of passing raw binary files for the firmware's `.text` and `.data` sections,
necessitating the manual passing of loading offsets, we instead pass a
[nuttx](https://github.com/projectara/nuttx) ELF executable to the `--elf` flag,
and let the script extract the `.text` and `.data` sections and offsets from the
ELF header.

    ./create-tftf -v --elf ~/nuttx-es2-debug-apbridgea \
    --load 0x10000000 --start 0x10000ae4 \
    --out ~/nuttx-es2-debug-apbridgea.tftf \
    --unipro-mfg 0x126 --unipro-pid 0x1000 --ara-vid 0x0 --ara-pid 0x1

The flags differing from Example 1 can be understood as follows:

* `--elf`: Specifies the filename in which an ELF executable can be found.

## Example 4: packaging a [nuttx](https://github.com/projectara/nuttx) FFFF and a [bootrom](https://github.com/projectara/bootrom) into a "dual image" for ES2 hardware

In this example, we hack the FFFF specification to package a
[bootrom](https://github.com/projectara/bootrom) *alongside* our FFFF image,
in the early portion of the binary.  This works only because the FFFF
specification expects to see the first FFFF header element at
address 0 in the flashrom.  If we instead place the
[bootrom](https://github.com/projectara/bootrom) there, the FFFF loader will
just assume the first FFFF header was corrupted and search for the "second" FFFF
header in progressively higher addresses in flashrom.  It will then find the
actual *first* FFFF header of our image (`~/nuttx-es2-debug-apbridge.ffff` in
this example), and load in accordance with that header.

This basically **only** exists for testing purposes, and should **never** be
done in any kind of production environment, as it subverts the spirit of FFFF
generation numbering.  Unfortunately, this inevitably means someone will try
it :-).  *C'est la vie.*

    ./create-dual-image --ffff ~/nuttx-es2-debug-apbridgea.ffff \
    --bootrom ~/bootrom/build/bootrom.bin \
    --out ~/es2-apbridgea-dual

The flags can be understood as follows:

* `--ffff`: Specifies the filename of the FFFF image to corrupt.
* `--bootrom`: Specifies the filename of the raw
[bootrom](https://github.com/projectara/bootrom) to insert into the low
addresses of the image.
* `--out`: Specifies the filename into which the output hack-image should be
written for testing purposes.
