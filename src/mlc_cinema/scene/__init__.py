"""Renderer-facing scene model.

The scene module is the boundary between MLC parsing and rendering.
Modules under ``render/`` should consume the dataclasses defined here
and never reach back into ``mlc_cinema.mlc.*`` directly.
"""

from mlc_cinema.scene.attitude import (
    NED_TO_VIEWER_MATRIX,
    body_to_ned_quaternion_to_body_to_viewer_wxyz,
    ned_to_viewer_quaternion_wxyz,
    quaternion_multiply_wxyz,
)
from mlc_cinema.scene.entities import SceneEntity
from mlc_cinema.scene.scene_model import (
    SceneBodyState,
    SceneFrame,
    scene_entities_from_bodies,
    scene_frame_from_timeline_frame,
)
from mlc_cinema.scene.transforms import (
    normalize_quaternion,
    quaternion_wxyz_to_rotation_matrix,
)

__all__ = [
    "NED_TO_VIEWER_MATRIX",
    "SceneBodyState",
    "SceneEntity",
    "SceneFrame",
    "body_to_ned_quaternion_to_body_to_viewer_wxyz",
    "ned_to_viewer_quaternion_wxyz",
    "normalize_quaternion",
    "quaternion_multiply_wxyz",
    "quaternion_wxyz_to_rotation_matrix",
    "scene_entities_from_bodies",
    "scene_frame_from_timeline_frame",
]
