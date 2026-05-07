"""Quick diagnostic: why is mlc-cinema falling back to the 2D viewport?

Usage:

    python scripts/diag_pygfx.py

Prints the version of every relevant package, attempts the imports the
dispatcher does, and tries to instantiate a ``PygfxViewport`` — surfacing
whichever step actually fails.
"""

from __future__ import annotations

import sys
import traceback


def _try(label: str, fn) -> None:
    print(f"--- {label} ---")
    try:
        fn()
    except Exception:
        traceback.print_exc()
    print()


def _versions() -> None:
    print("Python:", sys.version.split()[0])
    for name in ("PySide6", "pygfx", "wgpu", "rendercanvas", "pylinalg", "numpy"):
        try:
            mod = __import__(name)
        except Exception as exc:
            print(f"  {name}: NOT IMPORTABLE ({exc!r})")
            continue
        ver = getattr(mod, "__version__", "?")
        print(f"  {name}: {ver}")


def _wgpu_canvas() -> None:
    try:
        from rendercanvas.qt import QRenderWidget

        print("rendercanvas.qt.QRenderWidget:", QRenderWidget)
        return
    except Exception as exc:
        print(f"rendercanvas.qt failed: {exc!r}")
    try:
        from wgpu.gui.qt import WgpuCanvas

        print("wgpu.gui.qt.WgpuCanvas:", WgpuCanvas)
    except Exception as exc:
        print(f"wgpu.gui.qt failed: {exc!r}")
        from wgpu.gui.auto import WgpuCanvas

        print("wgpu.gui.auto.WgpuCanvas:", WgpuCanvas)


def _qapp_then_viewport() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    from mlc_cinema.render import pygfx_renderer

    print("pygfx_renderer.is_available():", pygfx_renderer.is_available())
    print("pygfx_renderer.gfx:", pygfx_renderer.gfx)
    print("pygfx_renderer.WgpuCanvas:", pygfx_renderer.WgpuCanvas)
    if pygfx_renderer.is_available():
        viewport = pygfx_renderer.PygfxViewport()
        print("PygfxViewport instantiated OK:", viewport)
    # Don't run the event loop.


if __name__ == "__main__":
    _try("Versions", _versions)
    _try("WgpuCanvas import", _wgpu_canvas)
    _try("PygfxViewport instantiation", _qapp_then_viewport)
