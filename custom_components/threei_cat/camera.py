"""Camera platform for 3i Smart Device - Map placeholder."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThreeiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 3i camera entities."""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ThreeiMapCamera(coordinator)])


def _generate_placeholder_image() -> bytes:
    """Generate a simple placeholder PNG image with 'Map not available' text.

    Returns a minimal valid PNG file.
    """
    # Minimal 1x1 white PNG (8 bytes IDAT)
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    # IHDR: 200x100, 8-bit RGB
    width, height = 200, 100
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    # IDAT: simple white image with gray border
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"  # filter byte
        for x in range(width):
            # Gray border, white interior
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                raw_data += b"\xcc\xcc\xcc"  # gray border
            else:
                raw_data += b"\xff\xff\xff"  # white fill
    compressed = zlib.compress(raw_data)

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr_data)
    png += _chunk(b"IDAT", compressed)
    png += _chunk(b"IEND", b"")
    return png


class ThreeiMapCamera(CoordinatorEntity, Camera):
    """Camera entity showing the robot's map (placeholder for now)."""

    _attr_has_entity_name = True
    _attr_name = "Map"
    _attr_icon = "mdi:map"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize the map camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.device_id}_map"
        self._attr_device_info = coordinator.device_info
        self._placeholder_image: bytes | None = None

    @property
    def is_on(self) -> bool:
        """Return True if the camera is on."""
        return True

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a camera image (placeholder)."""
        if self._placeholder_image is None:
            self._placeholder_image = _generate_placeholder_image()
        return self._placeholder_image

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "status": "Map data not available - placeholder",
            "note": "Map API endpoints need to be reverse-engineered from the 3i app",
        }
