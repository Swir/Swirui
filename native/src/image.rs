use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[cfg(target_os = "windows")]
use pyo3::exceptions::PyKeyError;
#[cfg(target_os = "windows")]
use std::collections::HashMap;
#[cfg(target_os = "windows")]
use wgpu::util::DeviceExt;

pub(crate) type ClipRect = (f32, f32, f32, f32);
pub(crate) type AffineTransform = (f32, f32, f32, f32, f32, f32);
type ImageVertex = (f32, f32, f32, f32);
type AxisAlignedImageData = (String, f32, f32, f32, f32, f32, ClipRect);
type AffineImageData = (
    String,
    f32,
    f32,
    f32,
    f32,
    f32,
    ClipRect,
    AffineTransform,
);
type TriangleImageData = (
    String,
    ImageVertex,
    ImageVertex,
    ImageVertex,
    f32,
    ClipRect,
);

#[derive(Clone, Debug, FromPyObject)]
pub(crate) enum ImageInstance {
    AxisAligned(AxisAlignedImageData),
    Affine(AffineImageData),
    Triangle(TriangleImageData),
}

impl ImageInstance {
    fn resource_id(&self) -> &str {
        match self {
            Self::AxisAligned((resource_id, ..))
            | Self::Affine((resource_id, ..))
            | Self::Triangle((resource_id, ..)) => resource_id,
        }
    }
}

const IMAGE_VERTEX_FLOATS: usize = 11;
const IMAGE_VERTICES_PER_INSTANCE: usize = 6;
const INITIAL_IMAGE_CAPACITY: usize = 8;

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
    vertex_buffer: wgpu::Buffer,
    vertex_capacity: usize,
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
                    array_stride: (IMAGE_VERTEX_FLOATS * std::mem::size_of::<f32>()) as u64,
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
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 5 * 4,
                            shader_location: 3,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x4,
                            offset: 7 * 4,
                            shader_location: 4,
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
        let vertex_capacity = INITIAL_IMAGE_CAPACITY;
        let vertex_buffer = create_vertex_buffer(device, vertex_capacity);

        Self {
            bind_group_layout,
            pipeline,
            sampler,
            resources: HashMap::new(),
            vertex_buffer,
            vertex_capacity,
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

    pub(crate) fn vertex_capacity(&self) -> usize {
        self.vertex_capacity
    }

    pub(crate) fn prepare_vertices(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        images: &[ImageInstance],
        surface_width: u32,
        surface_height: u32,
    ) -> PyResult<bool> {
        validate_image_instances(images)?;
        if images.is_empty() {
            return Ok(false);
        }
        if surface_width == 0 || surface_height == 0 {
            return Err(PyValueError::new_err(
                "Image rendering requires a non-zero surface size.",
            ));
        }

        self.ensure_vertex_capacity(device, images.len())?;
        let mut values = Vec::with_capacity(
            images.len() * IMAGE_VERTICES_PER_INSTANCE * IMAGE_VERTEX_FLOATS,
        );
        for image in images {
            if !self.resources.contains_key(image.resource_id()) {
                return Err(PyKeyError::new_err(format!(
                    "Image resource '{}' is not registered in this GPU context.",
                    image.resource_id()
                )));
            }
            match image {
                ImageInstance::AxisAligned((_, x, y, width, height, opacity, clip)) => {
                    append_axis_aligned_vertices(
                        &mut values,
                        (*x, *y, *width, *height),
                        *opacity,
                        *clip,
                        surface_width,
                        surface_height,
                    )?;
                }
                ImageInstance::Affine((_, x, y, width, height, opacity, clip, transform)) => {
                    append_affine_vertices(
                        &mut values,
                        (*x, *y, *width, *height),
                        *opacity,
                        *clip,
                        *transform,
                        surface_width,
                        surface_height,
                    );
                }
                ImageInstance::Triangle((_, first, second, third, opacity, clip)) => {
                    append_triangle_vertices(
                        &mut values,
                        (*first, *second, *third),
                        *opacity,
                        *clip,
                        surface_width,
                        surface_height,
                    );
                }
            }
        }

        let bytes = floats_to_bytes(&values);
        queue.write_buffer(&self.vertex_buffer, 0, &bytes);
        Ok(true)
    }

    pub(crate) fn render(
        &self,
        pass: &mut wgpu::RenderPass<'_>,
        images: &[ImageInstance],
    ) -> PyResult<()> {
        pass.set_pipeline(&self.pipeline);
        pass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
        for (index, image) in images.iter().enumerate() {
            let resource = self.resources.get(image.resource_id()).ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Image resource '{}' disappeared before rendering.",
                    image.resource_id()
                ))
            })?;
            pass.set_bind_group(0, &resource.bind_group, &[]);
            let start = u32::try_from(index * IMAGE_VERTICES_PER_INSTANCE)
                .map_err(|_| PyValueError::new_err("Too many images in one GPU frame."))?;
            pass.draw(start..start + IMAGE_VERTICES_PER_INSTANCE as u32, 0..1);
        }
        Ok(())
    }

    fn ensure_vertex_capacity(&mut self, device: &wgpu::Device, required: usize) -> PyResult<()> {
        let capacity = next_image_capacity(self.vertex_capacity, required)?;
        if capacity == self.vertex_capacity {
            return Ok(());
        }
        self.vertex_buffer = create_vertex_buffer(device, capacity);
        self.vertex_capacity = capacity;
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
    for image in images {
        match image {
            ImageInstance::AxisAligned((resource_id, x, y, width, height, opacity, clip)) => {
                validate_common_image_instance(
                    resource_id,
                    (*x, *y, *width, *height),
                    *opacity,
                    *clip,
                )?;
                if (*x + *width).min(clip.2) <= x.max(clip.0)
                    || (*y + *height).min(clip.3) <= y.max(clip.1)
                {
                    return Err(PyValueError::new_err(
                        "Image clip must intersect the image bounds.",
                    ));
                }
            }
            ImageInstance::Affine((resource_id, x, y, width, height, opacity, clip, transform)) => {
                validate_common_image_instance(
                    resource_id,
                    (*x, *y, *width, *height),
                    *opacity,
                    *clip,
                )?;
                if ![
                    transform.0,
                    transform.1,
                    transform.2,
                    transform.3,
                    transform.4,
                    transform.5,
                ]
                .into_iter()
                .all(f32::is_finite)
                {
                    return Err(PyValueError::new_err(
                        "Affine image transform values must be finite.",
                    ));
                }
                let bounds = transformed_bounds((*x, *y, *width, *height), *transform);
                if bounds.2 <= clip.0
                    || bounds.0 >= clip.2
                    || bounds.3 <= clip.1
                    || bounds.1 >= clip.3
                {
                    return Err(PyValueError::new_err(
                        "Image clip must intersect the transformed image bounds.",
                    ));
                }
            }
            ImageInstance::Triangle((resource_id, first, second, third, opacity, clip)) => {
                validate_triangle_image_instance(
                    resource_id,
                    (*first, *second, *third),
                    *opacity,
                    *clip,
                )?;
            }
        }
    }
    Ok(())
}

fn validate_image_identity_and_clip(
    resource_id: &str,
    opacity: f32,
    clip: ClipRect,
) -> PyResult<()> {
    if resource_id.trim().is_empty() {
        return Err(PyValueError::new_err(
            "Image instance resource_id cannot be empty.",
        ));
    }
    if ![opacity, clip.0, clip.1, clip.2, clip.3]
        .into_iter()
        .all(f32::is_finite)
    {
        return Err(PyValueError::new_err(
            "Image opacity and clip bounds must be finite.",
        ));
    }
    if !(0.0..=1.0).contains(&opacity) {
        return Err(PyValueError::new_err(
            "Image opacity must be between 0.0 and 1.0.",
        ));
    }
    if clip.2 <= clip.0 || clip.3 <= clip.1 {
        return Err(PyValueError::new_err(
            "Image clip bounds must have positive width and height.",
        ));
    }
    Ok(())
}

fn validate_common_image_instance(
    resource_id: &str,
    geometry: (f32, f32, f32, f32),
    opacity: f32,
    clip: ClipRect,
) -> PyResult<()> {
    validate_image_identity_and_clip(resource_id, opacity, clip)?;
    if ![geometry.0, geometry.1, geometry.2, geometry.3]
        .into_iter()
        .all(f32::is_finite)
    {
        return Err(PyValueError::new_err("Image geometry must be finite."));
    }
    if geometry.2 <= 0.0 || geometry.3 <= 0.0 {
        return Err(PyValueError::new_err(
            "Image width and height must be greater than zero.",
        ));
    }
    Ok(())
}

fn validate_triangle_image_instance(
    resource_id: &str,
    triangle: (ImageVertex, ImageVertex, ImageVertex),
    opacity: f32,
    clip: ClipRect,
) -> PyResult<()> {
    validate_image_identity_and_clip(resource_id, opacity, clip)?;
    let vertices = [triangle.0, triangle.1, triangle.2];
    if !vertices
        .iter()
        .flat_map(|vertex| [vertex.0, vertex.1, vertex.2, vertex.3])
        .all(f32::is_finite)
    {
        return Err(PyValueError::new_err(
            "Clipped image triangle positions and UVs must be finite.",
        ));
    }
    if vertices
        .iter()
        .any(|vertex| !(0.0..=1.0).contains(&vertex.2) || !(0.0..=1.0).contains(&vertex.3))
    {
        return Err(PyValueError::new_err(
            "Clipped image triangle UVs must be between 0.0 and 1.0.",
        ));
    }

    let twice_area = (triangle.1.0 - triangle.0.0) * (triangle.2.1 - triangle.0.1)
        - (triangle.1.1 - triangle.0.1) * (triangle.2.0 - triangle.0.0);
    if twice_area.abs() <= f32::EPSILON {
        return Err(PyValueError::new_err(
            "Clipped image triangle must have non-zero area.",
        ));
    }

    let left = triangle.0.0.min(triangle.1.0).min(triangle.2.0);
    let top = triangle.0.1.min(triangle.1.1).min(triangle.2.1);
    let right = triangle.0.0.max(triangle.1.0).max(triangle.2.0);
    let bottom = triangle.0.1.max(triangle.1.1).max(triangle.2.1);
    if right <= clip.0 || left >= clip.2 || bottom <= clip.1 || top >= clip.3 {
        return Err(PyValueError::new_err(
            "Image clip must intersect the clipped image triangle.",
        ));
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn append_axis_aligned_vertices(
    values: &mut Vec<f32>,
    geometry: (f32, f32, f32, f32),
    opacity: f32,
    clip: ClipRect,
    surface_width: u32,
    surface_height: u32,
) -> PyResult<()> {
    let (x, y, width, height) = geometry;
    let visible_left = x.max(clip.0);
    let visible_top = y.max(clip.1);
    let visible_right = (x + width).min(clip.2);
    let visible_bottom = (y + height).min(clip.3);
    if visible_right <= visible_left || visible_bottom <= visible_top {
        return Err(PyValueError::new_err(
            "Image clip must intersect the image bounds before GPU submission.",
        ));
    }

    let u0 = (visible_left - x) / width;
    let v0 = (visible_top - y) / height;
    let u1 = (visible_right - x) / width;
    let v1 = (visible_bottom - y) / height;
    let top_left = (visible_left, visible_top);
    let top_right = (visible_right, visible_top);
    let bottom_right = (visible_right, visible_bottom);
    let bottom_left = (visible_left, visible_bottom);
    push_screen_vertex(
        values,
        top_left,
        (u0, v0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        top_right,
        (u1, v0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        bottom_right,
        (u1, v1),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        top_left,
        (u0, v0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        bottom_right,
        (u1, v1),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        bottom_left,
        (u0, v1),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    Ok(())
}

#[cfg(target_os = "windows")]
fn append_affine_vertices(
    values: &mut Vec<f32>,
    geometry: (f32, f32, f32, f32),
    opacity: f32,
    clip: ClipRect,
    transform: AffineTransform,
    surface_width: u32,
    surface_height: u32,
) {
    let (x, y, width, height) = geometry;
    let top_left = transform_point(transform, x, y);
    let top_right = transform_point(transform, x + width, y);
    let bottom_right = transform_point(transform, x + width, y + height);
    let bottom_left = transform_point(transform, x, y + height);
    push_screen_vertex(
        values,
        top_left,
        (0.0, 0.0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        top_right,
        (1.0, 0.0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        bottom_right,
        (1.0, 1.0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        top_left,
        (0.0, 0.0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        bottom_right,
        (1.0, 1.0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        bottom_left,
        (0.0, 1.0),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
}

#[cfg(target_os = "windows")]
fn append_triangle_vertices(
    values: &mut Vec<f32>,
    triangle: (ImageVertex, ImageVertex, ImageVertex),
    opacity: f32,
    clip: ClipRect,
    surface_width: u32,
    surface_height: u32,
) {
    let first = triangle.0;
    let second = triangle.1;
    let third = triangle.2;
    push_screen_vertex(
        values,
        (first.0, first.1),
        (first.2, first.3),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        (second.0, second.1),
        (second.2, second.3),
        opacity,
        clip,
        surface_width,
        surface_height,
    );
    push_screen_vertex(
        values,
        (third.0, third.1),
        (third.2, third.3),
        opacity,
        clip,
        surface_width,
        surface_height,
    );

    // Each ImageInstance retains the fixed six-vertex batching contract. The second
    // triangle is intentionally degenerate, so exact clipped triangles neither
    // overdraw nor require variable per-instance draw ranges.
    for _ in 0..3 {
        push_screen_vertex(
            values,
            (first.0, first.1),
            (first.2, first.3),
            opacity,
            clip,
            surface_width,
            surface_height,
        );
    }
}

#[cfg(target_os = "windows")]
fn push_screen_vertex(
    values: &mut Vec<f32>,
    pixel_position: (f32, f32),
    uv: (f32, f32),
    opacity: f32,
    clip: ClipRect,
    surface_width: u32,
    surface_height: u32,
) {
    let ndc_x = (pixel_position.0 / surface_width as f32) * 2.0 - 1.0;
    let ndc_y = 1.0 - (pixel_position.1 / surface_height as f32) * 2.0;
    values.extend_from_slice(&[
        ndc_x,
        ndc_y,
        uv.0,
        uv.1,
        opacity,
        pixel_position.0,
        pixel_position.1,
        clip.0,
        clip.1,
        clip.2,
        clip.3,
    ]);
}

fn transform_point(transform: AffineTransform, x: f32, y: f32) -> (f32, f32) {
    (
        transform.0 * x + transform.1 * y + transform.4,
        transform.2 * x + transform.3 * y + transform.5,
    )
}

fn transformed_bounds(
    geometry: (f32, f32, f32, f32),
    transform: AffineTransform,
) -> (f32, f32, f32, f32) {
    let (x, y, width, height) = geometry;
    let points = [
        transform_point(transform, x, y),
        transform_point(transform, x + width, y),
        transform_point(transform, x + width, y + height),
        transform_point(transform, x, y + height),
    ];
    let mut left = f32::INFINITY;
    let mut top = f32::INFINITY;
    let mut right = f32::NEG_INFINITY;
    let mut bottom = f32::NEG_INFINITY;
    for (point_x, point_y) in points {
        left = left.min(point_x);
        top = top.min(point_y);
        right = right.max(point_x);
        bottom = bottom.max(point_y);
    }
    (left, top, right, bottom)
}

fn next_image_capacity(current: usize, required: usize) -> PyResult<usize> {
    if required <= current {
        return Ok(current);
    }
    required
        .checked_next_power_of_two()
        .ok_or_else(|| PyValueError::new_err("Image batch is too large for GPU buffering."))
}

#[cfg(target_os = "windows")]
fn create_vertex_buffer(device: &wgpu::Device, capacity: usize) -> wgpu::Buffer {
    let floats = capacity
        .saturating_mul(IMAGE_VERTICES_PER_INSTANCE)
        .saturating_mul(IMAGE_VERTEX_FLOATS);
    let size = floats
        .saturating_mul(std::mem::size_of::<f32>())
        .max(std::mem::size_of::<f32>()) as u64;
    device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("SwirUI reusable image vertices"),
        size,
        usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    })
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

    fn axis_aligned_instance(opacity: f32, width: f32, clip: ClipRect) -> ImageInstance {
        ImageInstance::AxisAligned((
            "checker".to_owned(),
            10.0,
            20.0,
            width,
            80.0,
            opacity,
            clip,
        ))
    }

    fn triangle_instance(clip: ClipRect) -> ImageInstance {
        ImageInstance::Triangle((
            "checker".to_owned(),
            (20.0, 25.0, 0.0, 0.0),
            (90.0, 40.0, 1.0, 0.15),
            (35.0, 110.0, 0.2, 1.0),
            0.8,
            clip,
        ))
    }

    #[test]
    fn validates_rgba_resource_length() {
        assert!(validate_image_resource("checker", 2, 2, &[255; 16]).is_ok());
        assert!(validate_image_resource("checker", 2, 2, &[255; 15]).is_err());
        assert!(validate_image_resource("", 2, 2, &[255; 16]).is_err());
        assert!(validate_image_resource("checker", 0, 2, &[]).is_err());
    }

    #[test]
    fn validates_axis_aligned_image_instances() {
        assert!(validate_image_instances(&[axis_aligned_instance(
            0.75,
            100.0,
            (0.0, 0.0, 200.0, 200.0),
        )])
        .is_ok());
        assert!(validate_image_instances(&[axis_aligned_instance(
            1.5,
            100.0,
            (0.0, 0.0, 200.0, 200.0),
        )])
        .is_err());
        assert!(validate_image_instances(&[axis_aligned_instance(
            1.0,
            0.0,
            (0.0, 0.0, 200.0, 200.0),
        )])
        .is_err());
        assert!(validate_image_instances(&[axis_aligned_instance(
            1.0,
            100.0,
            (300.0, 300.0, 400.0, 400.0),
        )])
        .is_err());
    }

    #[test]
    fn validates_affine_image_instances_and_transformed_clip_intersection() {
        let valid = ImageInstance::Affine((
            "checker".to_owned(),
            10.0,
            20.0,
            100.0,
            80.0,
            0.75,
            (0.0, 0.0, 220.0, 220.0),
            (0.0, -1.0, 1.0, 0.0, 160.0, 10.0),
        ));
        assert!(validate_image_instances(&[valid]).is_ok());

        let invalid_transform = ImageInstance::Affine((
            "checker".to_owned(),
            10.0,
            20.0,
            100.0,
            80.0,
            1.0,
            (0.0, 0.0, 220.0, 220.0),
            (f32::NAN, 0.0, 0.0, 1.0, 0.0, 0.0),
        ));
        assert!(validate_image_instances(&[invalid_transform]).is_err());

        let disjoint = ImageInstance::Affine((
            "checker".to_owned(),
            10.0,
            20.0,
            100.0,
            80.0,
            1.0,
            (300.0, 300.0, 400.0, 400.0),
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        ));
        assert!(validate_image_instances(&[disjoint]).is_err());
    }

    #[test]
    fn validates_exact_clipped_image_triangles() {
        assert!(
            validate_image_instances(&[triangle_instance((0.0, 0.0, 200.0, 200.0))]).is_ok()
        );

        let invalid_uv = ImageInstance::Triangle((
            "checker".to_owned(),
            (20.0, 25.0, -0.1, 0.0),
            (90.0, 40.0, 1.0, 0.15),
            (35.0, 110.0, 0.2, 1.0),
            0.8,
            (0.0, 0.0, 200.0, 200.0),
        ));
        assert!(validate_image_instances(&[invalid_uv]).is_err());

        let degenerate = ImageInstance::Triangle((
            "checker".to_owned(),
            (20.0, 20.0, 0.0, 0.0),
            (40.0, 40.0, 0.5, 0.5),
            (60.0, 60.0, 1.0, 1.0),
            1.0,
            (0.0, 0.0, 200.0, 200.0),
        ));
        assert!(validate_image_instances(&[degenerate]).is_err());

        assert!(
            validate_image_instances(&[triangle_instance((300.0, 300.0, 400.0, 400.0))])
                .is_err()
        );
    }

    #[test]
    fn affine_bounds_follow_the_shape_pipeline_matrix_convention() {
        let bounds = transformed_bounds(
            (10.0, 20.0, 40.0, 30.0),
            (0.0, -1.0, 1.0, 0.0, 100.0, 5.0),
        );
        assert_eq!(bounds, (50.0, 15.0, 80.0, 55.0));
    }

    #[test]
    fn image_buffer_capacity_grows_geometrically_and_never_shrinks() {
        assert_eq!(next_image_capacity(INITIAL_IMAGE_CAPACITY, 1).unwrap(), 8);
        assert_eq!(next_image_capacity(INITIAL_IMAGE_CAPACITY, 8).unwrap(), 8);
        assert_eq!(next_image_capacity(INITIAL_IMAGE_CAPACITY, 9).unwrap(), 16);
        assert_eq!(next_image_capacity(16, 17).unwrap(), 32);
        assert_eq!(next_image_capacity(32, 2).unwrap(), 32);
    }
}
