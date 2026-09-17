//! Validation boundary for Python-authored custom shader effects.
//!
//! SwirUI's Python API composes a restricted pure-function effect into an owned
//! fullscreen WGSL program. This module validates that final program with the same
//! Naga major used by wgpu before renderer pipeline creation is introduced.

use naga::ShaderStage;
use naga::front::wgsl;
use naga::valid::{Capabilities, ValidationFlags, Validator};

const MAX_CUSTOM_SHADER_BYTES: usize = 96 * 1024;

pub(crate) fn validate_custom_shader_wgsl(source: &str) -> Result<(), String> {
    if source.trim().is_empty() {
        return Err("custom shader WGSL cannot be empty".to_owned());
    }
    if source.len() > MAX_CUSTOM_SHADER_BYTES {
        return Err("custom shader WGSL cannot exceed 96 KiB after SwirUI composition".to_owned());
    }

    let module = wgsl::parse_str(source).map_err(|error| format!("WGSL parse error: {error}"))?;
    Validator::new(ValidationFlags::all(), Capabilities::empty())
        .validate(&module)
        .map_err(|error| format!("WGSL validation error: {error}"))?;

    let has_vertex_entry = module
        .entry_points
        .iter()
        .any(|entry| entry.name == "vs_main" && entry.stage == ShaderStage::Vertex);
    if !has_vertex_entry {
        return Err("custom shader WGSL must contain SwirUI's vs_main vertex entry point".to_owned());
    }

    let has_fragment_entry = module
        .entry_points
        .iter()
        .any(|entry| entry.name == "fs_main" && entry.stage == ShaderStage::Fragment);
    if !has_fragment_entry {
        return Err("custom shader WGSL must contain SwirUI's fs_main fragment entry point".to_owned());
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const VALID_SHADER: &str = r"
@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> @builtin(position) vec4<f32> {
    let x = f32(i32(vertex_index) - 1);
    return vec4<f32>(x, 0.0, 0.0, 1.0);
}

@fragment
fn fs_main() -> @location(0) vec4<f32> {
    return vec4<f32>(0.2, 0.4, 0.8, 1.0);
}
";

    #[test]
    fn accepts_valid_vertex_and_fragment_program() {
        assert!(validate_custom_shader_wgsl(VALID_SHADER).is_ok());
    }

    #[test]
    fn rejects_invalid_wgsl() {
        let error = validate_custom_shader_wgsl("@fragment fn fs_main( {")
            .expect_err("invalid WGSL must be rejected");
        assert!(error.contains("parse"));
    }

    #[test]
    fn rejects_missing_owned_entry_points() {
        let source = r"
@compute @workgroup_size(1)
fn main() {}
";
        let error = validate_custom_shader_wgsl(source)
            .expect_err("compute-only shader must not satisfy the SwirUI postprocess contract");
        assert!(error.contains("vs_main"));
    }

    #[test]
    fn rejects_oversized_programs_before_parsing() {
        let source = " ".repeat(MAX_CUSTOM_SHADER_BYTES + 1);
        let error = validate_custom_shader_wgsl(&source)
            .expect_err("oversized shader source must be rejected");
        assert!(error.contains("96 KiB"));
    }
}
