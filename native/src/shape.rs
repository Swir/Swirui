use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

pub(crate) type ShapeVertex = Vec<f32>;

const SHAPE_VERTEX_FLOATS: usize = 10;
const INITIAL_SHAPE_VERTEX_CAPACITY: usize = 96;

#[cfg(not(target_os = "windows"))]
pub(crate) struct ShapeSystem;

#[cfg(target_os = "windows")]
pub(crate) struct ShapeSystem {
    pipeline: wgpu::RenderPipeline,
    bind_group: wgpu::BindGroup,
    vertex_buffer: wgpu::Buffer,
    vertex_capacity: usize,
}

#[cfg(target_os = "windows")]
impl ShapeSystem {
    pub(crate) fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        frame_buffer: &wgpu::Buffer,
    ) -> Self {
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("SwirUI shape bind group layout"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("SwirUI shape bind group"),
            layout: &bind_group_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: frame_buffer.as_entire_binding(),
            }],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("SwirUI shape pipeline layout"),
            bind_group_layouts: &[Some(&bind_group_layout)],
            immediate_size: 0,
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("SwirUI filled path shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("shapes.wgsl").into()),
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("SwirUI persistent filled path pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[Some(wgpu::VertexBufferLayout {
                    array_stride: (SHAPE_VERTEX_FLOATS * std::mem::size_of::<f32>()) as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 0,
                            shader_location: 0,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x4,
                            offset: 2 * 4,
                            shader_location: 1,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x4,
                            offset: 6 * 4,
                            shader_location: 2,
                        },
                    ],
                })],
            },
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                ..Default::default()
            },
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
        let vertex_capacity = INITIAL_SHAPE_VERTEX_CAPACITY;
        let vertex_buffer = create_vertex_buffer(device, vertex_capacity);
        Self {
            pipeline,
            bind_group,
            vertex_buffer,
            vertex_capacity,
        }
    }

    pub(crate) fn vertex_capacity(&self) -> usize {
        self.vertex_capacity
    }

    pub(crate) fn prepare_vertices(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        vertices: &[ShapeVertex],
    ) -> PyResult<bool> {
        validate_shape_vertices(vertices)?;
        if vertices.is_empty() {
            return Ok(false);
        }
        self.ensure_vertex_capacity(device, vertices.len())?;
        let mut values = Vec::with_capacity(vertices.len() * SHAPE_VERTEX_FLOATS);
        for vertex in vertices {
            values.extend_from_slice(vertex);
        }
        queue.write_buffer(&self.vertex_buffer, 0, &floats_to_bytes(&values));
        Ok(true)
    }

    pub(crate) fn render(&self, pass: &mut wgpu::RenderPass<'_>, vertex_count: usize) -> PyResult<()> {
        let count = u32::try_from(vertex_count)
            .map_err(|_| PyValueError::new_err("Too many path vertices in one GPU frame."))?;
        pass.set_pipeline(&self.pipeline);
        pass.set_bind_group(0, &self.bind_group, &[]);
        pass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
        pass.draw(0..count, 0..1);
        Ok(())
    }

    fn ensure_vertex_capacity(&mut self, device: &wgpu::Device, required: usize) -> PyResult<()> {
        let capacity = next_shape_vertex_capacity(self.vertex_capacity, required)?;
        if capacity == self.vertex_capacity {
            return Ok(());
        }
        self.vertex_buffer = create_vertex_buffer(device, capacity);
        self.vertex_capacity = capacity;
        Ok(())
    }
}

pub(crate) fn validate_shape_vertices(vertices: &[ShapeVertex]) -> PyResult<()> {
    if vertices.is_empty() {
        return Ok(());
    }
    if !vertices.len().is_multiple_of(3) {
        return Err(PyValueError::new_err(
            "Filled path submission requires a multiple of three triangle vertices.",
        ));
    }
    for vertex in vertices {
        if vertex.len() != SHAPE_VERTEX_FLOATS {
            return Err(PyValueError::new_err(format!(
                "Shape vertices require exactly {SHAPE_VERTEX_FLOATS} floats."
            )));
        }
        if !vertex.iter().copied().all(f32::is_finite) {
            return Err(PyValueError::new_err(
                "Shape position, color and clip bounds must be finite.",
            ));
        }
        if vertex[2..6]
            .iter()
            .any(|channel| !(0.0..=1.0).contains(channel))
        {
            return Err(PyValueError::new_err(
                "Shape color channels must be between 0.0 and 1.0.",
            ));
        }
        if vertex[8] <= vertex[6] || vertex[9] <= vertex[7] {
            return Err(PyValueError::new_err(
                "Shape clip bounds must have positive width and height.",
            ));
        }
    }
    Ok(())
}

fn next_shape_vertex_capacity(current: usize, required: usize) -> PyResult<usize> {
    if required <= current {
        return Ok(current);
    }
    required
        .checked_next_power_of_two()
        .ok_or_else(|| PyValueError::new_err("Path batch is too large for GPU buffering."))
}

#[cfg(target_os = "windows")]
fn create_vertex_buffer(device: &wgpu::Device, capacity: usize) -> wgpu::Buffer {
    let size = capacity
        .saturating_mul(SHAPE_VERTEX_FLOATS)
        .saturating_mul(std::mem::size_of::<f32>())
        .max(std::mem::size_of::<f32>()) as u64;
    device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("SwirUI reusable filled path vertices"),
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

    fn vertex(x: f32, y: f32) -> ShapeVertex {
        vec![x, y, 0.1, 0.5, 1.0, 0.8, 0.0, 0.0, 640.0, 480.0]
    }

    #[test]
    fn validates_triangle_vertices() {
        assert!(validate_shape_vertices(&[vertex(0.0, 0.0), vertex(20.0, 0.0), vertex(10.0, 20.0)]).is_ok());
        assert!(validate_shape_vertices(&[]).is_ok());
        assert!(validate_shape_vertices(&[vertex(0.0, 0.0)]).is_err());

        let mut invalid_color = vertex(0.0, 0.0);
        invalid_color[4] = 1.2;
        assert!(validate_shape_vertices(&[invalid_color, vertex(20.0, 0.0), vertex(10.0, 20.0)]).is_err());

        let mut invalid_clip = vertex(0.0, 0.0);
        invalid_clip[8] = invalid_clip[6];
        assert!(validate_shape_vertices(&[invalid_clip, vertex(20.0, 0.0), vertex(10.0, 20.0)]).is_err());
    }

    #[test]
    fn shape_vertex_capacity_grows_geometrically_and_never_shrinks() {
        assert_eq!(next_shape_vertex_capacity(INITIAL_SHAPE_VERTEX_CAPACITY, 1).unwrap(), 96);
        assert_eq!(next_shape_vertex_capacity(INITIAL_SHAPE_VERTEX_CAPACITY, 96).unwrap(), 96);
        assert_eq!(next_shape_vertex_capacity(INITIAL_SHAPE_VERTEX_CAPACITY, 97).unwrap(), 128);
        assert_eq!(next_shape_vertex_capacity(128, 129).unwrap(), 256);
        assert_eq!(next_shape_vertex_capacity(256, 12).unwrap(), 256);
    }
}
