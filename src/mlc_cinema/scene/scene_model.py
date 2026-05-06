"""Scene-level dataclasses consumed by the renderer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mlc_cinema.mlc.records import MLCBody
from mlc_cinema.mlc.timeline import TimelineFrame
from mlc_cinema.scene.entities import SceneEntity


@dataclass
class SceneBodyState:
    """Body state at a single instant, in renderer-friendly form."""

    body_id: int
    position: np.ndarray
    velocity: np.ndarray | None = None
    quaternion: np.ndarray | None = None


@dataclass
class SceneFrame:
    """All body states at one instant in time."""

    t: float
    body_states: dict[int, SceneBodyState]


def scene_frame_from_timeline_frame(frame: TimelineFrame) -> SceneFrame:
    """Project a ``TimelineFrame`` into a renderer-facing ``SceneFrame``."""

    body_states: dict[int, SceneBodyState] = {}
    for body_id, state in frame.states_by_body.items():
        body_states[body_id] = SceneBodyState(
            body_id=body_id,
            position=state.position,
            velocity=state.velocity,
            quaternion=state.quaternion,
        )
    return SceneFrame(t=frame.t, body_states=body_states)


def scene_entities_from_bodies(
    bodies: dict[int, MLCBody],
) -> dict[int, SceneEntity]:
    """Convert a body dict into renderer-facing entities."""

    return {
        body_id: SceneEntity(
            body_id=body.id,
            name=body.name,
            platform=body.platform,
            model=body.model,
        )
        for body_id, body in bodies.items()
    }
