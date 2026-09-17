//! Persistent offscreen targets and native post-processing passes.
//!
//! The scene renderer writes into a sampleable texture before final presentation.
//! That target survives ordinary frames, which makes effects such as blur, glass and
//! bloom possible without allocating a full-size texture on every frame.

pub(crate) struct OffscreenRenderTarget {
    _texture: wgpu::Texture,
    view: wgpu::TextureView,
    width: u32,
    height: u32,
    generation: u64,
}

impl OffscreenRenderTarget {
    pub(crate) fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
    ) -> Self {
        Self::new_labeled(device, format, width, height, "SwirUI persistent offscreen scene target")
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

        let (texture, view) = create_target(
            device,
            format,
            width,
            height,
            "SwirUI resized persistent offscreen target",
        );
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
    horizontal_target: OffscreenRenderTarget,
    vertical_target: OffscreenRenderTarget,
    _sampler: wgpu::Sampler,
    bind_group_layout: wgpu::BindGroupLayout,
    horizontal_pipeline: wgpu::RenderPipeline,
    vertical_pipeline: wgpu::RenderPipeline,
    scene_bind_group: wgpu::BindGroup,
    horizontal_bind_group: wgpu::BindGroup,
    vertical_bind_group: wgpu::BindGroup,
}

impl SeparableBlur {
    pub(crate) fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
        scene_view: &wgpu::TextureView,
    ) -> Self {
        let horizontal_target = OffscreenRenderTarget::new_labeled(
            device,
            format,
            width,
            height,
            "SwirUI persistent horizontal blur target",
        );
        let vertical_target = OffscreenRenderTarget::new_labeled(
            device,
            format,
            width,
            height,
            "SwirUI persistent vertical blur target",
        );
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("SwirUI post-process blur sampler"),
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::MipmapFilterMode::Nearest,
            ..Default::default()
        });
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("SwirUI post-process blur bind group layout"),
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
            label: Some("SwirUI post-process blur pipeline layout"),
            bind_group_layouts: &[Some(&bind_group_layout)],
            immediate_size: 0,
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("SwirUI separable Gaussian blur shader"),
            source: wgpu::ShaderSource::Wgsl(include_str!("blur.wgsl").into()),
        });
        let horizontal_pipeline = create_blur_pipeline(
            device,
            &pipeline_layout,
            &shader,
            format,
            "fs_horizontal",
            "SwirUI horizontal Gaussian blur pipeline",
        );
        let vertical_pipeline = create_blur_pipeline(
            device,
            &pipeline_layout,
            &shader,
            format,
            "fs_vertical",
            "SwirUI vertical Gaussian blur pipeline",
        );
        let scene_bind_group = create_blur_bind_group(
            device,
            &bind_group_layout,
            scene_view,
            &sampler,
            "SwirUI scene blur source",
        );
        let horizontal_bind_group = create_blur_bind_group(
            device,
            &bind_group_layout,
            horizontal_target.view(),
            &sampler,
            "SwirUI horizontal blur source",
        );
        let vertical_bind_group = create_blur_bind_group(
            device,
            &bind_group_layout,
            vertical_target.view(),
            &sampler,
            "SwirUI vertical blur source",
        );

        Self {
            horizontal_target,
            vertical_target,
            _sampler: sampler,
            bind_group_layout,
            horizontal_pipeline,
            vertical_pipeline,
            scene_bind_group,
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
        scene_view: &wgpu::TextureView,
    ) {
        self.horizontal_target
            .resize(device, format, width, height);
        self.vertical_target.resize(device, format, width, height);
        self.rebuild_bind_groups(device, scene_view);
    }

    pub(crate) fn render<'a>(
        &'a self,
        encoder: &mut wgpu::CommandEncoder,
        iterations: u32,
    ) -> &'a wgpu::TextureView {
        debug_assert!(iterations > 0);

        for iteration in 0..iterations {
            let horizontal_source = if iteration == 0 {
                &self.scene_bind_group
            } else {
                &self.vertical_bind_group
            };
            encode_blur_pass(
                encoder,
                &self.horizontal_pipeline,
                horizontal_source,
                self.horizontal_target.view(),
                "SwirUI horizontal Gaussian blur pass",
            );
            encode_blur_pass(
                encoder,
                &self.vertical_pipeline,
                &self.horizontal_bind_group,
                self.vertical_target.view(),
                "SwirUI vertical Gaussian blur pass",
            );
        }

        self.vertical_target.view()
    }

    pub(crate) const fn size(&self) -> (u32, u32) {
        self.horizontal_target.size()
    }

    pub(crate) const fn generation(&self) -> u64 {
        self.horizontal_target.generation()
    }

    fn rebuild_bind_groups(&mut self, device: &wgpu::Device, scene_view: &wgpu::TextureView) {
        self.scene_bind_group = create_blur_bind_group(
            device,
            &self.bind_group_layout,
            scene_view,
            &self._sampler,
            "SwirUI scene blur source",
        );
        self.horizontal_bind_group = create_blur_bind_group(
            device,
            &self.bind_group_layout,
            self.horizontal_target.view(),
            &self._sampler,
            "SwirUI horizontal blur source",
        );
        self.vertical_bind_group = create_blur_bind_group(
            device,
            &self.bind_group_layout,
            self.vertical_target.view(),
            &self._sampler,
            "SwirUI vertical blur source",
        );
    }
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

fn create_blur_pipeline(
    device: &wgpu::Device,
    layout: &wgpu::PipelineLayout,
    shader: &wgpu::ShaderModule,
    format: wgpu::TextureFormat,
    fragment_entry_point: &'static str,
    label: &'static str,
) -> wgpu::RenderPipeline {
    device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
        label: Some(label),
        layout: Some(layout),
        vertex: wgpu::VertexState {
            module: shader,
            entry_point: Some("vs_main"),
            compilation_options: wgpu::PipelineCompilationOptions::default(),
            buffers: &[],
        },
        primitive: wgpu::PrimitiveState::default(),
        depth_stencil: None,
        multisample: wgpu::MultisampleState::default(),
        fragment: Some(wgpu::FragmentState {
            module: shader,
            entry_point: Some(fragment_entry_point),
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

fn create_blur_bind_group(
    device: &wgpu::Device,
    layout: &wgpu::BindGroupLayout,
    source_view: &wgpu::TextureView,
    sampler: &wgpu::Sampler,
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
        ],
    })
}

fn encode_blur_pass(
    encoder: &mut wgpu::CommandEncoder,
    pipeline: &wgpu::RenderPipeline,
    bind_group: &wgpu::BindGroup,
    target: &wgpu::TextureView,
    label: &'static str,
) {
    let mut render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
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
    render_pass.set_pipeline(pipeline);
    render_pass.set_bind_group(0, bind_group, &[]);
    render_pass.draw(0..3, 0..1);
}
