/*
 * Copyright (c) 2015 Google Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 * 1. Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 * 3. Neither the name of the copyright holder nor the names of its
 * contributors may be used to endorse or promote products derived from this
 * software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
 * ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/**
 *
 * @brief: This file contains the code for "create-tftf" a Linux command-line app
 * used to create an unsigned Trusted Firmware Transfer Format (TFTF)
 * file used by the secure bootloader.
 *
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <stdio.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <getopt.h>
#include "mytypes.h"
#include "tftf.h"


// Size in bytes of the buffer used to copy section files.
#define COPY_BUFFER_SIZE 4096

// Program return values
#define PROGRAM_SUCCESS     0
#define PROGRAM_WARNINGS    1
#define PROGRAM_ERRORS      2


/**
 * @brief Macro to calculate the last address in a section.
 */
#define SECTION_END(section_ptr) \
    ((section_ptr)->copy_offset + (section_ptr)->expanded_length - 1)


typedef struct
{
    const char *    filename;
    int             type;
    uint32_t        offset;     // 0 means no offset specified
} section_info;


/*
 * If compress is true, compress the data while copying; if false, just
 * perform a raw copy. (Ignored if COMPRESSED_SUPPORT is not defined.)
 */
static bool compress = false;

// if verbose is true, print out a summary of the TFTF header on success.
static bool verbose = false;

// Parsing table
static struct option long_options[] = {
        { "compress",       no_argument,       NULL, 'C' },
        { "verbose",        no_argument,       NULL, 'v' },
        { "manifest",       required_argument, NULL, 'm' },
        { "code",           required_argument, NULL, 'c' },
        { "data",           required_argument, NULL, 'd' },
        { "offset",         required_argument, NULL, 'f' },
        { "name",           required_argument, NULL, 'n' },
        { "load",           required_argument, NULL, 'l' },
        { "start",          required_argument, NULL, 's' },
        { "unipro-mfg",     required_argument, NULL, 'u' },
        { "unipro-product", required_argument, NULL, 'U' },
        { "ara-vendor",     required_argument, NULL, 'a' },
        { "ara-product",    required_argument, NULL, 'A' },
        { "out",            required_argument, NULL, 'o' },
        {NULL, 0, NULL, 0}
};

// Cache for section information from the command line.
static section_info section_cache[TFTF_MAX_SECTIONS];

static uint8_t  copy_buffer[COPY_BUFFER_SIZE];

static struct tftf_hdr tftf_header;


/**
 * @brief Print out the usage message
 *
 * @param None
 *
 * @returns Nothing
 */
void usage(void) {
    printf("Usage: create-tftf [setting]...\n");
    printf("Settings:\n");
    printf("--code [file] {-offset[number]}\n");
    printf("    Add[file] as a \"firmware code block\" with the specified offset from --load(assumes zero if omitted).\n");

    printf("--data [file] {-offset[number]}\n");
    printf("    Add[file] as a \"raw data block\" with the specified offset from --load(assumes zero if omitted).\n");

    printf("--manifest [file]\n");
    printf("    Add[file] as a \"manifest block\"\n");

    printf("--name [string]\n");
    printf("    Adds the firmware package name to the TFTF file\n");

    printf("--load [address]\n");
    printf("    Specifies the address that the TFTF package will be expanded into on the target machine(assumes 0x10000000 if omitted).\n");

    printf("--start [address]\n");
    printf("    Specifies the entry point for the TFTF package(assumes --load if omitted).\n");

    printf("--unipro_mfg [number]\n");
    printf("    Specifies the 32-bit UniPro manufacturer ID.\n");

    printf("--unipro_product [number]\n");
    printf("    Specifies the 32-bit UniPro product ID.\n");

    printf("--ara_vendor [number]\n");
    printf("    Specifies the 32-bit ARA manufacturer ID.\n");

    printf("--ara_product [number]\n");
    printf("    Specifies the 32-bit ARA product ID.\n");

    printf("--out [file]\n");
    printf("    The name of the output TFTF file (required).\n");

    printf("--compress\n");
    printf("    If supported, causes all code and data blocks to be compressed. If unsupported, this option is silently ignored.\n");

    printf("-v, --verbose\n");
    printf("    Print a synopsis of the TFTF file.\n");

    printf("where <number> is a hex number (leading 0x is optional)\n");
}


/**
 * @brief Print out a TFTF header
 *
 * @param header Pointer to the TFTF header to display
 *
 * @returns Nothing
 */
void print_tftf_header(struct tftf_hdr * header) {
    printf("TFTF Header:\n");
    char * ptr = (char *)&header->sentinel;
    char string_buf[TFTF_FW_PKG_NAME_LENGTH+1];
    int index;
    struct tftf_section * section = &header->section_descriptors[0];

    // Print out the header proper
    printf("    sentinel:          %08x (%c%c%c%c)\n",
            header->sentinel,
            isprint(ptr[0])? ptr[0] : '-',
            isprint(ptr[1])? ptr[1] : '-',
            isprint(ptr[2])? ptr[2] : '-',
            isprint(ptr[3])? ptr[3] : '-');
    /*
     * Note that ("%*s", -xxx_LENGTH, header->fw_pkg_name) should
     * work, but in practice it seems to run on when the string isn't null-
     * terminated. So, we copy the string into a temporary buffer to null
     * terminate it for printf.
     */
    memcpy(string_buf,
           tftf_header.timestamp,
           TFTF_TIMESTAMP_LENGTH);
    string_buf[TFTF_TIMESTAMP_LENGTH] = '\0';
    printf("    timestamp:         '%s'\n", string_buf);     // ASCII string
    memcpy(string_buf,
           tftf_header.fw_pkg_name,
           TFTF_FW_PKG_NAME_LENGTH);
    string_buf[TFTF_FW_PKG_NAME_LENGTH] = '\0';
    printf("    fw_pkg_name:       '%s'\n", string_buf); // ASCII string
    printf("    load_length:       %08x\n", header->load_length);
    printf("    load_base:         %08x\n", header->load_base);
    printf("    expanded_length:   %08x\n", header->expanded_length);
    printf("    start_location:    %08x\n", header->start_location);
    printf("    unipro_mfg_id:     %08x\n", header->unipro_mfg_id);
    printf("    unipro_product_id: %08x\n", header->unipro_product_id);
    printf("    ara_vendor_id:     %08x\n", header->ara_vendor_id);
    printf("    ara_product_id:    %08x\n", header->ara_product_id);

    // Print out the section headers
    for (index = 0; index < TFTF_MAX_SECTIONS; index++, section++) {
        if (header->section_descriptors[index].section_type ==
            TFTF_SECTION_TYPE_END_OF_DESCRIPTORS) {
            printf("    Section [%d] (%d remaining)\n",
                    index,
                    TFTF_MAX_SECTIONS - index);
            break;
        }
        printf("    Section [%d] (%08x-%08x):\n",
               index,
               section->copy_offset,
               SECTION_END(section));
        printf("        section_length  %08x\n", section->section_length);
        printf("        expanded_length %08x\n", section->expanded_length);
        printf("        copy_offset     %08x\n", section->copy_offset);
        printf("        section_type    %08x (%s)\n",
               section->section_type,
               PRINT_TFTF_SECTION_TYPE(section->section_type));
    }
}


/**
 * @brief Parse a hex number.
 *
 * @param input The (hopefully) numeric string to parse (argv[i])
 * @param optname The name of the argument, used for error messages.
 * @param num Points to the variable in which to store the parsed number.
 *
 * @returns Returns true on success, false on failure
 */
bool get_num(char * input, const char * optname, uint32_t * num) {
    char *tail = NULL;
    bool success = true;

    *num = strtoul(input, &tail, 16);
    if ((errno != errno) || ((tail != NULL) && (*tail != '\0'))) {
        fprintf (stderr, "Error: invalid %s '%s'\n", optname, optarg);
        success = false;
    }

    return success;
}


/**
 * @brief Add a section to the parser's section cache.
 *
 * Used in the command line parsing phase, add a section to the parser's
 * section cache for later processing.
 *
 * @param section_filename The pathname of the file containing this section's
 * contents
 * @param section type Identifies the type of the section (code/data/manifest)
 * in uncompressed form.
 * @param section_table_length Number of elements in section_table
 * @param optname The name of the argument, used for error messages.
 * @param section_index The index of the LAST valid section (-1 initially).
 * @param
 *
 * @returns Returns true on success, false on failure.
 */
bool cache_section(const char * section_filename, const int section_type,
                   section_info section_table[],
                   const int section_table_length, const char * optname,
                   int * section_index) {
    bool success = true;

    /*
     * Pre-increment our index into the table. This way, we leave the index
     * pointing at the last valid entry. This way, the "offset" parameter can
     * be inserted later.
     */
    if (*section_index < (section_table_length - 1)) {
        *section_index += 1;
        section_table[*section_index].filename = section_filename;
        section_table[*section_index].type = section_type;
    } else {
        fprintf(stderr,
               "Error: too many sections at (%s %s)\n",
               optname,
               section_filename);
    }

    return success;
}


/**
 * @brief Append a file to the output file
 *
 * @param section_file_name The name of the (TFTF section) file to append to
 * the TFTF output file
 * @param output_fd The file descriptor of the output file
 * @param section_length A pointer to a variable which will hold the length of
 * the section block as stored in the TFTF file.
 * @param expanded_length A pointer to a variable which will hold the length of
 * the section block when decompressed. In the case of uncompressed sections,
 * section_length == expanded_length. In the case of compressed sections,
 * section_length < expanded_length.
 *
 * @returns Returns true on success, false on failure
 *
 * @note Compression is an optional feature in the functional specification and
 * is not currently supported. It will be added later if/when desired.
 */
int copy_file(const char * section_file_name, const int output_fd,
              uint32_t * section_length, uint32_t * expanded_length) {
    int status = 0;
    int section_fd = -1;
    ssize_t bytes_read;
    ssize_t bytes_written = 0;
    ssize_t bytes_written_total = 0;


    section_fd = open(section_file_name, O_RDONLY);
    if (section_fd < 0) {
        fprintf(stderr, "Error: unable to open '%s' - errno %d\n",
                section_file_name,
                section_fd);
        status = section_fd;
    } else {
        // We've opened the section file, copy the contents

#ifdef COMPRESSED_SUPPORT
#error You must add the compression code!
// ***** Ignore the compressed flag for now (optional feature) *****
#else
           // uncompressed copy:
           do {
               bytes_read = read(section_fd,
                                 copy_buffer,
                                 sizeof(copy_buffer));
               if (bytes_read <= 0) {
                   bytes_written = 0;
                   break;
               } else {
                   bytes_written = write(output_fd, copy_buffer, bytes_read);
                   if (bytes_written > 0) {
                       bytes_written_total += bytes_written;
                   }
               }
           } while (bytes_written > 0);
#endif

       // Done, close the payload file
       close(section_fd);
    }

    if (bytes_written_total > 0) {
        // Update the out parameters
        *section_length = bytes_written_total;
        *expanded_length = bytes_written_total;
    } else {
        fprintf(stderr, "Error: unable to copy '%s'\n",
                section_file_name);
        status = 2;
    }

    return status;
}


/**
 * @brief Append a TFTF section file to the open TFTF output file and update
 * the corresponding TFTF section header.
 *
 * @param tftf_fd The file descriptor for the TFTF output file.
 * @param section_filename The name of the (TFTF section) file to append to
 * the TFTF output file.
 * @param section_type Identifies the (uncompressed)type of the section.
 * @param section A pointer to the TFTF section header that will, on success,
 * be set to reflect the section block appended to the end of the TFTF output
 * file.
 * @param tftf_copy_offset On entry, a pointer to the starting address where
 * this section will reside on the target. On successful exit, this will be
 * incremented by the expanded_length (i.e., uncompressed) to provide a
 * default offset for the next section parsed.
 *
 * @returns Returns true on success, false on failure
 *
 * @note Compression is an optional feature in the functional specification and
 * is not currently supported. It will be added later if/when desired.
 */
bool append_tftf_section(const int tftf_fd, const char * section_filename,
                         int section_type, struct tftf_section * section,
                         uint32_t * tftf_copy_offset) {
    int status = 0;

    // Copy the file and update the section header
    status = copy_file(section_filename,
                       tftf_fd,
                       &section->section_length,
                       &section->expanded_length);
    if (status == 0) {
        // success
#ifdef COMPRESSED_SUPPORT
        // Remap the section type if compression is on
        if (compress) {
            if (section_type == TFTF_SECTION_TYPE_RAW_CODE_BLOCK) {
                section_type = TFTF_SECTION_TYPE_COMPRESSED_CODE_BLOCK;
            } else if (section_type == TFTF_SECTION_TYPE_RAW_DATA_BLOCK) {
                section_type = TFTF_SECTION_TYPE_COMPRESSED_DATA_BLOCK;
            }
        }
#endif // COMPRESSED_SUPPORT
        section->section_type = section_type;
        section->copy_offset = *tftf_copy_offset;

        // Update the default copy offset to point to the first byte
        // past the end of this section
        // ***** Should we suppress this for manifest segments? *****
        *tftf_copy_offset += section->expanded_length;
    }


    return (0 == status);
}


/**
 * @brief Set the timestamp field in the TFTF header to the current time.
 *
 * Set the timestamp field in the TFTF header to the current time as an ASCII
 * string of the format "YYYYMMDD HHMMSS", where the time is in UTC.
 *
 * @param tftf_header A pointer to the TFTF header in which it will set the
 * timestamp.
 *
 * @returns Nothing
 */
void set_timestamp(struct tftf_hdr * tftf_header) {
    time_t now_raw;
    struct tm * now;

    if (tftf_header != NULL) {
        // Get the current time and convert it to UTC
        now_raw = time(NULL);
        now = gmtime(&now_raw);

        // Fill in the timestamp as "YYYYMMDD HHMMSS"
        sprintf(&tftf_header->timestamp[0],
                "%4d%02d%02d %02d%02d%02d",
                now->tm_year + 1900,
                now->tm_mon,
                now->tm_mday,
                now->tm_hour,
                now->tm_min,
                now->tm_sec);
    }
}


/**
 * @brief Write the TFTF file, based on the parsed data.
 *
 * Create a TFTF file from the parsed data and the various data, code and
 * manifest files specified.
 *
 * @param tftf_header The TFTF header to complete and insert into the start of
 * the TFTF file.
 * @param section_cache A pointer to the TFTF section cache.
 * @param num_sections The number of valid sections in the cache.
 * @param output_filename Pathname to the TFTF output file.
 *
 * @returns Returns true on success, false on failure.
 */
bool write_tftf_file(struct tftf_hdr * tftf_header, const section_info * section_cache,
                     const int num_sections, const char * output_filename) {
    bool success = true;
    int tftf_fd = -1;
    struct tftf_section * section;
    size_t bytes_written;
    uint32_t tftf_copy_offset = 0;

    tftf_fd = open(output_filename,
                     O_RDWR | O_CREAT | O_TRUNC,
                     0666);
    if (tftf_fd < 0) {
        fprintf(stderr, "Error: unable to create '%s' - errno %d\n",
               output_filename,
               tftf_fd);
        return PROGRAM_ERRORS;
    }

    /*
     *  Skip to the start of the TFTF section array (we'll come back and
     *  write out the header at the end, after we've determined all the
     *  settings).
     */
    lseek(tftf_fd, sizeof(*tftf_header), SEEK_SET);

    // Process the section cache.
    for (section = &tftf_header->section_descriptors[0];
         success &&
         (section < &tftf_header->section_descriptors[num_sections]);
         section++, section_cache++) {
        /*
         * Normally, sections are placed contiguously. Check to see if the
         * user has specified an explicit offset here
         * NOTE: We assume that all sections have been validated for
         * overlap, etc.
         */
        if (section_cache->offset > 0) {
            tftf_copy_offset = section_cache->offset;
        }

        // Append the section file and update the current section header
        success = append_tftf_section(tftf_fd,
                                      section_cache->filename,
                                      section_cache->type,
                                      section,
                                      &tftf_copy_offset);

        if (success) {
            // Update the  TFTF header's length fields
            tftf_header->load_length += section->section_length;
            tftf_header->expanded_length = tftf_copy_offset;
        }
    }

    /*
     * Having processed all the sections, fill out the remainder of the
     * start of the header and write it out to the beginning of the TFTF
     * file.
     */
    if (success) {
        tftf_header->sentinel = TFTF_SENTINEL;
        // Fill in the timestamp as "YYYYMMDD HHMMSS" UTC
        set_timestamp (tftf_header);

        // Write the TFTF header at the beginning of the file
        lseek(tftf_fd, 0, SEEK_SET);
        bytes_written = write(tftf_fd,
                              tftf_header,
                              sizeof(*tftf_header));
        if (bytes_written != sizeof(*tftf_header)) {
            fprintf(stderr,
                   "Error: unable to write TFTF header - err %d\n",
                   errno);
            success = false;
        }
    }

    // Done with the TFTF file.
    close(tftf_fd);


    return success;
}


/**
 * @brief Validate the TFTF header.
 *
 * Check the TFTF header for overlapped regions.
 *
 * @param tftf_header The TFTF header to check
 *
 * @returns Returns true on success, false on failure.
 */
bool validate_tftf_header(struct tftf_hdr * tftf_header) {
    bool valid = true;
    struct tftf_section * sections = &tftf_header->section_descriptors[0];
    int base;
    uint32_t base_begin;
    uint32_t base_end;
    int comp;
    uint32_t comp_end;

    /*
     * Scan through the section table, and for each entry, check for overlap
     * with all succeeding entries.
     */
    for (base = 0;
         ((base < TFTF_MAX_SECTIONS) &&
          (TFTF_SECTION_TYPE_END_OF_DESCRIPTORS !=
           sections[base].section_type));
         base++) {
        base_begin = sections[base].copy_offset;
        base_end = SECTION_END(&sections[base]);
        for (comp = base + 1;
             ((comp < TFTF_MAX_SECTIONS) &&
              (TFTF_SECTION_TYPE_END_OF_DESCRIPTORS !=
               sections[comp].section_type));
             comp++) {
            comp_end = sections[comp].copy_offset +
                       SECTION_END(&sections[comp]);
            if (!((comp_end < base_begin) ||
                    (sections[comp].copy_offset > base_end))) {
                fprintf(stderr,
                        "Warning: section %d (0x%08x-%08x) overlapped by"\
                        " section %d (0x%08x-%08x)\n",
                        base,
                        base_begin,
                        base_end,
                        comp,
                        sections[comp].copy_offset,
                        comp_end);
                valid = false;
            }
        }
    }

    return valid;
}

/**
 * @brief Entry point for the create-tftf application
 *
 * @param argc The number of elements in argv or parsed_argv (std. unix argc)
 * @param argv The unix argument vector - an array of pointers to strings.
 *
 * @returns 0 on success, 1 if there were warnings, 2 on failure
 */
int main(int argc, char * argv[]) {
    int option;
    int option_index;
    int section_index = -1;
    bool allow_offset = false;
    char * output_filename = NULL;
    bool success = true;
    int program_status = 0; // assume success

    compress = false;
    verbose = false;
    memset(&tftf_header, 0, sizeof(tftf_header));

    while (success) {
        option = getopt_long (argc,
                              argv,
                              "d:m:n:l:s:u:U:a:U:o:f:v",
                              long_options,
                              &option_index);
        if (option == -1) {
            break;
        }

        // Preprocess pending optional "offset" parameter
       if ((option != 'c') && (option != 'd') && (option != 'f')) {
            allow_offset = false;
        }

        /*
         * Cache the section information in the section cache for
         * now. All other TFTF inputs are stored immediately into the header
         */
        switch (option) {
        case 'm':   // manifest
            success = cache_section(optarg,
                                    TFTF_SECTION_TYPE_MANIFEST,
                                    &section_cache[0],
                                    _countof(section_cache),
                                    "manifest",
                                    &section_index);
            break;

        case 'c':   // code
            allow_offset = true;
            success = cache_section(optarg,
                                    TFTF_SECTION_TYPE_RAW_CODE_BLOCK,
                                    &section_cache[0],
                                    _countof(section_cache),
                                    "code",
                                    &section_index);
             break;

        case 'd':   // data
            success = cache_section(optarg,
                                    TFTF_SECTION_TYPE_RAW_DATA_BLOCK,
                                    &section_cache[0],
                                    _countof(section_cache),
                                    "data",
                                    &section_index);
          break;

        case 'f':   // offset (Secondary arg to code, data)
            if (allow_offset) {
                // Amend the section offset in the current section.
                success = get_num(optarg,
                                  "offset",
                                  &section_cache[section_index].offset);
          } else {
                fprintf (stderr,
                        "Error: offset only allowed after code and data\n");
            }
            allow_offset = false;
            break;

        case 'n':   // name
            strncpy (&tftf_header.fw_pkg_name[0],
                     optarg,
                     sizeof(tftf_header.fw_pkg_name));
            break;

        case 'l':   // load address
            success = get_num(optarg,
                              "load address",
                              &tftf_header.load_base);
             break;

        case 's':   // start address (i.e., entry point)
            success = get_num(optarg,
                              "start address",
                              &tftf_header.start_location);
            break;

        case 'u':   // unipro-mfg
            success = get_num(optarg,
                              "unipro-mfg",
                              &tftf_header.unipro_mfg_id);
            break;

        case 'U':   // unipro-product
            success = get_num(optarg,
                              "unipro-product",
                              &tftf_header.unipro_product_id);
            break;

        case 'a':   // ara-vendor
            success = get_num(optarg,
                              "ara-vendor",
                              &tftf_header.ara_vendor_id);
            break;

        case 'A':   // ara-product
            success = get_num(optarg,
                              "ara-product",
                              &tftf_header.ara_product_id);
            break;

        case 'o':   // out
            output_filename = optarg;
            break;

        case 'v':   // verbose
            verbose = true;
            break;

        case 'C':   // compress
            compress = true;
            break;

        case '?':   // extraneous parameter
            // getopt_long already printed an error message
            break;

        default:
            // Should never get here
            printf("?? getopt returned character code 0%o ??\n", option);
            break;
        }
    }


    if (!success) {
        program_status = PROGRAM_ERRORS;
    } else {
        // Validate that we have the needed args
        if (output_filename == 0) {
            fprintf(stderr, "Error: no output file specified\n");
            success = false;
            usage();
        }
        else if (section_index == -1) {
            fprintf(stderr,
                    "%s: missing input (code, data, manifest) section(s)\n",
                    argv[0]);
            usage();
            success = false;
        }
    }


    if (success) {
        // Process the section cache and write out the TFTF file
        success = write_tftf_file(&tftf_header,
                                  &section_cache[0],
                                  section_index+1,
                                  output_filename);
        // Indicate success/failure
        if (success) {
            // Optionally dump the header
            if (verbose) {
                print_tftf_header(&tftf_header);
            }

            // Sniff-test the header
            if (!validate_tftf_header(&tftf_header)) {
                program_status = PROGRAM_WARNINGS;
            }

            fprintf(stderr, "Wrote TFTF file: %s\n", output_filename);
        } else {
            unlink(output_filename);
            fprintf(stderr, "There were errors\n");
            program_status = PROGRAM_ERRORS;
        }
    }

    return program_status;
}

//                                  --< create-tftf.cpp >--
