//! Media decoding primitives for Python-first Image/SVG/GIF resources.

use std::io::Cursor;

use image::AnimationDecoder;

const MAX_INPUT_BYTES: usize = 64 * 1024 * 1024;
const MAX_DIMENSION: u32 = 16_384;
const MAX_PIXELS: u64 = 67_108_864;
const MAX_GIF_FRAMES: usize = 512;

pub(crate) type DecodedFrame = (u32, u32, u32, Vec<u8>);

fn validate_input(data: &[u8]) -> Result<(), String> {
    if data.is_empty() {
        return Err("Media payload cannot be empty.".to_owned());
    }
    if data.len() > MAX_INPUT_BYTES {
        return Err(format!(
            "Media payload exceeds the {MAX_INPUT_BYTES}-byte safety limit."
        ));
    }
    Ok(())
}

fn validate_dimensions(width: u32, height: u32) -> Result<(), String> {
    if width == 0 || height == 0 {
        return Err("Decoded media dimensions must be greater than zero.".to_owned());
    }
    if width > MAX_DIMENSION || height > MAX_DIMENSION {
        return Err(format!(
            "Decoded media dimensions exceed the {MAX_DIMENSION}px per-axis safety limit."
        ));
    }
    if u64::from(width) * u64::from(height) > MAX_PIXELS {
        return Err(format!(
            "Decoded media exceeds the {MAX_PIXELS}-pixel safety limit."
        ));
    }
    Ok(())
}

pub(crate) fn decode_image_rgba(data: &[u8]) -> Result<(u32, u32, Vec<u8>), String> {
    validate_input(data)?;
    let decoded = image::load_from_memory(data)
        .map_err(|error| format!("Unable to decode raster image: {error}"))?;
    let rgba = decoded.to_rgba8();
    let (width, height) = rgba.dimensions();
    validate_dimensions(width, height)?;
    Ok((width, height, rgba.into_raw()))
}

pub(crate) fn decode_gif_rgba_frames(data: &[u8]) -> Result<Vec<DecodedFrame>, String> {
    validate_input(data)?;
    let decoder = image::codecs::gif::GifDecoder::new(Cursor::new(data))
        .map_err(|error| format!("Unable to decode GIF header: {error}"))?;
    let mut decoded = Vec::new();

    for frame in decoder.into_frames() {
        if decoded.len() >= MAX_GIF_FRAMES {
            return Err(format!(
                "GIF exceeds the {MAX_GIF_FRAMES}-frame safety limit."
            ));
        }
        let frame = frame.map_err(|error| format!("Unable to decode GIF frame: {error}"))?;
        let delay = frame.delay();
        let (numerator, denominator) = delay.numer_denom_ms();
        let duration_ms = if denominator == 0 {
            numerator
        } else {
            numerator.saturating_add(denominator / 2) / denominator
        };
        let rgba = frame.into_buffer();
        let (width, height) = rgba.dimensions();
        validate_dimensions(width, height)?;
        decoded.push((width, height, duration_ms, rgba.into_raw()));
    }

    if decoded.is_empty() {
        return Err("GIF payload did not contain any frames.".to_owned());
    }
    Ok(decoded)
}

pub(crate) fn decode_svg_rgba(
    data: &[u8],
    requested_width: Option<u32>,
    requested_height: Option<u32>,
) -> Result<(u32, u32, Vec<u8>), String> {
    validate_input(data)?;
    if matches!(requested_width, Some(0)) || matches!(requested_height, Some(0)) {
        return Err("Requested SVG dimensions must be greater than zero.".to_owned());
    }

    let options = usvg::Options::default();
    let tree = usvg::Tree::from_data(data, &options)
        .map_err(|error| format!("Unable to parse SVG: {error}"))?;
    let source = tree.size();
    let source_width = source.width();
    let source_height = source.height();
    if !source_width.is_finite()
        || !source_height.is_finite()
        || source_width <= 0.0
        || source_height <= 0.0
    {
        return Err("SVG must declare a finite non-zero intrinsic size or viewBox.".to_owned());
    }

    let intrinsic_width = source_width.ceil().max(1.0) as u32;
    let intrinsic_height = source_height.ceil().max(1.0) as u32;
    let (width, height) = match (requested_width, requested_height) {
        (Some(width), Some(height)) => (width, height),
        (Some(width), None) => {
            let height = ((width as f32 / source_width) * source_height)
                .round()
                .max(1.0) as u32;
            (width, height)
        }
        (None, Some(height)) => {
            let width = ((height as f32 / source_height) * source_width)
                .round()
                .max(1.0) as u32;
            (width, height)
        }
        (None, None) => (intrinsic_width, intrinsic_height),
    };
    validate_dimensions(width, height)?;

    let mut pixmap = tiny_skia::Pixmap::new(width, height)
        .ok_or_else(|| "Unable to allocate SVG raster target.".to_owned())?;
    let transform = tiny_skia::Transform::from_scale(
        width as f32 / source_width,
        height as f32 / source_height,
    );
    resvg::render(&tree, transform, &mut pixmap.as_mut());
    Ok((width, height, pixmap.data().to_vec()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rasterizes_svg_to_requested_rgba_size() {
        let svg = br##"<svg xmlns="http://www.w3.org/2000/svg" width="4" height="2"><rect width="4" height="2" fill="#ff0000"/></svg>"##;
        let (width, height, rgba) = decode_svg_rgba(svg, Some(8), Some(4)).unwrap();
        assert_eq!((width, height), (8, 4));
        assert_eq!(rgba.len(), 8 * 4 * 4);
        assert_eq!(&rgba[0..4], &[255, 0, 0, 255]);
    }

    #[test]
    fn rejects_empty_media_payloads() {
        assert!(decode_image_rgba(&[]).is_err());
        assert!(decode_gif_rgba_frames(&[]).is_err());
        assert!(decode_svg_rgba(&[], None, None).is_err());
    }
}
