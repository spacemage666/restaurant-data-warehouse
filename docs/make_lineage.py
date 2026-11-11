"""Draw the dbt lineage like the dbt docs graph, but with bright yellow lines.

Needs Graphviz (the 'dot' program) to place the boxes, the same kind of layout algorithm dbt uses:
    sudo apt install graphviz

Run from the project root, after dbt has built the project (dbt build or dbt docs generate):
    python docs/make_lineage.py

Reads  dbt_project/target/manifest.json
Writes docs/images/dbt_lineage.svg  (GitHub shows SVG files inside README.md)

Colors and sizes are the constants right below, change them and run the script again.
"""
import json
import shutil
import subprocess
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "dbt_project" / "target" / "manifest.json"
OUTPUT = ROOT / "docs" / "images" / "dbt_lineage.svg"

# ---- look and feel (edit freely) -------------------------------------------------
BACKGROUND = "#00607F"      # dbt docs teal
EDGE_COLOR = "#FFD60A"      # the lines
EDGE_WIDTH = 1.8
EDGE_OPACITY = 0.9
TEXT_COLOR = "#FFFFFF"
COLORS = {"source": "#5FB825", "model": "#0094B3", "test": "#E0556B"}
FONT_SIZE = 13
BOX_H = 26
CHAR_W = 7.4                # estimated width of one character, used to size the boxes
SPACING = {"ranksep": 1.3, "nodesep": 0.28}   # inches between columns / between boxes
SHOW_TESTS = True           # False hides the assert_ tests
MARGIN = 30
# ----------------------------------------------------------------------------------


def load_graph():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    nodes = {}
    for uid, src in manifest.get("sources", {}).items():
        nodes[uid] = {"label": f"{src['source_name']}.{src['name']}", "kind": "source", "parents": []}
    for uid, node in manifest["nodes"].items():
        if node["resource_type"] == "model":
            nodes[uid] = {"label": node["name"], "kind": "model", "parents": node["depends_on"]["nodes"]}
        elif SHOW_TESTS and node["resource_type"] == "test" and not node.get("test_metadata"):
            # only our own singular tests (tests/*.sql), not the generic not_null/unique checks
            nodes[uid] = {"label": node["name"], "kind": "test", "parents": node["depends_on"]["nodes"]}
    for node in nodes.values():
        node["parents"] = [p for p in node["parents"] if p in nodes]
    return nodes


def run_graphviz(nodes):
    """Let Graphviz decide where every box and line goes. Returns node boxes and line curves in pixels."""
    if not shutil.which("dot"):
        raise SystemExit("Graphviz not found. Install it with: sudo apt install graphviz")
    ids = {uid: f"n{i}" for i, uid in enumerate(nodes)}
    lines = ["digraph G {", f'rankdir=LR; splines=true; ranksep={SPACING["ranksep"]}; nodesep={SPACING["nodesep"]};',
             "node [shape=box, fixedsize=true, fontsize=10]; edge [arrowhead=none];"]
    for uid, node in nodes.items():
        w = (len(node["label"]) * CHAR_W + 24) / 72
        lines.append(f'{ids[uid]} [width={w:.3f}, height={BOX_H / 72:.3f}];')
    for uid, node in nodes.items():
        for p in node["parents"]:
            lines.append(f"{ids[p]} -> {ids[uid]};")
    lines.append("}")
    out = subprocess.run(["dot", "-Tplain"], input="\n".join(lines), capture_output=True, text=True, check=True).stdout
    back = {v: k for k, v in ids.items()}
    boxes, curves, height = {}, [], 0.0
    for row in out.splitlines():
        f = row.split()
        if f[0] == "graph":
            height = float(f[3]) * 72
        elif f[0] == "node":
            boxes[back[f[1]]] = (float(f[2]) * 72, float(f[3]) * 72, float(f[4]) * 72, float(f[5]) * 72)
        elif f[0] == "edge":
            n = int(f[3])
            pts = [(float(f[4 + 2 * i]) * 72, float(f[5 + 2 * i]) * 72) for i in range(n)]
            curves.append(pts)
    return boxes, curves, height


def build_svg(nodes, boxes, curves, graph_h):
    xs = [b[0] - b[2] / 2 for b in boxes.values()] + [b[0] + b[2] / 2 for b in boxes.values()]
    min_x, max_x = min(xs), max(xs)
    top = 60  # room for the title
    width = (max_x - min_x) + 2 * MARGIN
    height = graph_h + top + 50

    def X(x): return x - min_x + MARGIN
    def Y(y): return graph_h - y + top    # Graphviz y goes up, SVG y goes down

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="Source Sans Pro, Helvetica, Arial, sans-serif">',
        f'<rect width="100%" height="100%" fill="{BACKGROUND}"/>',
        f'<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        f'<path d="M0,0 L8,4 L0,8 z" fill="{EDGE_COLOR}"/></marker></defs>',
        f'<text x="{MARGIN}" y="34" font-size="20" font-weight="bold" fill="{TEXT_COLOR}">Data lineage (dbt)</text>',
    ]
    for pts in curves:
        d = f"M{X(pts[0][0]):.1f},{Y(pts[0][1]):.1f}"
        for i in range(1, len(pts) - 2, 3):
            c1, c2, e = pts[i], pts[i + 1], pts[i + 2]
            d += f" C{X(c1[0]):.1f},{Y(c1[1]):.1f} {X(c2[0]):.1f},{Y(c2[1]):.1f} {X(e[0]):.1f},{Y(e[1]):.1f}"
        parts.append(f'<path d="{d}" fill="none" stroke="{EDGE_COLOR}" stroke-width="{EDGE_WIDTH}" '
                     f'opacity="{EDGE_OPACITY}" marker-end="url(#arrow)"/>')
    for uid, node in nodes.items():
        cx, cy, w, h = boxes[uid]
        x, y = X(cx) - w / 2, Y(cy) - h / 2
        dash = ' stroke-dasharray="4 3"' if node["kind"] == "test" else ""
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4" fill="{COLORS[node["kind"]]}" '
                     f'stroke="#FFFFFF" stroke-opacity="0.45"{dash}/>')
        parts.append(f'<text x="{X(cx):.1f}" y="{Y(cy) + FONT_SIZE / 2 - 1:.1f}" font-size="{FONT_SIZE}" '
                     f'text-anchor="middle" fill="{TEXT_COLOR}">{escape(node["label"])}</text>')
    ly, lx = height - 24, MARGIN
    legend = [("source", "Raw table (bronze)"), ("model", "dbt model (silver / gold)")]
    if SHOW_TESTS:
        legend.append(("test", "Data test"))
    for kind, text in legend:
        dash = ' stroke-dasharray="4 3"' if kind == "test" else ""
        parts.append(f'<rect x="{lx}" y="{ly - 11}" width="18" height="14" rx="3" fill="{COLORS[kind]}" '
                     f'stroke="#FFFFFF" stroke-opacity="0.45"{dash}/>')
        parts.append(f'<text x="{lx + 26}" y="{ly}" font-size="13" fill="{TEXT_COLOR}">{text}</text>')
        lx += 46 + len(text) * 7
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    if not MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} not found. Run 'dbt build' (or 'dbt docs generate') in dbt_project first.")
    nodes = load_graph()
    boxes, curves, graph_h = run_graphviz(nodes)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_svg(nodes, boxes, curves, graph_h), encoding="utf-8")
    print(f"{len(nodes)} nodes, {sum(len(n['parents']) for n in nodes.values())} edges -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
