//! Persistent custom WGSL post-processing for the Win32/wgpu renderer.
//!
//! Python owns the public `CustomShaderEffect` contract and composes user code
//! into SwirUI's bounded fullscreen shader interface. This module owns the GPU
//! resources needed to execute that validated program without rebuilding the
//! pipeline or full-size output target on every frame.

use wgpu::util::DeviceExt;

use crate::postprocess::OffscreenRenderTarget;
use crate::shader_validation::validate_custom_shader_wgsl;

pub(crate) const CUSTOM_SHADER_PARAMETER_FLOATS: usize = 4;

pub(crate) fn validate_custom_shader_parameters(values: &[f32]) -> Result<(), &'static str> {
    if values.len() != CUSTOM_SHADER_PARAMETER_FLOATS {
        return Err("custom shader effect requires exactly four parameter values");
    }
    if !values.iter().copied().all(f32::is_finite) {
        return Err("custom shader effect parameters must be finite");
    }
    Ok(())
}

pub(crate) struct CustomShaderPass {
    output_target: OffscreenRenderTarget,
    sampler: wgpu::Sampler,
    bind_group_layout: wgpu::BindGroupLayout,
    pipeline_layout: wgpu::PipelineLayout,
    pipeline: wgpu::RenderPipeline,
    params: wgpu::Buffer,
    bind_group: wgpu::BindGroup,
    source: String,
    pipeline_generation: u64,
}

impl CustomShaderPass {
    pub(crate) fn new(
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        source_view: &wgpu::TextureView,
        source: &str,
        parameters: &[f32],
    ) -> Result<Self, String> {
        validate_custom_shader_wgsl(source)?;
        validate_custom_shader_parameters(parameters).map_err(str::to_owned)?;

        let output_target = OffscreenRenderTarget::new(device, format, width, height);
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("SwirUI custom-shader linear sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });
        let bind_group_layout = create_bind_group_layout(device);
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("SwirUI custom-shader pipeline layout"),
            bind_group_layouts: &[Some(&bind_group_layout)],
            immediate_size: 0,
        });
        let pipeline = create_pipeline(device, format, &pipeline_layout, source);
        let params = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("SwirUI custom-shader parameters"),
            contents: &floats_to_bytes(parameters),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });
        let bind_group = create_bind_group(
            device,
            &bind_group_layout,
            source_view,
            &sampler,
            &params,
        );
        queue.write_buffer(&params, 0, &floats_to_bytes(parameters));

        Ok(Self {
            output_target,
            sampler,
            bind_group_layout,
            pipeline_layout,
            pipeline,
            params,
            bind_group,
            source: source.to_owned(),
            pipeline_generation: 1,
        })
    }

    pub(crate) fn set_shader(
        &mut self,
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        source: &str,
    ) -> Result<bool, String> {
        validate_custom_shader_wgsl(source)?;
        if self.source == source {
            return Ok(false);
        }

        self.pipeline = create_pipeline(device, format, &self.pipeline_layout, source);
        self.source.clear();
        self.source.push_str(source);
        self.pipeline_generation = self.pipeline_generation.saturating_add(1);
        Ok(true)
    }

    pub(crate) fn set_parameters(
        &self,
        queue: &wgpu::Queue,
        parameters: &[f32],
    ) -> Result<(), &'static str> {
        validate_custom_shader_parameters(parameters)?;
        queue.write_buffer(&self.params, 0, &floats_to_bytes(parameters));
        Ok(())
    }

    pub(crate) fn rebind_source(
        &mut self,
        device: &wgpu::Device,
        source_view: &wgpu::TextureView,
    ) {
        self.bind_group = create_bind_group(
            device,
            &self.bind_group_layout,
            source_view,
            &self.sampler,
            &self.params,
        );
    }

    pub(crate) fn resize(
        &mut self,
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        source_view: &wgpu::TextureView,
    ) -> bool {
        let resized = self.output_target.resize(device, format, width, height);
        if resized {
            self.rebind_source(device, source_view);
        }
        resized
    }

    pub(crate) fn encode(&self, encoder: &mut wgpu::CommandEncoder) -> &wgpu::TextureView {
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("SwirUI custom-shader postprocess pass"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: self.output_target.view(),
                depth_slice: None,
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: None,
            timestamp_writes: None,
            occlusion_query_set: None,
            multiview_mask: None,
        });
        pass.set_pipeline(&self.pipeline);
        pass.set_bind_group(0, &self.bind_group, &[]);
        pass.draw(0..3, 0..1);
        self.output_target.view()
    }

    pub(crate) const fn size(&self) -> (u32, u32) {
        self.output_target.size()
    }

    pub(crate) const fn generation(&self) -> u64 {
        self.output_target.generation()
    }

    pub(crate) const fn pipeline_generation(&self) -> u64 {
        self.pipeline_generation
    }
}

fn create_bind_group_layout(device: &wgpu::Device) -> wgpu::BindGroupLayout {
    device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
        label: Some("SwirUI custom-shader bind group layout"),
        entries: &[
            wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Texture {
                    sample_type: wgpu::TextureSampleType::Float { filterable: true },
                    view_dimension: wgpu::TextureViewDimension::D2,
                    multisampled: false,
                },
                count: None,
            },
            wgpu::BindGroupLayoutEntry {
                binding: 1,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                count: None,
            },
            wgpu::BindGroupLayoutEntry {
                binding: 2,
                visibility: wgpu::ShaderStages::FRAGMENT,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            },
        ],
    })
}

fn create_pipeline(
    device: &wgpu::Device,
    format: wgpu::TextureFormat,
    pipeline_layout: &wgpu::PipelineLayout,
    source: &str,
) -> wgpu::RenderPipeline {
    let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
        label: Some("SwirUI validated custom postprocess shader"),
        source: wgpu::ShaderSource::Wgsl(source.into()),
    });
    device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
        label: Some("SwirUI persistent custom-shader pipeline"),
        layout: Some(pipeline_layout),
        vertex: wgpu::VertexState {
            module: &shader,
            entry_point: Some("vs_main"),
            compilation_options: wgpu::PipelineCompilationOptions::default(),
            buffers: &[],
        },
        primitive: wgpu::PrimitiveState::default(),
        depth_stencil: None,
        multisample: wgpu::MultisampleState::default(),
        fragment: Some(wgpu::FragmentState {
            module: &shader,
            entry_point: Some("fs_main"),
            compilation_options: wgpu::PipelineCompilationOptions::default(),
            targets: &[Some(wgpu::ColorTargetState {
                format,
                blend: None,
                write_mask: wgpu::ColorWrites::ALL,
            })],
        }),
        multiview_mask: None,
        cache: None,
    })
}

fn create_bind_group(
    device: &wgpu::Device,
    layout: &wgpu::BindGroupLayout,
    source_view: &wgpu::TextureView,
    sampler: &wgpu::Sampler,
    params: &wgpu::Buffer,
) -> wgpu::BindGroup {
    device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: Some("SwirUI custom-shader bind group"),
        layout,
        entries: &[
            wgpu::BindGroupEntry {
                binding: 0,
                resource: wgpu::BindingResource::TextureView(source_view),
            },
            wgpu::BindGroupEntry {
                binding: 1,
                resource: wgpu::BindingResource::Sampler(sampler),
            },
            wgpu::BindGroupEntry {
                binding: 2,
                resource: params.as_entire_binding(),
            },
        ],
    })
}

fn floats_to_bytes(values: &[f32]) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(std::mem::size_of_val(values));
    for value in values {
        bytes.extend_from_slice(&value.to_ne_bytes());
    }
    bytes
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_custom_shader_parameter_contract() {
        assert!(validate_custom_shader_parameters(&[0.0, 1.0, -1.0, 0.5]).is_ok());
        assert!(validate_custom_shader_parameters(&[0.0, 1.0, -1.0]).is_err());
        assert!(validate_custom_shader_parameters(&[0.0, f32::NAN, 0.0, 0.0]).is_err());
        assert!(validate_custom_shader_parameters(&[0.0, f32::INFINITY, 0.0, 0.0]).is_err());
    }
}
