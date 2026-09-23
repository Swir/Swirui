//! Windows native microphone capture backed by CPAL/WASAPI and exposed through PyO3.

use std::sync::{Arc, Mutex};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Device, SampleFormat, Stream, StreamConfig};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::microphone::{
    MicrophoneRingBuffer, f32_to_pcm16, u16_to_pcm16, validate_microphone_buffer_ms,
};

pub(crate) type MicrophoneDeviceMetadata = (u32, String, bool);

type SharedCaptureState = Arc<Mutex<CaptureState>>;

struct CaptureState {
    buffer: MicrophoneRingBuffer,
    last_error: Option<String>,
}

pub(crate) fn list_microphone_devices() -> PyResult<Vec<MicrophoneDeviceMetadata>> {
    let host = cpal::default_host();
    let default_name = host
        .default_input_device()
        .and_then(|device| device.name().ok());
    let devices = host.input_devices().map_err(|error| {
        PyRuntimeError::new_err(format!("Microphone discovery failed: {error}"))
    })?;
    let mut result = Vec::new();
    for (position, device) in devices.enumerate() {
        let index = u32::try_from(position)
            .map_err(|_| PyRuntimeError::new_err("Too many microphone input devices."))?;
        let name = device
            .name()
            .unwrap_or_else(|_| format!("Input device {position}"));
        let is_default = default_name.as_deref() == Some(name.as_str());
        result.push((index, name, is_default));
    }
    Ok(result)
}

#[pyclass(name = "MicrophoneCapture", unsendable)]
pub(crate) struct PyMicrophoneCapture {
    stream: Option<Stream>,
    state: SharedCaptureState,
    sample_rate: u32,
    channels: u16,
    device_name: String,
    closed: bool,
    active: bool,
}

#[pymethods]
impl PyMicrophoneCapture {
    #[new]
    #[pyo3(signature = (index=None, buffer_ms=2_000))]
    fn new(index: Option<u32>, buffer_ms: u32) -> PyResult<Self> {
        validate_microphone_buffer_ms(buffer_ms).map_err(PyValueError::new_err)?;
        let host = cpal::default_host();
        let device = select_input_device(&host, index)?;
        let device_name = device
            .name()
            .unwrap_or_else(|_| "Default microphone input".to_owned());
        let supported = device.default_input_config().map_err(|error| {
            PyRuntimeError::new_err(format!("Unable to query microphone format: {error}"))
        })?;
        let sample_format = supported.sample_format();
        let sample_rate = supported.sample_rate().0;
        let channels = supported.channels();
        let config: StreamConfig = supported.into();
        let state = Arc::new(Mutex::new(CaptureState {
            buffer: MicrophoneRingBuffer::new(sample_rate, channels, buffer_ms)
                .map_err(PyValueError::new_err)?,
            last_error: None,
        }));
        let stream = build_input_stream(&device, &config, sample_format, Arc::clone(&state))?;
        stream.play().map_err(|error| {
            PyRuntimeError::new_err(format!("Unable to start microphone capture: {error}"))
        })?;
        Ok(Self {
            stream: Some(stream),
            state,
            sample_rate,
            channels,
            device_name,
            closed: false,
            active: true,
        })
    }

    #[pyo3(signature = (max_frames=None))]
    fn read_pcm16(&self, max_frames: Option<usize>) -> PyResult<Vec<u8>> {
        self.ensure_open()?;
        if max_frames == Some(0) {
            return Err(PyValueError::new_err(
                "max_frames must be greater than zero when provided.",
            ));
        }
        let mut state = self.lock_state()?;
        Ok(state.buffer.read_pcm16(max_frames))
    }

    fn available_frames(&self) -> PyResult<usize> {
        self.ensure_open()?;
        Ok(self.lock_state()?.buffer.available_frames())
    }

    fn dropped_frames(&self) -> PyResult<usize> {
        Ok(self.lock_state()?.buffer.dropped_frames())
    }

    fn clear(&self) -> PyResult<()> {
        self.ensure_open()?;
        self.lock_state()?.buffer.clear();
        Ok(())
    }

    fn pause(&mut self) -> PyResult<()> {
        self.ensure_open()?;
        if !self.active {
            return Ok(());
        }
        let stream = self
            .stream
            .as_ref()
            .ok_or_else(|| PyRuntimeError::new_err("Microphone stream is unavailable."))?;
        stream.pause().map_err(|error| {
            PyRuntimeError::new_err(format!("Unable to pause microphone capture: {error}"))
        })?;
        self.active = false;
        Ok(())
    }

    fn resume(&mut self) -> PyResult<()> {
        self.ensure_open()?;
        if self.active {
            return Ok(());
        }
        let stream = self
            .stream
            .as_ref()
            .ok_or_else(|| PyRuntimeError::new_err("Microphone stream is unavailable."))?;
        stream.play().map_err(|error| {
            PyRuntimeError::new_err(format!("Unable to resume microphone capture: {error}"))
        })?;
        self.active = true;
        Ok(())
    }

    fn close(&mut self) -> PyResult<()> {
        if self.closed {
            return Ok(());
        }
        let pause_error = if self.active {
            self.stream.as_ref().and_then(|stream| stream.pause().err())
        } else {
            None
        };
        self.stream = None;
        self.closed = true;
        self.active = false;
        if let Some(error) = pause_error {
            return Err(PyRuntimeError::new_err(format!(
                "Microphone capture closed after pause failed: {error}"
            )));
        }
        Ok(())
    }

    fn last_error(&self) -> PyResult<Option<String>> {
        Ok(self.lock_state()?.last_error.clone())
    }

    #[getter]
    fn sample_rate(&self) -> u32 {
        self.sample_rate
    }

    #[getter]
    fn channels(&self) -> u16 {
        self.channels
    }

    #[getter]
    fn device_name(&self) -> &str {
        &self.device_name
    }

    #[getter]
    fn is_open(&self) -> bool {
        !self.closed && self.stream.is_some()
    }

    #[getter]
    fn is_active(&self) -> bool {
        self.is_open() && self.active
    }
}

impl PyMicrophoneCapture {
    fn ensure_open(&self) -> PyResult<()> {
        if self.closed || self.stream.is_none() {
            return Err(PyRuntimeError::new_err("Microphone capture is closed."));
        }
        Ok(())
    }

    fn lock_state(&self) -> PyResult<std::sync::MutexGuard<'_, CaptureState>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("Microphone capture buffer lock was poisoned."))
    }
}

fn select_input_device(host: &cpal::Host, index: Option<u32>) -> PyResult<Device> {
    if let Some(index) = index {
        let position = usize::try_from(index)
            .map_err(|_| PyValueError::new_err("Microphone index exceeds platform limits."))?;
        return host
            .input_devices()
            .map_err(|error| {
                PyRuntimeError::new_err(format!("Microphone discovery failed: {error}"))
            })?
            .nth(position)
            .ok_or_else(|| PyValueError::new_err(format!("No microphone at index {index}.")));
    }
    host.default_input_device()
        .ok_or_else(|| PyRuntimeError::new_err("No default microphone input device is available."))
}

fn build_input_stream(
    device: &Device,
    config: &StreamConfig,
    sample_format: SampleFormat,
    state: SharedCaptureState,
) -> PyResult<Stream> {
    let stream = match sample_format {
        SampleFormat::F32 => build_f32_stream(device, config, state),
        SampleFormat::I16 => build_i16_stream(device, config, state),
        SampleFormat::U16 => build_u16_stream(device, config, state),
        unsupported => {
            return Err(PyRuntimeError::new_err(format!(
                "Unsupported microphone sample format: {unsupported}. Expected F32, I16, or U16."
            )));
        }
    };
    stream.map_err(|error| {
        PyRuntimeError::new_err(format!("Unable to open microphone input stream: {error}"))
    })
}

fn build_f32_stream(
    device: &Device,
    config: &StreamConfig,
    state: SharedCaptureState,
) -> Result<Stream, cpal::BuildStreamError> {
    let data_state = Arc::clone(&state);
    let error_state = state;
    device.build_input_stream(
        config,
        move |data: &[f32], _| {
            let samples = data.iter().copied().map(f32_to_pcm16).collect::<Vec<_>>();
            push_samples(&data_state, &samples);
        },
        move |error| record_stream_error(&error_state, error.to_string()),
        None,
    )
}

fn build_i16_stream(
    device: &Device,
    config: &StreamConfig,
    state: SharedCaptureState,
) -> Result<Stream, cpal::BuildStreamError> {
    let data_state = Arc::clone(&state);
    let error_state = state;
    device.build_input_stream(
        config,
        move |data: &[i16], _| push_samples(&data_state, data),
        move |error| record_stream_error(&error_state, error.to_string()),
        None,
    )
}

fn build_u16_stream(
    device: &Device,
    config: &StreamConfig,
    state: SharedCaptureState,
) -> Result<Stream, cpal::BuildStreamError> {
    let data_state = Arc::clone(&state);
    let error_state = state;
    device.build_input_stream(
        config,
        move |data: &[u16], _| {
            let samples = data.iter().copied().map(u16_to_pcm16).collect::<Vec<_>>();
            push_samples(&data_state, &samples);
        },
        move |error| record_stream_error(&error_state, error.to_string()),
        None,
    )
}

fn push_samples(state: &SharedCaptureState, samples: &[i16]) {
    if let Ok(mut state) = state.lock() {
        if let Err(error) = state.buffer.push_interleaved(samples) {
            state.last_error = Some(error);
        }
    }
}

fn record_stream_error(state: &SharedCaptureState, error: String) {
    if let Ok(mut state) = state.lock() {
        state.last_error = Some(error);
    }
}
