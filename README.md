# mlc-cinema

## Purpose

`mlc-cinema` is an MLC-native desktop engineering visualizer. It loads
`.mlc.ndjson` log files and replays one or more simulated bodies in a
3D scene with basic telemetry and playback controls.

The app is **simulator-agnostic**. The MLC NDJSON file is the only
required input. There is no dependency on any specific simulator
(rocketsim, train, etc.).

## Current Status

This is the **M0** milestone: a minimal replay skeleton.

What works in M0:

- Load and parse an MLC NDJSON file.
- Build a timeline of frames.
- Display the bodies declared in the file as entities.
- Replay body positions over time.
- Show telemetry for a selected body.
- Play / pause / scrub the timeline.

What is **not** yet implemented:

- Rocket-specific HUDs (PFD, thrust vector, throttle flame, propellant gauges).
- Reward plots, action visualization, event markers.
- Realistic rocket meshes / shaders.
- Live streaming, video export, multi-episode comparison.
- Full MLC schema validation.
- Plugin / web viewer.

## Installation

```bash
pip install -e .
```

Python `>=3.11` is required. PySide6, numpy, pygfx, and wgpu are
declared as dependencies. The default M0 viewport falls back to a
Qt-painted side-view projection when a hardware-accelerated renderer
is not available, so the app still launches even if pygfx/wgpu cannot
initialize on the host.

## Run Example

```bash
mlc-cinema examples/logs/minimal_demo.mlc.ndjson
```

Or, equivalently:

```bash
python -m mlc_cinema.app examples/logs/minimal_demo.mlc.ndjson
```

You can also launch with no argument and use **File > Open MLC Log**.

## MLC Input Format for M0

Each line of the `.mlc.ndjson` file is a JSON object with a `$` field
naming the record type. M0 supports the following types:

- `header` — metadata about the run.
- `body` — declares a body/entity (id, name, platform, model).
- `state` — body state at a timestamp.

Optional record types (`action_spec`, `event`, `metric`, `marker`)
are accepted and stored for future use; unknown record types are
warned about but never crash the loader.

State fields:

| Field | Meaning                                         | Required |
|-------|-------------------------------------------------|----------|
| `t`   | timestamp (seconds)                             | yes      |
| `b`   | body id                                         | yes      |
| `p`   | position `[x, y, z]`                            | yes      |
| `v`   | velocity `[vx, vy, vz]`                         | no       |
| `q`   | scalar-first quaternion `[w, x, y, z]`          | no       |
| `w`   | angular velocity `[wx, wy, wz]`                 | no       |

See `examples/logs/minimal_demo.mlc.ndjson` for a working example.

## Architecture

```
MLC NDJSON
   │
   ▼
MLCReader        (mlc/reader.py)
   │
   ▼
MLCTimeline      (mlc/timeline.py)
   │
   ▼
SceneModel       (scene/scene_model.py)
   │
   ▼
Renderer         (render/viewport.py, render/pygfx_renderer.py)
   │
   ▼
PySide6 UI       (ui/main_window.py, ui/*_panel.py, ui/timeline_widget.py)
```

Hard rules:

- The renderer **does not** parse raw MLC NDJSON.
- The UI **does not** parse raw MLC NDJSON.
- Only `mlc/reader.py` understands raw MLC records.
- The renderer consumes `SceneFrame` (not MLC records), so future
  renderer backends are drop-in replaceable.

## Roadmap

After M0, the natural next milestones are:

1. Real pygfx renderer with proper meshes and camera controls.
2. Rocket-specific overlays: thrust vector arrow, throttle flame,
   propellant gauge, attitude indicator, landing-pad markers.
3. Event markers, action vector visualization, reward plots.
4. PFD-style telemetry panel.
5. Multi-episode loading and comparison.
6. Live streaming from a running simulator.
