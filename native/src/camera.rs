//! Bounded live-camera frame primitives for Python-first retained media widgets.

const MAX_DIMENSION: u32 = 8_192;
const MAX_PIXELS: u64 = 33_554_432;
const MAX_FRAME_BYTES: usize = 128 * 1024 * 1024;

pub(crate) type CameraFrameMetadata = (u32, u32, usize);

pub(crate) fn validate_camera_rgba_frame(
    width: u32,
    height: u32,
    frame: &[u8],
) -> Result<CameraFrameMetadata, String> {
    if width == 0 || height == 0 {
        return Err("Camera frame dimensions must be greater than zero.".to_owned());
    }
    if width > MAX_DIMENSION || height > MAX_DIMENSION {
        return Err(format!(
            "Camera frame dimensions exceed the {MAX_DIMENSION}px per-axis safety limit."
        ));
    }
    let pixels = u64::from(width) * u64::from(height);
    if pixels > MAX_PIXELS {
        return Err(format!(
            "Camera frame dimensions exceed the {MAX_PIXELS}-pixel safety limit."
        ));
    }
    let frame_bytes = usize::try_from(pixels)
        .ok()
        .and_then(|pixels| pixels.checked_mul(4))
        .ok_or_else(|| "Camera frame byte size overflowed the platform limit.".to_owned())?;
    if frame_bytes > MAX_FRAME_BYTES {
        return Err(format!(
            "Camera frame exceeds the {MAX_FRAME_BYTES}-byte safety limit."
        ));
    }
    if frame.len() != frame_bytes {
        return Err(format!(
            "Camera frame requires exactly {frame_bytes} RGBA bytes; received {}.",
            frame.len()
        ));
    }
    Ok((width, height, frame_bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_bounded_rgba_camera_frame() {
        let frame = vec![255_u8; 640 * 480 * 4];
        assert_eq!(
            validate_camera_rgba_frame(640, 480, &frame).unwrap(),
            (640, 480, frame.len())
        );
    }

    #[test]
    fn rejects_malformed_or_unbounded_camera_frames() {
        assert!(validate_camera_rgba_frame(0, 480, &[]).is_err());
        assert!(validate_camera_rgba_frame(640, 480, &[0; 7]).is_err());
        assert!(validate_camera_rgba_frame(MAX_DIMENSION + 1, 1, &[]).is_err());
    }
}
