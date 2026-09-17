//! Persistent render targets and GPU post-processing passes.
//!
//! The scene renderer writes into a sampleable offscreen texture before final
//! presentation. Post-processing passes keep their own ping-pong targets and GPU
//! pipelines alive across frames so enabling an effect does not allocate full-size
//! textures or rebuild pipelines every frame.

use wgpu::util::DeviceExt;

const MAX_BLUR_RADIUS_PIXELS: f32 = 512.0;
const BLUR_KERNEL_MAX_OFFSET: f32 = 3.230_769_2;

pub(crate) struct OffscreenRenderTarget {
    _texture: wgpu::Texture,
    view: wgpu::TextureView,
    width: u32,
    height: u32,
    generation: u64,
    label: &'static str,
}

impl OffscreenRenderTarget {
    pub(crate) fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
    ) -> Self {
        Self::new_labeled(
            device,
            format,
            width,
            height,
            "SwirUI persistent offscreen scene target",
        )
    }

    fn new_labeled(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        label: &'static str,
    ) -> Self {
        let (texture, view) = create_target(device, format, width, height, label);
        Self {
            _texture: texture,
            view,
            width,
            height,
            generation: 1,
            label,
        }
    }

    pub(crate) fn resize(
        &mut self,
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
    ) -> bool {
        if self.width == width && self.height == height {
            return false;
        }

        let (texture, view) = create_target(device, format, width, height, self.label);
        self._texture = texture;
        self.view = view;
        self.width = width;
        self.height = height;
        self.generation = self.generation.saturating_add(1);
        true
    }

    pub(crate) fn view(&self) -> &wgpu::TextureView {
        &self.view
    }

    pub(crate) const fn size(&self) -> (u32, u32) {
        (self.width, self.height)
    }

    pub(crate) const fn generation(&self) -> u64 {
        self.generation
    }
}

pub(crate) struct SeparableBlur {
    ping_target: OffscreenRenderTarget,
    output_target: OffscreenRenderTarget,
    sampler: wgpu::Sampler,
    bind_group_layout: wgpu::BindGroupLayout,
    pipeline: wgpu::RenderPipeline,
    horizontal_params: wgpu::Buffer,
    vertical_params: wgpu::Buffer,
    horizontal_bind_group: wgpu::BindGroup,
    vertical_bind_group: wgpu::BindGroup,
}

impl SeparableBlur {
    pub(crate) fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        source_view: &wgpu::TextureView,
    ) -> Self {
        let ping_target = OffscreenRenderTarget::new_labeled(
            device,
            format,
            width,
            height,
            "SwirUI persistent blur ping target",
        );
        let output_target = OffscreenRenderTarget::new_labeled(
            device,
            format,
            width,
            height,
            "SwirUI persistent blur output target",
        );
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("SwirUI post-process linear sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            ..Default::default()
        });
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("SwirUI separable blur bind group layout"),
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
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("SwirUI separable blur pipeline layout"),
            bind_group_layouts: &[Some(&bind_group_layout)],
            immediate_size: 0,
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("SwirUI separable Gaussian blur shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("postprocess_blur.wgsl").into()),
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("SwirUI persistent separable blur pipeline"),
            layout: Some(&pipeline_layout),
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
        });
        let horizontal_params = create_blur_params_buffer(device, "horizontal");
        let vertical_params = create_blur_params_buffer(device, "vertical");
        let horizontal_bind_group = create_blur_bind_group(
            device,
            &bind_group_layout,
            source_view,
            &sampler,
            &horizontal_params,
            "SwirUI horizontal blur bind group",
        );
        let vertical_bind_group = create_blur_bind_group(
            device,
            &bind_group_layout,
            ping_target.view(),
            &sampler,
            &vertical_params,
            "SwirUI vertical blur bind group",
        );

        Self {
            ping_target,
            output_target,
            sampler,
            bind_group_layout,
            pipeline,
            horizontal_params,
            vertical_params,
            horizontal_bind_group,
            vertical_bind_group,
        }
    }

    pub(crate) fn resize(
        &mut self,
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        source_view: &wgpu::TextureView,
    ) -> bool {
        let ping_resized = self.ping_target.resize(device, format, width, height);
        let output_resized = self.output_target.resize(device, format, width, height);
        if !(ping_resized || output_resized) {
            return false;
        }
        self.horizontal_bind_group = create_blur_bind_group(
            device,
            &self.bind_group_layout,
            source_view,
            &self.sampler,
            &self.horizontal_params,
            "SwirUI horizontal blur bind group",
        );
        self.vertical_bind_group = create_blur_bind_group(
            device,
            &self.bind_group_layout,
            self.ping_target.view(),
            &self.sampler,
            &self.vertical_params,
            "SwirUI vertical blur bind group",
        );
        true
    }

    pub(crate) fn encode(
        &self,
        queue: &wgpu::Queue,
        encoder: &mut wgpu::CommandEncoder,
        radius_pixels: f32,
    ) -> &wgpu::TextureView {
        let (width, height) = self.output_target.size();
        let (horizontal, vertical) = blur_directions(radius_pixels, width, height);
        queue.write_buffer(&self.horizontal_params, 0, &floats_to_bytes(&horizontal));
        queue.write_buffer(&self.vertical_params, 0, &floats_to_bytes(&vertical));

        self.encode_pass(
            encoder,
            self.ping_target.view(),
            &self.horizontal_bind_group,
            "SwirUI horizontal blur pass",
        );
        self.encode_pass(
            encoder,
            self.output_target.view(),
            &self.vertical_bind_group,
            "SwirUI vertical blur pass",
        );
        self.output_target.view()
    }

    pub(crate) const fn size(&self) -> (u32, u32) {
        self.output_target.size()
    }

    pub(crate) const fn generation(&self) -> u64 {
        self.output_target.generation()
    }

    fn encode_pass(
        &self,
        encoder: &mut wgpu::CommandEncoder,
        target: &wgpu::TextureView,
        bind_group: &wgpu::BindGroup,
        label: &'static str,
    ) {
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some(label),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: target,
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
        pass.set_bind_group(0, bind_group, &[]);
        pass.draw(0..3, 0..1);
    }
}

pub(crate) fn validate_blur_radius(radius_pixels: f32) -> Result<(), &'static str> {
    if !radius_pixels.is_finite() {
        return Err("post-process blur radius must be finite");
    }
    if !(0.0..=MAX_BLUR_RADIUS_PIXELS).contains(&radius_pixels) {
        return Err("post-process blur radius must be between 0 and 512 physical pixels");
    }
    Ok(())
}

fn blur_directions(radius_pixels: f32, width: u32, height: u32) -> ([f32; 4], [f32; 4]) {
    let width = width.max(1) as f32;
    let height = height.max(1) as f32;
    let sample_step_pixels = radius_pixels / BLUR_KERNEL_MAX_OFFSET;
    (
        [sample_step_pixels / width, 0.0, 0.0, 0.0],
        [0.0, sample_step_pixels / height, 0.0, 0.0],
    )
}

fn create_target(
    device: &wgpu::Device,
    format: wgpu::TextureFormat,
    width: u32,
    height: u32,
    label: &'static str,
) -> (wgpu::Texture, wgpu::TextureView) {
    let texture = device.create_texture(&wgpu::TextureDescriptor {
        label: Some(label),
        size: wgpu::Extent3d {
            width,
            height,
            depth_or_array_layers: 1,
        },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format,
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
        view_formats: &[],
    });
    let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
    (texture, view)
}

fn create_blur_params_buffer(device: &wgpu::Device, axis: &str) -> wgpu::Buffer {
    device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
        label: Some(&format!("SwirUI {axis} blur parameters")),
        contents: &floats_to_bytes(&[0.0; 4]),
        usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
    })
}

fn create_blur_bind_group(
    device: &wgpu::Device,
    layout: &wgpu::BindGroupLayout,
    source_view: &wgpu::TextureView,
    sampler: &wgpu::Sampler,
    params: &wgpu::Buffer,
    label: &'static str,
) -> wgpu::BindGroup {
    device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: Some(label),
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
    fn validates_physical_blur_radius_budget() {
        assert!(validate_blur_radius(0.0).is_ok());
        assert!(validate_blur_radius(64.0).is_ok());
        assert!(validate_blur_radius(320.0).is_ok());
        assert!(validate_blur_radius(512.0).is_ok());
        assert!(validate_blur_radius(-0.01).is_err());
        assert!(validate_blur_radius(512.01).is_err());
        assert!(validate_blur_radius(f32::NAN).is_err());
        assert!(validate_blur_radius(f32::INFINITY).is_err());
    }

    #[test]
    fn blur_radius_maps_to_farthest_kernel_sample_at_any_resolution() {
        let radius = 12.0;
        let (horizontal, vertical) = blur_directions(radius, 600, 300);
        let horizontal_extent = horizontal[0] * 600.0 * BLUR_KERNEL_MAX_OFFSET;
        let vertical_extent = vertical[1] * 300.0 * BLUR_KERNEL_MAX_OFFSET;
        assert!((horizontal_extent - radius).abs() < 0.0001);
        assert!((vertical_extent - radius).abs() < 0.0001);
    }
}
