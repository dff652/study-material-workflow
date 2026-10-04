"""Create explicitly selected synthetic companion inputs and a draft export."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw
from collect_sources import collect_sources
from diagrams import draw_scene
from workflow_common import (
    WorkflowArgumentParser, canonical, cli_result, digest, fail, root_path, write_json,
)
from solution_companion.model import validate_content


def block(kind, content, role="body"):
    return {"kind": kind, "content": content, "role": role}


def prepare_demo_inputs(output_root):
    """Use a new directory; never rewrite an earlier demonstration or original."""
    root = root_path(output_root, must_exist=False)
    if root.exists():
        fail("demo_conflict", "Use a new directory for anonymous demonstration inputs")
    root.mkdir(parents=True, mode=0o700)
    sources_root, assets_root = root / "sources", root / "assets"
    sources_root.mkdir(mode=0o700); assets_root.mkdir(mode=0o700)
    texts = ["Example 1: Calculate 2 cubed.",
             "Example 2 (1): Calculate 1/2 + 1/4.",
             "Example 2 (2): Calculate 1/2 - 1/4.",
             "Example 3: Rectangle length 6, width 4. Find area. Units not given."]
    for n, text in enumerate(texts, 1):
        image = Image.new("RGB", (640, 160), "white")
        ImageDraw.Draw(image).text((20, 30), text, fill="black")
        path = sources_root / f"page{n}.png"
        image.save(path); path.chmod(0o600)
    selection = {"batch_id": "companion-anonymous-v1", "files": [
        {"path": f"page{n}.png", "book": "AnonA" if n < 4 else "AnonB",
         "token": f"{n:06d}", "page_order": n} for n in range(1, 5)],
        "expected_counts": {"sources": 4, "parent_questions": 3, "entries": 4}}
    sources = collect_sources(sources_root, selection)
    ids = [item["source_id"] for item in sources["sources"]]
    original = assets_root / "original.png"
    original.write_bytes((sources_root / "page1.png").read_bytes()); original.chmod(0o600)
    basis = "依给定长6、宽4构造长方形；示意图不从照片像素测量，不增加题设。"
    scene = {"width": 230, "height": 160, "source_ref": basis, "elements": [
        {"kind": "polygon", "points": [35, 30, 185, 30, 185, 130, 35, 130],
         "color": "#163C65", "fill": "#FFFFFF"},
        {"kind": "text", "x": 104, "y": 10, "text": "6", "size": 12},
        {"kind": "text", "x": 195, "y": 75, "text": "4", "size": 12}]}
    drawing = draw_scene(scene, root / "drawing")
    auxiliary = assets_root / "rectangle.png"
    auxiliary.write_bytes((Path(drawing["directory"]) / "diagram.png").read_bytes())
    auxiliary.chmod(0o600)
    assets = [
        {"storage_key": "original.png", "sha256": digest(original.read_bytes()),
         "kind": "source_image", "source_id": ids[0], "region": None,
         "basis": "匿名合成原题全图，保持原始RGB像素。"},
        {"storage_key": "rectangle.png", "sha256": digest(auxiliary.read_bytes()),
         "kind": "auxiliary", "source_id": None, "region": None, "basis": basis}]

    def picture(asset, alt, role):
        return block("diagram", {"storage_key": asset["storage_key"], "sha256": asset["sha256"],
                     "source_ref": asset["basis"], "alt": alt, "width_mm": 120,
                     "no_hint_confirmed": False}, role)

    def question(qid, lecture, number, title, stem, source_indices, parts, pages, unknowns=None):
        return {"question_id": qid, "lecture_id": lecture, "display_number": number,
                "title": title, "statement": {"text": stem, "status": "complete"},
                "source_refs": [{"source_id": ids[n], "sequence": s, "region": None}
                                for s, n in enumerate(source_indices, 1)],
                "parts": parts, "pages": pages, "unknowns": unknowns or [], "corrections": []}

    def part(pid, label, statement, answer, parent=None, unit=None):
        return {"part_id": pid, "parent_id": parent, "label": label,
                "statement": statement, "answer": answer, "unit": unit}

    first = question("power", "A", "1", "第1题：乘方", "计算2³。", [0],
                     [part("power-answer", "答案", None, "8")], [[
        block("title", "第1题：乘方", "title"), block("p", "计算2³。", "question"),
        picture(assets[0], "合成原题全图", "question"),
        block("h", "思路：指数表示相同因子的个数。", "method"),
        block("p", "2³表示三个2相乘；不要误算成2×3。", "method"),
        block("math", ["r", ["u", ["t", "2"], ["t", "3"]], ["t", " = 2 × 2 × 2 = 8"]], "method"),
        block("key", "答案：8", "answer")]])
    fraction_parts = [part("fraction-group", "两小问", None, None),
                      part("fraction-add", "(1)", "求1/2加1/4。", "3/4", "fraction-group"),
                      part("fraction-subtract", "(2)", "求1/2减1/4。", "1/4", "fraction-group")]
    fraction_pages = []
    for label, statement, operation, numerator, answer in [
            ("(1)", "求1/2加1/4。", "+", "3", "3/4"),
            ("(2)", "求1/2减1/4。", "−", "1", "1/4")]:
        fraction_pages.append([
            block("title", "第2题：分数运算 " + label, "title"),
            block("p", "计算以下两个分数问题。" if label == "(1)" else "第2题续页。", "question"),
            block("p", statement, "question"),
            block("h", "思路：先统一每一份的大小，再计算份数。", "method"),
            block("p", "分母2与4的最小公倍数是4。分子和分母同时乘2，把1/2写成2/4，数值保持不变。", "method"),
            block("math", ["r", ["f", ["t", "1"], ["t", "2"]], ["t", " = "],
                           ["f", ["t", "1 × 2"], ["t", "2 × 2"]], ["t", " = "],
                           ["f", ["t", "2"], ["t", "4"]]], "method"),
            block("p", "分母相同后，每一份都是四分之一，只对分子做运算。", "method"),
            block("math", ["r", ["f", ["t", "2"], ["t", "4"]], ["t", " " + operation + " "],
                           ["f", ["t", "1"], ["t", "4"]], ["t", " = "],
                           ["f", ["t", numerator], ["t", "4"]]], "method"),
            block("p", "检查结果：分母保持4，分子与4没有大于1的公因数，已经最简。", "method"),
            block("key", label + " 答案：" + answer, "answer"),
            block("warn", "易错点：直接相加分母会改变每一份的大小。")])
    second = question("fractions", "A", "2", "第2题：分数运算", "计算以下两个分数问题。",
                      [1, 2], fraction_parts, fraction_pages)
    third = question("area", "B", "1", "第1题：长方形面积", "长方形长6、宽4，求面积。", [3],
                     [part("area-answer", "答案", None, "24")], [[
        block("title", "第1题：长方形面积", "title"),
        block("p", "长方形长6、宽4，求面积。", "question"),
        picture(assets[1], "依题设构造的长方形示意图", "method"),
        block("p", "思路：长与宽分别给出横向和纵向的长度，面积等于长乘宽。", "method"),
        block("p", "步骤：6×4=24。", "method"), block("key", "答案：24", "answer"),
        block("small", "原题未给计量单位，保留未知；不自动补写平方厘米。")]], ["原题未给计量单位"])
    content = {"schema_version": "swf.solution-companion.v1", "batch_id": sources["batch_id"],
               "revision_id": "v1", "title": "匿名逐题解析示例", "sources_sha256": digest(canonical(sources)),
               "lectures": [{"lecture_id": "A", "title": "匿名计算讲"}, {"lecture_id": "B", "title": "匿名几何讲"}],
               "questions": [first, second, third], "assets": assets,
               "outputs": {"per_question": ["pdf", "docx"], "per_lecture": ["pdf"], "combined": ["docx", "pdf"]},
               "unknowns": ["合成来源不代表学习效果；作者、日期及独立作答情况未记录。"]}
    validate_content(content, sources)
    for name, value in (("selection.json", selection), ("sources.json", sources), ("content.json", content)):
        write_json(root / name, value)
    return {"root": root, "source_root": sources_root, "asset_root": assets_root,
            "sources": sources, "content": content,
            "sources_path": root / "sources.json", "content_path": root / "content.json"}


def make_demo(output_root, font_config):
    from solution_companion.cli import render, status
    from solution_companion.bundle import bundle_companion
    data = prepare_demo_inputs(output_root)
    args = SimpleNamespace(content=str(data["content_path"]), sources=str(data["sources_path"]),
                           source_root=str(data["source_root"]), asset_root=str(data["asset_root"]),
                           font_config=str(font_config), output_root=str(data["root"] / "run"))
    result = render(args)
    verification = status(SimpleNamespace(run=result["run"], source_root=None))
    package = bundle_companion(result["directory"], data["root"] / "companion-draft.zip")
    return {**result, "verification": verification, "bundle": package, "synthetic_sources": True}


def main():
    parser = WorkflowArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True); parser.add_argument("--font-config", required=True)
    args = parser.parse_args()
    return make_demo(args.output_root, args.font_config)


if __name__ == "__main__":
    raise SystemExit(cli_result(main))
