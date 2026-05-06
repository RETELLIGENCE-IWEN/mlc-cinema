# mlc-cinema

**MLC-native desktop replay and engineering analysis viewer.**

`mlc-cinema` is a desktop visualizer for replaying autonomous mission logs written in the MLC NDJSON format. It is designed for rockets, UAVs, multi-agent simulations, reinforcement-learning episodes, and future autonomy mission analysis.

The project starts simple: load an `.mlc.ndjson` file, build a timeline, replay entities, and inspect basic telemetry.

The long-term goal is larger:

> Make MLC a common replay layer for simulators, training environments, and analysis tools.

---

## Current Status

`mlc-cinema` is currently at:

```text
M0 — Desktop Replay Skeleton
```

M0 proves the core architecture:

```text
MLC NDJSON
  ↓
MLC reader
  ↓
Timeline
  ↓
Scene model
  ↓
Viewport / renderer
  ↓
PySide6 desktop UI
```

This milestone is intentionally minimal. It is not yet a full rocket visualizer, but it already establishes the replay pipeline that future rocket/UAV-specific features can build on.

---

## What Works in M0

M0 currently supports:

- Loading `.mlc.ndjson` files.
- Parsing basic MLC records.
- Building a frame timeline.
- Displaying declared bodies/entities.
- Replaying body positions over time.
- Play / pause timeline control.
- Timeline scrubbing.
- Selected-body telemetry display.
- Basic renderer/viewport separation.
- Unknown or future MLC record types handled without crashing.

---

## What M0 Is Not Yet

M0 does **not** yet implement:

- Realistic rocket meshes.
- Full 3D camera controls.
- Thrust vector visualization.
- Throttle flame visualization.
- Propellant gauges.
- Landing pad markers.
- PFD-style flight display.
- Reward plots.
- Action vector visualization.
- Event marker rendering.
- Multi-episode comparison.
- Live streaming from a simulator.
- Video export.
- Full MLC schema validation.
- Plugin system.

These are planned for later milestones.

---

## Installation

Recommended Python version:

```text
Python >= 3.11
```

Install in editable mode:

```bash
pip install -e .
```

The project currently depends on:

- `numpy`
- `PySide6`
- `pygfx`
- `wgpu`

The M0 viewport is designed to remain usable even if a hardware-accelerated renderer is not available. In that case, the app can fall back to a simpler Qt-painted projection instead of failing immediately.

---

## Run the Example

Run the included minimal example log:

```bash
mlc-cinema examples/logs/minimal_demo.mlc.ndjson
```

Equivalent module form:

```bash
python -m mlc_cinema.app examples/logs/minimal_demo.mlc.ndjson
```

You can also launch the app without an argument:

```bash
mlc-cinema
```

Then open a log from the menu:

```text
File > Open MLC Log
```

---

## Example MLC Log

A minimal MLC log is NDJSON: one JSON object per line.

Example:

```json
{"$":"header","format":1,"label":"minimal_demo","producer":"mlc-cinema-example","mode":"simulation","scenario":"single_body_demo","seed":1}
{"$":"body","id":0,"name":"rocket_0","platform":"rocket","model":"generic_vtv_booster"}
{"$":"state","t":0.0,"b":0,"p":[0.0,0.0,100.0],"v":[0.0,0.0,-10.0],"q":[1.0,0.0,0.0,0.0],"w":[0.0,0.0,0.0]}
{"$":"state","t":0.5,"b":0,"p":[0.0,0.0,95.0],"v":[0.0,0.0,-9.5],"q":[1.0,0.0,0.0,0.0],"w":[0.0,0.0,0.0]}
{"$":"state","t":1.0,"b":0,"p":[0.0,0.0,90.5],"v":[0.0,0.0,-9.0],"q":[1.0,0.0,0.0,0.0],"w":[0.0,0.0,0.0]}
```

See:

```text
examples/logs/minimal_demo.mlc.ndjson
```

---

## MLC Input Format for M0

Each line in an `.mlc.ndjson` file is a JSON object.

Each record must contain a `$` field describing the record type.

M0 supports these record types:

| Record Type | Purpose |
|---|---|
| `header` | Run metadata |
| `body` | Declares a body/entity |
| `state` | Body state at a timestamp |

Optional or future record types may be accepted and preserved or ignored safely.

Examples of future record types:

| Record Type | Future Use |
|---|---|
| `action_spec` | Action/control field declaration |
| `event` | Touchdown, crash, engine cutoff, stage separation, etc. |
| `metric` | Reward, error, fuel, constraint violation, etc. |
| `marker` | Waypoint, target, landing pad, obstacle, etc. |

Unknown record types should not crash the loader.

---

## State Record Fields

M0 state records use the following fields:

| Field | Meaning | Required |
|---|---|---|
| `t` | Timestamp in seconds | Yes |
| `b` | Body/entity id | Yes |
| `p` | Position `[x, y, z]` | Yes |
| `v` | Velocity `[vx, vy, vz]` | No |
| `q` | Scalar-first quaternion `[w, x, y, z]` | No |
| `w` | Angular velocity `[wx, wy, wz]` | No |

M0 assumes:

```text
altitude = position z
quaternion convention = [w, x, y, z]
```

Interpolation is not required in M0. The viewer may use nearest-frame lookup.

---

## Architecture

The project is intentionally separated into layers.

```text
MLC NDJSON file
  │
  ▼
MLCReader
  │
  ▼
MLCTimeline
  │
  ▼
SceneModel
  │
  ▼
Renderer / Viewport
  │
  ▼
PySide6 UI
```

The key architectural rule:

> The renderer does not parse MLC directly.

Instead:

- `mlc/reader.py` reads raw NDJSON records.
- `mlc/timeline.py` builds replay frames.
- `scene/scene_model.py` converts timeline frames into scene frames.
- `render/viewport.py` displays scene frames.
- `ui/main_window.py` coordinates the desktop application.

This keeps the app simulator-agnostic.

`mlc-cinema` should not depend on any one simulator, training repo, or dynamics engine. A simulator only needs to export MLC-compatible logs.

---

## Repository Structure

```text
mlc-cinema/
  pyproject.toml
  README.md
  .gitignore

  examples/
    logs/
      minimal_demo.mlc.ndjson

  src/
    mlc_cinema/
      app.py
      config.py

      mlc/
        records.py
        reader.py
        timeline.py
        validate.py

      scene/
        entities.py
        scene_model.py
        transforms.py

      render/
        viewport.py
        pygfx_renderer.py
        primitives.py

      ui/
        main_window.py
        timeline_widget.py
        telemetry_panel.py
        entity_tree.py

      playback/
        controller.py

  tests/
    test_mlc_reader.py
    test_timeline.py
    test_transforms.py
```

---

## Development

Install locally:

```bash
pip install -e .
```

Run tests:

```bash
python -m pytest
```

Run the app:

```bash
mlc-cinema examples/logs/minimal_demo.mlc.ndjson
```

Run through Python module entrypoint:

```bash
python -m mlc_cinema.app examples/logs/minimal_demo.mlc.ndjson
```

---

## Design Philosophy

`mlc-cinema` is not meant to be a simulator.

It is meant to be a replay and analysis tool.

The simulator produces logs:

```text
simulator / training environment / experiment
  ↓
MLC NDJSON log
```

`mlc-cinema` consumes logs:

```text
MLC NDJSON log
  ↓
visual replay
  ↓
engineering analysis
```

This separation allows multiple simulators to share the same viewer.

Possible producers:

- `project-nightfall-rocketsim`
- `project-nightfall-train`
- quadcopter landing environments
- multi-agent UAV simulations
- external autonomy experiments
- future live-streaming bridges

Possible consumers:

- `mlc-cinema`
- lightweight web viewers
- notebook analysis tools
- batch metric analyzers
- CI regression replay tools

---

## Roadmap

### M0 — Desktop Replay Skeleton

Status:

```text
Implemented
```

Focus:

- File loading.
- MLC parsing.
- Timeline construction.
- Entity display.
- Basic playback.
- Basic telemetry.
- Clean architecture.

---

### M1 — Real 3D Viewport

Goal:

```text
Upgrade from basic projection/placeholder rendering to a more capable 3D viewport.
```

Possible features:

- Proper 3D camera.
- Orbit / pan / zoom controls.
- Ground grid.
- World axes.
- Body primitives.
- Trajectory trails.
- Better scaling and framing.
- Basic screenshot capture.

---

### M2 — Rocket Visualization Layer

Goal:

```text
Make rocket episodes visually meaningful.
```

Possible features:

- Rocket body primitive.
- Landing pad marker.
- Thrust vector arrow.
- Throttle flame indicator.
- Velocity vector.
- Attitude indicator.
- Tilt angle display.
- Vertical speed display.
- Propellant gauge.
- Touchdown/crash/end-condition annotation.

---

### M3 — RL Episode Analysis

Goal:

```text
Support reinforcement-learning debugging and training analysis.
```

Possible features:

- Reward plot.
- Reward component plot.
- Action vector display.
- Constraint violation markers.
- Terminal reason display.
- Success/failure summary.
- Episode metadata panel.

---

### M4 — Multi-Episode Comparison

Goal:

```text
Compare different runs, policies, checkpoints, or scenarios.
```

Possible features:

- Load multiple logs.
- Overlay trajectories.
- Compare terminal states.
- Compare reward curves.
- Compare landing quality.
- Compare fuel usage.
- Compare policy behavior.

---

### M5 — Live Streaming

Goal:

```text
Replay data from a running simulator or training process.
```

Possible features:

- Live MLC stream input.
- Pause/resume live follow.
- Rolling timeline buffer.
- Real-time telemetry.
- Socket or file-tail based input.
- Future ROS 2 bridge support.

---

## Near-Term Priority

The recommended next step after M0 is:

```text
M1 — Real 3D Viewport
```

M1 should focus on making the visual scene genuinely useful while preserving the existing architecture.

Do not rush into simulator-specific features too early. First make the generic MLC replay experience solid.

Recommended M1 priorities:

1. Stable 3D camera.
2. Ground grid and axes.
3. Body primitives.
4. Trajectory trails.
5. Better viewport scaling.
6. Frame/time display polish.
7. Screenshot export if easy.

After that, add rocket-specific visual semantics in M2.

---

## Project Identity

`mlc-cinema` is part of a broader MLC-oriented tooling direction:

```text
MLC = common mission log / machine log / motion log layer
```

The intent is to make simulation results inspectable, portable, and comparable across projects.

In this sense, `mlc-cinema` is not just a viewer. It is the first desktop analysis tool built around the MLC idea.

---

## License

Add a license before public release or reuse by other projects.

Recommended default:

```text
MIT License
```

or, if stronger copyleft is desired:

```text
Apache-2.0
```

---

## Status Summary

```text
Current milestone: M0
Current role: MLC desktop replay skeleton
Current maturity: early prototype
Primary value: proves the replay architecture
Next milestone: real 3D viewport and camera controls
```