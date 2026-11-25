# Studio in SwirUI 0.2 development

From a Windows checkout of `development/0.2` with the native renderer installed,
run `python -m swirui studio`. In **Overview → Material library**, choose a
material, then select **Launch preview**.

The preview opens the same form in dark and light appearances. Both use the
themes from **Copy theme JSON**, so you can inspect the finish, focus ring and
button states your app will inherit. Tab to a project name, type a new name
and press Enter or select **Apply name**. Both halves update together. Your
Studio project keeps its original name.

To compare a different design, edit the material or accent in Studio and select
**Launch preview** again. Studio refreshes the existing window at its current
size. Closing the comparison leaves Studio open.

![An interactive form in the dark and light Studio appearances](screenshots/studio-comparison.png)

This 960 × 460 capture is a direct readback of the Windows wgpu frame on AMD
Radeon graphics with DX12. To reproduce it from the same checkout, run
`python tools/capture_studio.py --pane comparison --output studio-comparison.png`.
The OS cursor is outside the captured frame.
