"""Generate SVG icon set for game entities from backend/main.py seeds.

Creates icon files in frontend/public/icons/<category>/ and a JSON index map.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "backend" / "main.py"
ICONS_ROOT = ROOT / "frontend" / "public" / "icons"
INDEX_PATH = ICONS_ROOT / "index.generated.json"
README_PATH = ICONS_ROOT / "README.generated.md"

# Category -> SQL table names to scan.
CATEGORY_TABLES = {
    "items": ["items"],
    "abilities": ["abilities"],
    "classes": ["character_classes"],
    "races": ["races"],
    "mobs": ["mobs"],
    "npcs": ["npcs"],
    "objects": ["location_objects"],
    "loot_tables": ["loot_tables"],
    "quests": ["quests"],
}

# Index of quoted string in VALUES tuple per SQL table.
# Example for location_objects tuple:
# (1, 'npc', 'Охотник Раймонд', ...) -> name is quoted index 1
TABLE_QUOTED_NAME_INDEX = {
    "abilities": 0,
    "items": 0,
    "character_classes": 0,
    "races": 0,
    "mobs": 0,
    "npcs": 0,
    "location_objects": 1,
    "loot_tables": 0,
    "quests": 1,
}

CYR_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def translit(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch in CYR_MAP:
            out.append(CYR_MAP[ch])
        elif "a" <= ch <= "z" or "0" <= ch <= "9":
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "entity"


def hash_color(seed: str) -> tuple[str, str]:
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    c1 = f"#{h[:6]}"
    c2 = f"#{h[6:12]}"
    return c1, c2


def token_for(name: str) -> str:
    slug = translit(name)
    parts = [p for p in slug.split("-") if p]
    if len(parts) >= 2:
        token = (parts[0][0] + parts[1][0]).upper()
    else:
        token = slug[:2].upper()
    return token or "??"


def extract_names_for_table(text: str, table: str) -> set[str]:
    names: set[str] = set()
    # Capture execute(""" ... """) blocks that contain a concrete INSERT INTO <table>.
    for block in re.findall(r"execute\(\"\"\"([\s\S]*?)\"\"\"\)", text):
        if f"INSERT INTO {table}" not in block:
            continue

        # VALUES rows: parse each tuple line and take the table-specific quoted value.
        q_idx = TABLE_QUOTED_NAME_INDEX.get(table, 0)
        for line in block.splitlines():
            row = line.strip().rstrip(",")
            if not row.startswith("("):
                continue
            quoted = re.findall(r"'([^']+)'", row)
            if len(quoted) > q_idx:
                names.add(quoted[q_idx].strip())

        # SELECT rows used for idempotent inserts.
        for select_name in re.findall(r"SELECT\s+'([^']+)'\s*,", block):
            names.add(select_name.strip())

    return {n for n in names if n}


def make_svg(name: str, category: str) -> str:
    c1, c2 = hash_color(f"{category}:{name}")
    token = token_for(name)
    label = category.upper()
    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"128\" height=\"128\" viewBox=\"0 0 128 128\" role=\"img\" aria-label=\"{name}\">
  <defs>
    <linearGradient id=\"g\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">
      <stop offset=\"0%\" stop-color=\"{c1}\"/>
      <stop offset=\"100%\" stop-color=\"{c2}\"/>
    </linearGradient>
  </defs>
  <rect x=\"4\" y=\"4\" width=\"120\" height=\"120\" rx=\"18\" fill=\"url(#g)\" stroke=\"#0b1020\" stroke-width=\"3\"/>
  <circle cx=\"64\" cy=\"52\" r=\"26\" fill=\"rgba(255,255,255,0.18)\"/>
  <text x=\"64\" y=\"60\" text-anchor=\"middle\" font-family=\"Segoe UI, Tahoma, sans-serif\" font-size=\"20\" fill=\"#ffffff\" font-weight=\"700\">{token}</text>
  <text x=\"64\" y=\"108\" text-anchor=\"middle\" font-family=\"Consolas, monospace\" font-size=\"10\" fill=\"#e5e7eb\" letter-spacing=\"1\">{label}</text>
</svg>
"""


def unique_filename(name: str, used: set[str]) -> str:
    base = translit(name)
    candidate = f"{base}.svg"
    if candidate not in used:
        used.add(candidate)
        return candidate
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}.svg"
    used.add(candidate)
    return candidate


def main() -> None:
    text = MAIN_PY.read_text(encoding="utf-8")

    index: dict[str, dict[str, str]] = {}

    for category, tables in CATEGORY_TABLES.items():
        names: set[str] = set()
        for table in tables:
            names.update(extract_names_for_table(text, table))

        if not names:
            continue

        category_dir = ICONS_ROOT / category
        category_dir.mkdir(parents=True, exist_ok=True)

        used_files: set[str] = set()
        name_to_file: dict[str, str] = {}
        for name in sorted(names):
            filename = unique_filename(name, used_files)
            svg_path = category_dir / filename
            svg_path.write_text(make_svg(name, category), encoding="utf-8")
            name_to_file[name] = f"/icons/{category}/{filename}"

        index[category] = name_to_file

    ICONS_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(v) for v in index.values())
    readme = [
        "# Generated Icons",
        "",
        "This folder includes auto-generated SVG icon placeholders for game entities.",
        "",
        f"Total icons: {total}",
        "",
        "Categories:",
    ]
    for category in sorted(index):
        readme.append(f"- {category}: {len(index[category])}")
    readme.append("")
    readme.append("Name-to-path map: `frontend/public/icons/index.generated.json`")
    README_PATH.write_text("\n".join(readme) + "\n", encoding="utf-8")

    print(f"Generated {total} icons")
    for category in sorted(index):
        print(f"  {category}: {len(index[category])}")


if __name__ == "__main__":
    main()
