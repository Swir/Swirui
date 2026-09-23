//! Bounded microphone PCM primitives shared by the native capture backend and Python API.

use std::collections::VecDeque;

const MIN_BUFFER_MS: u32 = 50;
const MAX_BUFFER_MS: u32 = 10_000;
const MAX_SAMPLE_RATE: u32 = 384_000;
const MAX_CHANNELS: u16 = 8;

pub(crate) type MicrophoneChunkMetadata = (u32, u16, usize, f64);

pub(crate) fn validate_microphone_pcm16(
    sample_rate: u32,
    channels: u16,
    pcm16: &[u8],
) -> Result<MicrophoneChunkMetadata, String> {
    crate::audio::validate_audio_pcm16(sample_rate, channels, pcm16)
}

pub(crate) fn validate_microphone_buffer_ms(buffer_ms: u32) -> Result<u32, String> {
    if !(MIN_BUFFER_MS..=MAX_BUFFER_MS).contains(&buffer_ms) {
        return Err(format!(
            "Microphone buffer_ms must be in the range [{MIN_BUFFER_MS}, {MAX_BUFFER_MS}]."
        ));
    }
    Ok(buffer_ms)
}

pub(crate) fn f32_to_pcm16(sample: f32) -> i16 {
    let normalized = sample.clamp(-1.0, 1.0);
    let scaled = if normalized >= 0.0 {
        normalized * f32::from(i16::MAX)
    } else {
        normalized * 32_768.0
    };
    scaled.round() as i16
}

pub(crate) fn u16_to_pcm16(sample: u16) -> i16 {
    (i32::from(sample) - 32_768) as i16
}

pub(crate) struct MicrophoneRingBuffer {
    channels: usize,
    capacity_samples: usize,
    samples: VecDeque<i16>,
    dropped_samples: usize,
}

impl MicrophoneRingBuffer {
    pub(crate) fn new(sample_rate: u32, channels: u16, buffer_ms: u32) -> Result<Self, String> {
        if sample_rate == 0 || sample_rate > MAX_SAMPLE_RATE {
            return Err(format!(
                "Microphone sample rate must be in the range [1, {MAX_SAMPLE_RATE}]."
            ));
        }
        if channels == 0 || channels > MAX_CHANNELS {
            return Err(format!(
                "Microphone channel count must be in the range [1, {MAX_CHANNELS}]."
            ));
        }
        let buffer_ms = validate_microphone_buffer_ms(buffer_ms)?;
        let frame_capacity = (u64::from(sample_rate) * u64::from(buffer_ms) / 1000).max(1);
        let sample_capacity = frame_capacity
            .checked_mul(u64::from(channels))
            .ok_or_else(|| "Microphone buffer capacity overflowed.".to_owned())?;
        let capacity_samples = usize::try_from(sample_capacity)
            .map_err(|_| "Microphone buffer capacity exceeds the platform limit.".to_owned())?;
        Ok(Self {
            channels: usize::from(channels),
            capacity_samples,
            samples: VecDeque::with_capacity(capacity_samples),
            dropped_samples: 0,
        })
    }

    pub(crate) fn push_interleaved(&mut self, samples: &[i16]) -> Result<(), String> {
        if samples.len() % self.channels != 0 {
            return Err("Microphone callback produced a partial channel frame.".to_owned());
        }
        if samples.is_empty() {
            return Ok(());
        }

        if samples.len() >= self.capacity_samples {
            let dropped = self.samples.len() + samples.len() - self.capacity_samples;
            self.dropped_samples = self.dropped_samples.saturating_add(dropped);
            self.samples.clear();
            self.samples.extend(
                samples[samples.len() - self.capacity_samples..]
                    .iter()
                    .copied(),
            );
            return Ok(());
        }

        let overflow = self
            .samples
            .len()
            .saturating_add(samples.len())
            .saturating_sub(self.capacity_samples);
        for _ in 0..overflow {
            let _ = self.samples.pop_front();
        }
        self.dropped_samples = self.dropped_samples.saturating_add(overflow);
        self.samples.extend(samples.iter().copied());
        Ok(())
    }

    pub(crate) fn available_frames(&self) -> usize {
        self.samples.len() / self.channels
    }

    pub(crate) fn dropped_frames(&self) -> usize {
        self.dropped_samples / self.channels
    }

    pub(crate) fn clear(&mut self) {
        self.samples.clear();
    }

    pub(crate) fn read_pcm16(&mut self, max_frames: Option<usize>) -> Vec<u8> {
        let available_frames = self.available_frames();
        let frame_count = max_frames.unwrap_or(available_frames).min(available_frames);
        let sample_count = frame_count * self.channels;
        let mut pcm16 = Vec::with_capacity(sample_count * 2);
        for sample in self.samples.drain(..sample_count) {
            pcm16.extend_from_slice(&sample.to_le_bytes());
        }
        pcm16
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_microphone_pcm16_through_shared_audio_contract() {
        let pcm16 = [0_i16, 120_i16, -120_i16, 0_i16]
            .into_iter()
            .flat_map(|sample| sample.to_le_bytes())
            .collect::<Vec<_>>();
        assert_eq!(
            validate_microphone_pcm16(1_000, 1, &pcm16).unwrap(),
            (1_000, 1, 4, 4.0)
        );
    }

    #[test]
    fn ring_buffer_stays_frame_aligned_and_reports_drops() {
        let mut buffer = MicrophoneRingBuffer::new(1_000, 2, 100).unwrap();
        let samples = (0_i16..240_i16).collect::<Vec<_>>();
        buffer.push_interleaved(&samples).unwrap();

        assert_eq!(buffer.available_frames(), 100);
        assert_eq!(buffer.dropped_frames(), 20);
        let chunk = buffer.read_pcm16(Some(10));
        assert_eq!(chunk.len(), 10 * 2 * 2);
        assert_eq!(buffer.available_frames(), 90);
    }

    #[test]
    fn rejects_partial_frames_and_invalid_buffer_bounds() {
        let mut buffer = MicrophoneRingBuffer::new(48_000, 2, 250).unwrap();
        assert!(buffer.push_interleaved(&[1, 2, 3]).is_err());
        assert!(MicrophoneRingBuffer::new(48_000, 2, MIN_BUFFER_MS - 1).is_err());
        assert!(MicrophoneRingBuffer::new(48_000, 2, MAX_BUFFER_MS + 1).is_err());
    }

    #[test]
    fn converts_common_input_sample_formats_to_pcm16() {
        assert_eq!(f32_to_pcm16(-1.0), i16::MIN);
        assert_eq!(f32_to_pcm16(0.0), 0);
        assert_eq!(f32_to_pcm16(1.0), i16::MAX);
        assert_eq!(u16_to_pcm16(0), i16::MIN);
        assert_eq!(u16_to_pcm16(32_768), 0);
        assert_eq!(u16_to_pcm16(u16::MAX), i16::MAX);
    }
}
