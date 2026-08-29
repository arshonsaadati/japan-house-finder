"""Listing sources. Each module exposes `fetch(client, **opts) -> list[Listing]`."""

from __future__ import annotations

from . import akiyabank_blogspot, homes_akiyabank, suumo

# name -> module. CLI iterates this registry.
REGISTRY = {
    "blogspot": akiyabank_blogspot,
    "homes": homes_akiyabank,
    "suumo": suumo,
}

__all__ = ["REGISTRY"]
