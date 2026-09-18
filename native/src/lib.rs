//! Native GPU core entry point for SwirUI.
//!
//! Python remains the public developer API. Renderer implementation details live
//! in dedicated modules so the native core can grow without turning this file
//! into a monolithic backend.

#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod affine;
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod color_filter;
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod custom_effect;
mod image;
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod postprocess;
mod renderer;
mod shader_validation;
mod shape;
mod text;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use renderer::{clear_win32_surface, draw_rectangles_win32_surface};

#[cfg(target_os = "windows")]
use renderer::PyWin32GpuRenderer;

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

#[pyfunction]
fn validate_custom_shader_wgsl(source: &str) -> PyResult<()> {
    shader_validation::validate_custom_shader_wgsl(source).map_err(PyValueError::new_err)
}

#[pyfunction]
fn validate_affine_transform(values: Vec<f32>) -> PyResult<()> {
    affine::Affine2D::try_from_slice(&values)
        .map(|_| ())
        .map_err(PyValueError::new_err)
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

#[pymodule]
fn _swirui_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(core_version, module)?)?;
    module.add_function(wrap_pyfunction!(enabled_backends, module)?)?;
    module.add_function(wrap_pyfunction!(probe_adapter, module)?)?;
    module.add_function(wrap_pyfunction!(validate_custom_shader_wgsl, module)?)?;
    module.add_function(wrap_pyfunction!(validate_affine_transform, module)?)?;
    module.add_function(wrap_pyfunction!(clear_win32_surface, module)?)?;
    module.add_function(wrap_pyfunction!(draw_rectangles_win32_surface, module)?)?;
    #[cfg(target_os = "windows")]
    module.add_class::<PyWin32GpuRenderer>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reports_at_least_one_compiled_backend() {
        assert!(!enabled_backends().is_empty());
    }
}
