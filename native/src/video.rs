//! Bounded video playback primitives for Python-first retained media widgets.

const MAX_DIMENSION: u32 = 16_384;
const MAX_PIXELS: u64 = 67_108_864;
const MAX_VIDEO_FRAMES: usize = 4_096;
const MAX_VIDEO_BYTES: usize = 256 * 1024 * 1024;
const MAX_FRAME_RATE: f64 = 240.0;

pub(crate) type VideoMetadata = (u32, u32, f64, usize, f64);

fn validate_dimensions(width: u32, height: u32) -> Result<(), String> {
    if width == 0 || height == 0 {
        return Err("Video frame dimensions must be greater than zero.".to_owned());
    }
    if width > MAX_DIMENSION || height > MAX_DIMENSION {
        return Err(format!(
            "Video frame dimensions exceed the {MAX_DIMENSION}px per-axis safety limit."
        ));
    }
    if u64::from(width) * u64::from(height) > MAX_PIXELS {
        return Err(format!(
            "Video frame dimensions exceed the {MAX_PIXELS}-pixel safety limit."
        ));
    }
    Ok(())
}

fn validate_frame_rate(frame_rate: f64) -> Result<(), String> {
    if !frame_rate.is_finite() || frame_rate <= 0.0 || frame_rate > MAX_FRAME_RATE {
        return Err(format!(
            "Video frame rate must be finite and in the range (0, {MAX_FRAME_RATE}]."
        ));
    }
    Ok(())
}

pub(crate) fn validate_video_rgba_frames(
    width: u32,
    height: u32,
    frame_rate: f64,
    frames: &[Vec<u8>],
) -> Result<VideoMetadata, String> {
    validate_dimensions(width, height)?;
    validate_frame_rate(frame_rate)?;
    if frames.is_empty() {
        return Err("Video requires at least one RGBA frame.".to_owned());
    }
    if frames.len() > MAX_VIDEO_FRAMES {
        return Err(format!(
            "Video exceeds the {MAX_VIDEO_FRAMES}-frame in-memory safety limit."
        ));
    }

    let frame_bytes = usize::try_from(width)
        .ok()
        .and_then(|width| {
            usize::try_from(height)
                .ok()
                .and_then(|height| width.checked_mul(height))
        })
        .and_then(|pixels| pixels.checked_mul(4))
        .ok_or_else(|| "Video frame byte size overflowed the platform limit.".to_owned())?;
    let total_bytes = frame_bytes
        .checked_mul(frames.len())
        .ok_or_else(|| "Video frame storage size overflowed the platform limit.".to_owned())?;
    if total_bytes > MAX_VIDEO_BYTES {
        return Err(format!(
            "Video frame storage exceeds the {MAX_VIDEO_BYTES}-byte in-memory safety limit."
        ));
    }
    if let Some((index, frame)) = frames
        .iter()
        .enumerate()
        .find(|(_, frame)| frame.len() != frame_bytes)
    {
        return Err(format!(
            "Video frame {index} requires exactly {frame_bytes} RGBA bytes; received {}.",
            frame.len()
        ));
    }

    let duration_ms = frames.len() as f64 / frame_rate * 1000.0;
    Ok((width, height, frame_rate, frames.len(), duration_ms))
}

pub(crate) fn video_frame_index(
    elapsed_ms: f64,
    frame_rate: f64,
    frame_count: usize,
    loop_video: bool,
) -> Result<usize, String> {
    validate_frame_rate(frame_rate)?;
    if !elapsed_ms.is_finite() || elapsed_ms < 0.0 {
        return Err("Video elapsed time must be finite and non-negative.".to_owned());
    }
    if frame_count == 0 {
        return Err("Video frame_count must be greater than zero.".to_owned());
    }
    if frame_count > MAX_VIDEO_FRAMES {
        return Err(format!(
            "Video frame_count exceeds the {MAX_VIDEO_FRAMES}-frame safety limit."
        ));
    }

    let frame_position = elapsed_ms / 1000.0 * frame_rate;
    if !frame_position.is_finite() {
        return Err("Video elapsed time is too large to resolve safely.".to_owned());
    }
    let whole_frame = frame_position.floor();
    if loop_video {
        let wrapped = whole_frame % frame_count as f64;
        return Ok(wrapped as usize);
    }
    Ok(whole_frame.min((frame_count - 1) as f64) as usize)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rgba_frame(red: u8) -> Vec<u8> {
        vec![red, 0, 0, 255, red, 0, 0, 255]
    }

    #[test]
    fn validates_bounded_rgba_video_metadata() {
        let frames = vec![rgba_frame(10), rgba_frame(20), rgba_frame(30)];
        assert_eq!(
            validate_video_rgba_frames(2, 1, 2.0, &frames).unwrap(),
            (2, 1, 2.0, 3, 1500.0)
        );
    }

    #[test]
    fn selects_looping_and_clamped_video_frames() {
        assert_eq!(video_frame_index(0.0, 2.0, 3, true).unwrap(), 0);
        assert_eq!(video_frame_index(500.0, 2.0, 3, true).unwrap(), 1);
        assert_eq!(video_frame_index(1500.0, 2.0, 3, true).unwrap(), 0);
        assert_eq!(video_frame_index(1500.0, 2.0, 3, false).unwrap(), 2);
    }

    #[test]
    fn rejects_unbounded_or_malformed_video_inputs() {
        assert!(validate_video_rgba_frames(0, 1, 30.0, &[rgba_frame(10)]).is_err());
        assert!(validate_video_rgba_frames(2, 1, 0.0, &[rgba_frame(10)]).is_err());
        assert!(validate_video_rgba_frames(2, 1, 30.0, &[vec![0; 7]]).is_err());
        assert!(video_frame_index(-1.0, 30.0, 1, false).is_err());
    }
}
