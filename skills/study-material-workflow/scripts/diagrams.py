"""Render a bounded vector scene into PDF and PNG without guessing geometry."""
from workflow_common import WorkflowArgumentParser
import importlib.metadata
import math
from pathlib import Path
import tempfile
from reportlab.graphics.shapes import Drawing, Line, Polygon, Circle, String
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor
import pymupdf
from workflow_common import cli_result, fail, read_json, digest, canonical, write_json, assert_no_symlinks,resolve_under


def draw_scene(scene, output_root):
    if not isinstance(scene, dict) or set(scene) != {"width", "height", "elements", "source_ref"}:
        fail("invalid_scene", "Scene needs dimensions, elements and explicit source")
    width, height = scene["width"], scene["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 20 <= v <= 1000 for v in (width, height)):
        fail("invalid_scene", "Scene dimensions exceed the supported bound")
    if not isinstance(scene["source_ref"], str) or not scene["source_ref"].strip():
        fail("invalid_scene", "Drawing needs construction or source reference")
    if not isinstance(scene["elements"], list) or not 1 <= len(scene["elements"]) <= 300:
        fail("invalid_scene", "Scene needs a bounded element list")
    drawing = Drawing(width, height)
    for element in scene["elements"]:
        if not isinstance(element, dict) or element.get("kind") not in {"line", "polygon", "circle", "text"}:
            fail("invalid_scene", "Unsupported scene element")
        kind = element["kind"]
        keys = {"line": {"kind", "points", "color"}, "polygon": {"kind", "points", "color", "fill"},
                "circle": {"kind", "x", "y", "radius", "color"}, "text": {"kind", "x", "y", "text", "size"}}[kind]
        if set(element) != keys:
            fail("invalid_scene", "Element fields must be explicit")
        values = element.get("points", [element.get("x"), element.get("y")])
        if (not isinstance(values, list) or any(type(v) not in (int, float) or not math.isfinite(v) for v in values) or
            len(values) % 2 or any(not 0 <= v <= (width if i % 2 == 0 else height) for i, v in enumerate(values))):
            fail("invalid_scene", "Coordinates must stay inside the drawing")
        color = element.get("color", "#163C65")
        if not isinstance(color, str) or len(color) != 7 or color[0] != "#" or any(v not in "0123456789abcdefABCDEF" for v in color[1:]):
            fail("invalid_scene", "Color must be explicit RGB hex")
        if kind == "line" and len(values) == 4:
            drawing.add(Line(*values, strokeColor=HexColor(color)))
        elif kind == "polygon" and 6 <= len(values) <= 100:
            fill = element["fill"]
            if not isinstance(fill, str) or len(fill) != 7 or fill[0] != "#" or any(v not in "0123456789abcdefABCDEF" for v in fill[1:]):
                fail("invalid_scene", "Fill must be RGB hex")
            drawing.add(Polygon(values, strokeColor=HexColor(color), fillColor=HexColor(fill)))
        elif kind == "circle":
            r = element["radius"]
            if type(r) not in (int, float) or not math.isfinite(r) or not 0 < r <= min(width, height) / 2:
                fail("invalid_scene", "Invalid circle radius")
            if not r <= values[0] <= width-r or not r <= values[1] <= height-r:
                fail("invalid_scene", "Circle extends outside drawing")
            drawing.add(Circle(*values, r, strokeColor=HexColor(color), fillColor=None))
        elif kind == "text":
            text, size = element["text"], element["size"]
            if not isinstance(text, str) or not text or len(text) > 80 or any(not 32 <= ord(c) <= 126 for c in text):
                fail("invalid_scene", "Diagram labels currently use readable ASCII math/point names")
            if type(size) not in (int, float) or not 8 <= size <= 28:
                fail("invalid_scene", "Label size must be readable")
            from reportlab.pdfbase.pdfmetrics import stringWidth
            if values[0] + stringWidth(text, "Helvetica", size) > width or values[1] + size > height or values[1] < size/4:
                fail("invalid_scene", "Label extends outside drawing")
            drawing.add(String(*values, text, fontName="Helvetica", fontSize=size))
        else:
            fail("invalid_scene", "Wrong coordinate count for element")
    root = Path(output_root);assert_no_symlinks(root);root.mkdir(parents=True, exist_ok=True, mode=0o700)
    scene_sha=digest(canonical(scene))
    recipe={'scene_sha256':scene_sha,'generator_sha256':digest(Path(__file__).read_bytes()),
            'dependencies':{name:importlib.metadata.version(name) for name in ['reportlab','PyMuPDF']}}
    identity = digest(canonical(recipe))
    target = root / identity[:24]
    if target.exists():
        receipt = read_json(target/'drawing.json')
        if (set(receipt)!={'scene_sha256','scene','recipe','recipe_sha256','source_ref','files'} or
            receipt['scene_sha256']!=scene_sha or receipt['scene']!=scene or receipt['recipe']!=recipe or
            receipt['recipe_sha256']!=identity or receipt['source_ref']!=scene['source_ref'] or
            set(receipt['files'])!={'diagram.pdf','diagram.png'} or
            {p.name for p in target.iterdir()}!={'diagram.pdf','diagram.png','drawing.json'} or
            any(digest(resolve_under(target,name).read_bytes())!=sha for name,sha in receipt['files'].items())):
            fail("drawing_conflict", "Existing scene bytes changed")
        return {"directory":str(target), **receipt}
    with tempfile.TemporaryDirectory(prefix=".drawing-", dir=root) as temporary:
        stage=Path(temporary);renderPDF.drawToFile(drawing,str(stage/'diagram.pdf'))
        doc=pymupdf.open(stage/'diagram.pdf')
        doc[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).save(stage/'diagram.png');doc.close()
        receipt={'scene_sha256':scene_sha,'scene':scene,'recipe':recipe,'recipe_sha256':identity,'source_ref':scene['source_ref'],
                 'files':{name:digest((stage/name).read_bytes()) for name in ['diagram.pdf','diagram.png']}}
        for p in stage.iterdir():p.chmod(0o600)
        write_json(stage/'drawing.json',receipt)
        stage.rename(target)
    return {"directory":str(target),**receipt}


def main():
    parser=WorkflowArgumentParser(description=__doc__);parser.add_argument('--scene',required=True);parser.add_argument('--output-root',required=True)
    args=parser.parse_args();return draw_scene(read_json(args.scene),args.output_root)


if __name__=='__main__':
    raise SystemExit(cli_result(main))
