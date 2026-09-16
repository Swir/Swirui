use glyphon::{
    Attrs, Buffer, Cache, Color, Family, FontSystem, Metrics, Resolution, Shaping, SwashCache,
    TextArea, TextAtlas, TextBounds, TextRenderer, Viewport,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

pub(crate) type TextInstance = (
    String,
    f32,
    f32,
    f32,
    f32,
    f32,
    f32,
    f32,
    f32,
    f32,
    String,
);

pub(crate) struct TextSystem {
    font_system: FontSystem,
    swash_cache: SwashCache,
    _cache: Cache,
    viewport: Viewport,
    atlas: TextAtlas,
    renderer: TextRenderer,
}

impl TextSystem {
    pub(crate) fn new(
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        format: wgpu::TextureFormat,
        width: u32,
        height: u32,
    ) -> Self {
        let font_system = FontSystem::new();
        let swash_cache = SwashCache::new();
        let cache = Cache::new(device);
        let mut viewport = Viewport::new(device, &cache);
        viewport.update(queue, Resolution { width, height });
        let mut atlas = TextAtlas::new(device, queue, &cache, format);
        let renderer = TextRenderer::new(
            &mut atlas,
            device,
            wgpu::MultisampleState::default(),
            None,
        );

        Self {
            font_system,
            swash_cache,
            _cache: cache,
            viewport,
            atlas,
            renderer,
        }
    }

    pub(crate) fn resize(&mut self, queue: &wgpu::Queue, width: u32, height: u32) {
        self.viewport.update(queue, Resolution { width, height });
    }

    pub(crate) fn prepare(
        &mut self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        texts: &[TextInstance],
    ) -> PyResult<()> {
        validate_texts(texts)?;

        let mut buffers = Vec::with_capacity(texts.len());
        for text in texts {
            let (
                content,
                _x,
                _y,
                width,
                height,
                font_size,
                _red,
                _green,
                _blue,
                _alpha,
                family,
            ) = text;
            let metrics = Metrics::new(*font_size, *font_size * 1.25);
            let mut buffer = Buffer::new(&mut self.font_system, metrics);
            buffer.set_size(Some(*width), Some(*height));
            let attrs = Attrs::new().family(Family::Name(family.as_str()));
            buffer.set_text(content, &attrs, Shaping::Advanced, None);
            buffer.shape_until_scroll(&mut self.font_system, false);
            buffers.push(buffer);
        }

        let areas = buffers.iter().zip(texts.iter()).map(|(buffer, text)| {
            let (
                _content,
                x,
                y,
                width,
                height,
                _font_size,
                red,
                green,
                blue,
                alpha,
                _family,
            ) = text;
            TextArea {
                buffer,
                left: *x,
                top: *y,
                scale: 1.0,
                bounds: TextBounds {
                    left: float_to_i32(*x),
                    top: float_to_i32(*y),
                    right: float_to_i32(*x + *width),
                    bottom: float_to_i32(*y + *height),
                },
                default_color: Color::rgba(
                    channel_to_u8(*red),
                    channel_to_u8(*green),
                    channel_to_u8(*blue),
                    channel_to_u8(*alpha),
                ),
                custom_glyphs: &[],
            }
        });

        self.renderer
            .prepare(
                device,
                queue,
                &mut self.font_system,
                &mut self.atlas,
                &self.viewport,
                areas,
                &mut self.swash_cache,
            )
            .map_err(|error| {
                PyRuntimeError::new_err(format!("GPU text preparation failed: {error:?}"))
            })
    }

    pub(crate) fn render(&self, pass: &mut wgpu::RenderPass<'_>) -> PyResult<()> {
        self.renderer
            .render(&self.atlas, &self.viewport, pass)
            .map_err(|error| {
                PyRuntimeError::new_err(format!("GPU text rendering failed: {error:?}"))
            })
    }

    pub(crate) fn trim(&mut self) {
        self.atlas.trim();
    }
}

pub(crate) fn validate_texts(texts: &[TextInstance]) -> PyResult<()> {
    for text in texts {
        let (
            content,
            x,
            y,
            width,
            height,
            font_size,
            red,
            green,
            blue,
            alpha,
            family,
        ) = text;
        if content.is_empty() {
            return Err(PyValueError::new_err("Text content cannot be empty."));
        }
        if family.is_empty() {
            return Err(PyValueError::new_err("Text font family cannot be empty."));
        }
        if ![*x, *y, *width, *height, *font_size, *red, *green, *blue, *alpha]
            .into_iter()
            .all(f32::is_finite)
        {
            return Err(PyValueError::new_err(
                "Text geometry, size and color channels must be finite.",
            ));
        }
        if *width <= 0.0 || *height <= 0.0 || *font_size <= 0.0 {
            return Err(PyValueError::new_err(
                "Text width, height and font size must be greater than zero.",
            ));
        }
        if [*red, *green, *blue, *alpha]
            .into_iter()
            .any(|channel| !(0.0..=1.0).contains(&channel))
        {
            return Err(PyValueError::new_err(
                "Text color channels must be between 0.0 and 1.0.",
            ));
        }
    }
    Ok(())
}

fn channel_to_u8(channel: f32) -> u8 {
    (channel * 255.0).round() as u8
}

fn float_to_i32(value: f32) -> i32 {
    value.round().clamp(i32::MIN as f32, i32::MAX as f32) as i32
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_text() -> TextInstance {
        (
            "SwirUI".to_owned(),
            20.0,
            30.0,
            220.0,
            48.0,
            24.0,
            1.0,
            1.0,
            1.0,
            1.0,
            "Segoe UI".to_owned(),
        )
    }

    #[test]
    fn validates_text_instances() {
        assert!(validate_texts(&[valid_text()]).is_ok());

        let mut invalid = valid_text();
        invalid.5 = 0.0;
        assert!(validate_texts(&[invalid]).is_err());

        let mut invalid_color = valid_text();
        invalid_color.8 = 1.5;
        assert!(validate_texts(&[invalid_color]).is_err());
    }
}
