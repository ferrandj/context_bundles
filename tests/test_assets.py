"""Sanity checks for the hand-authored SVG assets under assets/ and
gui/static/favicon.svg.

Not a visual test (nothing in this environment can render/screenshot an
SVG) -- this only catches the failure mode a hand-edit is actually prone
to: truncated/corrupted XML, a missing root <svg> element, or a root
element with no usable sizing information. It's a floor, not a substitute
for opening the files in a browser.
"""

import io
import os
import sys
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
SVG_NS = "{http://www.w3.org/2000/svg}"

EXPECTED_ASSET_FILES = [
    os.path.join(ASSETS_DIR, "icon.svg"),
    os.path.join(ASSETS_DIR, "banner.svg"),
    os.path.join(ASSETS_DIR, "architecture-diagram.svg"),
    os.path.join(REPO_ROOT, "gui", "static", "favicon.svg"),
]


def parse_svg(path_or_text):
    """Parse an SVG file path (or raw text, for the malformed-input test)
    and return its root element. Raises ET.ParseError on malformed XML."""
    if os.path.exists(path_or_text):
        tree = ET.parse(path_or_text)
        return tree.getroot()
    return ET.fromstring(path_or_text)


class AssetFilesExistTest(unittest.TestCase):
    def test_expected_files_exist(self):
        for path in EXPECTED_ASSET_FILES:
            self.assertTrue(os.path.isfile(path), "missing asset: {}".format(path))


class SvgWellFormedTest(unittest.TestCase):
    def test_each_asset_parses_as_well_formed_xml_with_svg_root(self):
        for path in EXPECTED_ASSET_FILES:
            with self.subTest(path=path):
                root = parse_svg(path)
                self.assertEqual(root.tag, SVG_NS + "svg", "{} root is not <svg>".format(path))

    def test_each_asset_has_sizing_information(self):
        for path in EXPECTED_ASSET_FILES:
            with self.subTest(path=path):
                root = parse_svg(path)
                has_viewbox = bool(root.get("viewBox"))
                has_dimensions = bool(root.get("width")) and bool(root.get("height"))
                self.assertTrue(
                    has_viewbox or has_dimensions,
                    "{} has neither viewBox nor width/height".format(path),
                )

    def test_each_asset_is_non_trivial(self):
        # Catches an accidentally-empty/near-empty file (e.g. just the
        # root tag with no content) slipping through as "well-formed".
        for path in EXPECTED_ASSET_FILES:
            with self.subTest(path=path):
                root = parse_svg(path)
                self.assertGreater(len(list(root)), 0, "{} has no child elements".format(path))

    def test_icon_and_favicon_stay_in_sync(self):
        # gui/static/favicon.svg is a deliberate copy of assets/icon.svg
        # (kept as a plain file so gui/app.py's static server needs no
        # special-casing) -- if they drift, the favicon and the README
        # icon will silently show different marks.
        icon_path = os.path.join(ASSETS_DIR, "icon.svg")
        favicon_path = os.path.join(REPO_ROOT, "gui", "static", "favicon.svg")
        with open(icon_path, "r", encoding="utf-8") as fh:
            icon_content = fh.read()
        with open(favicon_path, "r", encoding="utf-8") as fh:
            favicon_content = fh.read()
        self.assertEqual(icon_content, favicon_content)


class MalformedSvgIsRejectedTest(unittest.TestCase):
    """Edge case: prove the well-formedness check isn't a no-op by feeding
    it something broken through the exact same parse_svg() helper."""

    def test_truncated_svg_raises_parse_error(self):
        truncated = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect x="0"'
        with self.assertRaises(ET.ParseError):
            parse_svg(truncated)

    def test_mismatched_tags_raise_parse_error(self):
        broken = '<svg xmlns="http://www.w3.org/2000/svg"><rect></circle></svg>'
        with self.assertRaises(ET.ParseError):
            parse_svg(broken)

    def test_non_svg_root_fails_the_root_tag_check(self):
        not_svg = '<div xmlns="http://www.w3.org/2000/svg"><rect/></div>'
        root = parse_svg(not_svg)
        self.assertNotEqual(root.tag, SVG_NS + "svg")


if __name__ == "__main__":
    unittest.main()
