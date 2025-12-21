import tempfile
import unittest
from pathlib import Path

from postprocess import opt_v3 as opt


IDENTITY_ROT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _make_line(x: float, y: float, z: float, color: str = "21", part: str = "3024.dat") -> str:
    rot = " ".join(f"{value:g}" for value in IDENTITY_ROT)
    return f"1 {color} {x:.3f} {y:.3f} {z:.3f} {rot} {part}"


class TestParsing(unittest.TestCase):
    def test_parse_type1_line(self):
        line = _make_line(0, 0, 0)
        parsed = opt.parse_mpd_line(line)
        self.assertIsNotNone(parsed)
        expected_color = opt.match_lego_color(opt.hex_to_rgb("21"))
        self.assertEqual(parsed["color"], expected_color)
        self.assertEqual(parsed["position"], (0.0, 0.0, 0.0))
        self.assertEqual(parsed["part_type"], "3024.dat")

    def test_parse_non_type1_line(self):
        self.assertIsNone(opt.parse_mpd_line("0 FILE test"))


class TestPartMapping(unittest.TestCase):
    def test_part_to_ldraw_alias(self):
        self.assertEqual(opt.part_to_ldraw("plate_1x1"), "3024.dat")
        self.assertEqual(opt.part_to_ldraw("brick_1x2"), "3004.dat")

    def test_part_to_ldraw_direct_number(self):
        self.assertEqual(opt.part_to_ldraw("3024.dat"), "3024.dat")
        self.assertEqual(opt.part_to_ldraw("3024"), "3024.dat")

    def test_part_to_ldraw_unknown(self):
        self.assertIsNone(opt.part_to_ldraw("unknown_part"))

    def test_get_part_size(self):
        self.assertEqual(opt.get_part_size_from_name("plate_1x2"), (1, 2))
        self.assertEqual(opt.get_part_size_from_name("3024.dat"), (1, 1))
        self.assertEqual(opt.get_part_size_from_name("foo"), (1, 1))


class TestGrouping(unittest.TestCase):
    def test_group_by_color_and_position(self):
        comps = []
        for x in (0.0, 20.0):
            line = _make_line(x, 0.0, 0.0)
            parsed = opt.parse_mpd_line(line)
            comps.append(parsed)
        line = _make_line(0.0, 20.0, 0.0)
        comps.append(opt.parse_mpd_line(line))
        grouped = opt.group_by_color_and_position(comps, axis=0)
        self.assertEqual(len(grouped), 2)
        lengths = sorted(len(items) for items in grouped.values())
        self.assertEqual(lengths, [1, 2])


class TestMerging(unittest.TestCase):
    def test_merge_in_line_creates_larger_part(self):
        comp_a = opt.parse_mpd_line(_make_line(0.0, 0.0, 0.0))
        comp_b = opt.parse_mpd_line(_make_line(20.0, 0.0, 0.0))
        merged = opt.merge_in_line([comp_a, comp_b], axis=0, part_type="plate_1x1")
        self.assertEqual(len(merged), 1)
        part = merged[0]
        self.assertEqual(part["part_type"], "3023.dat")
        self.assertAlmostEqual(part["position"][0], 10.0)
        self.assertAlmostEqual(part["position"][1], 0.0)
        self.assertAlmostEqual(part["position"][2], 0.0)

    def test_merge_in_line_requires_supported_part(self):
        with self.assertRaises(ValueError):
            opt.merge_in_line([], axis=0, part_type="unknown")

    def test_merge_in_line_partial_merge_uses_longest_first(self):
        comps: list[dict[str, object]] = []
        for idx in range(5):
            line = _make_line(idx * opt.STUD_PITCH_LDU, 0.0, 0.0)
            comps.append(opt.parse_mpd_line(line))
        merged = opt.merge_in_line(comps, axis=0, part_type="plate_1x1")
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["part_type"], "3710.dat")
        self.assertAlmostEqual(merged[0]["position"][0], 30.0)
        self.assertEqual(merged[1]["part_type"], "3024.dat")
        self.assertAlmostEqual(merged[1]["position"][0], 80.0)


class TestOptimizeFile(unittest.TestCase):
    def _write_mpd(self, rows: list[str]) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mpd")
        tmp.write("\n".join(rows).encode("utf-8"))
        tmp.close()
        return Path(tmp.name)

    def test_optimize_merges_adjacent(self):
        lines = [
            "0 FILE model.ldr",
            _make_line(0.0, 0.0, 0.0),
            _make_line(20.0, 0.0, 0.0),
            "0 NOFILE",
        ]
        mpd_path = self._write_mpd(lines)
        try:
            opt.optimize_mpd_file(mpd_path, "plate_1x1")
            result = mpd_path.read_text(encoding="utf-8")
            self.assertIn("3023.dat", result)
            self.assertIn("0 // --- Optimized components ---", result)
            self.assertNotIn(" 3024.dat\n", result)
        finally:
            mpd_path.unlink(missing_ok=True)

    def test_optimize_no_adjacent_keeps_original(self):
        lines = [
            "0 FILE model.ldr",
            _make_line(0.0, 0.0, 0.0),
            _make_line(40.0, 0.0, 0.0),
            "0 NOFILE",
        ]
        mpd_path = self._write_mpd(lines)
        try:
            opt.optimize_mpd_file(mpd_path, "plate_1x1")
            result = mpd_path.read_text(encoding="utf-8")
            self.assertNotIn("Optimized components", result)
            self.assertEqual(result.strip(), "\n".join(lines).strip())
        finally:
            mpd_path.unlink(missing_ok=True)

    def test_optimize_uses_y_axis_for_non_multiple_layer(self):
        lines = [
            "0 FILE model.ldr",
            _make_line(0.0, 0.0, 20.0),
            _make_line(0.0, 20.0, 20.0),
            "0 NOFILE",
        ]
        mpd_path = self._write_mpd(lines)
        try:
            opt.optimize_mpd_file(mpd_path, "plate_1x1")
            result = mpd_path.read_text(encoding="utf-8")
            self.assertIn("3023.dat", result)
            self.assertNotIn(" 3024.dat\n", result)
        finally:
            mpd_path.unlink(missing_ok=True)

    def test_optimize_uses_y_axis_for_odd_multiple_layer(self):
        lines = [
            "0 FILE model.ldr",
            _make_line(0.0, 0.0, 40.0),
            _make_line(0.0, 20.0, 40.0),
            "0 NOFILE",
        ]
        mpd_path = self._write_mpd(lines)
        try:
            opt.optimize_mpd_file(mpd_path, "plate_1x1")
            result = mpd_path.read_text(encoding="utf-8")
            self.assertIn("3023.dat", result)
            self.assertNotIn(" 3024.dat\n", result)
        finally:
            mpd_path.unlink(missing_ok=True)

    def test_optimize_unsupported_type(self):
        lines = ["0 FILE model.ldr", "0 NOFILE"]
        mpd_path = self._write_mpd(lines)
        try:
            with self.assertRaises(ValueError):
                opt.optimize_mpd_file(mpd_path, "foo")
        finally:
            mpd_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
