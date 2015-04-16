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
 * @brief: This file contains the definitions and constants for the Flash
 * Format For Firmware (FFFF) file and structures used by the secure
 * bootloader.
 *
 * @note: This file is shared between the APBridge firmware and the
 * command-line tools
 */

#ifndef _FFFF_H_
#define _FFFF_H_



/**
 * @brief TFTF Sentinel value.
 *
 * It consists of 4 identical words, each with the high-order bit set and the
 * remaining bits set to some distinctive value. This format ensures that the
 * the sentinel cannot appear "by accident" in the data containing a header
 * block, guaranteeing that a search for headers on 2**n byte boundaries will
 * always find the second header. The sentinel value is repeated at the very
 * end of the header block so that an interrupted write can be recognized.
 */
#define FFFF_SENTINEL     0x80ffff01


/**
 * @brief FFFF header & field sizes
 */
#define FFFF_SENTINEL_LENGTH          16
#define FFFF_TIMESTAMP_LENGTH         16
#define FFFF_FLASH_IMAGE_NAME_LENGTH  48


/**
 * @brief Macro to locate the ffff_hdr_tail at the end of the FFFF buffer.
 */
#define GET_FFFF_TAIL(ffff_start,size) \
    (ffff_hdr_tail*)((char*)(ffff) + (size) - sizeof(ffff_hdr_tail))


/**
 * @brief FFFF Element IDs (see: ffff_element.element_id)
 */
enum ffff_element_id {
    FFFF_ELEMENT_ID_END_OF_ELEMENT_TABLE     = 0x00,
    FFFF_ELEMENT_ID_STAGE2_FIRMWARE_PACKAGE,
    FFFF_ELEMENT_ID_STAGE3_FIRMWARE_PACKAGE,
    FFFF_ELEMENT_ID_IMS_CERTIFICATE,
    FFFF_ELEMENT_ID_CMS_CERTIFICATE,
    FFFF_ELEMENT_ID_DATA,
};



/**
 * @brief FFFF signature block field sizes
 */
#define FFFF_SIGNATURE_KEY_NAME_LENGTH  64
#define FFFF_SIGNATURE_KEY_HASH_LENGTH  32



/**
 * @brief FFFF element description
 *
 * The variable part of the FFFF header is an array of these elements.
 */
struct __attribute__ ((__packed__)) ffff_element
{
    uint32_t   element_type;
    uint32_t   element_id;              // enum ffff_element_id
    uint32_t   element_generation;
    uint32_t   element_location;
    uint32_t   element_length;
};


struct __attribute__ ((__packed__)) ffff_hdr
{
    // The global or "fixed" part of the header:
    uint8_t             sentinel[FFFF_SENTINEL_LENGTH];
    // NB. timestamp and flash_image_name are both ASCII strings
    char                timestamp[FFFF_TIMESTAMP_LENGTH];
    char                flash_image_name[FFFF_FLASH_IMAGE_NAME_LENGTH];
    uint32_t            flash_capacity;
    uint32_t            erase_block_size;
    uint32_t            header_block_size;
    uint32_t            flash_image_length;
    uint32_t            header_generation_number;

    // The element-specific part of the header.
    struct ffff_element element_table[1];   // Start of N-element array
};

/**
 * @brief Marks the end of the FFFF header buffer.
 *
 * The ffff_hdr_tail is placed at the end of the 2**n byte FFFF header buffer.
 */
struct
{
    uint8_t           sentinel[FFFF_SENTINEL_LENGTH];
} ffff_hdr_tail;


#endif // !_FFFF_H_
