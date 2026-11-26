"""Bounded PNG structural observation for dimension checks.

Only non-interlaced 8-bit RGB/RGBA PNG is decoded sufficiently to validate
chunk checksums and scanline structure. Unsupported variants abstain.
"""
import struct
import zlib
from pathlib import Path


def png_dimensions(path):
    raw = Path(path).read_bytes()
    if len(raw) > 8 * 1024 * 1024 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG signature missing or file exceeds 8 MiB")
    offset = 8
    width = height = channels = None
    compressed = bytearray()
    saw_ihdr = saw_iend = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", raw, offset)[0]
        if length > len(raw) - offset - 12:
            raise ValueError("Truncated PNG payload")
        tag = raw[offset + 4:offset + 8]
        payload = raw[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack_from(">I", raw, offset + 8 + length)[0]
        if zlib.crc32(tag + payload) != expected_crc:
            raise ValueError("Invalid PNG chunk CRC")
        if not saw_ihdr and tag != b"IHDR":
            raise ValueError("PNG IHDR must be first")
        if tag == b"IHDR":
            if saw_ihdr or length != 13:
                raise ValueError("Invalid PNG IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload)
            if (width < 1 or height < 1 or width * height > 4_000_000
                    or depth != 8 or color not in (2, 6)
                    or compression or filtering or interlace):
                raise ValueError("Unsupported PNG pixel layout")
            channels = 3 if color == 2 else 4
            saw_ihdr = True
        elif tag == b"IDAT":
            if saw_iend:
                raise ValueError("PNG IDAT after IEND")
            compressed.extend(payload)
        elif tag == b"IEND":
            if length or not compressed:
                raise ValueError("PNG missing IDAT or invalid IEND")
            offset += 12
            if offset != len(raw):
                raise ValueError("PNG trailing data")
            saw_iend = True
            break
        elif tag[0] & 32 == 0:
            # Do not silently interpret unsupported critical chunks.
            raise ValueError("Unsupported PNG critical chunk")
        offset += length + 12
    if not saw_iend or width is None:
        raise ValueError("Incomplete PNG")
    row_bytes = width * channels
    expected_size = height * (row_bytes + 1)
    decompressor = zlib.decompressobj()
    pixels = decompressor.decompress(bytes(compressed), expected_size + 1)
    if (len(pixels) != expected_size or not decompressor.eof
            or decompressor.unused_data or decompressor.unconsumed_tail
            or decompressor.flush()):
        raise ValueError("Invalid PNG compressed pixel stream")
    for row in range(height):
        if pixels[row * (row_bytes + 1)] > 4:
            raise ValueError("Invalid PNG scanline filter")
    return width, height
