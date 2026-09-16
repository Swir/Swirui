use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[cfg(target_os = "windows")]
use wgpu::util::DeviceExt;

pub(crate) type PathTriangleInstance = Vec<f32>;

const PATH_TRIANGLE_INSTANCE_FLOATS: usize = 14;
const PATH_VERTEX_FLOATS: usize = 10;
const INITIAL_PATH_TRIANGLE_CAPACITY: usize = 32;

pub(crate) fn validate_path_triangles(paths: &[PathTriangleInstance]) -> PyResult<()> {
    for triangle in paths {
        if triangle.len() != PATH_TRIANGLE_INSTANCE_FLOATS {
            return Err(PyValueError::new_err(format!(
                "Path triangle instances require exactly {PATH_TRIANGLE_INSTANCE_FLOATS} floats."
            )));
        }
        if !triangle.iter().copied().all(f32::is_finite) {
            return Err(PyValueError::new_err(
                "Path triangle geometry, color and clip bounds must be finite.",
            ));
        }
        if triangle[6..10]
            .iter()
            .any(|channel| !(0.0..=1.0).contains(channel))
        {
            return Err(PyValueError::new_err(
                "Path triangle color channels must be between 0.0 and 1.0.",
            ));
        }
        if triangle[12] <= triangle[10] || triangle[13] <= triangle[11] {
            return Err(PyValueError::new_err(
                "Path triangle clip bounds must have positive width and height.",
            ));
        }
        let twice_area = (triangle[2] - triangle[0]) * (triangle[5] - triangle[1])
            - (triangle[3] - triangle[1]) * (triangle[4] - triangle[0]);
        if twice_area.abs() <= f32::EPSILON {
            return Err(PyValueError::new_err(
                "Path triangles must enclose a non-zero area.",
            ));
        }
    }
    Ok(())
}

fn next_path_triangle_capacity(current: usize, required: usize) -> PyResult<usize> {
    if required <= current {
        return Ok(current);
    }
    required
        .checked_next_power_of_two()
        .ok_or_else(|| PyValueError::new_err("Path triangle batch is too large for GPU buffering."))
}

#[cfg(target_os = "windows")]
pub(crate) struct PathSystem {
    pipeline: wgpu::RenderPipeline,
    vertex_buffer: wgpu::Buffer,
    triangle_capacity: usize,
}

#[cfg(target_os = "windows")]
impl PathSystem {
    pub(crate) fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("SwirUI path shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("paths.wgsl").into()),
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("SwirUI path pipeline layout"),
            bind_group_layouts: &[],
            immediate_size: 0,
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("SwirUI filled path pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: (PATH_VERTEX_FLOATS * std::mem::size_of::<f32>()) as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x2,
                            offset: 0,
                            shader_location: 0,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x4,
                            offset: (2 * std::mem::size_of::<f32>()) as u64,
                            shader_location: 1,
                        },
                        wgpu::VertexAttribute {
                            format: wgpu::VertexFormat::Float32x4,
                            offset: (6 * std::mem::size_of::<f32>()) as u64,
                            shader_location: 2,
                        },
                    ],
                }],
            },
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                front_face: wgpu::FrontFace::Ccw,
                cull_mode: None,
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
        let triangle_capacity = INITIAL_PATH_TRIANGLE_CAPACITY;
        let vertex_buffer = create_path_vertex_buffer(device, triangle_capacity);
        Self {
            pipeline,
            vertex_buffer,
            triangle_capacity,
        }
    }

    pub(crate) fn triangle_capacity(&self) -> usize {
        self.triangle_capacity
    }

    pub(crate) fn prepare_vertices(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        paths: &[PathTriangleInstance],
        surface_width: u32,
        surface_height: u32,
    ) -> PyResult<bool> {
        if paths.is_empty() {
            return Ok(false);
        }
        validate_path_triangles(paths)?;
        self.ensure_capacity(device, paths.len())?;

        let width = surface_width as f32;
        let height = surface_height as f32;
        let mut values = Vec::with_capacity(paths.len() * 3 * PATH_VERTEX_FLOATS);
        for triangle in paths {
            let color = &triangle[6..10];
            let clip = &triangle[10..14];
            for offset in [0usize, 2, 4] {
                let x = triangle[offset];
                let y = triangle[offset + 1];
                values.extend_from_slice(&[
                    x / width * 2.0 - 1.0,
                    1.0 - y / height * 2.0,
                    color[0],
                    color[1],
                    color[2],
                    color[3],
                    clip[0],
                    clip[1],
                    clip[2],
                    clip[3],
                ]);
            }
        }
        queue.write_buffer(&self.vertex_buffer, 0, &floats_to_bytes(&values));
        Ok(true)
    }

    pub(crate) fn render<'pass>(
        &'pass self,
        render_pass: &mut wgpu::RenderPass<'pass>,
        triangle_count: usize,
    ) {
        if triangle_count == 0 {
            return;
        }
        render_pass.set_pipeline(&self.pipeline);
        render_pass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
        render_pass.draw(0..(triangle_count as u32 * 3), 0..1);
    }

    fn ensure_capacity(&mut self, device: &wgpu::Device, required: usize) -> PyResult<()> {
        let capacity = next_path_triangle_capacity(self.triangle_capacity, required)?;
        if capacity == self.triangle_capacity {
            return Ok(());
        }
        self.vertex_buffer = create_path_vertex_buffer(device, capacity);
        self.triangle_capacity = capacity;
        Ok(())
    }
}

#[cfg(target_os = "windows")]
fn create_path_vertex_buffer(device: &wgpu::Device, triangle_capacity: usize) -> wgpu::Buffer {
    let size = triangle_capacity
        .saturating_mul(3)
        .saturating_mul(PATH_VERTEX_FLOATS)
        .saturating_mul(std::mem::size_of::<f32>())
        .max(std::mem::size_of::<f32>()) as u64;
    device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("SwirUI reusable path vertices"),
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

    fn valid_triangle() -> PathTriangleInstance {
        vec![
            10.0, 10.0, 80.0, 20.0, 30.0, 90.0, 0.0, 0.6, 1.0, 0.8, 0.0, 0.0, 100.0,
            100.0,
        ]
    }

    #[test]
    fn validates_path_triangle_contract() {
        assert!(validate_path_triangles(&[valid_triangle()]).is_ok());

        let mut wrong_length = valid_triangle();
        wrong_length.pop();
        assert!(validate_path_triangles(&[wrong_length]).is_err());

        let mut invalid_alpha = valid_triangle();
        invalid_alpha[9] = 1.2;
        assert!(validate_path_triangles(&[invalid_alpha]).is_err());

        let mut invalid_clip = valid_triangle();
        invalid_clip[12] = invalid_clip[10];
        assert!(validate_path_triangles(&[invalid_clip]).is_err());

        let mut degenerate = valid_triangle();
        degenerate[4] = 150.0;
        degenerate[5] = 30.0;
        assert!(validate_path_triangles(&[degenerate]).is_err());
    }

    #[test]
    fn path_capacity_grows_geometrically_and_never_shrinks() {
        assert_eq!(
            next_path_triangle_capacity(INITIAL_PATH_TRIANGLE_CAPACITY, 1).unwrap(),
            32
        );
        assert_eq!(
            next_path_triangle_capacity(INITIAL_PATH_TRIANGLE_CAPACITY, 32).unwrap(),
            32
        );
        assert_eq!(
            next_path_triangle_capacity(INITIAL_PATH_TRIANGLE_CAPACITY, 33).unwrap(),
            64
        );
        assert_eq!(next_path_triangle_capacity(64, 4).unwrap(), 64);
    }
}
