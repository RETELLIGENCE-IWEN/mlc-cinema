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
M1.0 — Real 3D viewport
```

The primary supported format is the canonical
[`maneuver-log-contract`](https://github.com/RETELLIGENCE-IWEN/maneuver-log-contract)
**v1**. The earlier single-line `"$":"state"` demo format has been
removed.

The pipeline:

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

## What Works

`mlc-cinema` currently supports:

- Loading canonical MLC v1 `.mlc.ndjson` files.
- Parsing typed records: `header`, `body`, `step`, `action_spec`,
  `reward_spec`, `event`.
- Parsing step-scoped compact rows: `{"b":..., "x":[...28 values...]}`,
  `{"a":..., "x":[...]}`, `{"r":..., "x":[...]}`.
- Reader hardening: rejects non-v1 format, duplicates, monotonicity
  violations, unknown body / spec ids, length mismatches.
- Decoding the 28-element fundamental maneuver state vector and
  converting NED to viewer-frame coordinates.
- Multi-body timeline replay.
- `mlc-cinema-validate` CLI for headless smoke tests.
- Real 3D viewport (pygfx + wgpu) with orbit camera, zoom, ground grid,
  world axes, body primitives, trajectory trails, and selected-body
  highlighting.
- Auto-fit camera (`Frame All`) and `Reset Camera` actions.
- Selected-body telemetry display, including step index, altitude (m),
  and source format.
- Drag-and-drop opening from a file explorer.
- Playback speed multiplier (0.001× – 1000×, wall-clock paced).
- Qt-painted fallback viewport when pygfx + wgpu are unavailable.

---

## What is Not Yet Implemented

The current version does **not** yet implement:

- Body-to-viewer attitude conversion (rocket attitude is shown as the
  raw NED-frame quaternion; visually approximate but not yet
  frame-correct — see roadmap M1.1).
- Realistic rocket meshes.
- Pan / advanced camera controls.
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
- `rendercanvas`

`rendercanvas` is used by newer `wgpu` / `pygfx` stacks for Qt canvas
integration.

The viewport stays usable even if the hardware-accelerated renderer
is unavailable: the dispatcher falls back to a simpler Qt-painted 2D
projection instead of failing to launch.

---

## Run the Example

Run the included minimal MLC v1 example log:

```bash
mlc-cinema examples/logs/minimal_demo_v1.mlc.ndjson
```

Other bundled example logs:

```bash
mlc-cinema examples/logs/multibody_demo_v1.mlc.ndjson
mlc-cinema examples/logs/action_reward_event_demo_v1.mlc.ndjson
```

Equivalent module form:

```bash
python -m mlc_cinema.app examples/logs/minimal_demo_v1.mlc.ndjson
```

---

## Validation

Validate an MLC v1 file without opening the GUI:

```bash
mlc-cinema-validate examples/logs/minimal_demo_v1.mlc.ndjson
```

Exits with code `0` on success, `1` on a parse or timeline error. The
report includes the header, record counts, timeline duration, and
declared bodies. Suitable for CI smoke-testing external MLC producers.

Compatibility:

| Source | Status |
|---|---|
| maneuver-log-contract v1 examples | Supported |
| mlc-cinema minimal v1 demo | Supported |
| multibody MLC v1 logs | Supported |
| action/reward/event records | Parsed and validated, not yet visualized |
| legacy `"$":"state"` demo format | Removed |

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

An MLC v1 log is NDJSON: one JSON object per line. Records are
either **typed** (have a `$` field) or **step-scoped compact rows**
(no `$`; inherit `t` and `s` from the most recent `$=step`).

Example:

```json
{"$":"header","format":1,"label":"minimal_demo_v1","origin_lla":[0.651733,2.216568,120.0],"producer":"mlc-cinema-example","mode":"simulation","scenario":"single_body_mlc_v1_demo","seed":1}
{"$":"body","id":0,"name":"rocket_0","platform":"rocket","model":"generic_vtv_booster"}
{"$":"action_spec","id":0,"b":0,"fields":["raw_action_0","raw_action_1","raw_action_2","throttle_cmd","tvc_x_cmd","tvc_y_cmd"]}
{"$":"step","s":0,"t":0.0}
{"b":0,"x":[0.651733,2.216568,220.0,0.0,0.0,-100.0,0.0,0.0,10.0,10.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,-9.8,0.0,0.0,-9.8]}
{"a":0,"x":[0.0,0.0,1.0,0.70,0.0,0.0]}
```

See:

```text
examples/logs/minimal_demo_v1.mlc.ndjson
```

---

## MLC Input Format

Each line in an `.mlc.ndjson` file is a JSON object.

Some records are typed using `$`:

| Record Type | Purpose |
|---|---|
| `header` | Run metadata |
| `body` | Declares a body/entity |
| `step` | Opens a frame at `(s, t)`; subsequent untyped rows inherit it |
| `action_spec` | Action/control field declaration |
| `reward_spec` | Reward field declaration |
| `event` | Touchdown, crash, engine cutoff, stage separation, etc. |

Step-scoped compact samples do **not** use `$` and are recognized by
their key signature:

| Compact Row | Meaning |
|---|---|
| `{"b": body_id, "x": [...28 values...]}` | Body fundamental maneuver state |
| `{"a": action_spec_id, "x": [...]}` | Action sample matching an `action_spec` |
| `{"r": reward_spec_id, "x": [...]}` | Reward sample matching a `reward_spec` |

Unknown typed records should not crash the loader. Untyped rows that
don't match any compact pattern are reported as parse errors.

---

## Body State Vector (MLC v1)

Each body state row carries a 28-element `x` vector with a fixed layout:

| Index | Field | Unit |
|---|---|---|
| 0 | `lat_rad` | rad |
| 1 | `lon_rad` | rad |
| 2 | `alt_m` | m (geodetic) |
| 3 | `pn_m` | m (NED north) |
| 4 | `pe_m` | m (NED east) |
| 5 | `pd_m` | m (NED down) |
| 6 | `vn_mps` | m/s |
| 7 | `ve_mps` | m/s |
| 8 | `vd_mps` | m/s |
| 9 | `u_mps` | m/s (body x) |
| 10 | `v_mps` | m/s (body y) |
| 11 | `w_mps` | m/s (body z) |
| 12 | `qw` | scalar-first quat |
| 13 | `qx` | |
| 14 | `qy` | |
| 15 | `qz` | |
| 16 | `roll_rad` | rad |
| 17 | `pitch_rad` | rad |
| 18 | `yaw_rad` | rad |
| 19 | `p_radps` | rad/s (body) |
| 20 | `q_radps` | rad/s (body) |
| 21 | `r_radps` | rad/s (body) |
| 22 | `an_mps2` | m/s² |
| 23 | `ae_mps2` | m/s² |
| 24 | `ad_mps2` | m/s² |
| 25 | `ax_body_mps2` | m/s² |
| 26 | `ay_body_mps2` | m/s² |
| 27 | `az_body_mps2` | m/s² |

The MLC v1 contract specifies NED. Cinema decodes it into a viewer
frame with Z up:

```text
x_view =  pe_m
y_view =  pn_m
z_view = -pd_m
```

`altitude_m` in the telemetry panel comes from `x[2]` (geodetic
altitude). Producers are responsible for emitting canonical NED;
cinema does not attempt to detect or convert other world frames.

Interpolation is not required. The viewer uses nearest-frame lookup.

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
      minimal_demo_v1.mlc.ndjson
      multibody_demo_v1.mlc.ndjson
      action_reward_event_demo_v1.mlc.ndjson

  src/
    mlc_cinema/
      app.py
      cli_validate.py
      config.py

      mlc/
        records.py
        reader.py
        timeline.py
        validate.py
        mlc_v1.py
        summary.py

      scene/
        entities.py
        scene_model.py
        transforms.py
        bounds.py
        camera.py

      render/
        viewport.py
        pygfx_renderer.py
        fallback_viewport.py
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
mlc-cinema examples/logs/minimal_demo_v1.mlc.ndjson
```

Run through Python module entrypoint:

```bash
python -m mlc_cinema.app examples/logs/minimal_demo_v1.mlc.ndjson
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

### M0.5 — Maneuver Log Contract v1 Alignment

Status:

```text
Implemented
```

Focus:

- Replace the legacy `"$":"state"` demo format with canonical MLC v1.
- Step-scoped compact rows (`{"b": ..., "x": [28]}`).
- 28-element fundamental maneuver state vector.
- NED → viewer-frame coordinate conversion.
- `step_index`, `altitude_m`, and `source_format` in telemetry.
- Action / reward / event records collected for future milestones.

---

### M0.6 — MLC v1 Robustness and Ecosystem Smoke Test

Status:

```text
Implemented
```

Focus:

- Stricter reader validation (duplicate ids, monotonic steps,
  unknown spec ids, body/sample length checks).
- Multibody timeline grouping verified by example logs and tests.
- `mlc-cinema-validate` CLI for headless validation.
- `mlc/summary.py` parse summary suitable for CI reports.
- Additional example logs (multibody, action / reward / event).

---

### M1.0 — Real 3D Viewport

Status:

```text
Implemented
```

Focus:

- pygfx + wgpu 3D viewport with ground grid, world axes,
  per-platform body primitives, and trajectory trails.
- Orbit camera with mouse interaction.
- Auto-fit camera from scene bounds (`scene/bounds.py`).
- Renderer-agnostic camera state (`scene/camera.py`).
- Backward-scrub trail recomputation handled inside the viewport.
- Selected-body highlighting.
- Qt-painted fallback when pygfx is unavailable on the host.

Recommended next milestone:

```text
M1.1 — Attitude Frame Correctness
```

---

### M1.1 — Attitude Frame Correctness

Status:

```text
Planned
```

Goal:

```text
Make rendered body orientation match the MLC v1 attitude in the
viewer frame, not just the raw NED quaternion.
```

The current renderer converts position and velocity from NED to the
cinema viewer frame:

```text
x_view =  pe
y_view =  pn
z_view = -pd
```

…but feeds the body quaternion through unchanged (after
`(w,x,y,z) → (x,y,z,w)` for pylinalg). That is acceptable for M1.0
rough replay, but bodies' orientations are visually off because
``q_body_to_NED`` is not the same as ``q_body_to_viewer``.

M1.1 should:

- Add an explicit attitude conversion in `mlc_v1.py` (or a new
  `scene/attitude.py`): ``q_body_to_viewer = q_NED_to_viewer · q_body_to_NED``.
- Apply the conversion at decode time, so renderers always receive
  viewer-frame quaternions.
- Add unit tests against synthetic attitudes
  (e.g. yaw=90° about NED-down should rotate body forward from north
  to east in the viewer).
- Update the renderer to assume the quaternion is already
  viewer-frame.

This must land before any rocket-attitude / thrust-vector work in M2.

---

### M1.5 — Replay UX and Inspection Polish

Status:

```text
Planned
```

Goal:

```text
Smoother, more inspectable replay for long high-rate logs.
```

Possible work items:

- **Per-body trajectory caching.** Today the pygfx renderer rebuilds
  trail point lists from `timeline.frames[0..frame_index]` on every
  `set_scene_frame` call. For a 30 s / 100 Hz log that's 3000 list
  copies per frame change while playing. Cache `(N, 3)` numpy arrays
  per body once in `set_timeline()`, then on each frame slice the
  cached array.
- Optional pan camera control + `Shift`-drag mapping.
- "Show full trail / trail up to current frame" toggle.
- Screenshot export to PNG.
- Smarter grid step sizing from `SceneBounds`.
- Mouse-hover entity picking → telemetry panel.

---

### M2.0 — Rocket Visualization Layer

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

The current version is M1.0 (real 3D viewport). The recommended next
steps, in order, are:

```text
M1.1 — Attitude Frame Correctness
M1.5 — Replay UX and Inspection Polish
M2.0 — Rocket Visualization Layer
```

M1.1 is a small but important correctness milestone: rocket attitude
will not be visually right until ``q_body_to_NED`` is converted to
``q_body_to_viewer`` in the decoder. This must land before any
rocket-attitude / thrust-vector work in M2.

M1.5 is a polish milestone: cache per-body trajectory arrays so trail
recomputation stays cheap for long high-rate logs, plus assorted
inspection-experience improvements.

Do not rush into simulator-specific features too early. First make
the generic MLC replay experience solid and frame-correct.

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

`mlc-cinema` is proprietary. Not licensed for redistribution or
external reuse at this time. See `pyproject.toml` for the declared
license string.

---

## Status Summary

```text
Current milestone: M1.0
Current role: MLC v1 desktop 3D replay viewer
Current maturity: early but useful engineering visualizer
Primary value:
  - consumes canonical MLC v1
  - validates logs (mlc-cinema-validate)
  - replays multi-body motion in 3D
  - provides telemetry and trajectory inspection
Next milestone:
  M1.1 — attitude frame correctness
Then:
  M1.5 — replay UX polish
  M2.0 — rocket visualization layer
```