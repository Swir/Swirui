//! Windows Media Foundation camera capture exposed to Python through PyO3.

use nokhwa::pixel_format::RgbAFormat;
use nokhwa::utils::{ApiBackend, CameraIndex, RequestedFormat, RequestedFormatType};
use nokhwa::Camera;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use crate::camera::validate_camera_rgba_frame;

pub(crate) type CameraDeviceMetadata = (u32, String, String);

pub(crate) fn list_camera_devices() -> PyResult<Vec<CameraDeviceMetadata>> {
    let devices = nokhwa::query(ApiBackend::MediaFoundation)
        .map_err(|error| PyRuntimeError::new_err(format!("Camera discovery failed: {error}")))?;
    Ok(devices
        .into_iter()
        .enumerate()
        .map(|(position, info)| {
            (
                u32::try_from(position).unwrap_or(u32::MAX),
                info.human_name(),
                info.description().to_owned(),
            )
        })
        .collect())
}

#[pyclass(name = "CameraCapture", unsendable)]
pub(crate) struct PyCameraCapture {
    camera: Camera,
    closed: bool,
}

#[pymethods]
impl PyCameraCapture {
    #[new]
    fn new(index: u32) -> PyResult<Self> {
        let requested =
            RequestedFormat::new::<RgbAFormat>(RequestedFormatType::AbsoluteHighestFrameRate);
        let mut camera = Camera::with_backend(
            CameraIndex::Index(index),
            requested,
            ApiBackend::MediaFoundation,
        )
        .map_err(|error| PyRuntimeError::new_err(format!("Camera open failed: {error}")))?;
        camera
            .open_stream()
            .map_err(|error| PyRuntimeError::new_err(format!("Camera stream failed: {error}")))?;
        Ok(Self {
            camera,
            closed: false,
        })
    }

    fn read_frame(&mut self) -> PyResult<(u32, u32, Vec<u8>)> {
        if self.closed {
            return Err(PyRuntimeError::new_err("Camera capture is closed."));
        }
        let buffer = self
            .camera
            .frame()
            .map_err(|error| PyRuntimeError::new_err(format!("Camera frame failed: {error}")))?;
        let decoded = buffer
            .decode_image::<RgbAFormat>()
            .map_err(|error| PyRuntimeError::new_err(format!("Camera decode failed: {error}")))?;
        let (width, height) = decoded.dimensions();
        let rgba = decoded.into_raw();
        validate_camera_rgba_frame(width, height, &rgba).map_err(PyRuntimeError::new_err)?;
        Ok((width, height, rgba))
    }

    fn close(&mut self) -> PyResult<()> {
        if self.closed {
            return Ok(());
        }
        self.camera
            .stop_stream()
            .map_err(|error| PyRuntimeError::new_err(format!("Camera close failed: {error}")))?;
        self.closed = true;
        Ok(())
    }

    #[getter]
    fn is_open(&self) -> bool {
        !self.closed && self.camera.is_stream_open()
    }
}
