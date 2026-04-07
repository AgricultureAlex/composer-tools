#!/usr/bin/env python3
"""
Part Preparation Tool
=====================
Renames, prepends cover pages, and stamps part names onto a set of
music part PDFs exported from a notation program.

Requirements:
    pip install pypdf reportlab

Setup:
    Place a config file called part_prep_config.txt in your working
    directory (option 5 generates an example). It includes all settings:
    parts directory, composer, cover page, font, score order, and search strings.

    Alternatively, for interactive mode (options 1-3), place a
    score_order.txt file in the part PDF directory listing one
    instrument per line in score order.

Usage:
    python part_prep.py

Search string format (in config or interactive mode):
    input -> file_name / stamp_name + extra_blank_pages
    input -> stamp_name + extra_blank_pages
    input -> stamp_name
    input

    Examples:
        Soprano_Saxophone -> Sx / Soprano Saxophone + 3
          (file renamed using "Sx", stamped "Soprano Saxophone", 3 extra blank pages)
        Soprano_Saxophone -> Soprano Saxophone + 1
          (file renamed/stamped "Soprano Saxophone", 1 extra blank page)
        Soprano_Saxophone -> Soprano Saxophone
          (file renamed/stamped "Soprano Saxophone", 0 extra blank pages)
        Soprano_Saxophone
          (all values default to the search string, 0 extra blank pages)
"""

import os
import re
import shutil
import sys
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── config file ──────────────────────────────────────────────────────

CONFIG_FILENAME = "part_prep_config.txt"

EXAMPLE_CONFIG = """\
# Part Preparation Tool — Config File
# ====================================
# Fill in the fields below. Lines starting with # are ignored.
# To regenerate this file, delete it and run part_prep.py.

--- parts directory ---
# Path to the folder containing the exported part PDFs.
./your_parts_here

--- composer ---
Ma

--- cover_page ---
./your_front_matter_here/Pelagic (Part) Cover Page.pdf

--- blank_pages_after_cover ---
# Number of blank pages to insert after the cover and before the part.
# This is the global default; per-part overrides go in search_strings below.
# Default: 0
0

--- blank_page ---
./your_front_matter_here/Pelagic (Part) Cover Page.pdf

--- font_path ---
# If you're OK with boldface Cardo, you can leave this unchanged.
./fonts/cardo/Cardo-Bold.ttf

--- font_size ---
# If you're OK with font size 18, you can leave this unchanged.
18

--- search_strings ---
# One mapping per line. The order of lines here defines the output score order (!!!).
# Format:
#   input -> file_name / stamp_name + extra_blank_pages
#   input -> stamp_name + extra_blank_pages
#   input -> stamp_name
#   input
#
# file_name  = the name used in the output filename (defaults to stamp_name)
# stamp_name = the text stamped on page 1 (defaults to input)
# extra_blank_pages = blank pages inserted after cover for this part (defaults to 0)
#              (use extra_blank_pages if you need it for planned page turns)
#
# Examples:
#     Soprano_Saxophone -> Sx / Soprano Saxophone + 3
#         (file renamed using "Sx", stamped "Soprano Saxophone", 3 extra blank pages)
#     Soprano_Saxophone -> Soprano Saxophone + 1
#         (file renamed/stamped "Soprano Saxophone", 1 extra blank page)
#     Soprano_Saxophone -> Soprano Saxophone
#         (file renamed/stamped "Soprano Saxophone", 0 extra blank pages)
#     Soprano_Saxophone
#         (all values default to the search string, 0 extra blank pages)
#         (note the underscore in the search string/output!)
Flute -> Flute
Oboe -> Oboe
Clarinet -> Cl / Clarinet in B♭
Soprano_Saxophone -> Sx / Soprano Saxophone + 3
Bassoon -> Bassoon
Vibraphone -> Vibraphone
Harp -> Harp
Piano -> Piano
Violin_1 -> Violin 1
Violin_2 -> Violin 2
Viola -> Viola
Violoncello -> Violoncello
Contrabass -> Db / Double Bass
"""

# ── accidental fallback fonts ─────────────────────────────────────────
# These fonts are tried in order when rendering ♭ or ♯ glyphs that the
# primary font may not contain. Leland and Edwin ship with MuseScore;
# adjust the paths below to match your system if needed.

ACCIDENTAL_CHARS = "♭♯"

FALLBACK_FONT_PATHS = ["./fonts/Edwin/Edwin-Roman.ttf", "./fonts/Leland/Leland.ttf"]

# Registered ReportLab name for the accidental fallback font (set at runtime)
_accidental_font_name = None


def _ensure_accidental_font():
    """Register the first available accidental fallback font and return its name.

    Returns None if no fallback font could be loaded.
    """
    global _accidental_font_name
    if _accidental_font_name is not None:
        return _accidental_font_name

    for path in FALLBACK_FONT_PATHS:
        expanded = os.path.expanduser(path)
        if not os.path.exists(expanded):
            continue
        font_name = os.path.splitext(os.path.basename(expanded))[0]
        try:
            try:
                pdfmetrics.getFont(font_name)
            except KeyError:
                pdfmetrics.registerFont(TTFont(font_name, expanded))
            _accidental_font_name = font_name
            print(f"  → Accidental fallback font: {font_name}")
            return font_name
        except Exception as e:
            print(f"  Warning: could not load fallback font {expanded}: {e}")

    print("  Warning: no accidental fallback font available — ♭/♯ may not render.")
    return None


def _split_text_for_fonts(text, primary_font):
    """Split *text* into segments, each tagged with the font to use.

    Characters in ACCIDENTAL_CHARS are rendered with the accidental fallback
    font (if available); all other characters use *primary_font*.

    Returns a list of (segment_text, font_name) tuples.
    """
    fallback = _ensure_accidental_font()
    segments = []
    current_chars = []
    current_font = None

    for ch in text:
        font = fallback if (ch in ACCIDENTAL_CHARS and fallback) else primary_font
        if font != current_font:
            if current_chars:
                segments.append(("".join(current_chars), current_font))
            current_chars = [ch]
            current_font = font
        else:
            current_chars.append(ch)

    if current_chars:
        segments.append(("".join(current_chars), current_font))

    return segments


def _parse_search_line(line, default_name):
    """Parse one search_strings line into (search, file_name, stamp_name, extra_blank_pages).

    Supported formats:
        input -> file_name / stamp_name + N
        input -> stamp_name + N
        input -> stamp_name
        input
    """
    extra_blank_pages = 0

    if "->" in line:
        search, rhs = [part.strip() for part in line.split("->", 1)]
        search = search or default_name

        # Pull off trailing "+ N"
        plus_match = re.search(r"\+\s*(\d+)\s*$", rhs)
        if plus_match:
            extra_blank_pages = int(plus_match.group(1))
            rhs = rhs[: plus_match.start()].strip()

        # Check for "file_name / stamp_name"
        if "/" in rhs:
            file_name, stamp_name = [part.strip() for part in rhs.split("/", 1)]
            file_name = file_name or search
            stamp_name = stamp_name or file_name
        else:
            stamp_name = rhs or search
            file_name = stamp_name
    else:
        search = line.strip() or default_name
        file_name = search
        stamp_name = search

    return search, file_name, stamp_name, extra_blank_pages


def load_config(path):
    """Parse a part_prep_config.txt file into a dict."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    config = {}
    # Split on --- field_name --- dividers
    sections = re.split(r"^---\s*(.+?)\s*---\s*$", raw, flags=re.MULTILINE)
    # sections = ['preamble', 'field1', 'content1', 'field2', 'content2', ...]
    for i in range(1, len(sections) - 1, 2):
        field = sections[i].strip()
        lines = [
            line.strip()
            for line in sections[i + 1].strip().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if field == "search_strings":
            config[field] = lines  # keep as list
        elif lines:
            config[field] = lines[0]  # single value

    return config


def generate_example_config(directory):
    """Write an example config file and exit."""
    path = os.path.join(directory, CONFIG_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write(EXAMPLE_CONFIG)
    print(f"Generated example config: {path}")
    print("Edit it with your settings, then run part_prep.py again.")


def resolve_config(config):
    """Build search tuples from search_strings lines.

    Score order is derived from the order of search_strings lines.
    The stamp_name of each line is used as the score-order label.
    """
    raw_searches = config.get("search_strings", [])
    search_strings = []

    for i, line in enumerate(raw_searches):
        order = i + 1
        line = line.strip()
        # Use the raw search token as the fallback default name
        default_name = line.split("->")[0].strip() if "->" in line else line
        search, file_name, stamp_name, extra_blank_pages = _parse_search_line(
            line, default_name
        )
        search_strings.append((search, order, file_name, stamp_name, extra_blank_pages))

    return search_strings


# ── helpers ──────────────────────────────────────────────────────────


def confirm(prompt="Proceed? (y/n): "):
    return input(prompt).strip().lower() == "y"


def numbered_part_files(directory):
    """Return sorted list of filenames matching '##. ...' in directory."""
    return sorted(
        f
        for f in os.listdir(directory)
        if f.endswith(".pdf") and re.match(r"\d{2}\.", f)
    )


def ask_directory():
    directory = input("Parts directory containing the part PDFs [.]: ").strip() or "."
    if not os.path.isdir(directory):
        print(f"Directory not found: {directory}")
        sys.exit(1)
    return directory


def ask_composer():
    composer = input("Composer last name (e.g. Ma): ").strip()
    if not composer:
        print("No name entered. Exiting.")
        sys.exit(1)
    composer_upper = composer.upper()
    print(f"  → Composer tag: {composer_upper}")
    return composer_upper


def load_score_order(directory):
    """Load score order from score_order.txt in the given directory."""
    path = os.path.join(directory, "score_order.txt")
    if not os.path.exists(path):
        print(f"score_order.txt not found in {directory}")
        print("Create a text file called score_order.txt with one instrument per line.")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        score_order = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    if not score_order:
        print("score_order.txt is empty.")
        sys.exit(1)

    print(f"Loaded score order from {path} ({len(score_order)} parts):\n")
    for i, name in enumerate(score_order, 1):
        print(f"    {i:2d}. {name}")

    return score_order


def ask_search_strings(score_order):
    """Ask for search-string mapping per instrument.

    Format: input -> file_name / stamp_name + extra_blank_pages
    """
    print("\nFor each instrument, enter one line in this format:")
    print("  input -> file_name / stamp_name + extra_blank_pages")
    print("Simpler forms are also accepted:")
    print("  input -> stamp_name + extra_blank_pages")
    print("  input -> stamp_name")
    print("  input")
    print("Examples:")
    print("  Soprano_Saxophone -> Sx / Soprano Saxophone + 3")
    print("  Violin_1 -> Violin 1 + 1")
    print("  Flute")
    print("Type 'b' to go back.\n")

    search_strings = []
    i = 0
    while i < len(score_order):
        default_name = score_order[i]
        order = i + 1

        if i < len(search_strings):
            prev_search, _, prev_file, prev_stamp, prev_extra = search_strings[i]
            # Reconstruct a representative default line
            if prev_file != prev_stamp:
                default_line = f"{prev_search} -> {prev_file} / {prev_stamp}"
            elif prev_stamp != prev_search:
                default_line = f"{prev_search} -> {prev_stamp}"
            else:
                default_line = prev_search
            if prev_extra:
                default_line += f" + {prev_extra}"
        else:
            default_line = default_name

        line = input(
            f'  {order:2d}. {default_name} [Enter = "{default_line}"]: '
        ).strip()

        if line.lower() == "b":
            if i > 0:
                i -= 1
                print(f"      ↩ Back to {score_order[i]}")
            else:
                print("      Already at the first instrument.")
            continue

        if not line:
            line = default_line

        search, file_name, stamp_name, extra_blank_pages = _parse_search_line(
            line, default_name
        )

        entry = (search, order, file_name, stamp_name, extra_blank_pages)
        if i < len(search_strings):
            search_strings[i] = entry
        else:
            search_strings.append(entry)
        i += 1

    if not search_strings:
        print("No search strings entered. Exiting.")
        sys.exit(1)

    return search_strings


def make_output_dir(composer, cwd=None):
    """Create and return an output directory named '[COMPOSER NAME] [PIECE NAME HERE]'.

    The directory is created in *cwd* (defaults to the current working directory).
    """
    # TODO: When directly naming the folder to composer
    if cwd is None:
        cwd = os.getcwd()
    output_name = "outputs_go_here"
    output_path = os.path.join(cwd, output_name)
    os.makedirs(output_path, exist_ok=True)
    return output_path


# ── 1. rename (copy) ─────────────────────────────────────────────────


def rename_parts(
    directory=None,
    composer=None,
    score_order=None,
    search_strings=None,
    output_dir=None,
):
    """Copy exported part PDFs into score order in the output directory.

    New names follow the format: ##. COMPOSER File Name.pdf
    Files are copied from *directory* into *output_dir*; originals are untouched.
    """
    directory = directory or ask_directory()
    composer = composer or ask_composer()
    if score_order is None:
        score_order = load_score_order(directory)
    if search_strings is None:
        search_strings = ask_search_strings(score_order)
    if output_dir is None:
        output_dir = make_output_dir(composer)

    all_pdfs = [f for f in os.listdir(directory) if f.endswith(".pdf")]
    copies = []

    for search, order, file_name, _stamp_name, _extra_blank_pages in search_strings:
        matches = [f for f in all_pdfs if search in f]
        if len(matches) == 1:
            old = matches[0]
            new = f"{order:02d}. {composer} {file_name}.pdf"
            copies.append((order, old, new))
        elif len(matches) == 0:
            print(f"  WARNING: No file found containing '{search}'")
        else:
            print(f"  WARNING: Multiple files match '{search}': {matches}")
            print("           Skipping — make the search string more specific.")

    copies.sort(key=lambda x: x[0])

    if not copies:
        print("No files matched. Nothing to copy.")
        return False

    print(f"\nPlanned copies ({len(copies)} files) → {output_dir}:\n")
    for order, old, new in copies:
        print(f"  {old}")
        print(f"  → {new}\n")

    if not confirm():
        print("Copy cancelled.")
        return False

    for _, old, new in copies:
        shutil.copy2(
            os.path.join(directory, old),
            os.path.join(output_dir, new),
        )
    print(f"Copied {len(copies)} files to {output_dir}.\n")
    return True


# ── 2. prepend cover ─────────────────────────────────────────────────


def prepend_cover(
    directory=None,
    cover_name=None,
    blank_pages_after_cover=0,
    search_strings=None,
    cwd=None,
):
    """Prepend a cover-page PDF to each numbered part file, then optional blank pages.

    Cover and blank-page PDFs are resolved relative to *cwd* (the current working
    directory), not the parts directory. Per-part blank page counts (from
    search_strings) override the global default.
    """
    if cwd is None:
        cwd = os.getcwd()
    directory = directory
    if not cover_name:
        cover_name = input("Cover page path (relative to current directory): ").strip()
    if not cover_name:
        print("No filename entered. Skipping cover prepend.")
        return False

    if blank_pages_after_cover is None:
        blank_input = input("Blank pages after cover [0]: ").strip()
        blank_pages_after_cover = int(blank_input) if blank_input else 0

    if blank_pages_after_cover < 0:
        print("Blank pages cannot be negative.")
        return False

    # Resolve cover path: if already absolute use as-is, otherwise resolve from cwd
    if os.path.isabs(cover_name):
        cover_path = cover_name
    else:
        cover_path = os.path.normpath(os.path.join(cwd, cover_name))
    if not os.path.exists(cover_path):
        print(f"File not found: {cover_path}")
        return False

    cover_reader = PdfReader(cover_path)
    print(f"Cover PDF has {len(cover_reader.pages)} page(s).")
    print(f"Global blank pages after cover: {blank_pages_after_cover}\n")

    # Build a lookup from filename → per-part extra blank pages
    per_part_blanks = {}
    if search_strings:
        for (
            _search,
            order,
            _file_name,
            _stamp_name,
            extra_blank_pages,
        ) in search_strings:
            numbered_name_prefix = f"{order:02d}."
            per_part_blanks[numbered_name_prefix] = extra_blank_pages

    part_files = [
        f for f in numbered_part_files(directory) if f != os.path.basename(cover_name)
    ]

    if not part_files:
        print("No numbered part files found.")
        return False

    print(f"Will prepend cover to {len(part_files)} file(s):\n")
    for f in part_files:
        prefix = f[:3]  # e.g. "01."
        blanks = per_part_blanks.get(prefix, blank_pages_after_cover)
        print(f"  {f}  (blank pages after cover: {blanks})")

    print()
    if not confirm():
        print("Cover prepend cancelled.")
        return False

    for filename in part_files:
        filepath = os.path.join(directory, filename)
        part_reader = PdfReader(filepath)
        writer = PdfWriter()

        for page in cover_reader.pages:
            writer.add_page(page)

        prefix = filename[:3]
        blanks = per_part_blanks.get(prefix, blank_pages_after_cover)
        if blanks > 0:
            ref = cover_reader.pages[-1] if cover_reader.pages else part_reader.pages[0]
            blank_w = float(ref.mediabox.width)
            blank_h = float(ref.mediabox.height)
            for _ in range(blanks):
                writer.add_blank_page(blank_w, blank_h)

        for page in part_reader.pages:
            writer.add_page(page)

        with open(filepath, "wb") as out:
            writer.write(out)
        print(f"  Done: {filename}")

    print(f"\nPrepended cover to {len(part_files)} files.\n")
    return True


# ── 3. stamp part names ──────────────────────────────────────────────


def _register_font(font_path):
    """Register a TTF font file and return its ReportLab name."""
    font_name = os.path.splitext(os.path.basename(font_path))[0]
    try:
        pdfmetrics.getFont(font_name)
    except KeyError:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    return font_name


def _create_text_overlay(
    text, page_width, page_height, font_name="Times-Bold", font_size=12
):
    """Create a one-page PDF with text at the top-right corner.

    Text is split into segments so that ♭/♯ characters are drawn with the
    accidental fallback font while the rest uses the primary font.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    margin_right = 36  # 0.5 in
    margin_top = 36  # 0.5 in

    # TODO: Change this when finally implementing accidentals support.
    # It should read
    # segments = _split_text_for_fonts(text, font_name)
    segments = [(text, font_name)]

    # Calculate total width across all segments so we can right-align the block.
    total_width = 0.0
    for seg_text, seg_font in segments:
        c.setFont(seg_font, font_size)
        total_width += c.stringWidth(seg_text, seg_font, font_size)

    x = page_width - margin_right - total_width
    y = page_height - margin_top - font_size

    # Draw each segment in its own font, advancing x as we go.
    for seg_text, seg_font in segments:
        c.setFont(seg_font, font_size)
        c.drawString(x, y, seg_text)
        x += c.stringWidth(seg_text, seg_font, font_size)

    c.save()
    buf.seek(0)
    return buf


def _extract_part_name(filename, search_strings=None):
    """Extract stamp name for a file.

    If search_strings is provided, look up the stamp_name by order number.
    Otherwise fall back to parsing '##. COMPOSER Stamp Name.pdf'.
    """
    if search_strings:
        prefix_match = re.match(r"(\d{2})\.", filename)
        if prefix_match:
            order = int(prefix_match.group(1))
            for (
                _search,
                ss_order,
                _file_name,
                stamp_name,
                _extra_blank_pages,
            ) in search_strings:
                if ss_order == order:
                    return stamp_name

    # Fallback: derive from filename
    name = filename.rsplit(".pdf", 1)[0]
    match = re.match(r"\d{2}\.\s+\S+\s+(.+)$", name)
    return match.group(1).strip() if match else None


def stamp_part_names(
    directory=None, font_path=None, font_size=None, search_strings=None
):
    """Add the part name to the top-right of page 1 using a user-specified font."""
    directory = directory or ask_directory()

    # Font configuration
    if font_path is None:
        print("Font setup:")
        font_path = input(
            "  Path to .ttf font file [leave blank for Times-Bold]: "
        ).strip()

    if font_path:
        font_path = os.path.expanduser(font_path)
        if not os.path.exists(font_path):
            print(f"  Font file not found: {font_path}")
            return False
        font_name = _register_font(font_path)
        print(f"  → Registered font: {font_name}")
    else:
        font_name = "Times-Bold"
        print(f"  → Using built-in: {font_name}")

    if font_size is None:
        size_input = input("  Font size in pt [12]: ").strip()
        font_size = int(size_input) if size_input else 12
    print(f"  → Size: {font_size}pt\n")

    part_files = numbered_part_files(directory)
    if not part_files:
        print("No numbered part files found.")
        return False

    plan = []
    print(f"Found {len(part_files)} file(s):\n")
    for f in part_files:
        part_name = _extract_part_name(f, search_strings)
        if part_name:
            plan.append((f, part_name))
            print(f'  {f}  →  "{part_name}"')
        else:
            print(f"  {f}  →  [SKIPPED: could not extract part name]")

    if not plan:
        print("\nNo files to process.")
        return False

    print()
    if not confirm("Add part names to these files? (y/n): "):
        print("Stamp cancelled.")
        return False

    for filename, part_name in plan:
        filepath = os.path.join(directory, filename)
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            if i == 0:
                box = page.mediabox
                pw, ph = float(box.width), float(box.height)
                overlay_buf = _create_text_overlay(
                    part_name, pw, ph, font_name, font_size
                )
                overlay_page = PdfReader(overlay_buf).pages[0]
                page.merge_page(overlay_page)
            writer.add_page(page)

        with open(filepath, "wb") as out:
            writer.write(out)
        print(f"  Done: {filename}")

    print(f"\nStamped part names on {len(plan)} files.\n")
    return True


# ── 4. all-in-one ─────────────────────────────────────────────────────


def all_in_one_interactive():
    """Run copy-rename → prepend cover → stamp part names (interactive prompts)."""
    cwd = os.getcwd()
    directory = ask_directory()
    composer = ask_composer()
    score_order = load_score_order(directory)
    search_strings = ask_search_strings(score_order)

    output_dir = make_output_dir(composer, cwd)
    print(f"\nOutput directory: {output_dir}\n")

    print("\n── Step 1/3: Copy & Rename ──\n")
    if not rename_parts(directory, composer, score_order, search_strings, output_dir):
        if not confirm("Copy did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 2/3: Prepend Cover Page ──\n")
    blank_input = input("Global blank pages after cover [0]: ").strip()
    blank_pages_after_cover = int(blank_input) if blank_input else 0
    if not prepend_cover(
        output_dir,
        blank_pages_after_cover=blank_pages_after_cover,
        search_strings=search_strings,
        cwd=cwd,
    ):
        if not confirm("Cover prepend did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 3/3: Stamp Part Names ──\n")
    stamp_part_names(output_dir, search_strings=search_strings)

    print("\n" + "=" * 60)
    print("  All done!")
    print("=" * 60)


def all_in_one_from_config(config, cwd=None):
    """Run copy-rename → prepend cover → stamp part names from config file."""
    if cwd is None:
        cwd = os.getcwd()

    directory = config.get("parts directory", config.get("directory", "."))
    directory = os.path.expanduser(directory)
    if not os.path.isdir(directory):
        print(f"Parts directory not found: {directory}")
        return

    composer = config.get("composer", "").upper()
    if not composer:
        print("No composer specified in config. Exiting.")
        return
    print(f"Composer tag: {composer}")

    search_strings = resolve_config(config)

    if not search_strings:
        print("No search_strings found in config. Exiting.")
        return

    # Derive score order from the stamp names in search_strings order
    score_order = [
        stamp_name for _search, _order, _file_name, stamp_name, _extra in search_strings
    ]
    print(f"\nScore order from search_strings ({len(score_order)} parts):\n")
    for i, name in enumerate(score_order, 1):
        print(f"    {i:2d}. {name}")

    output_dir = make_output_dir(composer, cwd)
    print(f"\nOutput directory: {output_dir}\n")

    cover_name = config.get("cover_page", "")
    blank_pages_str = config.get("blank_pages_after_cover", "0")
    blank_pages_after_cover = int(blank_pages_str) if blank_pages_str else 0
    font_path = config.get("font_path", "")
    font_size_str = config.get("font_size", "12")
    font_size = int(font_size_str) if font_size_str else 12

    print("\n── Step 1/3: Copy & Rename ──\n")
    if not rename_parts(directory, composer, score_order, search_strings, output_dir):
        if not confirm("Copy did not complete. Continue anyway? (y/n): "):
            return

    print("\n── Step 2/3: Prepend Cover Page ──\n")
    if cover_name:
        if not prepend_cover(
            output_dir, cover_name, blank_pages_after_cover, search_strings, cwd=cwd
        ):
            if not confirm("Cover prepend did not complete. Continue anyway? (y/n): "):
                return
    else:
        print("No cover_page in config. Skipping.")

    print("\n── Step 3/3: Stamp Part Names ──\n")
    stamp_part_names(output_dir, font_path, font_size, search_strings)

    print("\n" + "=" * 60)
    print("  All done!")
    print("=" * 60)


# ── main menu ─────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("  Part Preparation Tool")
    print("=" * 60)
    print()
    print("  1. Rename files into score order")
    print("  2. Prepend a cover page to each part")
    print("  3. Stamp part names on page 1 (top-right, custom font)")
    print("  4. All of the above (1 → 2 → 3)")
    print("  5. Generate example config file")
    print()

    choice = input("Choose [1/2/3/4/5]: ").strip()
    print()

    if choice == "5":
        directory = input("Directory for config file [.]: ").strip() or "."
        generate_example_config(directory)
        return

    # Check for config file in current directory
    cwd = os.getcwd()
    config = None
    if choice == "4":
        # Look for config in . first, then ask
        for candidate in [".", cwd]:
            cfg_path = os.path.join(candidate, CONFIG_FILENAME)
            if os.path.exists(cfg_path):
                print(f"Found config: {cfg_path}")
                if confirm("Use this config file? (y/n): "):
                    config = load_config(cfg_path)
                    print(f"  Loaded {len(config)} fields from config.\n")
                break

    if choice == "1":
        rename_parts()
    elif choice == "2":
        prepend_cover()
    elif choice == "3":
        stamp_part_names()
    elif choice == "4":
        if config:
            all_in_one_from_config(config, cwd=cwd)
        else:
            all_in_one_interactive()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
