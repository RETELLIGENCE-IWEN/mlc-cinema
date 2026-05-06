"""Renderer-facing description of a body/entity in the scene."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SceneEntity:
    """A persistent entity in the scene.

    Mirrors the static metadata of an MLC body, but is decoupled from
    the MLC record class so the renderer never imports MLC types.
    """

    body_id: int
    name: str
    platform: str | None = None
    model: str | None = None
