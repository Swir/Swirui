use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use std::collections::HashMap;
use wgpu::util::DeviceExt;

pub(crate) type ImageInstance = (String, f32, f32, f32, f32, f32);

#[cfg(target_os = "windows")]
struct GpuImage {
    _texture: wgpu::Texture,
    view: wgpu::TextureView,
}

#[cfg(target_os = "windows")]
pub(crate) struct PreparedImage {
    _uniform_buffer: wgpu::Buffer,
    bind_group: wgpu::BindGroup,
}

#[cfg(target_os = "windows")]
pub(crate) struct ImageSystem {
    viewport_width: u32,
    viewport_height: u32,
    bind_group_layout: wgpu::BindGroupLayout,
    pipeline: wgpu::RenderPipeline,
    sampler: wgpu::Sampler,
    resources: HashMap<String, GpuImage>,
}

#[cfg(target_os = "windows")]
impl ImageSystem {
    pub(crate) fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
    ) -> Self {
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("SwirUI image bind group layout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("SwirUI image pipeline layout"),
            bind_group_layouts: &[Some(&bind_group_layout)],
            immediate_size: 0,
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("SwirUI image shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("images.wgsl").into()),
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("SwirUI persistent image pipeline"),
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
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            multiview_mask: None,
            cache: None,
        });
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("SwirUI image sampler"),
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::MipmapFilterMode::Nearest,
            ..Default::default()
        });

        Self {
            viewport_width: width,
            viewport_height: height,
            bind_group_layout,
            pipeline,
            sampler,
            resources: HashMap::new(),
        }
    }

    pub(crate) fn resize(&mut self, width: u32, height: u32) {
        self.viewport_width = width;
        self.viewport_height = height;
    }

    pub(crate) fn register_rgba8(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        resource_id: String,
        width: u32,
        height: u32,
        rgba8: &[u8],
    ) -> PyResult<()> {
        validate_image_resource(&resource_id, width, height, rgba8)?;
        let size = wgpu::Extent3d {
            width,
            height,
            depth_or_array_layers: 1,
        };
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("SwirUI image texture"),
            size,
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
            view_formats: &[],
        });
        queue.write_texture(
            wgpu::TexelCopyTextureInfo {
                texture: &texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            rgba8,
            wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(width * 4),
                rows_per_image: Some(height),
            },
            size,
        );
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        self.resources.insert(resource_id, GpuImage { _texture: texture, view });
        Ok(())
    }

    pub(crate) fn unregister(&mut self, resource_id: &str) -> bool {
        self.resources.remove(resource_id).is_some()
    }

    pub(crate) fn resource_count(&self) -> usize {
        self.resources.len()
    }

    pub(crate) fn prepare(
        &self,
        device: &wgpu::Device,
        images: &[ImageInstance],
    ) -> PyResult<Vec<PreparedImage>> {
        validate_image_instances(images)?;
        let mut prepared = Vec::with_capacity(images.len());
        for (resource_id, x, y, width, height, opacity) in images {
            let image = self.resources.get(resource_id).ok_or_else(|| {
                PyKeyError::new_err(format!("Unknown GPU image resource: {resource_id}"))
            })?;
            let uniforms = floats_to_bytes(&[
                self.viewport_width as f32,
                self.viewport_height as f32,
                *x,
                *y,
                *width,
                *height,
                *opacity,
                0.0,
            ]);
            let uniform_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("SwirUI image uniforms"),
                contents: &uniforms,
                usage: wgpu::BufferUsages::UNIFORM,
            });
            let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("SwirUI image bind group"),
                layout: &self.bind_group_layout,
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: uniform_buffer.as_entire_binding(),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: wgpu::BindingResource::TextureView(&image.view),
                    },
                    wgpu::BindGroupEntry {
                        binding: 2,
                        resource: wgpu::BindingResource::Sampler(&self.sampler),
                    },
                ],
            });
            prepared.push(PreparedImage {
                _uniform_buffer: uniform_buffer,
                bind_group,
            });
        }
        Ok(prepared)
    }

    pub(crate) fn render<'a>(
        &'a self,
        pass: &mut wgpu::RenderPass<'a>,
        prepared: &'a [PreparedImage],
    ) {
        pass.set_pipeline(&self.pipeline);
        for image in prepared {
            pass.set_bind_group(0, &image.bind_group, &[]);
            pass.draw(0..6, 0..1);
        }
    }
}

pub(crate) fn validate_image_resource(
    resource_id: &str,
    width: u32,
    height: u32,
    rgba8: &[u8],
) -> PyResult<()> {
    if resource_id.is_empty() {
        return Err(PyValueError::new_err("Image resource id cannot be empty."));
    }
    if width == 0 || height == 0 {
        return Err(PyValueError::new_err(
            "Image resource dimensions must be greater than zero.",
        ));
    }
    let expected = width as usize * height as usize * 4;
    if rgba8.len() != expected {
        return Err(PyValueError::new_err(format!(
            "RGBA8 image resource requires {expected} bytes, received {}.",
            rgba8.len()
        )));
    }
    Ok(())
}

pub(crate) fn validate_image_instances(images: &[ImageInstance]) -> PyResult<()> {
    for (resource_id, x, y, width, height, opacity) in images {
        if resource_id.is_empty() {
            return Err(PyValueError::new_err("Image resource id cannot be empty."));
        }
        if ![*x, *y, *width, *height, *opacity]
            .into_iter()
            .all(f32::is_finite)
        {
            return Err(PyValueError::new_err(
                "Image geometry and opacity must be finite.",
            ));
        }
        if *width <= 0.0 || *height <= 0.0 {
            return Err(PyValueError::new_err(
                "Image width and height must be greater than zero.",
            ));
        }
        if !(0.0..=1.0).contains(opacity) {
            return Err(PyValueError::new_err(
                "Image opacity must be between 0.0 and 1.0.",
            ));
        }
    }
    Ok(())
}

#[cfg(target_os = "windows")]
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
    fn validates_rgba8_resource_size() {
        assert!(validate_image_resource("logo", 2, 2, &[255; 16]).is_ok());
        assert!(validate_image_resource("", 2, 2, &[255; 16]).is_err());
        assert!(validate_image_resource("logo", 0, 2, &[]).is_err());
        assert!(validate_image_resource("logo", 2, 2, &[255; 15]).is_err());
    }

    #[test]
    fn validates_image_instances() {
        let valid = ("logo".to_owned(), 10.0, 20.0, 100.0, 80.0, 0.75);
        assert!(validate_image_instances(&[valid.clone()]).is_ok());

        let mut invalid_size = valid.clone();
        invalid_size.3 = 0.0;
        assert!(validate_image_instances(&[invalid_size]).is_err());

        let mut invalid_opacity = valid;
        invalid_opacity.5 = 1.5;
        assert!(validate_image_instances(&[invalid_opacity]).is_err());
    }
}
