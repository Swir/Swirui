//! Native affine transform math shared by compositor preparation and GPU backends.
//!
//! The Python SceneGraph owns the public transform API. This module mirrors the
//! same six-float matrix convention inside the Rust core so future GPU submission
//! can consume retained transforms without inventing a second ordering contract.

const DETERMINANT_EPSILON: f32 = 1.0e-6;
const AXIS_ALIGNMENT_EPSILON: f32 = 1.0e-6;

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Affine2D {
    pub(crate) m11: f32,
    pub(crate) m12: f32,
    pub(crate) m21: f32,
    pub(crate) m22: f32,
    pub(crate) tx: f32,
    pub(crate) ty: f32,
}

impl Affine2D {
    pub(crate) const IDENTITY: Self = Self {
        m11: 1.0,
        m12: 0.0,
        m21: 0.0,
        m22: 1.0,
        tx: 0.0,
        ty: 0.0,
    };

    pub(crate) fn try_from_slice(values: &[f32]) -> Result<Self, &'static str> {
        if values.len() != 6 {
            return Err("Affine2D requires exactly six floats.");
        }
        if values.iter().any(|value| !value.is_finite()) {
            return Err("Affine2D values must be finite.");
        }
        let transform = Self {
            m11: values[0],
            m12: values[1],
            m21: values[2],
            m22: values[3],
            tx: values[4],
            ty: values[5],
        };
        if transform.determinant().abs() <= DETERMINANT_EPSILON {
            return Err("Affine2D must be invertible.");
        }
        Ok(transform)
    }

    pub(crate) fn determinant(self) -> f32 {
        self.m11 * self.m22 - self.m12 * self.m21
    }

    pub(crate) fn is_identity(self) -> bool {
        self == Self::IDENTITY
    }

    pub(crate) fn is_axis_aligned(self) -> bool {
        self.m12.abs() <= AXIS_ALIGNMENT_EPSILON && self.m21.abs() <= AXIS_ALIGNMENT_EPSILON
    }

    pub(crate) fn then(self, following: Self) -> Self {
        Self {
            m11: following.m11 * self.m11 + following.m12 * self.m21,
            m12: following.m11 * self.m12 + following.m12 * self.m22,
            m21: following.m21 * self.m11 + following.m22 * self.m21,
            m22: following.m21 * self.m12 + following.m22 * self.m22,
            tx: following.m11 * self.tx + following.m12 * self.ty + following.tx,
            ty: following.m21 * self.tx + following.m22 * self.ty + following.ty,
        }
    }

    pub(crate) fn transform_point(self, point: [f32; 2]) -> [f32; 2] {
        [
            self.m11 * point[0] + self.m12 * point[1] + self.tx,
            self.m21 * point[0] + self.m22 * point[1] + self.ty,
        ]
    }

    pub(crate) fn inverse(self) -> Self {
        let determinant = self.determinant();
        let m11 = self.m22 / determinant;
        let m12 = -self.m12 / determinant;
        let m21 = -self.m21 / determinant;
        let m22 = self.m11 / determinant;
        Self {
            m11,
            m12,
            m21,
            m22,
            tx: -(m11 * self.tx + m12 * self.ty),
            ty: -(m21 * self.tx + m22 * self.ty),
        }
    }

    pub(crate) fn transform_rect_bounds(self, rect: [f32; 4]) -> [f32; 4] {
        let x = rect[0];
        let y = rect[1];
        let right = x + rect[2];
        let bottom = y + rect[3];
        let corners = [
            self.transform_point([x, y]),
            self.transform_point([right, y]),
            self.transform_point([right, bottom]),
            self.transform_point([x, bottom]),
        ];
        let mut left = corners[0][0];
        let mut top = corners[0][1];
        let mut visual_right = corners[0][0];
        let mut visual_bottom = corners[0][1];
        for point in corners.into_iter().skip(1) {
            left = left.min(point[0]);
            top = top.min(point[1]);
            visual_right = visual_right.max(point[0]);
            visual_bottom = visual_bottom.max(point[1]);
        }
        [left, top, visual_right - left, visual_bottom - top]
    }

    pub(crate) fn to_gpu_array(self) -> [f32; 6] {
        [self.m11, self.m12, self.m21, self.m22, self.tx, self.ty]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_close(actual: f32, expected: f32) {
        assert!(
            (actual - expected).abs() <= 1.0e-4,
            "expected {expected}, got {actual}"
        );
    }

    #[test]
    fn rejects_invalid_native_contract_payloads() {
        assert_eq!(
            Affine2D::try_from_slice(&[1.0, 0.0, 0.0, 1.0, 0.0]),
            Err("Affine2D requires exactly six floats.")
        );
        assert_eq!(
            Affine2D::try_from_slice(&[1.0, 0.0, 0.0, f32::NAN, 0.0, 0.0]),
            Err("Affine2D values must be finite.")
        );
        assert_eq!(
            Affine2D::try_from_slice(&[1.0, 2.0, 2.0, 4.0, 0.0, 0.0]),
            Err("Affine2D must be invertible.")
        );
    }

    #[test]
    fn composition_matches_python_visual_order() {
        let translation = Affine2D::try_from_slice(&[1.0, 0.0, 0.0, 1.0, 12.0, -5.0])
            .expect("translation should be valid");
        let quarter_turn = Affine2D::try_from_slice(&[0.0, -1.0, 1.0, 0.0, 0.0, 0.0])
            .expect("rotation should be valid");
        let composed = translation.then(quarter_turn);
        let point = composed.transform_point([4.0, 3.0]);
        assert_close(point[0], 2.0);
        assert_close(point[1], 16.0);
    }

    #[test]
    fn inverse_round_trips_visual_points() {
        let transform = Affine2D::try_from_slice(&[0.8, -0.6, 0.6, 0.8, 19.0, -11.0])
            .expect("rotation/translation should be invertible");
        let authored = [132.5, 74.25];
        let visual = transform.transform_point(authored);
        let recovered = transform.inverse().transform_point(visual);
        assert_close(recovered[0], authored[0]);
        assert_close(recovered[1], authored[1]);
    }

    #[test]
    fn transformed_bounds_enclose_rotated_rectangle() {
        let quarter_turn = Affine2D::try_from_slice(&[0.0, -1.0, 1.0, 0.0, 0.0, 0.0])
            .expect("rotation should be valid");
        let bounds = quarter_turn.transform_rect_bounds([10.0, 20.0, 30.0, 40.0]);
        assert_close(bounds[0], -60.0);
        assert_close(bounds[1], 10.0);
        assert_close(bounds[2], 40.0);
        assert_close(bounds[3], 30.0);
    }

    #[test]
    fn classifies_axis_alignment_without_losing_gpu_packing_order() {
        let scale_translate = Affine2D::try_from_slice(&[1.5, 0.0, 0.0, 0.75, 8.0, 9.0])
            .expect("scale/translation should be valid");
        let rotation = Affine2D::try_from_slice(&[0.0, -1.0, 1.0, 0.0, 0.0, 0.0])
            .expect("rotation should be valid");
        assert!(Affine2D::IDENTITY.is_identity());
        assert!(scale_translate.is_axis_aligned());
        assert!(!rotation.is_axis_aligned());
        assert_eq!(
            scale_translate.to_gpu_array(),
            [1.5, 0.0, 0.0, 0.75, 8.0, 9.0]
        );
    }
}
