//! CPU text geometry using the same font discovery and shaping as glyphon.

use glyphon::{Attrs, Buffer, Family, FontSystem, Metrics, Shaping};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;

type SelectionSegment = (usize, usize, f32, f32);
type LineGeometry = (f32, Vec<f32>, Vec<SelectionSegment>);
const MAX_LINE_BYTES: usize = 1_048_576;

#[pyclass(name = "TextShaper")]
pub(crate) struct PyTextShaper {
    fonts: FontSystem,
}

#[pymethods]
impl PyTextShaper {
    #[new]
    fn new() -> Self {
        Self {
            fonts: FontSystem::new(),
        }
    }

    /// Return render width, scalar-indexed carets and visual selection segments.
    /// Coordinates are physical pixels; the Python bridge converts them to DIPs.
    fn shape_line(
        &mut self,
        content: &str,
        font_size: f32,
        family: &str,
    ) -> PyResult<LineGeometry> {
        if content.len() > MAX_LINE_BYTES {
            return Err(PyValueError::new_err(
                "Text line exceeds the 1 MiB shaping limit.",
            ));
        }
        if content.contains(['\n', '\r', '\u{2028}', '\u{2029}']) {
            return Err(PyValueError::new_err(
                "shape_line requires a single text line.",
            ));
        }
        if family.trim().is_empty() || family.len() > 1024 {
            return Err(PyValueError::new_err(
                "Font family must contain 1 to 1024 bytes.",
            ));
        }
        if !font_size.is_finite() || font_size <= 0.0 || font_size > 16_384.0 {
            return Err(PyValueError::new_err(
                "Font size must be finite and between 0 and 16384.",
            ));
        }
        let mut buffer = Buffer::new(&mut self.fonts, Metrics::new(font_size, font_size * 1.25));
        buffer.set_size(None, Some(font_size * 1.25));
        buffer.set_text(
            content,
            &Attrs::new().family(Family::Name(family)),
            Shaping::Advanced,
            None,
        );
        buffer.shape_until_scroll(&mut self.fonts, false);
        // Leave one physical pixel for floating-point rounding so the renderer's
        // default wrapping cannot move the final cluster to a second line.
        let width = buffer
            .layout_runs()
            .map(|run| run.line_w)
            .fold(0.0_f32, f32::max)
            .ceil()
            + 1.0;
        buffer.set_size(Some(width), Some(font_size * 1.25));
        buffer.shape_until_scroll(&mut self.fonts, false);

        let byte_indices: Vec<usize> = content
            .char_indices()
            .map(|(i, _)| i)
            .chain(std::iter::once(content.len()))
            .collect();
        let mut carets = vec![None; byte_indices.len()];
        let mut ends = vec![None; byte_indices.len()];
        let mut segments = Vec::new();
        for run in buffer.layout_runs() {
            for glyph in run.glyphs {
                let cluster = &content[glyph.start..glyph.end];
                let total = cluster.graphemes(true).count().max(1);
                let advance = glyph.w / total as f32;
                for (part, (offset, grapheme)) in cluster.grapheme_indices(true).enumerate() {
                    let start_byte = glyph.start + offset;
                    let end_byte = start_byte + grapheme.len();
                    let start = byte_indices
                        .binary_search(&start_byte)
                        .expect("grapheme boundary");
                    let end = byte_indices
                        .binary_search(&end_byte)
                        .expect("grapheme boundary");
                    let (left, right) = if glyph.level.is_rtl() {
                        (
                            glyph.x + glyph.w - (part + 1) as f32 * advance,
                            glyph.x + glyph.w - part as f32 * advance,
                        )
                    } else {
                        (
                            glyph.x + part as f32 * advance,
                            glyph.x + (part + 1) as f32 * advance,
                        )
                    };
                    let (before, after) = if glyph.level.is_rtl() {
                        (right, left)
                    } else {
                        (left, right)
                    };
                    carets[start].get_or_insert(before);
                    for caret in &mut carets[start + 1..end] {
                        caret.get_or_insert(after);
                    }
                    ends[end].get_or_insert(after);
                    if right > left {
                        segments.push((start, end, left, right));
                    }
                }
            }
        }
        let mut previous = 0.0;
        let positions = carets
            .into_iter()
            .zip(ends)
            .map(|(start, end)| {
                previous = start.or(end).unwrap_or(previous);
                previous
            })
            .collect();
        Ok((width, positions, segments))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn proportional_advances_and_unicode_scalar_indices() {
        let mut shaper = PyTextShaper::new();
        let (_, narrow, _) = shaper.shape_line("iiii", 24.0, "Segoe UI").unwrap();
        let (_, wide, _) = shaper.shape_line("WWWW", 24.0, "Segoe UI").unwrap();
        assert!(wide[4] > narrow[4] * 1.5);
        let (_, positions, segments) = shaper.shape_line("Aé😀e\u{301}", 24.0, "Segoe UI").unwrap();
        assert_eq!(positions.len(), 6);
        assert!(
            segments
                .iter()
                .all(|(start, end, left, right)| start < end && *end <= 5 && left <= right)
        );
        assert!(positions.iter().all(|x| x.is_finite()));
    }

    #[test]
    fn rejects_invalid_requests_before_shaping() {
        let mut shaper = PyTextShaper::new();
        assert!(shaper.shape_line("a\nb", 16.0, "Segoe UI").is_err());
        assert!(shaper.shape_line("x", f32::NAN, "Segoe UI").is_err());
        assert!(shaper.shape_line("x", 16.0, " ").is_err());
        assert!(
            shaper
                .shape_line(&"x".repeat(MAX_LINE_BYTES + 1), 16.0, "Segoe UI")
                .is_err()
        );
        assert_eq!(
            shaper.shape_line("", 16.0, "Segoe UI").unwrap().1,
            vec![0.0]
        );
    }
}
