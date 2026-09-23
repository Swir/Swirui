//! Native GPU core entry point for SwirUI.
//!
//! Python remains the public developer API. Renderer implementation details live
//! in dedicated modules so the native core can grow without turning this file
//! into a monolithic backend.

#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod affine;
mod audio;
#[cfg(target_os = "windows")]
mod audio_output;
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod color_filter;
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod custom_effect;
mod image;
mod media;
#[cfg_attr(not(target_os = "windows"), allow(dead_code))]
mod postprocess;
mod renderer;
mod shader_validation;
mod shape;
mod text;
mod video;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use renderer::{clear_win32_surface, draw_rectangles_win32_surface};

#[cfg(target_os = "windows")]
use audio_output::PyAudioOutput;
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

#[pyfunction]
#[pyo3(signature = (content, width, height, font_size, red, green, blue, alpha, family))]
fn rasterize_text_rgba(
    content: &str,
    width: u32,
    height: u32,
    font_size: f32,
    red: f32,
    green: f32,
    blue: f32,
    alpha: f32,
    family: &str,
) -> PyResult<Vec<u8>> {
    text::rasterize_text_rgba(
        content, width, height, font_size, red, green, blue, alpha, family,
    )
}

#[pyfunction]
fn decode_image_rgba(data: Vec<u8>) -> PyResult<(u32, u32, Vec<u8>)> {
    media::decode_image_rgba(&data).map_err(PyValueError::new_err)
}

#[pyfunction]
fn decode_gif_rgba_frames(data: Vec<u8>) -> PyResult<Vec<media::DecodedFrame>> {
    media::decode_gif_rgba_frames(&data).map_err(PyValueError::new_err)
}

#[pyfunction]
#[pyo3(signature = (data, width=None, height=None))]
fn decode_svg_rgba(
    data: Vec<u8>,
    width: Option<u32>,
    height: Option<u32>,
) -> PyResult<(u32, u32, Vec<u8>)> {
    media::decode_svg_rgba(&data, width, height).map_err(PyValueError::new_err)
}

#[pyfunction]
fn parse_lottie_metadata(data: Vec<u8>) -> PyResult<media::LottieMetadata> {
    media::parse_lottie_metadata(&data).map_err(PyValueError::new_err)
}

#[pyfunction]
#[pyo3(signature = (data, frame, width=None, height=None))]
fn render_lottie_frame_rgba(
    data: Vec<u8>,
    frame: f64,
    width: Option<u32>,
    height: Option<u32>,
) -> PyResult<(u32, u32, Vec<u8>)> {
    media::render_lottie_frame_rgba(&data, frame, width, height).map_err(PyValueError::new_err)
}

#[pyfunction]
fn validate_video_rgba_frames(
    width: u32,
    height: u32,
    frame_rate: f64,
    frames: Vec<Vec<u8>>,
) -> PyResult<video::VideoMetadata> {
    video::validate_video_rgba_frames(width, height, frame_rate, &frames)
        .map_err(PyValueError::new_err)
}

#[pyfunction]
#[pyo3(signature = (elapsed_ms, frame_rate, frame_count, loop_video=true))]
fn video_frame_index(
    elapsed_ms: f64,
    frame_rate: f64,
    frame_count: usize,
    loop_video: bool,
) -> PyResult<usize> {
    video::video_frame_index(elapsed_ms, frame_rate, frame_count, loop_video)
        .map_err(PyValueError::new_err)
}

#[pyfunction]
fn validate_audio_pcm16(
    sample_rate: u32,
    channels: u16,
    pcm16: Vec<u8>,
) -> PyResult<audio::AudioMetadata> {
    audio::validate_audio_pcm16(sample_rate, channels, &pcm16).map_err(PyValueError::new_err)
}

#[pyfunction]
#[pyo3(signature = (elapsed_ms, sample_rate, frame_count, loop_audio=true))]
fn audio_frame_index(
    elapsed_ms: f64,
    sample_rate: u32,
    frame_count: usize,
    loop_audio: bool,
) -> PyResult<usize> {
    audio::audio_frame_index(elapsed_ms, sample_rate, frame_count, loop_audio)
        .map_err(PyValueError::new_err)
}

#[pyfunction]
fn native_audio_output_supported() -> bool {
    cfg!(target_os = "windows")
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
    module.add_function(wrap_pyfunction!(rasterize_text_rgba, module)?)?;
    module.add_function(wrap_pyfunction!(decode_image_rgba, module)?)?;
    module.add_function(wrap_pyfunction!(decode_gif_rgba_frames, module)?)?;
    module.add_function(wrap_pyfunction!(decode_svg_rgba, module)?)?;
    module.add_function(wrap_pyfunction!(parse_lottie_metadata, module)?)?;
    module.add_function(wrap_pyfunction!(render_lottie_frame_rgba, module)?)?;
    module.add_function(wrap_pyfunction!(validate_video_rgba_frames, module)?)?;
    module.add_function(wrap_pyfunction!(video_frame_index, module)?)?;
    module.add_function(wrap_pyfunction!(validate_audio_pcm16, module)?)?;
    module.add_function(wrap_pyfunction!(audio_frame_index, module)?)?;
    module.add_function(wrap_pyfunction!(native_audio_output_supported, module)?)?;
    module.add_function(wrap_pyfunction!(clear_win32_surface, module)?)?;
    module.add_function(wrap_pyfunction!(draw_rectangles_win32_surface, module)?)?;
    #[cfg(target_os = "windows")]
    module.add_class::<PyAudioOutput>()?;
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
