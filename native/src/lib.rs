//! Native GPU core entry point for SwirUI.
//!
//! The Python package remains the public developer API. This crate owns the performance-critical
//! renderer path and will progressively absorb surface management, GPU resources and scene
//! submission while keeping Python-facing application code stable.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

#[cfg(target_os = "windows")]
use raw_window_handle::{RawWindowHandle, Win32WindowHandle, WindowsDisplayHandle};
#[cfg(target_os = "windows")]
use std::num::NonZeroIsize;

#[pyfunction]
fn core_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
fn enabled_backends() -> Vec<&'static str> {
    backend_names(wgpu::Instance::enabled_backend_features())
}

#[pyfunction]
fn probe_adapter() -> PyResult<(String, String)> {
    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle());
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        force_fallback_adapter: false,
        compatible_surface: None,
        apply_limit_buckets: false,
    }))
    .map_err(|error| PyRuntimeError::new_err(format!("No usable GPU adapter: {error}")))?;
    let info = adapter.get_info();
    Ok((info.name, info.backend.to_string()))
}

#[cfg(target_os = "windows")]
#[pyfunction]
#[pyo3(signature = (hwnd, width, height, red=0.027, green=0.043, blue=0.078, alpha=1.0))]
fn clear_win32_surface(
    hwnd: isize,
    width: u32,
    height: u32,
    red: f64,
    green: f64,
    blue: f64,
    alpha: f64,
) -> PyResult<(String, String)> {
    validate_dimensions(width, height)?;
    validate_color(red, green, blue, alpha)?;

    let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle());
    let surface = create_win32_surface(&instance, hwnd)?;
    let adapter = request_present_adapter(&instance, &surface)?;

    let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
        label: Some("SwirUI native GPU device"),
        ..Default::default()
    }))
    .map_err(|error| PyRuntimeError::new_err(format!("GPU device creation failed: {error}")))?;

    let mut config = surface
        .get_default_config(&adapter, width, height)
        .ok_or_else(|| PyRuntimeError::new_err("The selected GPU cannot configure this surface."))?;
    config.present_mode = wgpu::PresentMode::AutoVsync;
    config.desired_maximum_frame_latency = 1;
    surface.configure(&device, &config);

    let frame = acquire_surface_texture(&surface)?;
    let view = frame
        .texture
        .create_view(&wgpu::TextureViewDescriptor::default());
    let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
        label: Some("SwirUI first GPU frame"),
    });

    {
        let _render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("SwirUI clear pass"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: &view,
                depth_slice: None,
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(wgpu::Color {
                        r: red,
                        g: green,
                        b: blue,
                        a: alpha,
                    }),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
            multiview_mask: None,
        });
    }

    queue.submit([encoder.finish()]);
    queue.present(frame);

    let info = adapter.get_info();
    Ok((info.name, info.backend.to_string()))
}

#[cfg(not(target_os = "windows"))]
#[pyfunction]
#[pyo3(signature = (hwnd, width, height, red=0.027, green=0.043, blue=0.078, alpha=1.0))]
fn clear_win32_surface(
    hwnd: isize,
    width: u32,
    height: u32,
    red: f64,
    green: f64,
    blue: f64,
    alpha: f64,
) -> PyResult<(String, String)> {
    let _ = (hwnd, width, height, red, green, blue, alpha);
    Err(PyRuntimeError::new_err(
        "clear_win32_surface is only available on Windows.",
    ))
}

fn backend_names(backends: wgpu::Backends) -> Vec<&'static str> {
    let candidates = [
        (wgpu::Backends::DX12, "dx12"),
        (wgpu::Backends::VULKAN, "vulkan"),
        (wgpu::Backends::METAL, "metal"),
        (wgpu::Backends::GL, "gl"),
        (wgpu::Backends::BROWSER_WEBGPU, "browser-webgpu"),
    ];

    candidates
        .into_iter()
        .filter_map(|(backend, name)| backends.contains(backend).then_some(name))
        .collect()
}

#[cfg_attr(not(any(test, target_os = "windows")), allow(dead_code))]
fn validate_dimensions(width: u32, height: u32) -> PyResult<()> {
    if width == 0 || height == 0 {
        return Err(PyValueError::new_err(
            "GPU surface dimensions must be greater than zero.",
        ));
    }
    Ok(())
}

#[cfg_attr(not(any(test, target_os = "windows")), allow(dead_code))]
fn validate_color(red: f64, green: f64, blue: f64, alpha: f64) -> PyResult<()> {
    if [red, green, blue, alpha]
        .into_iter()
        .any(|channel| !(0.0..=1.0).contains(&channel))
    {
        return Err(PyValueError::new_err(
            "GPU clear color channels must be between 0.0 and 1.0.",
        ));
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn request_present_adapter(
    instance: &wgpu::Instance,
    surface: &wgpu::Surface<'_>,
) -> PyResult<wgpu::Adapter> {
    let primary = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        force_fallback_adapter: false,
        compatible_surface: Some(surface),
        apply_limit_buckets: false,
    }));
    if let Ok(adapter) = primary {
        return Ok(adapter);
    }

    pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::LowPower,
        force_fallback_adapter: true,
        compatible_surface: Some(surface),
        apply_limit_buckets: false,
    }))
    .map_err(|error| {
        PyRuntimeError::new_err(format!(
            "No hardware or fallback GPU can present to this HWND: {error}"
        ))
    })
}

#[cfg(target_os = "windows")]
#[allow(unsafe_code)]
fn create_win32_surface(
    instance: &wgpu::Instance,
    hwnd: isize,
) -> PyResult<wgpu::Surface<'static>> {
    let hwnd = NonZeroIsize::new(hwnd)
        .ok_or_else(|| PyValueError::new_err("A non-zero Win32 HWND is required."))?;
    let handle = Win32WindowHandle::new(hwnd);
    let target = wgpu::SurfaceTargetUnsafe::RawHandle {
        raw_display_handle: Some(WindowsDisplayHandle::new().into()),
        raw_window_handle: RawWindowHandle::Win32(handle),
    };

    unsafe { instance.create_surface_unsafe(target) }
        .map_err(|error| PyRuntimeError::new_err(format!("wgpu surface creation failed: {error}")))
}

#[cfg(target_os = "windows")]
fn acquire_surface_texture(surface: &wgpu::Surface<'_>) -> PyResult<wgpu::SurfaceTexture> {
    match surface.get_current_texture() {
        wgpu::CurrentSurfaceTexture::Success(frame)
        | wgpu::CurrentSurfaceTexture::Suboptimal(frame) => Ok(frame),
        wgpu::CurrentSurfaceTexture::Timeout => {
            Err(PyRuntimeError::new_err("Timed out while acquiring a GPU frame."))
        }
        wgpu::CurrentSurfaceTexture::Occluded => {
            Err(PyRuntimeError::new_err("The SwirUI GPU surface is occluded."))
        }
        wgpu::CurrentSurfaceTexture::Outdated => {
            Err(PyRuntimeError::new_err("The SwirUI GPU surface is outdated."))
        }
        wgpu::CurrentSurfaceTexture::Lost => {
            Err(PyRuntimeError::new_err("The SwirUI GPU surface was lost."))
        }
        wgpu::CurrentSurfaceTexture::Validation => Err(PyRuntimeError::new_err(
            "The SwirUI GPU surface failed validation.",
        )),
    }
}

#[pymodule]
fn _swirui_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(core_version, module)?)?;
    module.add_function(wrap_pyfunction!(enabled_backends, module)?)?;
    module.add_function(wrap_pyfunction!(probe_adapter, module)?)?;
    module.add_function(wrap_pyfunction!(clear_win32_surface, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reports_at_least_one_compiled_backend() {
        assert!(!enabled_backends().is_empty());
    }

    #[test]
    fn rejects_zero_surface_size() {
        assert!(validate_dimensions(0, 100).is_err());
        assert!(validate_dimensions(100, 0).is_err());
    }

    #[test]
    fn rejects_invalid_clear_color() {
        assert!(validate_color(0.0, 0.5, 1.0, 1.0).is_ok());
        assert!(validate_color(-0.1, 0.5, 1.0, 1.0).is_err());
        assert!(validate_color(0.0, 0.5, 1.1, 1.0).is_err());
    }
}
