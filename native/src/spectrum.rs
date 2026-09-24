//! Bounded PCM16 spectrum analysis for retained media visualization.

const MAX_CHANNELS: u16 = 8;
const MAX_BINS: usize = 512;
const MAX_ANALYSIS_FRAMES: usize = 4_096;

pub(crate) fn spectrum_magnitudes_pcm16(
    channels: u16,
    pcm16: &[u8],
    bin_count: usize,
) -> Result<Vec<f32>, String> {
    if channels == 0 || channels > MAX_CHANNELS {
        return Err(format!(
            "Spectrum channel count must be in the range [1, {MAX_CHANNELS}]."
        ));
    }
    if bin_count == 0 || bin_count > MAX_BINS {
        return Err(format!(
            "Spectrum bin_count must be in the range [1, {MAX_BINS}]."
        ));
    }
    if pcm16.len() % 2 != 0 {
        return Err("Spectrum PCM16 payload must contain whole signed 16-bit samples.".to_owned());
    }

    let channel_count = usize::from(channels);
    let sample_count = pcm16.len() / 2;
    if sample_count % channel_count != 0 {
        return Err("Spectrum PCM16 payload must contain complete interleaved frames.".to_owned());
    }
    let frame_count = sample_count / channel_count;
    if frame_count == 0 {
        return Ok(Vec::new());
    }

    let analysis_frames = frame_count.min(MAX_ANALYSIS_FRAMES);
    let start_frame = frame_count - analysis_frames;
    let mut mono = Vec::with_capacity(analysis_frames);
    for frame_index in start_frame..frame_count {
        let mut mixed = 0.0_f32;
        for channel_index in 0..channel_count {
            let sample_index = frame_index * channel_count + channel_index;
            let byte_index = sample_index * 2;
            let sample = i16::from_le_bytes([pcm16[byte_index], pcm16[byte_index + 1]]);
            mixed += normalize_pcm16(sample);
        }
        mono.push(mixed / f32::from(channels));
    }

    let max_frequency_bin = analysis_frames / 2;
    let output_bins = bin_count.min(max_frequency_bin + 1);
    let mut magnitudes = Vec::with_capacity(output_bins);
    let mut windowed = Vec::with_capacity(analysis_frames);
    let mut window_sum = 0.0_f32;
    for (index, sample) in mono.into_iter().enumerate() {
        let window = if analysis_frames == 1 {
            1.0
        } else {
            let phase =
                2.0 * std::f32::consts::PI * index as f32 / (analysis_frames - 1) as f32;
            0.5 - 0.5 * phase.cos()
        };
        windowed.push(sample * window);
        window_sum += window;
    }
    if window_sum <= f32::EPSILON {
        return Ok(vec![0.0; output_bins]);
    }

    for output_index in 0..output_bins {
        let frequency_bin = if output_bins == 1 {
            0
        } else {
            ((output_index * max_frequency_bin) as f32 / (output_bins - 1) as f32).round() as usize
        };
        let angle =
            -2.0 * std::f32::consts::PI * frequency_bin as f32 / analysis_frames as f32;
        let step_real = angle.cos();
        let step_imaginary = angle.sin();
        let mut oscillator_real = 1.0_f32;
        let mut oscillator_imaginary = 0.0_f32;
        let mut real = 0.0_f32;
        let mut imaginary = 0.0_f32;
        for sample in &windowed {
            real += sample * oscillator_real;
            imaginary += sample * oscillator_imaginary;
            let next_real =
                oscillator_real * step_real - oscillator_imaginary * step_imaginary;
            oscillator_imaginary =
                oscillator_real * step_imaginary + oscillator_imaginary * step_real;
            oscillator_real = next_real;
        }

        let edge_bin =
            frequency_bin == 0 || (analysis_frames % 2 == 0 && frequency_bin == max_frequency_bin);
        let scale = if edge_bin { 1.0 } else { 2.0 };
        let magnitude = (real.hypot(imaginary) * scale / window_sum).clamp(0.0, 1.0);
        magnitudes.push(magnitude);
    }

    Ok(magnitudes)
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
    fn silence_produces_bounded_zero_spectrum() {
        let data = pcm16(&[0; 64]);
        let spectrum = spectrum_magnitudes_pcm16(1, &data, 16).unwrap();

        assert_eq!(spectrum.len(), 16);
        assert!(spectrum.iter().all(|value| *value == 0.0));
    }

    #[test]
    fn alternating_signal_peaks_near_nyquist() {
        let samples: Vec<i16> = (0..64)
            .map(|index| if index % 2 == 0 { i16::MAX } else { i16::MIN })
            .collect();
        let spectrum = spectrum_magnitudes_pcm16(1, &pcm16(&samples), 33).unwrap();

        assert_eq!(spectrum.len(), 33);
        assert!(spectrum[0] < 0.05);
        assert!(spectrum[32] > 0.95);
        assert!(spectrum.iter().all(|value| (0.0..=1.0).contains(value)));
    }

    #[test]
    fn downmixes_interleaved_channels_before_analysis() {
        let data = pcm16(&[
            i16::MAX,
            i16::MIN,
            16_384,
            -16_384,
            -16_384,
            16_384,
            i16::MIN,
            i16::MAX,
        ]);
        let spectrum = spectrum_magnitudes_pcm16(2, &data, 8).unwrap();

        assert_eq!(spectrum.len(), 3);
        assert!(spectrum.iter().all(|value| *value < 0.001));
    }

    #[test]
    fn accepts_empty_audio_and_caps_bins_to_available_frequency_bins() {
        assert!(spectrum_magnitudes_pcm16(2, &[], 8).unwrap().is_empty());
        let spectrum = spectrum_magnitudes_pcm16(1, &pcm16(&[1, 2, 3, 4]), 64).unwrap();
        assert_eq!(spectrum.len(), 3);
    }

    #[test]
    fn rejects_invalid_alignment_channels_and_bin_count() {
        assert!(spectrum_magnitudes_pcm16(0, &[0, 0], 1).is_err());
        assert!(spectrum_magnitudes_pcm16(1, &[0], 1).is_err());
        assert!(spectrum_magnitudes_pcm16(2, &[0, 0], 1).is_err());
        assert!(spectrum_magnitudes_pcm16(1, &[0, 0], 0).is_err());
        assert!(spectrum_magnitudes_pcm16(1, &[0, 0], MAX_BINS + 1).is_err());
    }
}
