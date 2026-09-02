from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

import new_harmony_empirical_c as c  # noqa: E402


class TestHarmony(unittest.TestCase):
    def test_zero_maps_to_zero(self):
        self.assertEqual(float(c.harmony(0.0)), 0.0)

    def test_known_value_at_one(self):
        self.assertAlmostEqual(float(c.harmony(1.0)), 1.0 / 2.1, places=14)

    def test_matches_manual_formula_offset_1_1(self):
        for x in (0.0, 0.1, 0.3, 0.5, 0.75, 1.0, 2.0):
            expected = x / (1.1 + x)
            self.assertAlmostEqual(float(c.harmony(x)), expected, places=14)

    def test_strictly_increasing_on_0_1(self):
        grid = np.linspace(0.0, 1.0, 101)
        values = c.harmony(grid)
        self.assertTrue(np.all(np.diff(values) > 0.0))

    def test_bounded_within_0_and_1_on_domain_0_1(self):
        grid = np.linspace(0.0, 1.0, 101)
        values = c.harmony(grid)
        self.assertTrue(np.all(values >= 0.0))
        self.assertTrue(np.all(values <= 1.0))

    def test_concave_on_0_1(self):
        # Discrete concavity: for any x0<x1<x2 the midpoint value must not lie
        # below the chord, i.e. h is above its secants (concave function).
        grid = np.linspace(0.0, 1.0, 21)
        values = c.harmony(grid)
        second_diff = values[:-2] - 2.0 * values[1:-1] + values[2:]
        self.assertTrue(np.all(second_diff <= 1e-12))

    def test_vectorized_matches_elementwise_scalar_calls(self):
        xs = np.array([0.0, 0.2, 0.5, 0.9, 1.0])
        vectorized = c.harmony(xs)
        scalarwise = np.array([float(c.harmony(float(x))) for x in xs])
        np.testing.assert_allclose(vectorized, scalarwise, rtol=0.0, atol=0.0)

    def test_accepts_plain_python_list(self):
        result = c.harmony([0.0, 1.0])
        np.testing.assert_allclose(result, [0.0, 1.0 / 2.1])


class TestHarmonyInverse(unittest.TestCase):
    def test_zero_maps_to_zero(self):
        self.assertEqual(float(c.harmony_inverse(0.0)), 0.0)

    def test_matches_manual_formula_offset_1_1(self):
        for h in (0.0, 0.1, 0.2, 0.3, 0.4499856498597829):
            expected = 1.1 * h / (1.0 - h)
            self.assertAlmostEqual(float(c.harmony_inverse(h)), expected, places=12)

    def test_is_left_inverse_of_harmony_on_0_1(self):
        # harmony_inverse(harmony(x)) == x for every x the model actually uses.
        grid = np.linspace(0.0, 1.0, 101)
        roundtrip = c.harmony_inverse(c.harmony(grid))
        np.testing.assert_allclose(roundtrip, grid, rtol=1e-10, atol=1e-12)

    def test_is_right_inverse_of_harmony_below_one(self):
        # harmony(harmony_inverse(h)) == h for h strictly below the h(1) asymptote's
        # domain edge; h=1 is excluded because harmony_inverse(1) is a genuine pole.
        grid = np.linspace(0.0, 1.0 / 2.1, 101)
        roundtrip = c.harmony(c.harmony_inverse(grid))
        np.testing.assert_allclose(roundtrip, grid, rtol=1e-10, atol=1e-12)

    def test_strictly_increasing_on_0_1(self):
        grid = np.linspace(0.0, 0.99, 100)
        values = c.harmony_inverse(grid)
        self.assertTrue(np.all(np.diff(values) > 0.0))

    def test_diverges_to_infinity_at_the_h_equals_1_pole(self):
        with np.errstate(divide="ignore"):
            value = c.harmony_inverse(1.0)
        self.assertTrue(np.isinf(float(value)))

    def test_vectorized_matches_elementwise_scalar_calls(self):
        hs = np.array([0.0, 0.1, 0.3, 0.45, 0.6])
        vectorized = c.harmony_inverse(hs)
        scalarwise = np.array([float(c.harmony_inverse(float(h))) for h in hs])
        np.testing.assert_allclose(vectorized, scalarwise, rtol=0.0, atol=0.0)


class TestHarmonyPiecewiseLinearTangentUsedByTheLP(unittest.TestCase):
    """new_harmony_empirical_f.py upper-bounds Harmony in the LP with tangent lines
    slope = HARMONY_OFFSET / (HARMONY_OFFSET + x0) ** 2 at each grid point x0.  This
    is only a valid outer approximation of a concave function if every tangent lies
    on or above the curve for the whole domain the LP solves over."""

    def test_tangent_lines_are_a_valid_upper_envelope_on_0_1(self):
        offset = 1.1
        grid_points = np.linspace(0.0, 1.0, 81)
        eval_grid = np.linspace(0.0, 1.0, 401)
        curve = c.harmony(eval_grid)
        for x0 in grid_points:
            h0 = float(c.harmony(x0))
            slope = offset / (offset + x0) ** 2
            intercept = h0 - slope * x0
            tangent = slope * eval_grid + intercept
            self.assertTrue(np.all(tangent >= curve - 1e-12))

    def test_tangent_touches_the_curve_at_its_own_grid_point(self):
        offset = 1.1
        for x0 in np.linspace(0.0, 1.0, 81):
            h0 = float(c.harmony(x0))
            slope = offset / (offset + x0) ** 2
            intercept = h0 - slope * x0
            self.assertAlmostEqual(slope * x0 + intercept, h0, places=12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
