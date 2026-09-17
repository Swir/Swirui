//! Persistent offscreen render target used by the native post-processing pipeline.
//!
//! The scene renderer writes into this texture before the final presentation blit.
//! Keeping the target alive across frames avoids allocating a full-size texture per
//! frame and provides a sampleable scene image for upcoming blur/glass/bloom passes.

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
        let (texture, view) = create_target(device, format, width, height);
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

        let (texture, view) = create_target(device, format, width, height);
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

fn create_target(
    device: &wgpu::Device,
    format: wgpu::TextureFormat,
    width: u32,
    height: u32,
) -> (wgpu::Texture, wgpu::TextureView) {
    let texture = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("SwirUI persistent offscreen scene target"),
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
