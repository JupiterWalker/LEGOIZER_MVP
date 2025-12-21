import io
import os
import tempfile
import unittest
from pathlib import Path

from postprocess import opt_from_tencent as opt


class TestUtilityFunctions(unittest.TestCase):
    def test_normalize_part_number(self):
        self.assertEqual(opt.normalize_part_number("3005.dat"), "3005")
        self.assertEqual(opt.normalize_part_number("abc"), "ABC")

    def test_ensure_part_extension(self):
        self.assertEqual(opt.ensure_part_extension("3005"), "3005.dat")
        self.assertEqual(opt.ensure_part_extension("3024.dat"), "3024.dat")

    def test_round_and_quantize(self):
        self.assertEqual(opt.round_int(1.2), 1)
        self.assertEqual(opt.round_int(1.7), 2)
        self.assertEqual(opt.quantize(1.49), 1)
        self.assertEqual(opt.quantize(1.51), 2)

    def test_rect_helpers(self):
        self.assertEqual(opt.bbox2rect((0.1, 0.2, 1.9, 1.8)), (0, 0, 2, 2))
        self.assertEqual(opt.rect_area((0, 0, 1, 1)), 4)
        self.assertTrue(opt.rect_intersect((0, 0, 1, 1), (1, 1, 2, 2)))
        self.assertFalse(opt.rect_intersect((0, 0, 1, 1), (2, 2, 3, 3)))
        self.assertTrue(opt.rect_cover((0, 0, 5, 5), (1, 1, 2, 2)))
        self.assertFalse(opt.rect_inside((0, 0, 1, 1), (0, 0, 0, 0)))

    def test_cells_and_dilate(self):
        cells = opt.cells_in_rect((0, 0, 1, 1))
        self.assertEqual(cells, {(0, 0), (0, 1), (1, 0), (1, 1)})
        self.assertEqual(opt.dilate_rect((1, 1, 2, 2), 1), (0, 0, 3, 3))

    def test_bfs_connected_components(self):
        grid = {(0, 0): 1, (1, 0): 1, (5, 5): 1}
        comps = opt.bfs_connected_components(grid, connectivity=4)
        sorted_lengths = sorted(len(c) for c in comps)
        self.assertEqual(sorted_lengths, [1, 2])

    def test_snap_and_bbox(self):
        verts = [(0.1, 0.1, 0.0), (1.8, 0.2, 0.0), (1.9, 1.9, 0.3)]
        snapped = opt.snap_to_grid_xy(verts)
        self.assertIn((0, 0), snapped)
        self.assertIn((2, 0), snapped)
        self.assertNotIn((2, 2), snapped)
        bbox = opt.polygon_bbox([(0, 0), (2, 1)])
        self.assertEqual(bbox, (0, 0, 2, 1))


class TestLDrawHelpers(unittest.TestCase):
    def test_ldraw_comment(self):
        self.assertEqual(opt.ldraw_comment("test"), "0 // test")

    def test_ldraw_subfile(self):
        line = opt.ldraw_subfile("3024", 21, 0.0, 0.0, 0.0)
        expected = "1 21 0.000000 0.000000 0.000000 1 0 0 0 1 0 0 0 1 3024.dat"
        self.assertEqual(line, expected)

    def test_ldraw_meta_step(self):
        self.assertEqual(opt.ldraw_meta_step(), "0 STEP")

    def test_part_library(self):
        lib = opt.get_part_library()
        self.assertIn((1, 1), lib)
        self.assertIn((1, 2), lib)
        self.assertNotIn((3, 3), lib)

    def test_candidate_sizes(self):
        sizes = opt.candidate_sizes(2)
        self.assertEqual(sizes[0], (2, 2))
        self.assertEqual(sizes[-1], (1, 1))


class TestParserAndExtract(unittest.TestCase):
    def _write_simple_mpd(self, directory: Path) -> Path:
        mpd_path = directory / "simple.mpd"
        lines = [
            "0 FILE model.ldr",
            "1 21 0 0 0 1 0 0 0 1 0 0 0 1 3024.dat",
            "1 21 1 0 0 1 0 0 0 1 0 0 0 1 3024.dat",
            "0 NOFILE",
        ]
        mpd_path.write_text("\n".join(lines), encoding="utf-8")
        return mpd_path

    def test_parser_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_simple_mpd(Path(tmp))
            parser = opt.LDrawMPDParser(path)
            self.assertIn("model.ldr", parser.files)
            out_path = Path(tmp) / "out.mpd"
            parser.save(out_path)
            self.assertTrue(out_path.exists())

    def test_extract_bricks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_simple_mpd(Path(tmp))
            parser = opt.LDrawMPDParser(path)
            bricks = opt.extract_bricks_from_mpd(parser)
            self.assertEqual(len(bricks), 2)
            keys = sorted(bricks.keys())
            self.assertEqual(keys[0][0], 0)
            self.assertEqual(keys[0][1], (0, 0))

    def test_build_voxel_grid(self):
        bricks = {
            (0, (0, 0), 21): (((0, 0, 0, 0)), []),
            (0, (1, 0), 21): (((1, 0, 1, 0)), []),
        }
        grid = opt.build_voxel_grid(bricks)
        self.assertIn((0, 0), grid[0])
        self.assertEqual(grid[0][(1, 0)], 21)


class TestMergeHelpers(unittest.TestCase):
    def test_propose_rects_from_component(self):
        comp = {(0, 0), (1, 0), (0, 1), (1, 1)}
        grid = {0: {(0, 0): 21, (1, 0): 21, (0, 1): 21, (1, 1): 21}}
        rects = opt.propose_rects_from_component(comp, grid, 0, 21, [(1, 1), (2, 2)])
        self.assertIn((0, 0, 1, 1), rects)

    def test_can_place_rect(self):
        grid = {0: {(0, 0): 21, (1, 0): 21}}
        rect = (0, 0, 1, 0)
        self.assertTrue(opt.can_place_rect(rect, 0, 21, grid, {}))
        grid_conflict = {0: {(0, 0): 21, (1, 0): 5}}
        self.assertFalse(opt.can_place_rect(rect, 0, 21, grid_conflict, {}))

    def test_stability_check(self):
        grid = {0: {(0, 0): 21}, -1: {(0, 0): 21}}
        self.assertTrue(opt.stability_check((0, 0, 0, 0), 0, 21, grid))
        grid_missing = {0: {(0, 0): 21}}
        self.assertFalse(opt.stability_check((0, 0, 0, 0), 0, 21, grid_missing))

    def test_post_merge_hook(self):
        self.assertTrue(opt.post_merge_hook((0, 0, 0, 0), 0, 21, "3024", {}))

    def test_merge_components_for_layer_merges_adjacent(self):
        grid = {0: {(0, 0): 21, (1, 0): 21}}
        kept, new_bricks = opt.merge_components_for_layer(
            grid_by_z=grid,
            z=0,
            color=21,
            candidates=opt.candidate_sizes(2),
        )
        self.assertEqual(kept, set())
        self.assertEqual(len(new_bricks), 1)
        rect, brick_color, part_no = new_bricks[0]
        self.assertEqual(rect, (0, 0, 1, 0))
        self.assertEqual(brick_color, 21)
        self.assertEqual(part_no, "3023")


class TestBuildMergedMPD(unittest.TestCase):
    def _simple_layer_results(self):
        kept = {(0, 0)}
        new_bricks = [((0, 0, 1, 0), 21, "3023")]
        return {0: (kept, new_bricks)}

    def test_build_merged_mpd(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                "0 FILE model.ldr",
                "1 21 0 0 0 1 0 0 0 1 0 0 0 1 3024.dat",
                "1 21 1 0 0 1 0 0 0 1 0 0 0 1 3024.dat",
                "0 NOFILE",
            ]
            mpd_path = Path(tmp) / "model.mpd"
            mpd_path.write_text("\n".join(lines), encoding="utf-8")
            parser = opt.LDrawMPDParser(mpd_path)
            merged = opt.build_merged_mpd(parser, self._simple_layer_results())
            file_lines = "\n".join(merged.files["model.ldr"])
            self.assertIn("3023.dat", file_lines)
            self.assertEqual(file_lines.count("3024.dat"), 1)


class TestMergeEndToEnd(unittest.TestCase):
    def test_merge_1x1_to_larger(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = [
                "0 FILE model.ldr",
                "1 21 0 0 0 1 0 0 0 1 0 0 0 1 3024.dat",
                "1 21 1 0 0 1 0 0 0 1 0 0 0 1 3024.dat",
                "0 NOFILE",
            ]
            mpd_path = Path(tmp) / "input.mpd"
            mpd_path.write_text("\n".join(lines), encoding="utf-8")
            out_path = Path(tmp) / "output.mpd"
            opt.merge_1x1_to_larger(str(mpd_path), str(out_path), max_wh=4)
            result = out_path.read_text(encoding="utf-8")
            self.assertIn("3023.dat", result)
            self.assertNotIn(" 3024.dat", result)


if __name__ == "__main__":
    unittest.main()
