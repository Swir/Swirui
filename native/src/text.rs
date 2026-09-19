use glyphon::{
    Attrs, Buffer, Cache, Color, Family, FontSystem, Metrics, Resolution, Shaping, SwashCache,
    TextArea, TextAtlas, TextBounds, TextRenderer, Viewport,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

pub(crate) type ClipRect = (f32, f32, f32, f32);
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
    ClipRect,
);

const MAX_RASTER_PIXELS: usize = 16_777_216;

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
                _clip,
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
                clip,
            ) = text;
            let left = (*x).max(clip.0);
            let top = (*y).max(clip.1);
            let right = (*x + *width).min(clip.2);
            let bottom = (*y + *height).min(clip.3);
            TextArea {
                buffer,
                left: *x,
                top: *y,
                scale: 1.0,
                bounds: TextBounds {
                    left: float_to_i32(left),
                    top: float_to_i32(top),
                    right: float_to_i32(right),
                    bottom: float_to_i32(bottom),
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

pub(crate) fn rasterize_text_rgba(
    content: &str,
    width: u32,
    height: u32,
    font_size: f32,
    red: f32,
    green: f32,
    blue: f32,
    alpha: f32,
    family: &str,
) -> PyResult<Vec<u8>> {
    let byte_len = validate_raster_request(
        content, width, height, font_size, red, green, blue, alpha, family,
    )?;
    let mut rgba = vec![0_u8; byte_len];
    let mut font_system = FontSystem::new();
    let mut swash_cache = SwashCache::new();
    let metrics = Metrics::new(font_size, font_size * 1.25);
    let mut buffer = Buffer::new(&mut font_system, metrics);
    buffer.set_size(Some(width as f32), Some(height as f32));
    let attrs = Attrs::new().family(Family::Name(family));
    buffer.set_text(content, &attrs, Shaping::Advanced, None);
    let base_color = Color::rgba(
        channel_to_u8(red),
        channel_to_u8(green),
        channel_to_u8(blue),
        255,
    );
    buffer.draw(
        &mut font_system,
        &mut swash_cache,
        base_color,
        |x, y, glyph_width, glyph_height, color| {
            let (source_red, source_green, source_blue, source_alpha) = color.as_rgba_tuple();
            let source_alpha = ((f32::from(source_alpha) * alpha).round()).clamp(0.0, 255.0) as u8;
            if source_alpha == 0 {
                return;
            }
            for offset_y in 0..glyph_height {
                let pixel_y = i64::from(y) + i64::from(offset_y);
                if pixel_y < 0 || pixel_y >= i64::from(height) {
                    continue;
                }
                for offset_x in 0..glyph_width {
                    let pixel_x = i64::from(x) + i64::from(offset_x);
                    if pixel_x < 0 || pixel_x >= i64::from(width) {
                        continue;
                    }
                    let pixel_index = ((pixel_y as usize * width as usize) + pixel_x as usize) * 4;
                    blend_rgba_pixel(
                        &mut rgba[pixel_index..pixel_index + 4],
                        (source_red, source_green, source_blue, source_alpha),
                    );
                }
            }
        },
    );
    Ok(rgba)
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
            clip,
        ) = text;
        if content.is_empty() {
            return Err(PyValueError::new_err("Text content cannot be empty."));
        }
        if family.is_empty() {
            return Err(PyValueError::new_err("Text font family cannot be empty."));
        }
        if ![
            *x, *y, *width, *height, *font_size, *red, *green, *blue, *alpha, clip.0, clip.1,
            clip.2, clip.3,
        ]
        .into_iter()
        .all(f32::is_finite)
        {
            return Err(PyValueError::new_err(
                "Text geometry, size, color channels and clip bounds must be finite.",
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
        if clip.2 <= clip.0 || clip.3 <= clip.1 {
            return Err(PyValueError::new_err(
                "Text clip bounds must have positive width and height.",
            ));
        }
        if (*x + *width).min(clip.2) <= (*x).max(clip.0)
            || (*y + *height).min(clip.3) <= (*y).max(clip.1)
        {
            return Err(PyValueError::new_err(
                "Text clip must intersect the text bounds.",
            ));
        }
    }
    Ok(())
}

fn validate_raster_request(
    content: &str,
    width: u32,
    height: u32,
    font_size: f32,
    red: f32,
    green: f32,
    blue: f32,
    alpha: f32,
    family: &str,
) -> PyResult<usize> {
    if content.is_empty() {
        return Err(PyValueError::new_err("Text content cannot be empty."));
    }
    if family.trim().is_empty() {
        return Err(PyValueError::new_err("Text font family cannot be empty."));
    }
    if width == 0 || height == 0 {
        return Err(PyValueError::new_err(
            "Text raster dimensions must be greater than zero.",
        ));
    }
    if !font_size.is_finite() || font_size <= 0.0 || !(font_size * 1.25).is_finite() {
        return Err(PyValueError::new_err(
            "Text raster font size must be finite and greater than zero.",
        ));
    }
    if [red, green, blue, alpha]
        .into_iter()
        .any(|channel| !channel.is_finite() || !(0.0..=1.0).contains(&channel))
    {
        return Err(PyValueError::new_err(
            "Text raster color channels must be finite and between 0.0 and 1.0.",
        ));
    }
    let pixels = (width as usize)
        .checked_mul(height as usize)
        .ok_or_else(|| PyValueError::new_err("Text raster dimensions are too large."))?;
    if pixels > MAX_RASTER_PIXELS {
        return Err(PyValueError::new_err(format!(
            "Text raster exceeds the {MAX_RASTER_PIXELS}-pixel safety limit."
        )));
    }
    pixels
        .checked_mul(4)
        .ok_or_else(|| PyValueError::new_err("Text raster byte size overflowed."))
}

fn blend_rgba_pixel(destination: &mut [u8], source: (u8, u8, u8, u8)) {
    let source_alpha = f32::from(source.3) / 255.0;
    if source_alpha <= 0.0 {
        return;
    }
    let destination_alpha = f32::from(destination[3]) / 255.0;
    let output_alpha = source_alpha + destination_alpha * (1.0 - source_alpha);
    if output_alpha <= f32::EPSILON {
        destination.fill(0);
        return;
    }
    for channel in 0..3 {
        let source_premultiplied =
            f32::from([source.0, source.1, source.2][channel]) / 255.0 * source_alpha;
        let destination_premultiplied =
            f32::from(destination[channel]) / 255.0 * destination_alpha;
        let output = (source_premultiplied
            + destination_premultiplied * (1.0 - source_alpha))
            / output_alpha;
        destination[channel] = (output * 255.0).round().clamp(0.0, 255.0) as u8;
    }
    destination[3] = (output_alpha * 255.0).round().clamp(0.0, 255.0) as u8;
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
            (0.0, 0.0, 640.0, 480.0),
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

        let mut disjoint_clip = valid_text();
        disjoint_clip.11 = (500.0, 500.0, 600.0, 600.0);
        assert!(validate_texts(&[disjoint_clip]).is_err());
    }

    #[test]
    fn validates_raster_requests_and_limits_allocation() {
        assert_eq!(
            validate_raster_request(
                "SwirUI",
                128,
                48,
                22.0,
                0.2,
                0.8,
                1.0,
                1.0,
                "Segoe UI",
            )
            .expect("valid raster request"),
            128 * 48 * 4
        );
        assert!(
            validate_raster_request("", 128, 48, 22.0, 1.0, 1.0, 1.0, 1.0, "Segoe UI").is_err()
        );
        assert!(
            validate_raster_request("SwirUI", 0, 48, 22.0, 1.0, 1.0, 1.0, 1.0, "Segoe UI")
                .is_err()
        );
        assert!(
            validate_raster_request(
                "SwirUI",
                16_384,
                16_384,
                22.0,
                1.0,
                1.0,
                1.0,
                1.0,
                "Segoe UI",
            )
            .is_err()
        );
    }

    #[test]
    fn alpha_blending_preserves_straight_rgba() {
        let mut destination = [0_u8, 0, 255, 128];
        blend_rgba_pixel(&mut destination, (255, 0, 0, 128));
        assert_eq!(destination[3], 192);
        assert!((i16::from(destination[0]) - 170).abs() <= 1);
        assert_eq!(destination[1], 0);
        assert!((i16::from(destination[2]) - 85).abs() <= 1);
    }
}
