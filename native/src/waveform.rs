//! Bounded PCM16 waveform-envelope extraction for retained media visualization.

const MAX_CHANNELS: u16 = 8;
const MAX_BUCKETS: usize = 4_096;

pub(crate) type WaveformBucket = (f32, f32);

pub(crate) fn waveform_envelope_pcm16(
    channels: u16,
    pcm16: &[u8],
    bucket_count: usize,
) -> Result<Vec<WaveformBucket>, String> {
    if channels == 0 || channels > MAX_CHANNELS {
        return Err(format!(
            "Waveform channel count must be in the range [1, {MAX_CHANNELS}]."
        ));
    }
    if bucket_count == 0 || bucket_count > MAX_BUCKETS {
        return Err(format!(
            "Waveform bucket_count must be in the range [1, {MAX_BUCKETS}]."
        ));
    }
    if pcm16.len() % 2 != 0 {
        return Err("Waveform PCM16 payload must contain whole signed 16-bit samples.".to_owned());
    }

    let channel_count = usize::from(channels);
    let sample_count = pcm16.len() / 2;
    if sample_count % channel_count != 0 {
        return Err("Waveform PCM16 payload must contain complete interleaved frames.".to_owned());
    }
    let frame_count = sample_count / channel_count;
    if frame_count == 0 {
        return Ok(Vec::new());
    }

    let bucket_count = bucket_count.min(frame_count);
    let mut envelope = Vec::with_capacity(bucket_count);
    for bucket_index in 0..bucket_count {
        let start_frame = bucket_index * frame_count / bucket_count;
        let end_frame = ((bucket_index + 1) * frame_count / bucket_count).max(start_frame + 1);
        let mut minimum = 1.0_f32;
        let mut maximum = -1.0_f32;

        for frame_index in start_frame..end_frame {
            let mut mixed = 0.0_f32;
            for channel_index in 0..channel_count {
                let sample_index = frame_index * channel_count + channel_index;
                let byte_index = sample_index * 2;
                let sample = i16::from_le_bytes([pcm16[byte_index], pcm16[byte_index + 1]]);
                mixed += normalize_pcm16(sample);
            }
            mixed /= f32::from(channels);
            minimum = minimum.min(mixed);
            maximum = maximum.max(mixed);
        }

        envelope.push((minimum, maximum));
    }
    Ok(envelope)
}

fn normalize_pcm16(sample: i16) -> f32 {
    if sample >= 0 {
        f32::from(sample) / f32::from(i16::MAX)
    } else {
        f32::from(sample) / 32_768.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pcm16(samples: &[i16]) -> Vec<u8> {
        samples
            .iter()
            .flat_map(|sample| sample.to_le_bytes())
            .collect()
    }

    #[test]
    fn extracts_bounded_mono_min_max_envelope() {
        let data = pcm16(&[i16::MIN, -8_192, 0, 8_192, i16::MAX, 0, -16_384, 16_384]);
        let envelope = waveform_envelope_pcm16(1, &data, 4).unwrap();

        assert_eq!(envelope.len(), 4);
        assert_eq!(envelope[0].0, -1.0);
        assert!(envelope[0].1 < 0.0);
        assert_eq!(envelope[1].0, 0.0);
        assert!(envelope[1].1 > 0.24 && envelope[1].1 < 0.26);
        assert_eq!(envelope[2].1, 1.0);
        assert!(envelope[3].0 < -0.49 && envelope[3].0 > -0.51);
        assert!(envelope[3].1 > 0.49 && envelope[3].1 < 0.51);
    }

    #[test]
    fn downmixes_interleaved_channels_before_bucket_reduction() {
        let data = pcm16(&[i16::MAX, i16::MIN, 16_384, 16_384]);
        let envelope = waveform_envelope_pcm16(2, &data, 2).unwrap();

        assert_eq!(envelope.len(), 2);
        assert!(envelope[0].0.abs() < 0.001);
        assert!(envelope[0].1.abs() < 0.001);
        assert!(envelope[1].0 > 0.49 && envelope[1].0 < 0.51);
        assert_eq!(envelope[1].0, envelope[1].1);
    }

    #[test]
    fn caps_buckets_to_available_frames_and_accepts_empty_audio() {
        let data = pcm16(&[1, 2, 3]);
        assert_eq!(waveform_envelope_pcm16(1, &data, 64).unwrap().len(), 3);
        assert!(waveform_envelope_pcm16(2, &[], 8).unwrap().is_empty());
    }

    #[test]
    fn rejects_invalid_alignment_channels_and_bucket_count() {
        assert!(waveform_envelope_pcm16(0, &[0, 0], 1).is_err());
        assert!(waveform_envelope_pcm16(1, &[0], 1).is_err());
        assert!(waveform_envelope_pcm16(2, &[0, 0], 1).is_err());
        assert!(waveform_envelope_pcm16(1, &[0, 0], 0).is_err());
        assert!(waveform_envelope_pcm16(1, &[0, 0], MAX_BUCKETS + 1).is_err());
    }
}
