"""Async TCP client for Arctic Spa communication.

Ported from the Node.js implementation (spa-client.js).
Uses asyncio streams for non-blocking TCP communication.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable

from .levven_packet import (
    MessageType,
    PacketParser,
    ParsedPacket,
    create_packet,
)
from .const import CONNECTION_TIMEOUT, DEFAULT_PORT, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Import protobuf module (generated from spa.proto)
from . import spa_pb2  # noqa: E402


class ArcticSpaClient:
    """Async TCP client for Arctic Spa communication."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._parser = PacketParser()
        self._sequence = 0
        self._poll_cycle = 0
        self._connected = False
        self._poll_task: asyncio.Task | None = None
        self._read_task: asyncio.Task | None = None
        self._callbacks: list[Callable[[], None]] = []
        self._disconnect_callbacks: list[Callable[[], None]] = []

        # State data
        self.live: dict[str, Any] | None = None
        self.info: dict[str, Any] | None = None
        self.config: dict[str, Any] | None = None
        self.last_update: datetime | None = None

    @property
    def available(self) -> bool:
        """Return True if connected and has received data."""
        return self._connected and self.live is not None

    @property
    def temperature_celsius(self) -> float | None:
        """Current water temperature in Celsius."""
        if self.live and self.live.get("temperature_fahrenheit") is not None:
            return self._f_to_c(self.live["temperature_fahrenheit"])
        return None

    @property
    def temperature_setpoint_celsius(self) -> float | None:
        """Target temperature in Celsius."""
        if self.live and self.live.get("temperature_setpoint_fahrenheit") is not None:
            return self._f_to_c(self.live["temperature_setpoint_fahrenheit"])
        return None

    @property
    def temperature_fahrenheit(self) -> int | None:
        """Current water temperature in Fahrenheit."""
        if self.live:
            return self.live.get("temperature_fahrenheit")
        return None

    @property
    def temperature_setpoint_fahrenheit(self) -> int | None:
        """Target temperature in Fahrenheit."""
        if self.live:
            return self.live.get("temperature_setpoint_fahrenheit")
        return None

    @staticmethod
    def _f_to_c(fahrenheit: int) -> float:
        """Convert Fahrenheit to Celsius, rounded to 1 decimal."""
        return round((fahrenheit - 32) * 5 / 9 * 10) / 10

    @staticmethod
    def _c_to_f(celsius: float) -> int:
        """Convert Celsius to Fahrenheit, rounded to integer."""
        return round(celsius * 9 / 5 + 32)

    async def connect(self) -> bool:
        """Connect to the spa. Returns True on success."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECTION_TIMEOUT,
            )
            self._connected = True
            self._parser.reset()
            self._sequence = 0
            self._poll_cycle = 0
            _LOGGER.info("Connected to Arctic Spa at %s:%s", self.host, self.port)

            # Start read and poll loops
            self._read_task = asyncio.create_task(self._read_loop())
            self._poll_task = asyncio.create_task(self._poll_loop())

            return True
        except (OSError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to connect to spa at %s:%s: %s", self.host, self.port, err)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the spa."""
        self._connected = False

        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None

        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        self._read_task = None

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass
        self._writer = None
        self._reader = None

    async def _read_loop(self) -> None:
        """Read bytes from TCP stream and feed to parser."""
        try:
            while self._connected and self._reader:
                data = await self._reader.read(1024)
                if not data:
                    _LOGGER.warning("Spa connection closed (EOF)")
                    break
                for byte in data:
                    packet = self._parser.feed(byte)
                    if packet:
                        self._handle_packet(packet)
        except asyncio.CancelledError:
            return
        except OSError as err:
            _LOGGER.error("Spa read error: %s", err)

        # Connection lost
        self._connected = False
        _LOGGER.info("Disconnected from spa")
        for callback in self._disconnect_callbacks:
            callback()

    async def _poll_loop(self) -> None:
        """Send polling requests every 3 seconds."""
        try:
            while self._connected:
                self._send_request()
                await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            return
        except OSError as err:
            _LOGGER.error("Spa poll error: %s", err)

    def _send_request(self) -> None:
        """Send a single poll request based on cycle position."""
        if not self._connected or not self._writer:
            return

        cycle = self._poll_cycle

        # 16-cycle pattern: PING, LIVE, LIVE, LIVE, CONFIG, LIVE, LIVE, LIVE,
        #                    INFO, LIVE, LIVE, LIVE, PING, LIVE, LIVE, LIVE
        if cycle % 16 == 4:
            msg_type = MessageType.CONFIGURATION
        elif cycle % 16 == 8:
            msg_type = MessageType.INFORMATION
        elif cycle % 4 == 0:
            msg_type = MessageType.PING
        else:
            msg_type = MessageType.LIVE

        try:
            packet = create_packet(msg_type, None, self._sequence)
            self._writer.write(packet)
            self._sequence += 1
            self._poll_cycle += 1
        except OSError as err:
            _LOGGER.error("Send error: %s", err)

    def _handle_packet(self, packet: ParsedPacket) -> None:
        """Decode protobuf payload and update state."""
        try:
            if packet.msg_type == MessageType.LIVE and packet.payload:
                msg = spa_pb2.spa_live()
                msg.ParseFromString(packet.payload)
                self.live = self._proto_to_dict(msg, spa_pb2.spa_live)
                self.last_update = datetime.now()
                self._fire_callbacks()

            elif packet.msg_type == MessageType.INFORMATION and packet.payload:
                try:
                    msg = spa_pb2.spa_information()
                    msg.ParseFromString(packet.payload)
                    self.info = self._proto_to_dict(msg, spa_pb2.spa_information)
                except Exception:
                    # Fallback: parse pH/ORP from raw bytes
                    if self.info is None:
                        self.info = {}
                    self._parse_ph_orp(packet.payload)
                self._fire_callbacks()

            elif packet.msg_type == MessageType.CONFIGURATION and packet.payload:
                msg = spa_pb2.spa_configuration()
                msg.ParseFromString(packet.payload)
                self.config = self._proto_to_dict(msg, spa_pb2.spa_configuration)
                self._fire_callbacks()

        except Exception as err:
            _LOGGER.error("Error parsing %s packet: %s", packet.type_name, err)

    def _proto_to_dict(self, msg: Any, descriptor: Any) -> dict[str, Any]:
        """Convert a protobuf message to a dict with all fields."""
        result = {}
        for field in descriptor.DESCRIPTOR.fields:
            value = getattr(msg, field.name)
            # Convert enum values to their names
            if field.enum_type:
                enum_desc = field.enum_type
                for val in enum_desc.values:
                    if val.number == value:
                        value = val.name
                        break
            result[field.name] = value
        return result

    def _parse_ph_orp(self, payload: bytes) -> None:
        """Parse pH and ORP from non-protobuf payload (firmware fallback)."""
        orp_marker = 0x10
        try:
            idx = payload.index(bytes([orp_marker]))
            if idx + 5 < len(payload):
                orp_raw = payload[idx + 1] | (payload[idx + 2] << 8)
                ph_raw = payload[idx + 4] | (payload[idx + 5] << 8)
                self.info["orp"] = orp_raw / 2.0
                self.info["ph"] = ph_raw / 200.0
        except (ValueError, IndexError):
            pass

    async def send_command(self, **kwargs: Any) -> bool:
        """Send a command to the spa.

        Keyword arguments map to spa_command protobuf fields:
          set_temperature_setpoint_fahrenheit=104
          set_pump_1=2  (0=OFF, 1=LOW, 2=HIGH)
          set_lights=True
          etc.
        """
        if not self._connected or not self._writer:
            return False

        try:
            cmd = spa_pb2.spa_command()
            for key, value in kwargs.items():
                setattr(cmd, key, value)
            payload = cmd.SerializeToString()
            packet = create_packet(MessageType.COMMAND, payload, self._sequence)
            self._writer.write(packet)
            await self._writer.drain()
            self._sequence += 1
            _LOGGER.debug("Command sent: %s", kwargs)
            return True
        except Exception as err:
            _LOGGER.error("Command error: %s", err)
            return False

    async def set_temperature(self, celsius: float) -> bool:
        """Set target temperature in Celsius."""
        fahrenheit = self._c_to_f(celsius)
        return await self.send_command(
            set_temperature_setpoint_fahrenheit=fahrenheit
        )

    def register_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for state updates. Returns unregister function."""
        self._callbacks.append(callback)

        def unregister() -> None:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return unregister

    def register_disconnect_callback(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback for disconnect events."""
        self._disconnect_callbacks.append(callback)

        def unregister() -> None:
            if callback in self._disconnect_callbacks:
                self._disconnect_callbacks.remove(callback)

        return unregister

    def _fire_callbacks(self) -> None:
        """Notify all registered callbacks of a state update."""
        for callback in self._callbacks:
            try:
                callback()
            except Exception as err:
                _LOGGER.error("Callback error: %s", err)
