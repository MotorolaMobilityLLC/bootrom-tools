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
 * @brief: This file contains the definitions and constants for the Trusted
 * Firmware Transfer Format (TFTF) file and structures used by the secure
 * bootloader.
 *
 * @note: this file is shared between the APBridge firmware and the
 * command-line tools.
 */

#ifndef _TFTF_H_
#define _TFTF_H_

#
/**
 * @brief TFTF compressed image support compile flag
 *
 * If COMPRESSED_SUPPORT is defined, then the --compress option becomes active
 * and all code and data segments will be compressed.
 *
 * NOTE ***** This is an optional feature *****
 */
// #define COMPRESSED_SUPPORT


/**
 * @brief TFTF Sentinal value "TFTF"
 *
 * Note: string must be in reverse order so that it looks OK on a little-
 * endian dump.
 */
#define TFTF_SENTINEL     0x46544654

/**
 * @brief TFTF Section types (see: tftf_section.section_type)
 */
enum tftf_section_type {
    TFTF_SECTION_TYPE_RAW_CODE_BLOCK        = 0x01,
    TFTF_SECTION_TYPE_RAW_DATA_BLOCK,
    TFTF_SECTION_TYPE_COMPRESSED_CODE_BLOCK,
    TFTF_SECTION_TYPE_COMPRESSED_DATA_BLOCK,
    TFTF_SECTION_TYPE_MANIFEST,
    TFTF_SECTION_TYPE_SIGNATURE_BLOCK       = 0x8f,
    TFTF_SECTION_TYPE_CERTIFICATE,
    TFTF_SECTION_TYPE_END_OF_DESCRIPTORS    = 0xFE
};

/**
 * @brief Macro to convert tftf_section_type to a human-readable form
 * (intended for debugging)
 */
#define PRINT_TFTF_SECTION_TYPE(t)\
        (((t) == TFTF_SECTION_TYPE_END_OF_DESCRIPTORS)? "end of sections" : \
         ((t) == TFTF_SECTION_TYPE_RAW_CODE_BLOCK)? "code" : \
         ((t) == TFTF_SECTION_TYPE_RAW_DATA_BLOCK)? "data" : \
         ((t) == TFTF_SECTION_TYPE_COMPRESSED_CODE_BLOCK)? "compressed code" : \
         ((t) == TFTF_SECTION_TYPE_COMPRESSED_DATA_BLOCK)? "compressed data" : \
         ((t) == TFTF_SECTION_TYPE_MANIFEST)? "manifest" : \
         ((t) == TFTF_SECTION_TYPE_SIGNATURE_BLOCK)? "signature" :  \
         ((t) == TFTF_SECTION_TYPE_CERTIFICATE)? "certificate" : "?")


/**
 * @brief TFTF header & field sizes
 */
#define TFTF_TIMESTAMP_LENGTH    16
#define TFTF_FW_PKG_NAME_LENGTH  48
#define TFTF_HDR_LENGTH          512
#define TFTF_MAX_SECTIONS        25
#define TFTF_PADDING             12


/**
 * @brief TFTF signature block field sizes
 */
#define TFTF_SIGNATURE_KEY_NAME_LENGTH  96


/**
 * @brief TFTF signature types (see: tftf_Signature.signature_type)
 */
enum tftf_signature_type {
    TFTF_SIGNATURE_TYPE_RSA2048_SHA256 = 0x01,
};


/**
 * @brief TFTF section:
 *
 * This is used to describe a contiguous block of bytes having a constant
 * meaning. There is one section for each code block, data block, manifest, or
 * signature.
 */
struct __attribute__ ((__packed__)) tftf_section
{
    uint32_t   section_length;
    uint32_t   expanded_length;
    uint32_t   copy_offset;
    uint32_t   section_type;    // enum tftf_section_type
};


/**
 * @brief TFTF header
 */
struct __attribute__ ((__packed__)) tftf_hdr
{
    /* The global or "fixed" part of the header: */
    uint32_t            sentinel;
    char                timestamp[TFTF_TIMESTAMP_LENGTH];     /* ASCIIZ string */
    char                fw_pkg_name[TFTF_FW_PKG_NAME_LENGTH]; /* ASCIIZ string */
    uint32_t            load_length;
    uint32_t            load_base;
    uint32_t            expanded_length;
    uint32_t            start_location;
    uint32_t            unipro_mfg_id;
    uint32_t            unipro_product_id;
    uint32_t            ara_vendor_id;
    uint32_t            ara_product_id;

    /* The section-specific part of the header. */
    struct tftf_section section_descriptors[TFTF_MAX_SECTIONS];

    /* Padding to bring up up to 512 bytes. */
    uint8_t             padding[TFTF_PADDING];
};


/**
 * @brief TFTF signature block:
 */
struct __attribute__ ((__packed__)) tftf_signature_block
{
    uint32_t    length;

    /* Holds a tftf_signature_type enum */
    uint32_t    signature_type;

    /* ASCIIZ string */
    char        key_name[TFTF_SIGNATURE_KEY_NAME_LENGTH];

    /* Placeholder for start of signature */
    uint8_t     signature_blob[1];
};


#endif // !_TFTF_H_
