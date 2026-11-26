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


def png_grayscale_pixels(path):
    """Decode bounded 8-bit RGB PNG into grayscale intensities (0..255).

    Supports all standard PNG filter types. RGBA and color-management chunks
    are deliberately unsupported for reproducible quality metrics.
    """
    raw = Path(path).read_bytes()
    if len(raw) > 8 * 1024 * 1024 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Unsupported PNG signature or input size")
    offset = 8
    width = height = None
    compressed = bytearray()
    saw_ihdr = saw_iend = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("Truncated PNG chunk")
        size = struct.unpack_from(">I", raw, offset)[0]
        if size > len(raw) - offset - 12:
            raise ValueError("Bad PNG chunk length")
        tag = raw[offset + 4:offset + 8]
        payload = raw[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", raw, offset + 8 + size)[0]
        if zlib.crc32(tag + payload) != crc:
            raise ValueError("PNG chunk checksum mismatch")
        if not saw_ihdr and tag != b"IHDR":
            raise ValueError("IHDR not first")
        if tag == b"IHDR":
            if saw_ihdr or len(payload) != 13:
                raise ValueError("Invalid IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload)
            if (width < 3 or height < 3 or width * height > 1_000_000
                    or depth != 8 or color != 2 or compression or filtering or interlace):
                raise ValueError("Only non-interlaced RGB8 PNG >=3x3 supported")
            saw_ihdr = True
        elif tag == b"IDAT":
            compressed.extend(payload)
        elif tag == b"IEND":
            if size or not compressed:
                raise ValueError("Missing image data")
            offset += 12
            if offset != len(raw):
                raise ValueError("Trailing bytes after IEND")
            saw_iend = True
            break
        else:
            # Unmodeled metadata may affect appearance or interpretation.
            raise ValueError("Unsupported PNG ancillary or critical chunk")
        offset += size + 12
    if not saw_iend or width is None:
        raise ValueError("Incomplete PNG")
    row_size = width * 3
    expected = height * (row_size + 1)
    dec = zlib.decompressobj()
    scanlines = dec.decompress(bytes(compressed), expected + 1)
    if (len(scanlines) != expected or not dec.eof or
            dec.unused_data or dec.unconsumed_tail or dec.flush()):
        raise ValueError("Invalid PNG pixel data")
    prev = bytearray(row_size)
    values = []
    for y in range(height):
        start = y * (row_size + 1)
        mode = scanlines[start]
        line = bytearray(scanlines[start + 1:start + 1 + row_size])
        if mode > 4:
            raise ValueError("Invalid PNG scanline filter")
        for pos in range(row_size):
            left = line[pos - 3] if pos >= 3 else 0
            upper = prev[pos]
            upper_left = prev[pos - 3] if pos >= 3 else 0
            if mode == 1:
                line[pos] = (line[pos] + left) & 255
            elif mode == 2:
                line[pos] = (line[pos] + upper) & 255
            elif mode == 3:
                line[pos] = (line[pos] + (left + upper) // 2) & 255
            elif mode == 4:
                predictor = left + upper - upper_left
                distances = (abs(predictor - left), abs(predictor - upper),
                             abs(predictor - upper_left))
                predicted = (left, upper, upper_left)[distances.index(min(distances))]
                line[pos] = (line[pos] + predicted) & 255
        for x in range(width):
            at = 3 * x
            r, g, b = line[at:at + 3]
            # Deterministic BT.601 integer grayscale.
            values.append((299 * r + 587 * g + 114 * b + 500) // 1000)
        prev = line
    return width, height, values
