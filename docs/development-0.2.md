# Studio in SwirUI 0.2 development

From a Windows checkout of `development/0.2` with the native renderer installed,
run `python -m swirui studio`. In **Overview → Material library**, choose a
material, then select **Launch preview**.

The preview opens the same form in dark and light appearances. Both use the
themes from **Copy theme JSON**, so you can inspect the finish, focus ring and
button states your app will inherit. Tab to a project name, type a new name
and press Enter or select **Apply name**. Both halves update together. Your
Studio project keeps its original name.

Leave the comparison open while you work in Studio. Changing the accent,
material, depth, tint, glow, corners or headline updates both panes together.
For example, choose **Rose** in **Settings → Signature color**, then move
**Corners** in the preview. Your sample text and its selection survive both
edits. Select **Launch preview** again when you want to restore the sample to
the current project name. Closing the comparison leaves Studio open.

![The dark and light forms after applying the same rose accent and rounded corners in Studio](screenshots/studio-comparison.png)

This 960 × 460 capture is a direct readback of the Windows wgpu frame on AMD
Radeon graphics with DX12. To reproduce it from the same checkout, run
`python tools/capture_studio.py --pane comparison --accent "#FF7ADE" --corner-radius 24 --output studio-comparison.png`.
The OS cursor is outside the captured frame.

## Shape your controls

The **Corners** slider below the preview sets the radius of themed buttons,
inputs and material cards in logical pixels. Drag from 0 for square corners
to 24 for a rounded finish. With keyboard focus on the slider, the arrow keys
change the value by one. Home and End jump to the two extremes.

Both exported appearances carry the same `control_radius`. In your app,
assign `ThemePackage.load("studio-theme.json").default` to the root panel's
`theme` after saving the JSON from Studio. Controls with a locally specified
radius keep their own shape.

![Studio showing mint buttons and a glass card with the corner radius set to 24](screenshots/studio-corners.png)

To reproduce this cursor-free native capture, run
`python tools/capture_studio.py --pane preview --width 1440 --height 900 --accent "#7FE0BF" --corner-radius 24 --output studio-corners.png`.
