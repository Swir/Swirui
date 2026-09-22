//! Media decoding primitives for Python-first Image/SVG/GIF/Lottie resources.

use std::io::Cursor;

use image::AnimationDecoder;
use serde_json::Value;
use tiny_skia::{FillRule, Paint, PathBuilder, Pixmap, Rect, Transform};

const MAX_INPUT_BYTES: usize = 64 * 1024 * 1024;
const MAX_DIMENSION: u32 = 16_384;
const MAX_PIXELS: u64 = 67_108_864;
const MAX_GIF_FRAMES: usize = 512;
const MAX_LOTTIE_BYTES: usize = 8 * 1024 * 1024;
const MAX_LOTTIE_LAYERS: usize = 512;

pub(crate) type DecodedFrame = (u32, u32, u32, Vec<u8>);
pub(crate) type LottieMetadata = (u32, u32, f64, f64, f64, usize);

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

    let mut pixmap = Pixmap::new(width, height)
        .ok_or_else(|| "Unable to allocate SVG raster target.".to_owned())?;
    let transform = Transform::from_scale(
        width as f32 / source_width,
        height as f32 / source_height,
    );
    resvg::render(&tree, transform, &mut pixmap.as_mut());
    Ok((width, height, pixmap.data().to_vec()))
}

pub(crate) fn parse_lottie_metadata(data: &[u8]) -> Result<LottieMetadata, String> {
    let root = parse_lottie_root(data)?;
    metadata_from_root(&root)
}

pub(crate) fn render_lottie_frame_rgba(
    data: &[u8],
    frame: f64,
    requested_width: Option<u32>,
    requested_height: Option<u32>,
) -> Result<(u32, u32, Vec<u8>), String> {
    if !frame.is_finite() {
        return Err("Lottie frame must be finite.".to_owned());
    }
    let root = parse_lottie_root(data)?;
    let (source_width, source_height, _, in_point, out_point, _) = metadata_from_root(&root)?;
    let (width, height) = target_dimensions(
        source_width,
        source_height,
        requested_width,
        requested_height,
    )?;
    let layers = root
        .get("layers")
        .and_then(Value::as_array)
        .ok_or_else(|| "Lottie composition requires a layers array.".to_owned())?;
    if !layers.iter().any(is_supported_layer) {
        return Err(
            "Lottie composition has no currently supported solid or flat rectangle/ellipse shape layers."
                .to_owned(),
        );
    }

    let sample_frame = frame.clamp(in_point, (out_point - f64::EPSILON).max(in_point));
    let mut pixmap = Pixmap::new(width, height)
        .ok_or_else(|| "Unable to allocate Lottie raster target.".to_owned())?;
    let output_scale_x = width as f32 / source_width as f32;
    let output_scale_y = height as f32 / source_height as f32;

    for layer in layers.iter().rev() {
        let layer_in = layer.get("ip").and_then(Value::as_f64).unwrap_or(in_point);
        let layer_out = layer.get("op").and_then(Value::as_f64).unwrap_or(out_point);
        if sample_frame < layer_in || sample_frame >= layer_out {
            continue;
        }
        match layer.get("ty").and_then(Value::as_i64) {
            Some(1) => render_solid_layer(
                &mut pixmap,
                layer,
                sample_frame,
                output_scale_x,
                output_scale_y,
            ),
            Some(4) => render_shape_layer(
                &mut pixmap,
                layer,
                sample_frame,
                output_scale_x,
                output_scale_y,
            ),
            _ => {}
        }
    }

    Ok((width, height, pixmap.data().to_vec()))
}

fn parse_lottie_root(data: &[u8]) -> Result<Value, String> {
    validate_input(data)?;
    if data.len() > MAX_LOTTIE_BYTES {
        return Err(format!(
            "Lottie JSON exceeds the {MAX_LOTTIE_BYTES}-byte safety limit."
        ));
    }
    let root: Value = serde_json::from_slice(data)
        .map_err(|error| format!("Unable to parse Lottie JSON: {error}"))?;
    if !root.is_object() {
        return Err("Lottie payload root must be a JSON object.".to_owned());
    }
    Ok(root)
}

fn metadata_from_root(root: &Value) -> Result<LottieMetadata, String> {
    let width = required_dimension(root, "w")?;
    let height = required_dimension(root, "h")?;
    validate_dimensions(width, height)?;
    let frame_rate = required_number(root, "fr")?;
    let in_point = required_number(root, "ip")?;
    let out_point = required_number(root, "op")?;
    if !frame_rate.is_finite() || frame_rate <= 0.0 || frame_rate > 1000.0 {
        return Err("Lottie frame rate must be finite and in the range (0, 1000].".to_owned());
    }
    if !in_point.is_finite() || !out_point.is_finite() || out_point <= in_point {
        return Err("Lottie out point must be finite and greater than its in point.".to_owned());
    }
    let layers = root
        .get("layers")
        .and_then(Value::as_array)
        .ok_or_else(|| "Lottie composition requires a layers array.".to_owned())?;
    if layers.len() > MAX_LOTTIE_LAYERS {
        return Err(format!(
            "Lottie composition exceeds the {MAX_LOTTIE_LAYERS}-layer safety limit."
        ));
    }
    Ok((width, height, frame_rate, in_point, out_point, layers.len()))
}

fn required_number(root: &Value, key: &str) -> Result<f64, String> {
    root.get(key)
        .and_then(Value::as_f64)
        .ok_or_else(|| format!("Lottie field {key:?} must be numeric."))
}

fn required_dimension(root: &Value, key: &str) -> Result<u32, String> {
    let value = required_number(root, key)?;
    if !value.is_finite() || value <= 0.0 || value.fract() != 0.0 || value > f64::from(u32::MAX) {
        return Err(format!("Lottie field {key:?} must be a positive integer dimension."));
    }
    Ok(value as u32)
}

fn target_dimensions(
    source_width: u32,
    source_height: u32,
    requested_width: Option<u32>,
    requested_height: Option<u32>,
) -> Result<(u32, u32), String> {
    if matches!(requested_width, Some(0)) || matches!(requested_height, Some(0)) {
        return Err("Requested Lottie dimensions must be greater than zero.".to_owned());
    }
    let (width, height) = match (requested_width, requested_height) {
        (Some(width), Some(height)) => (width, height),
        (Some(width), None) => {
            let height = ((f64::from(width) / f64::from(source_width)) * f64::from(source_height))
                .round()
                .max(1.0) as u32;
            (width, height)
        }
        (None, Some(height)) => {
            let width = ((f64::from(height) / f64::from(source_height)) * f64::from(source_width))
                .round()
                .max(1.0) as u32;
            (width, height)
        }
        (None, None) => (source_width, source_height),
    };
    validate_dimensions(width, height)?;
    Ok((width, height))
}

fn is_supported_layer(layer: &Value) -> bool {
    match layer.get("ty").and_then(Value::as_i64) {
        Some(1) => true,
        Some(4) => layer
            .get("shapes")
            .and_then(Value::as_array)
            .is_some_and(|shapes| {
                shapes.iter().any(|shape| {
                    matches!(shape.get("ty").and_then(Value::as_str), Some("rc" | "el"))
                })
            }),
        _ => false,
    }
}

#[derive(Clone, Copy)]
struct AxisTransform {
    position: (f32, f32),
    anchor: (f32, f32),
    scale: (f32, f32),
    opacity: f32,
    rotation: f32,
}

fn sampled_transform(value: &Value, frame: f64) -> AxisTransform {
    AxisTransform {
        position: sample_vec2(&value["p"], frame, (0.0, 0.0)),
        anchor: sample_vec2(&value["a"], frame, (0.0, 0.0)),
        scale: {
            let sampled = sample_vec2(&value["s"], frame, (100.0, 100.0));
            (sampled.0 / 100.0, sampled.1 / 100.0)
        },
        opacity: (sample_scalar(&value["o"], frame, 100.0) / 100.0).clamp(0.0, 1.0),
        rotation: sample_scalar(&value["r"], frame, 0.0),
    }
}

fn apply_transform(point: (f32, f32), transform: AxisTransform) -> (f32, f32) {
    (
        (point.0 - transform.anchor.0) * transform.scale.0 + transform.position.0,
        (point.1 - transform.anchor.1) * transform.scale.1 + transform.position.1,
    )
}

fn render_solid_layer(
    pixmap: &mut Pixmap,
    layer: &Value,
    frame: f64,
    output_scale_x: f32,
    output_scale_y: f32,
) {
    let transform = sampled_transform(&layer["ks"], frame);
    if transform.rotation.abs() > f32::EPSILON || transform.opacity <= 0.0 {
        return;
    }
    let Some(solid_width) = layer.get("sw").and_then(Value::as_f64) else {
        return;
    };
    let Some(solid_height) = layer.get("sh").and_then(Value::as_f64) else {
        return;
    };
    if solid_width <= 0.0 || solid_height <= 0.0 {
        return;
    }
    let Some((red, green, blue)) = layer
        .get("sc")
        .and_then(Value::as_str)
        .and_then(parse_hex_rgb)
    else {
        return;
    };
    let top_left = apply_transform((0.0, 0.0), transform);
    let width = solid_width as f32 * transform.scale.0.abs() * output_scale_x;
    let height = solid_height as f32 * transform.scale.1.abs() * output_scale_y;
    let Some(rect) = Rect::from_xywh(
        top_left.0 * output_scale_x,
        top_left.1 * output_scale_y,
        width,
        height,
    ) else {
        return;
    };
    let mut paint = Paint::default();
    paint.anti_alias = true;
    paint.set_color_rgba8(red, green, blue, alpha_u8(transform.opacity));
    pixmap.fill_rect(rect, &paint, Transform::identity(), None);
}

fn render_shape_layer(
    pixmap: &mut Pixmap,
    layer: &Value,
    frame: f64,
    output_scale_x: f32,
    output_scale_y: f32,
) {
    let Some(shapes) = layer.get("shapes").and_then(Value::as_array) else {
        return;
    };
    let layer_transform = sampled_transform(&layer["ks"], frame);
    if layer_transform.rotation.abs() > f32::EPSILON || layer_transform.opacity <= 0.0 {
        return;
    }
    let shape_transform = shapes
        .iter()
        .find(|shape| shape.get("ty").and_then(Value::as_str) == Some("tr"))
        .map_or(
            AxisTransform {
                position: (0.0, 0.0),
                anchor: (0.0, 0.0),
                scale: (1.0, 1.0),
                opacity: 1.0,
                rotation: 0.0,
            },
            |shape| sampled_transform(shape, frame),
        );
    if shape_transform.rotation.abs() > f32::EPSILON || shape_transform.opacity <= 0.0 {
        return;
    }
    let Some(fill) = shapes
        .iter()
        .find(|shape| shape.get("ty").and_then(Value::as_str) == Some("fl"))
    else {
        return;
    };
    let color = sample_color(&fill["c"], frame, (0, 0, 0, 255));
    let fill_opacity = (sample_scalar(&fill["o"], frame, 100.0) / 100.0).clamp(0.0, 1.0);
    let opacity = layer_transform.opacity * shape_transform.opacity * fill_opacity;
    if opacity <= 0.0 {
        return;
    }
    let mut paint = Paint::default();
    paint.anti_alias = true;
    let alpha = ((f32::from(color.3) / 255.0) * opacity).clamp(0.0, 1.0);
    paint.set_color_rgba8(color.0, color.1, color.2, alpha_u8(alpha));

    for shape in shapes {
        let Some(kind) = shape.get("ty").and_then(Value::as_str) else {
            continue;
        };
        if !matches!(kind, "rc" | "el") {
            continue;
        }
        let center = sample_vec2(&shape["p"], frame, (0.0, 0.0));
        let size = sample_vec2(&shape["s"], frame, (0.0, 0.0));
        if size.0 <= 0.0 || size.1 <= 0.0 {
            continue;
        }
        let center = apply_transform(center, shape_transform);
        let center = apply_transform(center, layer_transform);
        let width = size.0.abs()
            * shape_transform.scale.0.abs()
            * layer_transform.scale.0.abs()
            * output_scale_x;
        let height = size.1.abs()
            * shape_transform.scale.1.abs()
            * layer_transform.scale.1.abs()
            * output_scale_y;
        let Some(rect) = Rect::from_xywh(
            center.0 * output_scale_x - width / 2.0,
            center.1 * output_scale_y - height / 2.0,
            width,
            height,
        ) else {
            continue;
        };
        if kind == "rc" {
            pixmap.fill_rect(rect, &paint, Transform::identity(), None);
        } else {
            let mut builder = PathBuilder::new();
            builder.push_oval(rect);
            if let Some(path) = builder.finish() {
                pixmap.fill_path(
                    &path,
                    &paint,
                    FillRule::Winding,
                    Transform::identity(),
                    None,
                );
            }
        }
    }
}

fn sample_scalar(property: &Value, frame: f64, default: f32) -> f32 {
    sample_component(property, frame, 0).unwrap_or(f64::from(default)) as f32
}

fn sample_vec2(property: &Value, frame: f64, default: (f32, f32)) -> (f32, f32) {
    (
        sample_component(property, frame, 0).unwrap_or(f64::from(default.0)) as f32,
        sample_component(property, frame, 1).unwrap_or(f64::from(default.1)) as f32,
    )
}

fn sample_color(property: &Value, frame: f64, default: (u8, u8, u8, u8)) -> (u8, u8, u8, u8) {
    let component = |index: usize, fallback: u8| {
        sample_component(property, frame, index)
            .map(|value| (value.clamp(0.0, 1.0) * 255.0).round() as u8)
            .unwrap_or(fallback)
    };
    (
        component(0, default.0),
        component(1, default.1),
        component(2, default.2),
        component(3, default.3),
    )
}

fn sample_component(property: &Value, frame: f64, component: usize) -> Option<f64> {
    let key = property.get("k").unwrap_or(property);
    if let Some(number) = key.as_f64() {
        return (component == 0).then_some(number);
    }
    let values = key.as_array()?;
    let animated = values
        .first()
        .is_some_and(|value| value.get("t").and_then(Value::as_f64).is_some());
    if !animated {
        return values.get(component).and_then(Value::as_f64);
    }

    let mut current = values.first()?;
    let mut next: Option<&Value> = None;
    for candidate in values.iter().skip(1) {
        if candidate
            .get("t")
            .and_then(Value::as_f64)
            .is_some_and(|time| time > frame)
        {
            next = Some(candidate);
            break;
        }
        current = candidate;
    }
    let start = component_from_value(current.get("s")?, component)?;
    let Some(next_keyframe) = next else {
        return Some(start);
    };
    let end = current
        .get("e")
        .and_then(|value| component_from_value(value, component))
        .or_else(|| {
            next_keyframe
                .get("s")
                .and_then(|value| component_from_value(value, component))
        })
        .unwrap_or(start);
    let start_time = current.get("t").and_then(Value::as_f64).unwrap_or(frame);
    let end_time = next_keyframe
        .get("t")
        .and_then(Value::as_f64)
        .unwrap_or(start_time);
    if end_time <= start_time {
        return Some(start);
    }
    let ratio = ((frame - start_time) / (end_time - start_time)).clamp(0.0, 1.0);
    Some(start + (end - start) * ratio)
}

fn component_from_value(value: &Value, component: usize) -> Option<f64> {
    if let Some(number) = value.as_f64() {
        return (component == 0).then_some(number);
    }
    value.as_array()?.get(component)?.as_f64()
}

fn parse_hex_rgb(value: &str) -> Option<(u8, u8, u8)> {
    let hex = value.strip_prefix('#').unwrap_or(value);
    if hex.len() != 6 {
        return None;
    }
    Some((
        u8::from_str_radix(&hex[0..2], 16).ok()?,
        u8::from_str_radix(&hex[2..4], 16).ok()?,
        u8::from_str_radix(&hex[4..6], 16).ok()?,
    ))
}

fn alpha_u8(opacity: f32) -> u8 {
    (opacity.clamp(0.0, 1.0) * 255.0).round() as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    const LOTTIE_SOLID: &[u8] = br##"{
        "v":"5.7.4","fr":30,"ip":0,"op":30,"w":20,"h":10,
        "layers":[{
            "ty":1,"ip":0,"op":30,"sw":4,"sh":4,"sc":"#ff0000",
            "ks":{
                "p":{"a":1,"k":[{"t":0,"s":[2,2,0]},{"t":30,"s":[12,2,0]}]},
                "a":{"a":0,"k":[0,0,0]},
                "s":{"a":0,"k":[100,100,100]},
                "o":{"a":0,"k":100}
            }
        }]
    }"##;

    #[test]
    fn rasterizes_svg_to_requested_rgba_size() {
        let svg = br##"<svg xmlns="http://www.w3.org/2000/svg" width="4" height="2"><rect width="4" height="2" fill="#ff0000"/></svg>"##;
        let (width, height, rgba) = decode_svg_rgba(svg, Some(8), Some(4)).unwrap();
        assert_eq!((width, height), (8, 4));
        assert_eq!(rgba.len(), 8 * 4 * 4);
        assert_eq!(&rgba[0..4], &[255, 0, 0, 255]);
    }

    #[test]
    fn parses_lottie_metadata() {
        assert_eq!(
            parse_lottie_metadata(LOTTIE_SOLID).unwrap(),
            (20, 10, 30.0, 0.0, 30.0, 1)
        );
    }

    #[test]
    fn renders_lottie_solid_motion_at_requested_frame() {
        let (_, _, first) = render_lottie_frame_rgba(LOTTIE_SOLID, 0.0, None, None).unwrap();
        let (_, _, middle) = render_lottie_frame_rgba(LOTTIE_SOLID, 15.0, None, None).unwrap();
        let alpha = |pixels: &[u8], x: usize, y: usize| pixels[(y * 20 + x) * 4 + 3];
        assert_eq!(alpha(&first, 3, 3), 255);
        assert_eq!(alpha(&middle, 3, 3), 0);
        assert_eq!(alpha(&first, 8, 3), 0);
        assert_eq!(alpha(&middle, 8, 3), 255);
    }

    #[test]
    fn rejects_empty_media_payloads() {
        assert!(decode_image_rgba(&[]).is_err());
        assert!(decode_gif_rgba_frames(&[]).is_err());
        assert!(decode_svg_rgba(&[], None, None).is_err());
        assert!(parse_lottie_metadata(&[]).is_err());
    }
}
