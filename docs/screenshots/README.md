# Cursor-free native screenshots

The current README uses `studio-dark.png`, `studio-light.png` and
`studio-preview.png`. They are unmodified 1600 × 1000 RGBA frames read from the
real Windows/wgpu scene renderer, encoded losslessly as PNG. The OS cursor,
pointer highlight, title bar and desktop overlays are never part of this frame.
No cursor was painted out and no mockup was substituted for running UI.

Captured on 2026-11-04 with AMD Radeon(TM) Graphics / DX12, Python 3.13,
the 0.1.0b3 Python candidate and the published 0.1.0b2 native renderer.
This release changes Python visuals; its native source is unchanged apart from
the package version. Release qualification separately rebuilds the matching core.
The dashboard data is generated demonstration data, including its FPS value.

From a checkout with the native module available, in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path $PWD 'src'
python tools/capture_studio.py --output docs/screenshots/studio-dark.png
python tools/capture_studio.py --theme light --output docs/screenshots/studio-light.png
python tools/capture_studio.py --pane preview --output docs/screenshots/studio-preview.png
```

The tool reports actual pixel dimensions, adapter, backend and PNG SHA256.
Use `--width 1024 --height 720` for compact-layout review. Windows scaling can
change physical pixel dimensions. Inspect each final PNG for clipping and layout
before committing it. Use this readback path for future screenshots so the cursor
cannot enter an image accidentally. Earlier JPEG files are historical captures;
the current README does not use them.
