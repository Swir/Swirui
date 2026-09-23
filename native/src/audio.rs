//! Bounded PCM audio primitives shared by SwirUI's Python API and native output path.

const MAX_SAMPLE_RATE: u32 = 384_000;
const MAX_CHANNELS: u16 = 8;
const MAX_AUDIO_BYTES: usize = 256 * 1024 * 1024;

pub(crate) type AudioMetadata = (u32, u16, usize, f64);

fn validate_sample_rate(sample_rate: u32) -> Result<(), String> {
    if sample_rate == 0 || sample_rate > MAX_SAMPLE_RATE {
        return Err(format!(
            "Audio sample rate must be in the range [1, {MAX_SAMPLE_RATE}]."
        ));
    }
    Ok(())
}

fn validate_channels(channels: u16) -> Result<(), String> {
    if channels == 0 || channels > MAX_CHANNELS {
        return Err(format!(
            "Audio channel count must be in the range [1, {MAX_CHANNELS}]."
        ));
    }
    Ok(())
}

pub(crate) fn validate_audio_pcm16(
    sample_rate: u32,
    channels: u16,
    pcm: &[u8],
) -> Result<AudioMetadata, String> {
    validate_sample_rate(sample_rate)?;
    validate_channels(channels)?;
    if pcm.is_empty() {
        return Err("Audio PCM16 data cannot be empty.".to_owned());
    }
    if pcm.len() > MAX_AUDIO_BYTES {
        return Err(format!(
            "Audio PCM16 storage exceeds the {MAX_AUDIO_BYTES}-byte safety limit."
        ));
    }
    if pcm.len() % 2 != 0 {
        return Err("Audio PCM16 data must contain complete 16-bit samples.".to_owned());
    }

    let sample_count = pcm.len() / 2;
    let channels_usize = usize::from(channels);
    if sample_count % channels_usize != 0 {
        return Err("Audio PCM16 sample count must align to complete channel frames.".to_owned());
    }

    let frame_count = sample_count / channels_usize;
    if frame_count == 0 {
        return Err("Audio PCM16 data must contain at least one frame.".to_owned());
    }
    let duration_ms = frame_count as f64 / f64::from(sample_rate) * 1000.0;
    Ok((sample_rate, channels, frame_count, duration_ms))
}

pub(crate) fn audio_frame_index(
    elapsed_ms: f64,
    sample_rate: u32,
    frame_count: usize,
    loop_audio: bool,
) -> Result<usize, String> {
    validate_sample_rate(sample_rate)?;
    if !elapsed_ms.is_finite() || elapsed_ms < 0.0 {
        return Err("Audio elapsed time must be finite and non-negative.".to_owned());
    }
    if frame_count == 0 {
        return Err("Audio frame_count must be greater than zero.".to_owned());
    }

    let frame_position = elapsed_ms / 1000.0 * f64::from(sample_rate);
    if !frame_position.is_finite() {
        return Err("Audio elapsed time is too large to resolve safely.".to_owned());
    }
    let whole_frame = frame_position.floor();
    if loop_audio {
        let wrapped = whole_frame % frame_count as f64;
        return Ok(wrapped as usize);
    }
    Ok(whole_frame.min((frame_count - 1) as f64) as usize)
}

pub(crate) fn normalize_audio_position_ms(
    elapsed_ms: f64,
    duration_ms: f64,
    loop_audio: bool,
) -> Result<f64, String> {
    if !elapsed_ms.is_finite() || elapsed_ms < 0.0 {
        return Err("Audio elapsed time must be finite and non-negative.".to_owned());
    }
    if !duration_ms.is_finite() || duration_ms <= 0.0 {
        return Err("Audio duration must be finite and positive.".to_owned());
    }
    if loop_audio {
        Ok(elapsed_ms % duration_ms)
    } else {
        Ok(elapsed_ms.min(duration_ms))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pcm16_stereo(frames: &[(i16, i16)]) -> Vec<u8> {
        frames
            .iter()
            .flat_map(|(left, right)| {
                left.to_le_bytes()
                    .into_iter()
                    .chain(right.to_le_bytes())
            })
            .collect()
    }

    #[test]
    fn validates_bounded_pcm16_metadata() {
        let pcm = pcm16_stereo(&[(0, 0), (1200, -1200), (3200, -3200), (0, 0)]);
        assert_eq!(
            validate_audio_pcm16(48_000, 2, &pcm).unwrap(),
            (48_000, 2, 4, 4.0 / 48_000.0 * 1000.0)
        );
    }

    #[test]
    fn selects_looping_and_clamped_audio_frames() {
        assert_eq!(audio_frame_index(0.0, 1_000, 3, true).unwrap(), 0);
        assert_eq!(audio_frame_index(1.0, 1_000, 3, true).unwrap(), 1);
        assert_eq!(audio_frame_index(3.0, 1_000, 3, true).unwrap(), 0);
        assert_eq!(audio_frame_index(3.0, 1_000, 3, false).unwrap(), 2);
    }

    #[test]
    fn normalizes_seek_positions() {
        assert_eq!(normalize_audio_position_ms(1_500.0, 1_000.0, true).unwrap(), 500.0);
        assert_eq!(normalize_audio_position_ms(1_500.0, 1_000.0, false).unwrap(), 1_000.0);
    }

    #[test]
    fn rejects_malformed_pcm16() {
        assert!(validate_audio_pcm16(0, 2, &[0, 0, 0, 0]).is_err());
        assert!(validate_audio_pcm16(48_000, 0, &[0, 0, 0, 0]).is_err());
        assert!(validate_audio_pcm16(48_000, 2, &[0, 0, 0]).is_err());
        assert!(validate_audio_pcm16(48_000, 2, &[0, 0]).is_err());
    }
}
