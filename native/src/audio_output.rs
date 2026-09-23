//! Windows native PCM playback backed by rodio/CPAL without exposing backend details to Python.

use std::num::NonZero;
use std::time::Duration;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use rodio::buffer::SamplesBuffer;
use rodio::{DeviceSinkBuilder, MixerDeviceSink, Player, Source};

use crate::audio;

const MAX_VOLUME: f32 = 4.0;
const MIN_PLAYBACK_RATE: f32 = 0.25;
const MAX_PLAYBACK_RATE: f32 = 4.0;

#[pyclass(name = "AudioOutput", unsendable)]
pub(crate) struct PyAudioOutput {
    _device_sink: MixerDeviceSink,
    player: Player,
    samples: Vec<f32>,
    sample_rate: NonZero<u32>,
    channels: NonZero<u16>,
    duration_ms: f64,
    loop_audio: bool,
}

#[pymethods]
impl PyAudioOutput {
    #[new]
    #[pyo3(signature = (
        sample_rate,
        channels,
        pcm16,
        loop_audio=false,
        autoplay=true,
        volume=1.0,
        playback_rate=1.0
    ))]
    fn new(
        sample_rate: u32,
        channels: u16,
        pcm16: Vec<u8>,
        loop_audio: bool,
        autoplay: bool,
        volume: f32,
        playback_rate: f32,
    ) -> PyResult<Self> {
        let (_, _, _, duration_ms) =
            audio::validate_audio_pcm16(sample_rate, channels, &pcm16)
                .map_err(PyValueError::new_err)?;
        let volume = validate_volume(volume)?;
        let playback_rate = validate_playback_rate(playback_rate)?;
        let sample_rate = NonZero::new(sample_rate)
            .ok_or_else(|| PyValueError::new_err("sample_rate cannot be zero."))?;
        let channels = NonZero::new(channels)
            .ok_or_else(|| PyValueError::new_err("channels cannot be zero."))?;
        let samples = pcm16_to_f32(&pcm16);

        let mut device_sink = DeviceSinkBuilder::open_default_sink().map_err(|error| {
            PyRuntimeError::new_err(format!("Unable to open the default audio output: {error}"))
        })?;
        device_sink.log_on_drop(false);
        let player = Player::connect_new(device_sink.mixer());
        let output = Self {
            _device_sink: device_sink,
            player,
            samples,
            sample_rate,
            channels,
            duration_ms,
            loop_audio,
        };
        output.append_source();
        output.player.set_volume(volume);
        output.player.set_speed(playback_rate);
        if !autoplay {
            output.player.pause();
        }
        Ok(output)
    }

    fn play(&self) {
        if self.player.empty() {
            self.append_source();
        }
        self.player.play();
    }

    fn pause(&self) {
        self.player.pause();
    }

    fn stop(&self) {
        self.player.stop();
        self.player.pause();
    }

    fn seek_ms(&self, elapsed_ms: f64) -> PyResult<f64> {
        let target =
            audio::normalize_audio_position_ms(elapsed_ms, self.duration_ms, self.loop_audio)
                .map_err(PyValueError::new_err)?;
        let was_paused = self.player.is_paused();
        if self.player.empty() {
            self.append_source();
        }
        self.player
            .try_seek(Duration::from_secs_f64(target / 1000.0))
            .map_err(|error| PyRuntimeError::new_err(format!("Audio seek failed: {error}")))?;
        if was_paused {
            self.player.pause();
        }
        Ok(target)
    }

    fn position_ms(&self) -> f64 {
        let elapsed_ms = self.player.get_pos().as_secs_f64() * 1000.0;
        if self.loop_audio && self.duration_ms > 0.0 {
            elapsed_ms % self.duration_ms
        } else {
            elapsed_ms.min(self.duration_ms)
        }
    }

    fn is_playing(&self) -> bool {
        !self.player.is_paused() && !self.player.empty()
    }

    fn set_volume(&self, volume: f32) -> PyResult<()> {
        self.player.set_volume(validate_volume(volume)?);
        Ok(())
    }

    fn volume(&self) -> f32 {
        self.player.volume()
    }

    fn set_playback_rate(&self, playback_rate: f32) -> PyResult<()> {
        self.player
            .set_speed(validate_playback_rate(playback_rate)?);
        Ok(())
    }

    fn playback_rate(&self) -> f32 {
        self.player.speed()
    }

    fn duration_ms(&self) -> f64 {
        self.duration_ms
    }
}

impl PyAudioOutput {
    fn append_source(&self) {
        let source =
            SamplesBuffer::new(self.channels, self.sample_rate, self.samples.clone());
        if self.loop_audio {
            self.player.append(source.repeat_infinite());
        } else {
            self.player.append(source);
        }
    }
}

fn pcm16_to_f32(pcm16: &[u8]) -> Vec<f32> {
    pcm16
        .chunks_exact(2)
        .map(|sample| f32::from(i16::from_le_bytes([sample[0], sample[1]])) / 32_768.0)
        .collect()
}

fn validate_volume(volume: f32) -> PyResult<f32> {
    if !volume.is_finite() || !(0.0..=MAX_VOLUME).contains(&volume) {
        return Err(PyValueError::new_err(format!(
            "volume must be finite and in the range [0, {MAX_VOLUME}]."
        )));
    }
    Ok(volume)
}

fn validate_playback_rate(playback_rate: f32) -> PyResult<f32> {
    if !playback_rate.is_finite()
        || !(MIN_PLAYBACK_RATE..=MAX_PLAYBACK_RATE).contains(&playback_rate)
    {
        return Err(PyValueError::new_err(format!(
            "playback_rate must be finite and in the range \
             [{MIN_PLAYBACK_RATE}, {MAX_PLAYBACK_RATE}]."
        )));
    }
    Ok(playback_rate)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn converts_signed_pcm16_to_normalized_float_samples() {
        let pcm = [
            i16::MIN.to_le_bytes(),
            0_i16.to_le_bytes(),
            i16::MAX.to_le_bytes(),
        ]
        .concat();
        let samples = pcm16_to_f32(&pcm);
        assert_eq!(samples[0], -1.0);
        assert_eq!(samples[1], 0.0);
        assert!((samples[2] - (32_767.0 / 32_768.0)).abs() < f32::EPSILON);
    }
}
