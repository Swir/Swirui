use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[cfg(target_os = "windows")]
use pyo3::exceptions::PyKeyError;
#[cfg(target_os = "windows")]
use std::collections::HashMap;
#[cfg(target_os = "windows")]
use wgpu::util::DeviceExt;

pub(crate) type ClipRect = (f32, f32, f32, f32);
pub(crate) type ImageInstance = (String, f32, f32, f32, f32, f32, ClipRect);

#[cfg(not(target_os = "windows"))]
pub(crate) struct ImageSystem;

#[cfg(target_os = "windows")]
struct ImageResource {
    _texture: wgpu::Texture,
    _view: wgpu::TextureView,
    bind_group: wgpu::BindGroup,
    width: u32,
    height: u32,
}

#[cfg(target_os = "windows")]
pub(crate) struct ImageSystem {
    bind_group_layout: wgpu::BindGroupLayout,
    pipeline: wgpu::RenderPipeline,
    sampler: wgpu::Sampler,
    resources: HashMap<String, ImageResource>,
}

#[cfg(target_os = "windows")]
impl ImageSystem {
    pub(crate) fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("SwirUI image bind group layout"),
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
                buffers: &[Some(wgpu::VertexBufferLayout {
                    array_stride: 5 * 4,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 0,
                            shader_location: 0,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 2 * 4,
                            shader_location: 1,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32,
                            offset: 4 * 4,
                            shader_location: 2,
                        },
                    ],
                })],
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
            bind_group_layout,
            pipeline,
            sampler,
            resources: HashMap::new(),
        }
    }

    pub(crate) fn register_rgba(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        resource_id: String,
        width: u32,
        height: u32,
        rgba: &[u8],
    ) -> PyResult<()> {
        validate_image_resource(&resource_id, width, height, rgba)?;
        let texture = device.create_texture_with_data(
            queue,
            &wgpu::TextureDescriptor {
                label: Some("SwirUI image texture"),
                size: wgpu::Extent3d {
                    width,
                    height,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Rgba8UnormSrgb,
                usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                view_formats: &[],
            },
            wgpu::util::TextureDataOrder::LayerMajor,
            rgba,
        );
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("SwirUI image bind group"),
            layout: &self.bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&self.sampler),
                },
            ],
        });
        self.resources.insert(
            resource_id,
            ImageResource {
                _texture: texture,
                _view: view,
                bind_group,
                width,
                height,
            },
        );
        Ok(())
    }

    pub(crate) fn unregister(&mut self, resource_id: &str) -> bool {
        self.resources.remove(resource_id).is_some()
    }

    pub(crate) fn resource_count(&self) -> usize {
        self.resources.len()
    }

    pub(crate) fn resource_size(&self, resource_id: &str) -> Option<(u32, u32)> {
        self.resources
            .get(resource_id)
            .map(|resource| (resource.width, resource.height))
    }

    pub(crate) fn prepare_vertices(
        &self,
        device: &wgpu::Device,
        images: &[ImageInstance],
        surface_width: u32,
        surface_height: u32,
    ) -> PyResult<Option<wgpu::Buffer>> {
        validate_image_instances(images)?;
        if images.is_empty() {
            return Ok(None);
        }
        if surface_width == 0 || surface_height == 0 {
            return Err(PyValueError::new_err(
                "Image rendering requires a non-zero surface size.",
            ));
        }

        let mut values = Vec::with_capacity(images.len() * 6 * 5);
        for (resource_id, x, y, width, height, opacity, clip) in images {
            if !self.resources.contains_key(resource_id) {
                return Err(PyKeyError::new_err(format!(
                    "Image resource '{resource_id}' is not registered in this GPU context."
                )));
            }
            let visible_left = x.max(clip.0);
            let visible_top = y.max(clip.1);
            let visible_right = (*x + *width).min(clip.2);
            let visible_bottom = (*y + *height).min(clip.3);
            if visible_right <= visible_left || visible_bottom <= visible_top {
                return Err(PyValueError::new_err(
                    "Image clip must intersect the image bounds before GPU submission.",
                ));
            }

            let u0 = (visible_left - *x) / *width;
            let v0 = (visible_top - *y) / *height;
            let u1 = (visible_right - *x) / *width;
            let v1 = (visible_bottom - *y) / *height;
            let left = (visible_left / surface_width as f32) * 2.0 - 1.0;
            let right = (visible_right / surface_width as f32) * 2.0 - 1.0;
            let top = 1.0 - (visible_top / surface_height as f32) * 2.0;
            let bottom = 1.0 - (visible_bottom / surface_height as f32) * 2.0;
            push_vertex(&mut values, left, top, u0, v0, *opacity);
            push_vertex(&mut values, right, top, u1, v0, *opacity);
            push_vertex(&mut values, right, bottom, u1, v1, *opacity);
            push_vertex(&mut values, left, top, u0, v0, *opacity);
            push_vertex(&mut values, right, bottom, u1, v1, *opacity);
            push_vertex(&mut values, left, bottom, u0, v1, *opacity);
        }

        let bytes = floats_to_bytes(&values);
        Ok(Some(device.create_buffer_init(
            &wgpu::util::BufferInitDescriptor {
                label: Some("SwirUI image vertices"),
                contents: &bytes,
                usage: wgpu::BufferUsages::VERTEX,
            },
        )))
    }

    pub(crate) fn render(
        &self,
        pass: &mut wgpu::RenderPass<'_>,
        vertex_buffer: &wgpu::Buffer,
        images: &[ImageInstance],
    ) -> PyResult<()> {
        pass.set_pipeline(&self.pipeline);
        pass.set_vertex_buffer(0, vertex_buffer.slice(..));
        for (index, image) in images.iter().enumerate() {
            let resource = self.resources.get(&image.0).ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Image resource '{}' disappeared before rendering.",
                    image.0
                ))
            })?;
            pass.set_bind_group(0, &resource.bind_group, &[]);
            let start = u32::try_from(index * 6)
                .map_err(|_| PyValueError::new_err("Too many images in one GPU frame."))?;
            pass.draw(start..start + 6, 0..1);
        }
        Ok(())
    }
}

pub(crate) fn validate_image_resource(
    resource_id: &str,
    width: u32,
    height: u32,
    rgba: &[u8],
) -> PyResult<()> {
    if resource_id.trim().is_empty() {
        return Err(PyValueError::new_err("Image resource_id cannot be empty."));
    }
    if width == 0 || height == 0 {
        return Err(PyValueError::new_err(
            "Image resource dimensions must be greater than zero.",
        ));
    }
    let expected = (width as usize)
        .checked_mul(height as usize)
        .and_then(|pixels| pixels.checked_mul(4))
        .ok_or_else(|| PyValueError::new_err("Image resource dimensions are too large."))?;
    if rgba.len() != expected {
        return Err(PyValueError::new_err(format!(
            "RGBA image resource requires exactly {expected} bytes for {width}x{height}; received {}.",
            rgba.len()
        )));
    }
    Ok(())
}

pub(crate) fn validate_image_instances(images: &[ImageInstance]) -> PyResult<()> {
    for (resource_id, x, y, width, height, opacity, clip) in images {
        if resource_id.trim().is_empty() {
            return Err(PyValueError::new_err("Image instance resource_id cannot be empty."));
        }
        if ![
            *x, *y, *width, *height, *opacity, clip.0, clip.1, clip.2, clip.3,
        ]
        .into_iter()
        .all(f32::is_finite)
        {
            return Err(PyValueError::new_err(
                "Image geometry, opacity and clip bounds must be finite.",
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
        if clip.2 <= clip.0 || clip.3 <= clip.1 {
            return Err(PyValueError::new_err(
                "Image clip bounds must have positive width and height.",
            ));
        }
        if (*x + *width).min(clip.2) <= x.max(clip.0)
            || (*y + *height).min(clip.3) <= y.max(clip.1)
        {
            return Err(PyValueError::new_err(
                "Image clip must intersect the image bounds.",
            ));
        }
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn push_vertex(values: &mut Vec<f32>, x: f32, y: f32, u: f32, v: f32, opacity: f32) {
    values.extend_from_slice(&[x, y, u, v, opacity]);
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
    fn validates_rgba_resource_length() {
        assert!(validate_image_resource("checker", 2, 2, &[255; 16]).is_ok());
        assert!(validate_image_resource("checker", 2, 2, &[255; 15]).is_err());
        assert!(validate_image_resource("", 2, 2, &[255; 16]).is_err());
        assert!(validate_image_resource("checker", 0, 2, &[]).is_err());
    }

    #[test]
    fn validates_image_instances() {
        let valid = (
            "checker".to_owned(),
            10.0,
            20.0,
            100.0,
            80.0,
            0.75,
            (0.0, 0.0, 200.0, 200.0),
        );
        assert!(validate_image_instances(&[valid]).is_ok());

        let invalid_opacity = (
            "checker".to_owned(),
            10.0,
            20.0,
            100.0,
            80.0,
            1.5,
            (0.0, 0.0, 200.0, 200.0),
        );
        assert!(validate_image_instances(&[invalid_opacity]).is_err());

        let invalid_size = (
            "checker".to_owned(),
            10.0,
            20.0,
            0.0,
            80.0,
            1.0,
            (0.0, 0.0, 200.0, 200.0),
        );
        assert!(validate_image_instances(&[invalid_size]).is_err());

        let disjoint_clip = (
            "checker".to_owned(),
            10.0,
            20.0,
            100.0,
            80.0,
            1.0,
            (300.0, 300.0, 400.0, 400.0),
        );
        assert!(validate_image_instances(&[disjoint_clip]).is_err());
    }
}
