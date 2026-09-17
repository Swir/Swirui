use crate::image::{ImageInstance, ImageSystem};
#[cfg(target_os = "windows")]
use crate::postprocess::OffscreenRenderTarget;
use crate::shape::{ShapeSystem, ShapeVertex};
use crate::text::{TextInstance, TextSystem};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

#[cfg(target_os = "windows")]
use raw_window_handle::{RawWindowHandle, Win32WindowHandle, WindowsDisplayHandle};
#[cfg(target_os = "windows")]
use std::num::NonZeroIsize;
#[cfg(target_os = "windows")]
use wgpu::util::DeviceExt;

type RectangleInstance = Vec<f32>;
const LEGACY_RECTANGLE_INSTANCE_FLOATS: usize = 12;
const RECTANGLE_INSTANCE_FLOATS: usize = 16;
const INITIAL_RECTANGLE_CAPACITY: usize = 16;
const UNBOUNDED_CLIP: [f32; 4] = [-1.0e9, -1.0e9, 1.0e9, 1.0e9];

#[cfg(target_os = "windows")]
struct PersistentGpuContext {
    _instance: wgpu::Instance,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    offscreen_target: OffscreenRenderTarget,
    present_blitter: wgpu::util::TextureBlitter,
    frame_buffer: wgpu::Buffer,
    bind_group_layout: wgpu::BindGroupLayout,
    pipeline: wgpu::RenderPipeline,
    rectangle_buffer: wgpu::Buffer,
    rectangle_bind_group: wgpu::BindGroup,
    rectangle_capacity: usize,
    text_system: TextSystem,
    image_system: ImageSystem,
    shape_system: ShapeSystem,
    adapter_name: String,
    graphics_backend: String,
}

#[cfg(target_os = "windows")]
impl PersistentGpuContext {
    fn new(hwnd: isize, width: u32, height: u32) -> PyResult<Self> {
        Self::new_configured(hwnd, width, height, "auto_vsync", 1)
    }

    fn new_configured(
        hwnd: isize,
        width: u32,
        height: u32,
        presentation_mode: &str,
        maximum_frame_latency: u32,
    ) -> PyResult<Self> {
        validate_dimensions(width, height)?;
        validate_frame_latency(maximum_frame_latency)?;
        let present_mode = parse_present_mode(presentation_mode)?;

        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle());
        let surface = create_win32_surface(&instance, hwnd)?;
        let adapter = request_present_adapter(&instance, &surface)?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor {
            label: Some("SwirUI persistent GPU device"),
            ..Default::default()
        }))
        .map_err(|error| PyRuntimeError::new_err(format!("GPU device creation failed: {error}")))?;

        let mut config = surface
            .get_default_config(&adapter, width, height)
            .ok_or_else(|| PyRuntimeError::new_err("The selected GPU cannot configure this surface."))?;
        config.present_mode = present_mode;
        config.desired_maximum_frame_latency = maximum_frame_latency;
        surface.configure(&device, &config);

        let offscreen_target = OffscreenRenderTarget::new(&device, config.format, width, height);
        let present_blitter = wgpu::util::TextureBlitter::new(&device, config.format);
        let frame_uniforms = floats_to_bytes(&[width as f32, height as f32, 0.0, 0.0]);
        let frame_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("SwirUI persistent frame uniforms"),
            contents: &frame_uniforms,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });

        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("SwirUI rectangle bind group layout"),
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
                    visibility: wgpu::ShaderStages::VERTEX,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Storage { read_only: true },
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("SwirUI rectangle pipeline layout"),
            bind_group_layouts: &[Some(&bind_group_layout)],
            immediate_size: 0,
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("SwirUI rounded rectangle shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("rectangles.wgsl").into()),
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("SwirUI persistent rounded rectangle pipeline"),
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
                    format: config.format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            multiview_mask: None,
            cache: None,
        });
        let rectangle_capacity = INITIAL_RECTANGLE_CAPACITY;
        let rectangle_buffer = create_rectangle_buffer(&device, rectangle_capacity);
        let rectangle_bind_group = create_rectangle_bind_group(
            &device,
            &bind_group_layout,
            &frame_buffer,
            &rectangle_buffer,
        );
        let text_system = TextSystem::new(&device, &queue, config.format, width, height);
        let image_system = ImageSystem::new(&device, config.format);
        let shape_system = ShapeSystem::new(&device, config.format, &frame_buffer);

        Ok(Self {
            _instance: instance,
            surface,
            device,
            queue,
            config,
            offscreen_target,
            present_blitter,
            frame_buffer,
            bind_group_layout,
            pipeline,
            rectangle_buffer,
            rectangle_bind_group,
            rectangle_capacity,
            text_system,
            image_system,
            shape_system,
            adapter_name: info.name,
            graphics_backend: info.backend.to_string(),
        })
    }

    fn resize(&mut self, width: u32, height: u32) -> PyResult<()> {
        validate_dimensions(width, height)?;
        self.config.width = width;
        self.config.height = height;
        self.surface.configure(&self.device, &self.config);
        self.offscreen_target
            .resize(&self.device, self.config.format, width, height);
        let frame_uniforms = floats_to_bytes(&[width as f32, height as f32, 0.0, 0.0]);
        self.queue.write_buffer(&self.frame_buffer, 0, &frame_uniforms);
        self.text_system.resize(&self.queue, width, height);
        Ok(())
    }

    fn configure_presentation(
        &mut self,
        presentation_mode: &str,
        maximum_frame_latency: u32,
    ) -> PyResult<()> {
        validate_frame_latency(maximum_frame_latency)?;
        self.config.present_mode = parse_present_mode(presentation_mode)?;
        self.config.desired_maximum_frame_latency = maximum_frame_latency;
        self.surface.configure(&self.device, &self.config);
        Ok(())
    }

    fn register_image_rgba(
        &mut self,
        resource_id: String,
        width: u32,
        height: u32,
        rgba: &[u8],
    ) -> PyResult<()> {
        self.image_system
            .register_rgba(&self.device, &self.queue, resource_id, width, height, rgba)
    }

    fn unregister_image(&mut self, resource_id: &str) -> bool {
        self.image_system.unregister(resource_id)
    }

    fn clear(&self, red: f64, green: f64, blue: f64, alpha: f64) -> PyResult<()> {
        validate_color(red, green, blue, alpha)?;
        let frame = acquire_surface_texture(&self.surface)?;
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("SwirUI persistent clear encoder"),
            });
        {
            let _render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("SwirUI persistent offscreen clear pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: self.offscreen_target.view(),
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: red,
                            g: green,
                            b: blue,
                            a: alpha,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
                multiview_mask: None,
            });
        }
        self.present_blitter.copy(
            &self.device,
            &mut encoder,
            self.offscreen_target.view(),
            &view,
        );
        self.queue.submit([encoder.finish()]);
        self.queue.present(frame);
        Ok(())
    }

    fn draw_rectangles(
        &mut self,
        rectangles: &[RectangleInstance],
        background_red: f64,
        background_green: f64,
        background_blue: f64,
        background_alpha: f64,
    ) -> PyResult<usize> {
        let (rectangle_count, _text_count, _image_count, _shape_count) = self.draw_scene_with_paths(
            rectangles,
            &[],
            &[],
            &[],
            background_red,
            background_green,
            background_blue,
            background_alpha,
        )?;
        Ok(rectangle_count)
    }

    fn draw_scene(
        &mut self,
        rectangles: &[RectangleInstance],
        texts: &[TextInstance],
        images: &[ImageInstance],
        background_red: f64,
        background_green: f64,
        background_blue: f64,
        background_alpha: f64,
    ) -> PyResult<(usize, usize, usize)> {
        let (rectangle_count, text_count, image_count, _shape_count) = self.draw_scene_with_paths(
            rectangles,
            texts,
            images,
            &[],
            background_red,
            background_green,
            background_blue,
            background_alpha,
        )?;
        Ok((rectangle_count, text_count, image_count))
    }

    fn draw_scene_with_paths(
        &mut self,
        rectangles: &[RectangleInstance],
        texts: &[TextInstance],
        images: &[ImageInstance],
        shapes: &[ShapeVertex],
        background_red: f64,
        background_green: f64,
        background_blue: f64,
        background_alpha: f64,
    ) -> PyResult<(usize, usize, usize, usize)> {
        validate_color(
            background_red,
            background_green,
            background_blue,
            background_alpha,
        )?;
        if !rectangles.is_empty() {
            validate_rectangles(rectangles)?;
            self.ensure_rectangle_capacity(rectangles.len())?;
            let rectangle_data = rectangle_bytes(rectangles);
            self.queue
                .write_buffer(&self.rectangle_buffer, 0, &rectangle_data);
        }
        if rectangles.is_empty() && texts.is_empty() && images.is_empty() && shapes.is_empty() {
            self.clear(
                background_red,
                background_green,
                background_blue,
                background_alpha,
            )?;
            return Ok((0, 0, 0, 0));
        }
        if !texts.is_empty() {
            self.text_system.prepare(&self.device, &self.queue, texts)?;
        }
        let images_prepared = self.image_system.prepare_vertices(
            &self.device,
            &self.queue,
            images,
            self.config.width,
            self.config.height,
        )?;
        let shapes_prepared =
            self.shape_system
                .prepare_vertices(&self.device, &self.queue, shapes)?;

        let frame = acquire_surface_texture(&self.surface)?;
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("SwirUI persistent scene encoder"),
            });
        {
            let mut render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("SwirUI persistent offscreen scene pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: self.offscreen_target.view(),
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: background_red,
                            g: background_green,
                            b: background_blue,
                            a: background_alpha,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
                multiview_mask: None,
            });

            if !rectangles.is_empty() {
                render_pass.set_pipeline(&self.pipeline);
                render_pass.set_bind_group(0, &self.rectangle_bind_group, &[]);
                render_pass.draw(0..6, 0..rectangles.len() as u32);
            }
            if shapes_prepared {
                self.shape_system.render(&mut render_pass, shapes.len())?;
            }
            if images_prepared {
                self.image_system.render(&mut render_pass, images)?;
            }
            if !texts.is_empty() {
                self.text_system.render(&mut render_pass)?;
            }
        }

        self.present_blitter.copy(
            &self.device,
            &mut encoder,
            self.offscreen_target.view(),
            &view,
        );
        self.queue.submit([encoder.finish()]);
        self.queue.present(frame);
        if !texts.is_empty() {
            self.text_system.trim();
        }
        Ok((rectangles.len(), texts.len(), images.len(), shapes.len() / 3))
    }

    fn ensure_rectangle_capacity(&mut self, required: usize) -> PyResult<()> {
        let capacity = next_rectangle_capacity(self.rectangle_capacity, required)?;
        if capacity == self.rectangle_capacity {
            return Ok(());
        }
        let buffer = create_rectangle_buffer(&self.device, capacity);
        let bind_group = create_rectangle_bind_group(
            &self.device,
            &self.bind_group_layout,
            &self.frame_buffer,
            &buffer,
        );
        self.rectangle_buffer = buffer;
        self.rectangle_bind_group = bind_group;
        self.rectangle_capacity = capacity;
        Ok(())
    }
}

#[cfg(target_os = "windows")]
#[pyclass(name = "Win32GpuRenderer", unsendable)]
pub(crate) struct PyWin32GpuRenderer {
    context: PersistentGpuContext,
}

#[cfg(target_os = "windows")]
#[pymethods]
impl PyWin32GpuRenderer {
    #[new]
    #[pyo3(signature = (
        hwnd,
        width,
        height,
        presentation_mode="auto_vsync",
        maximum_frame_latency=1
    ))]
    fn new(
        hwnd: isize,
        width: u32,
        height: u32,
        presentation_mode: &str,
        maximum_frame_latency: u32,
    ) -> PyResult<Self> {
        Ok(Self {
            context: PersistentGpuContext::new_configured(
                hwnd,
                width,
                height,
                presentation_mode,
                maximum_frame_latency,
            )?,
        })
    }

    #[getter]
    fn adapter_name(&self) -> &str {
        &self.context.adapter_name
    }

    #[getter]
    fn graphics_backend(&self) -> &str {
        &self.context.graphics_backend
    }

    #[getter]
    fn width(&self) -> u32 {
        self.context.config.width
    }

    #[getter]
    fn height(&self) -> u32 {
        self.context.config.height
    }

    #[getter]
    fn presentation_mode(&self) -> &'static str {
        present_mode_name(self.context.config.present_mode)
    }

    #[getter]
    fn maximum_frame_latency(&self) -> u32 {
        self.context.config.desired_maximum_frame_latency
    }

    #[getter]
    fn rectangle_capacity(&self) -> usize {
        self.context.rectangle_capacity
    }

    #[getter]
    fn image_vertex_capacity(&self) -> usize {
        self.context.image_system.vertex_capacity()
    }

    #[getter]
    fn shape_vertex_capacity(&self) -> usize {
        self.context.shape_system.vertex_capacity()
    }

    #[getter]
    fn image_resource_count(&self) -> usize {
        self.context.image_system.resource_count()
    }

    #[getter]
    fn offscreen_size(&self) -> (u32, u32) {
        self.context.offscreen_target.size()
    }

    #[getter]
    fn offscreen_generation(&self) -> u64 {
        self.context.offscreen_target.generation()
    }

    fn image_resource_size(&self, resource_id: &str) -> Option<(u32, u32)> {
        self.context.image_system.resource_size(resource_id)
    }

    fn resize(&mut self, width: u32, height: u32) -> PyResult<()> {
        self.context.resize(width, height)
    }

    fn configure_presentation(
        &mut self,
        presentation_mode: &str,
        maximum_frame_latency: u32,
    ) -> PyResult<()> {
        self.context
            .configure_presentation(presentation_mode, maximum_frame_latency)
    }

    fn register_image_rgba(
        &mut self,
        resource_id: String,
        width: u32,
        height: u32,
        rgba: Vec<u8>,
    ) -> PyResult<()> {
        self.context
            .register_image_rgba(resource_id, width, height, &rgba)
    }

    fn unregister_image(&mut self, resource_id: &str) -> bool {
        self.context.unregister_image(resource_id)
    }

    #[pyo3(signature = (red=0.027, green=0.043, blue=0.078, alpha=1.0))]
    fn clear(&self, red: f64, green: f64, blue: f64, alpha: f64) -> PyResult<()> {
        self.context.clear(red, green, blue, alpha)
    }

    #[pyo3(signature = (
        rectangles,
        background_red=0.027,
        background_green=0.043,
        background_blue=0.078,
        background_alpha=1.0
    ))]
    fn draw_rectangles(
        &mut self,
        rectangles: Vec<RectangleInstance>,
        background_red: f64,
        background_green: f64,
        background_blue: f64,
        background_alpha: f64,
    ) -> PyResult<usize> {
        self.context.draw_rectangles(
            &rectangles,
            background_red,
            background_green,
            background_blue,
            background_alpha,
        )
    }

    #[pyo3(signature = (
        rectangles,
        texts,
        images,
        background_red=0.027,
        background_green=0.043,
        background_blue=0.078,
        background_alpha=1.0
    ))]
    fn draw_scene(
        &mut self,
        rectangles: Vec<RectangleInstance>,
        texts: Vec<TextInstance>,
        images: Vec<ImageInstance>,
        background_red: f64,
        background_green: f64,
        background_blue: f64,
        background_alpha: f64,
    ) -> PyResult<(usize, usize, usize)> {
        self.context.draw_scene(
            &rectangles,
            &texts,
            &images,
            background_red,
            background_green,
            background_blue,
            background_alpha,
        )
    }

    #[pyo3(signature = (
        rectangles,
        texts,
        images,
        shapes,
        background_red=0.027,
        background_green=0.043,
        background_blue=0.078,
        background_alpha=1.0
    ))]
    fn draw_scene_with_paths(
        &mut self,
        rectangles: Vec<RectangleInstance>,
        texts: Vec<TextInstance>,
        images: Vec<ImageInstance>,
        shapes: Vec<ShapeVertex>,
        background_red: f64,
        background_green: f64,
        background_blue: f64,
        background_alpha: f64,
    ) -> PyResult<(usize, usize, usize, usize)> {
        self.context.draw_scene_with_paths(
            &rectangles,
            &texts,
            &images,
            &shapes,
            background_red,
            background_green,
            background_blue,
            background_alpha,
        )
    }
}

#[cfg(target_os = "windows")]
#[pyfunction]
#[pyo3(signature = (hwnd, width, height, red=0.027, green=0.043, blue=0.078, alpha=1.0))]
pub(crate) fn clear_win32_surface(
    hwnd: isize,
    width: u32,
    height: u32,
    red: f64,
    green: f64,
    blue: f64,
    alpha: f64,
) -> PyResult<(String, String)> {
    let context = PersistentGpuContext::new(hwnd, width, height)?;
    context.clear(red, green, blue, alpha)?;
    Ok((context.adapter_name, context.graphics_backend))
}

#[cfg(target_os = "windows")]
#[pyfunction]
#[pyo3(signature = (
    hwnd,
    width,
    height,
    rectangles,
    background_red=0.027,
    background_green=0.043,
    background_blue=0.078,
    background_alpha=1.0
))]
pub(crate) fn draw_rectangles_win32_surface(
    hwnd: isize,
    width: u32,
    height: u32,
    rectangles: Vec<RectangleInstance>,
    background_red: f64,
    background_green: f64,
    background_blue: f64,
    background_alpha: f64,
) -> PyResult<(String, String, usize)> {
    let mut context = PersistentGpuContext::new(hwnd, width, height)?;
    let count = context.draw_rectangles(
        &rectangles,
        background_red,
        background_green,
        background_blue,
        background_alpha,
    )?;
    Ok((context.adapter_name, context.graphics_backend, count))
}

#[cfg(not(target_os = "windows"))]
#[pyfunction]
#[pyo3(signature = (hwnd, width, height, red=0.027, green=0.043, blue=0.078, alpha=1.0))]
pub(crate) fn clear_win32_surface(
    hwnd: isize,
    width: u32,
    height: u32,
    red: f64,
    green: f64,
    blue: f64,
    alpha: f64,
) -> PyResult<(String, String)> {
    let _ = (hwnd, width, height, red, green, blue, alpha);
    Err(PyRuntimeError::new_err(
        "clear_win32_surface is only available on Windows.",
    ))
}

#[cfg(not(target_os = "windows"))]
#[pyfunction]
#[pyo3(signature = (
    hwnd,
    width,
    height,
    rectangles,
    background_red=0.027,
    background_green=0.043,
    background_blue=0.078,
    background_alpha=1.0
))]
pub(crate) fn draw_rectangles_win32_surface(
    hwnd: isize,
    width: u32,
    height: u32,
    rectangles: Vec<RectangleInstance>,
    background_red: f64,
    background_green: f64,
    background_blue: f64,
    background_alpha: f64,
) -> PyResult<(String, String, usize)> {
    let _ = (
        hwnd,
        width,
        height,
        rectangles,
        background_red,
        background_green,
        background_blue,
        background_alpha,
    );
    Err(PyRuntimeError::new_err(
        "draw_rectangles_win32_surface is only available on Windows.",
    ))
}

fn validate_dimensions(width: u32, height: u32) -> PyResult<()> {
    if width == 0 || height == 0 {
        return Err(PyValueError::new_err(
            "GPU surface dimensions must be greater than zero.",
        ));
    }
    Ok(())
}

fn validate_color(red: f64, green: f64, blue: f64, alpha: f64) -> PyResult<()> {
    if [red, green, blue, alpha]
        .into_iter()
        .any(|channel| !(0.0..=1.0).contains(&channel))
    {
        return Err(PyValueError::new_err(
            "GPU clear color channels must be between 0.0 and 1.0.",
        ));
    }
    Ok(())
}

fn validate_frame_latency(maximum_frame_latency: u32) -> PyResult<()> {
    if maximum_frame_latency == 0 {
        return Err(PyValueError::new_err(
            "maximum_frame_latency must be greater than zero.",
        ));
    }
    Ok(())
}

fn parse_present_mode(mode: &str) -> PyResult<wgpu::PresentMode> {
    match mode {
        "auto_vsync" => Ok(wgpu::PresentMode::AutoVsync),
        "auto_no_vsync" => Ok(wgpu::PresentMode::AutoNoVsync),
        _ => Err(PyValueError::new_err(
            "presentation_mode must be 'auto_vsync' or 'auto_no_vsync'.",
        )),
    }
}

fn present_mode_name(mode: wgpu::PresentMode) -> &'static str {
    match mode {
        wgpu::PresentMode::AutoVsync => "auto_vsync",
        wgpu::PresentMode::AutoNoVsync => "auto_no_vsync",
        wgpu::PresentMode::Fifo => "fifo",
        wgpu::PresentMode::FifoRelaxed => "fifo_relaxed",
        wgpu::PresentMode::Immediate => "immediate",
        wgpu::PresentMode::Mailbox => "mailbox",
    }
}

fn validate_rectangles(rectangles: &[RectangleInstance]) -> PyResult<()> {
    if rectangles.is_empty() {
        return Err(PyValueError::new_err(
            "At least one rectangle is required for GPU submission.",
        ));
    }

    for rectangle in rectangles {
        if !matches!(
            rectangle.len(),
            LEGACY_RECTANGLE_INSTANCE_FLOATS | RECTANGLE_INSTANCE_FLOATS
        ) {
            return Err(PyValueError::new_err(format!(
                "Rectangle instances require either {LEGACY_RECTANGLE_INSTANCE_FLOATS} legacy floats or {RECTANGLE_INSTANCE_FLOATS} floats with clip bounds."
            )));
        }
        if !rectangle.iter().copied().all(f32::is_finite) {
            return Err(PyValueError::new_err(
                "Rectangle geometry, colors, corner radii and clip bounds must be finite.",
            ));
        }
        if rectangle[2] <= 0.0 || rectangle[3] <= 0.0 {
            return Err(PyValueError::new_err(
                "Rectangle width and height must be greater than zero.",
            ));
        }
        if rectangle[4..8]
            .iter()
            .any(|channel| !(0.0..=1.0).contains(channel))
        {
            return Err(PyValueError::new_err(
                "Rectangle color channels must be between 0.0 and 1.0.",
            ));
        }
        if rectangle[8..12].iter().any(|radius| *radius < 0.0) {
            return Err(PyValueError::new_err(
                "Rectangle corner radii cannot be negative.",
            ));
        }
        if rectangle.len() == RECTANGLE_INSTANCE_FLOATS
            && (rectangle[14] <= rectangle[12] || rectangle[15] <= rectangle[13])
        {
            return Err(PyValueError::new_err(
                "Rectangle clip bounds must have positive width and height.",
            ));
        }
    }
    Ok(())
}

fn next_rectangle_capacity(current: usize, required: usize) -> PyResult<usize> {
    if required <= current {
        return Ok(current);
    }
    required
        .checked_next_power_of_two()
        .ok_or_else(|| PyValueError::new_err("Rectangle batch is too large for GPU buffering."))
}

#[cfg(target_os = "windows")]
fn create_rectangle_buffer(device: &wgpu::Device, capacity: usize) -> wgpu::Buffer {
    let size = capacity
        .saturating_mul(RECTANGLE_INSTANCE_FLOATS)
        .saturating_mul(std::mem::size_of::<f32>())
        .max(std::mem::size_of::<f32>()) as u64;
    device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("SwirUI reusable rectangle instances"),
        size,
        usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST,
        mapped_at_creation: false,
    })
}

#[cfg(target_os = "windows")]
fn create_rectangle_bind_group(
    device: &wgpu::Device,
    layout: &wgpu::BindGroupLayout,
    frame_buffer: &wgpu::Buffer,
    rectangle_buffer: &wgpu::Buffer,
) -> wgpu::BindGroup {
    device.create_bind_group(&wgpu::BindGroupDescriptor {
        label: Some("SwirUI persistent rectangle bind group"),
        layout,
        entries: &[
            wgpu::BindGroupEntry {
                binding: 0,
                resource: frame_buffer.as_entire_binding(),
            },
            wgpu::BindGroupEntry {
                binding: 1,
                resource: rectangle_buffer.as_entire_binding(),
            },
        ],
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

#[cfg(target_os = "windows")]
fn rectangle_bytes(rectangles: &[RectangleInstance]) -> Vec<u8> {
    let mut values = Vec::with_capacity(rectangles.len() * RECTANGLE_INSTANCE_FLOATS);
    for rectangle in rectangles {
        values.extend_from_slice(rectangle);
        if rectangle.len() == LEGACY_RECTANGLE_INSTANCE_FLOATS {
            values.extend_from_slice(&UNBOUNDED_CLIP);
        }
    }
    floats_to_bytes(&values)
}

#[cfg(target_os = "windows")]
fn request_present_adapter(
    instance: &wgpu::Instance,
    surface: &wgpu::Surface<'_>,
) -> PyResult<wgpu::Adapter> {
    let primary = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::HighPerformance,
        force_fallback_adapter: false,
        compatible_surface: Some(surface),
        apply_limit_buckets: false,
    }));
    if let Ok(adapter) = primary {
        return Ok(adapter);
    }

    pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
        power_preference: wgpu::PowerPreference::LowPower,
        force_fallback_adapter: true,
        compatible_surface: Some(surface),
        apply_limit_buckets: false,
    }))
    .map_err(|error| {
        PyRuntimeError::new_err(format!(
            "No hardware or fallback GPU can present to this HWND: {error}"
        ))
    })
}

#[cfg(target_os = "windows")]
#[allow(unsafe_code)]
fn create_win32_surface(
    instance: &wgpu::Instance,
    hwnd: isize,
) -> PyResult<wgpu::Surface<'static>> {
    let hwnd = NonZeroIsize::new(hwnd)
        .ok_or_else(|| PyValueError::new_err("A non-zero Win32 HWND is required."))?;
    let handle = Win32WindowHandle::new(hwnd);
    let target = wgpu::SurfaceTargetUnsafe::RawHandle {
        raw_display_handle: Some(WindowsDisplayHandle::new().into()),
        raw_window_handle: RawWindowHandle::Win32(handle),
    };

    unsafe { instance.create_surface_unsafe(target) }
        .map_err(|error| PyRuntimeError::new_err(format!("wgpu surface creation failed: {error}")))
}

#[cfg(target_os = "windows")]
fn acquire_surface_texture(surface: &wgpu::Surface<'_>) -> PyResult<wgpu::SurfaceTexture> {
    match surface.get_current_texture() {
        wgpu::CurrentSurfaceTexture::Success(frame)
        | wgpu::CurrentSurfaceTexture::Suboptimal(frame) => Ok(frame),
        wgpu::CurrentSurfaceTexture::Timeout => {
            Err(PyRuntimeError::new_err("Timed out while acquiring a GPU frame."))
        }
        wgpu::CurrentSurfaceTexture::Occluded => {
            Err(PyRuntimeError::new_err("The SwirUI GPU surface is occluded."))
        }
        wgpu::CurrentSurfaceTexture::Outdated => {
            Err(PyRuntimeError::new_err("The SwirUI GPU surface is outdated."))
        }
        wgpu::CurrentSurfaceTexture::Lost => {
            Err(PyRuntimeError::new_err("The SwirUI GPU surface was lost."))
        }
        wgpu::CurrentSurfaceTexture::Validation => Err(PyRuntimeError::new_err(
            "The SwirUI GPU surface failed validation.",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_rectangle() -> RectangleInstance {
        vec![
            20.0, 30.0, 100.0, 50.0, 0.0, 0.5, 1.0, 1.0, 12.0, 18.0, 22.0, 8.0,
        ]
    }

    fn clipped_rectangle() -> RectangleInstance {
        vec![
            20.0, 30.0, 100.0, 50.0, 0.0, 0.5, 1.0, 1.0, 12.0, 18.0, 22.0, 8.0, 30.0, 35.0,
            90.0, 70.0,
        ]
    }

    #[test]
    fn rejects_zero_surface_size() {
        assert!(validate_dimensions(0, 100).is_err());
        assert!(validate_dimensions(100, 0).is_err());
    }

    #[test]
    fn rejects_invalid_clear_color() {
        assert!(validate_color(0.0, 0.5, 1.0, 1.0).is_ok());
        assert!(validate_color(-0.1, 0.5, 1.0, 1.0).is_err());
        assert!(validate_color(0.0, 0.5, 1.1, 1.0).is_err());
    }

    #[test]
    fn validates_presentation_configuration() {
        assert_eq!(
            parse_present_mode("auto_vsync").unwrap(),
            wgpu::PresentMode::AutoVsync
        );
        assert_eq!(
            parse_present_mode("auto_no_vsync").unwrap(),
            wgpu::PresentMode::AutoNoVsync
        );
        assert!(parse_present_mode("immediate").is_err());
        assert!(validate_frame_latency(1).is_ok());
        assert!(validate_frame_latency(2).is_ok());
        assert!(validate_frame_latency(0).is_err());
    }

    #[test]
    fn validates_rounded_rectangle_instances() {
        assert!(validate_rectangles(&[valid_rectangle()]).is_ok());
        assert!(validate_rectangles(&[clipped_rectangle()]).is_ok());
        assert!(validate_rectangles(&[]).is_err());

        let mut wrong_length = valid_rectangle();
        wrong_length.pop();
        assert!(validate_rectangles(&[wrong_length]).is_err());

        let mut zero_width = valid_rectangle();
        zero_width[2] = 0.0;
        assert!(validate_rectangles(&[zero_width]).is_err());

        let mut invalid_color = valid_rectangle();
        invalid_color[5] = 1.5;
        assert!(validate_rectangles(&[invalid_color]).is_err());

        let mut negative_radius = valid_rectangle();
        negative_radius[8] = -1.0;
        assert!(validate_rectangles(&[negative_radius]).is_err());

        let mut invalid_clip = clipped_rectangle();
        invalid_clip[14] = invalid_clip[12];
        assert!(validate_rectangles(&[invalid_clip]).is_err());
    }

    #[test]
    fn rectangle_buffer_capacity_grows_geometrically_and_never_shrinks() {
        assert_eq!(
            next_rectangle_capacity(INITIAL_RECTANGLE_CAPACITY, 1).unwrap(),
            16
        );
        assert_eq!(
            next_rectangle_capacity(INITIAL_RECTANGLE_CAPACITY, 16).unwrap(),
            16
        );
        assert_eq!(
            next_rectangle_capacity(INITIAL_RECTANGLE_CAPACITY, 17).unwrap(),
            32
        );
        assert_eq!(next_rectangle_capacity(32, 33).unwrap(), 64);
        assert_eq!(next_rectangle_capacity(64, 2).unwrap(), 64);
    }
}
