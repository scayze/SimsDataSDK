"""Read the venue ID from a lot architecture record bundle."""

import struct


def architecture_venue_id(data: bytes) -> int | None:
    """Return the venue in the LDNB lot settings record, if readable."""
    if len(data) < 40 or data[:8] != b"LDNB\x03\0\0\0":
        return None
    count, instances, offsets, body, group_count, groups = struct.unpack_from("<6I", data, 16)
    if (instances + 8 * count > len(data) or offsets + 3 * (count + 1) > len(data)
            or groups + 12 * (group_count + 1) > len(data)):
        return None
    for group_index in range(group_count):
        position = groups + 12 * group_index
        type_id, group, first = struct.unpack_from("<3I", data, position)
        if (type_id, group) != (0xE6BBD7DE, 0):
            continue
        stop = struct.unpack_from("<I", data, position + 20)[0]
        if not first <= stop <= count:
            return None
        for index in range(first, stop):
            if struct.unpack_from("<Q", data, instances + 8 * index)[0] != 1:
                continue
            position = offsets + 3 * index
            start = body + int.from_bytes(data[position:position + 3], "big")
            end = body + int.from_bytes(data[position + 3:position + 6], "big")
            if 40 <= start <= end - 12 and end <= len(data):
                version, venue = struct.unpack_from("<IQ", data, start)
                if version in (3, 4, 5, 6):
                    return venue or None
    return None
