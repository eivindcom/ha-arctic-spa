"""Levven binary protocol: packet creation, parsing, and CRC32.

Ported from the Node.js implementation (levven-packet.js).
Protocol uses a 20-byte header + variable protobuf payload over TCP.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum


class MessageType(IntEnum):
    """Levven protocol message types."""

    LIVE = 0x00
    COMMAND = 0x01
    COMMAND_ACK = 0x02
    CONFIGURATION = 0x03
    CONFIG_EXTENDED = 0x04
    SETTINGS = 0x06
    SCHEDULE = 0x07
    PING = 0x0A
    ERROR_STATUS = 0x10
    INFORMATION = 0x30
    ONZEN_SETTINGS = 0x32


MESSAGE_TYPE_NAME: dict[int, str] = {v.value: v.name for v in MessageType}

# Magic bytes that start every Levven packet
MAGIC = bytes([0xAB, 0xAD, 0x1D, 0x3A])


def crc32(data: bytes) -> int:
    """Calculate CRC32 checksum (polynomial 0xEDB88320)."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def create_packet(
    msg_type: int, payload: bytes | None = None, sequence: int = 0
) -> bytes:
    """Create a Levven packet with 20-byte header + optional payload.

    Header format (big-endian):
      [0:4]   Magic bytes (AB AD 1D 3A)
      [4:8]   CRC32 checksum
      [8:12]  Sequence number
      [12:16] Field2 (always 0 for outgoing)
      [16:18] Message type
      [18:20] Payload size
    """
    payload = payload or b""
    size = len(payload)

    # Build header with CRC placeholder (zeros)
    header = bytearray(20)
    header[0:4] = MAGIC
    struct.pack_into(">I", header, 8, sequence)
    struct.pack_into(">I", header, 12, 0)  # field2
    struct.pack_into(">H", header, 16, msg_type)
    struct.pack_into(">H", header, 18, size)

    packet = bytearray(header) + bytearray(payload)

    # Calculate and insert CRC32
    checksum = crc32(bytes(packet))
    struct.pack_into(">I", packet, 4, checksum)

    return bytes(packet)


@dataclass
class ParsedPacket:
    """A parsed Levven packet."""

    msg_type: int
    type_name: str
    counter: int
    payload: bytes


class PacketParser:
    """Byte-by-byte state machine parser for incoming Levven packets.

    Feed bytes one at a time via feed(). Returns a ParsedPacket when
    a complete packet has been received, or None otherwise.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset parser state."""
        self._state = 0
        self._checksum = bytearray(4)
        self._counter = bytearray(4)
        self._field2 = bytearray(4)
        self._msg_type = bytearray(2)
        self._size = bytearray(2)
        self._payload: bytearray | None = None
        self._payload_offset = 0

    def feed(self, byte: int) -> ParsedPacket | None:
        """Feed a single byte. Returns ParsedPacket when complete."""
        s = self._state

        # States 0-3: Magic bytes (AB AD 1D 3A)
        if s == 0:
            self._state = 1 if byte == 0xAB else 0
        elif s == 1:
            if byte == 0xAD:
                self._state = 2
            elif byte == 0xAB:
                self._state = 1
            else:
                self._state = 0
        elif s == 2:
            if byte == 0x1D:
                self._state = 3
            elif byte == 0xAB:
                self._state = 1
            else:
                self._state = 0
        elif s == 3:
            if byte == 0x3A:
                self._state = 4
            elif byte == 0xAB:
                self._state = 1
            else:
                self._state = 0

        # States 4-7: Checksum
        elif 4 <= s <= 7:
            self._checksum[s - 4] = byte
            self._state = s + 1

        # States 8-11: Counter (sequence number)
        elif 8 <= s <= 11:
            self._counter[s - 8] = byte
            self._state = s + 1

        # States 12-15: Field2
        elif 12 <= s <= 15:
            self._field2[s - 12] = byte
            self._state = s + 1

        # States 16-17: Message type
        elif s == 16:
            self._msg_type[0] = byte
            self._state = 17
        elif s == 17:
            self._msg_type[1] = byte
            self._state = 18

        # States 18-19: Payload size
        elif s == 18:
            self._size[0] = byte
            self._state = 19
        elif s == 19:
            self._size[1] = byte
            payload_size = struct.unpack(">H", self._size)[0]
            if payload_size == 0:
                result = self._build_result()
                self.reset()
                return result
            self._payload = bytearray(payload_size)
            self._payload_offset = 0
            self._state = 20

        # State 20: Payload bytes
        elif s == 20:
            self._payload[self._payload_offset] = byte
            self._payload_offset += 1
            if self._payload_offset >= len(self._payload):
                result = self._build_result()
                self.reset()
                return result

        return None

    def _build_result(self) -> ParsedPacket:
        """Build a ParsedPacket from accumulated state."""
        type_val = struct.unpack(">H", self._msg_type)[0]
        counter = struct.unpack(">I", self._counter)[0]
        return ParsedPacket(
            msg_type=type_val,
            type_name=MESSAGE_TYPE_NAME.get(
                type_val, f"UNKNOWN(0x{type_val:02x})"
            ),
            counter=counter,
            payload=bytes(self._payload) if self._payload else b"",
        )
