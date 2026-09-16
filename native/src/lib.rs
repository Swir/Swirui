//! Native GPU core entry point for SwirUI.
//!
//! The Python package remains the public developer API. This crate owns the performance-critical
//! renderer path and will progressively absorb surface management, GPU resources and scene
//! submission while keeping Python-facing application code stable.

use pyo3::prelude::*;

#[pyfunction]
fn core_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
fn enabled_backends() -> Vec<&'static str> {
    backend_names(wgpu::Instance::enabled_backend_features())
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
