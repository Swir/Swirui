use glyphon::{
    Attrs, Buffer, Cache, Color, Family, FontSystem, Metrics, Resolution, Shaping, SwashCache,
    TextArea, TextAtlas, TextBounds, TextRenderer, Viewport,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

pub(crate) type ClipRect = (f32, f32, f32, f32);
pub(crate) type PlainTextInstance = (
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

pub(crate) type TextColorSpan = (usize, usize, f32, f32, f32, f32);

#[derive(Clone, FromPyObject)]
pub(crate) enum TextInstance {
    #[pyo3(transparent)]
    Plain(PlainTextInstance),
    Rich(PlainTextInstance, Vec<TextColorSpan>),
}

impl TextInstance {
    fn base(&self) -> &PlainTextInstance {
        match self {
            Self::Plain(base) | Self::Rich(base, _) => base,
        }
    }
    fn spans(&self) -> &[TextColorSpan] {
        match self {
            Self::Plain(_) => &[],
            Self::Rich(_, spans) => spans,
        }
    }
}

fn validate_spans(content: &str, spans: &[TextColorSpan]) -> PyResult<()> {
    if spans.is_empty() {
        return Ok(());
    }
    if spans.len() > 4096 {
        return Err(PyValueError::new_err(
            "Text supports at most 4096 color spans per node.",
        ));
    }
    let length = content.chars().count();
    let mut previous = 0;
    for &(start, end, r, g, b, a) in spans {
        if start < previous || start >= end || end > length {
            return Err(PyValueError::new_err(
                "Color spans must be ordered, disjoint scalar ranges within the text.",
            ));
        }
        if [r, g, b, a]
            .into_iter()
            .any(|v| !v.is_finite() || !(0.0..=1.0).contains(&v))
        {
            return Err(PyValueError::new_err(
                "Text span colors must be finite channels in 0..1.",
            ));
        }
        previous = end;
    }
    Ok(())
}

fn set_buffer_text(buffer: &mut Buffer, content: &str, attrs: &Attrs, spans: &[TextColorSpan]) {
    if spans.is_empty() {
        buffer.set_text(content, attrs, Shaping::Advanced, None);
        return;
    }
    let bytes: Vec<usize> = content
        .char_indices()
        .map(|(i, _)| i)
        .chain(std::iter::once(content.len()))
        .collect();
    let mut runs = Vec::with_capacity(spans.len() * 2 + 1);
    let mut previous = 0;
    for &(start, end, r, g, b, a) in spans {
        if bytes[start] > previous {
            runs.push((&content[previous..bytes[start]], attrs.clone()));
        }
        let color = Color::rgba(
            channel_to_u8(r),
            channel_to_u8(g),
            channel_to_u8(b),
            channel_to_u8(a),
        );
        runs.push((
            &content[bytes[start]..bytes[end]],
            attrs.clone().color(color),
        ));
        previous = bytes[end];
    }
    if previous < content.len() {
        runs.push((&content[previous..], attrs.clone()));
    }
    buffer.set_rich_text(runs, attrs, Shaping::Advanced, None);
}

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
        let renderer =
            TextRenderer::new(&mut atlas, device, wgpu::MultisampleState::default(), None);

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
            ) = text.base();
            let metrics = Metrics::new(*font_size, *font_size * 1.25);
            let mut buffer = Buffer::new(&mut self.font_system, metrics);
            buffer.set_size(Some(*width), Some(*height));
            let attrs = Attrs::new().family(Family::Name(family.as_str()));
            set_buffer_text(&mut buffer, content, &attrs, text.spans());
            buffer.shape_until_scroll(&mut self.font_system, false);
            buffers.push(buffer);
        }

        let areas =
            buffers.iter().zip(texts.iter()).map(|(buffer, text)| {
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
                ) = text.base();
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
    spans: &[TextColorSpan],
) -> PyResult<Vec<u8>> {
    let byte_len = validate_raster_request(
        content, width, height, font_size, red, green, blue, alpha, family,
    )?;
    validate_spans(content, spans)?;
    let mut rgba = vec![0_u8; byte_len];
    let mut font_system = FontSystem::new();
    let mut swash_cache = SwashCache::new();
    let metrics = Metrics::new(font_size, font_size * 1.25);
    let mut buffer = Buffer::new(&mut font_system, metrics);
    buffer.set_size(Some(width as f32), Some(height as f32));
    let attrs = Attrs::new().family(Family::Name(family));
    set_buffer_text(&mut buffer, content, &attrs, spans);
    let base_color = Color::rgba(
        channel_to_u8(red),
        channel_to_u8(green),
        channel_to_u8(blue),
        if spans.is_empty() {
            255
        } else {
            channel_to_u8(alpha)
        },
    );
    buffer.shape_until_scroll(&mut font_system, false);
    for run in buffer.layout_runs() {
        for glyph in run.glyphs {
            let physical = glyph.physical((0.0, run.line_y), 1.0);
            let glyph_color = glyph.color_opt.unwrap_or(base_color);
            let opacity = if spans.is_empty() {
                alpha
            } else {
                f32::from(glyph_color.a()) / 255.0
            };
            // cosmic-text's SwashCache returns coverage (including color glyphs)
            // without applying the attribute alpha. Apply it once per glyph.
            swash_cache.with_pixels(
                &mut font_system,
                physical.cache_key,
                glyph_color,
                |x, y, color| {
                    let pixel_x = i64::from(physical.x) + i64::from(x);
                    let pixel_y = i64::from(physical.y) + i64::from(y);
                    if pixel_x < 0
                        || pixel_x >= i64::from(width)
                        || pixel_y < 0
                        || pixel_y >= i64::from(height)
                    {
                        return;
                    }
                    let (r, g, b, a) = color.as_rgba_tuple();
                    let a = (f32::from(a) * opacity).round().clamp(0.0, 255.0) as u8;
                    if a == 0 {
                        return;
                    }
                    let pixel_index = ((pixel_y as usize * width as usize) + pixel_x as usize) * 4;
                    blend_rgba_pixel(&mut rgba[pixel_index..pixel_index + 4], (r, g, b, a));
                },
            );
        }
    }
    Ok(rgba)
}

pub(crate) fn validate_texts(texts: &[TextInstance]) -> PyResult<()> {
    for text in texts {
        validate_spans(&text.base().0, text.spans())?;
        let (content, x, y, width, height, font_size, red, green, blue, alpha, family, clip) =
            text.base();
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
        let destination_premultiplied = f32::from(destination[channel]) / 255.0 * destination_alpha;
        let output = (source_premultiplied + destination_premultiplied * (1.0 - source_alpha))
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

    fn valid_text() -> PlainTextInstance {
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
        assert!(validate_texts(&[TextInstance::Plain(valid_text())]).is_ok());

        let mut invalid = valid_text();
        invalid.5 = 0.0;
        assert!(validate_texts(&[TextInstance::Plain(invalid)]).is_err());

        let mut invalid_color = valid_text();
        invalid_color.8 = 1.5;
        assert!(validate_texts(&[TextInstance::Plain(invalid_color)]).is_err());

        let mut disjoint_clip = valid_text();
        disjoint_clip.11 = (500.0, 500.0, 600.0, 600.0);
        assert!(validate_texts(&[TextInstance::Plain(disjoint_clip)]).is_err());
    }

    #[test]
    fn validates_raster_requests_and_limits_allocation() {
        assert_eq!(
            validate_raster_request("SwirUI", 128, 48, 22.0, 0.2, 0.8, 1.0, 1.0, "Segoe UI",)
                .expect("valid raster request"),
            128 * 48 * 4
        );
        assert!(
            validate_raster_request("", 128, 48, 22.0, 1.0, 1.0, 1.0, 1.0, "Segoe UI").is_err()
        );
        assert!(
            validate_raster_request("SwirUI", 0, 48, 22.0, 1.0, 1.0, 1.0, 1.0, "Segoe UI").is_err()
        );
        assert!(
            validate_raster_request(
                "SwirUI", 16_384, 16_384, 22.0, 1.0, 1.0, 1.0, 1.0, "Segoe UI",
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

    #[test]
    fn validates_rich_text_scalar_ranges_and_color_channels() {
        assert!(validate_spans("Aé😀", &[(1, 3, 1.0, 0.0, 0.0, 0.5)]).is_ok());
        assert!(validate_spans("Aé😀", &[(1, 4, 1.0, 0.0, 0.0, 1.0)]).is_err());
        assert!(
            validate_spans(
                "abc",
                &[(0, 2, 1.0, 0.0, 0.0, 1.0), (1, 3, 0.0, 1.0, 0.0, 1.0)]
            )
            .is_err()
        );
        assert!(validate_spans("abc", &[(0, 1, f32::NAN, 0.0, 0.0, 1.0)]).is_err());
    }
}
