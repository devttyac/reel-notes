"""
File output module.

Renders structured summary data into plain markdown notes.
No YAML frontmatter, no wikilink syntax, no Obsidian-specific formatting.
"""

import os
import re
from datetime import date
from pathlib import Path


def _sanitise_filename(title: str) -> str:
    """Convert a title to a safe filename. Removes special chars, truncates to 80 chars."""
    safe = re.sub(r"[^\w\s-]", "", title)
    safe = re.sub(r"\s+", "-", safe.strip())
    safe = safe[:80].rstrip("-")
    return safe


def render_note_plain(
    summary_data: dict,
    video_metadata: dict,
    output_dir: str,
    compact: bool = False,
) -> str:
    """Render a summary as plain markdown — no YAML frontmatter, no [[wikilink]] syntax.

    Produces a single combined file (no atomic concept notes, no MOC).

    Args:
        summary_data: dict from summariser.summarise_transcript()
        video_metadata: dict with "title", "channel", "url" keys
        output_dir: base output directory
        compact: if True, append "(Compact)" to the folder/file name

    Returns:
        Absolute path to the plain markdown summary file.
    """
    title = video_metadata["title"]
    channel = video_metadata.get("channel", "Unknown")
    url = video_metadata.get("url", "")
    mode_suffix = " (Compact)" if compact else " (Full)"
    display_title = title + mode_suffix
    safe_title = _sanitise_filename(display_title)
    today = date.today().isoformat()

    # Create subfolder for this video
    video_dir = os.path.join(output_dir, safe_title)
    os.makedirs(video_dir, exist_ok=True)

    real_video_dir = os.path.realpath(video_dir)
    real_output_dir = os.path.realpath(output_dir)
    if not real_video_dir.startswith(real_output_dir):
        raise RuntimeError(
            f"Output directory resolved outside expected path.\n"
            f"  Expected under: {real_output_dir}\n"
            f"  Actual:         {real_video_dir}\n"
        )

    lines: list[str] = []

    # H1 title — no YAML, no frontmatter
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Channel:** {channel}")
    lines.append(f"**Date:** {today}")
    lines.append(f"**Source:** {url}")
    lines.append("")

    # Overview
    overview = summary_data.get("overview", "No overview available.")
    lines.append("## Overview")
    lines.append("")
    lines.append(overview)
    lines.append("")

    # Key Concepts — plain text, no wikilinks
    key_concepts = summary_data.get("key_concepts", [])
    lines.append("## Key Concepts")
    lines.append("")
    if key_concepts:
        for kc in key_concepts:
            concept_name = kc.get("concept", "Unknown Concept")
            timestamp = kc.get("timestamp", "")
            explanation = kc.get("explanation", "")
            ts_str = f" ({timestamp})" if timestamp else ""
            lines.append(f"- **{concept_name}**{ts_str} — {explanation}")
            for sc in kc.get("sub_concepts", []):
                sc_name = sc.get("concept", "")
                sc_ts = sc.get("timestamp", "")
                sc_exp = sc.get("explanation", "")
                sc_ts_str = f" ({sc_ts})" if sc_ts else ""
                lines.append(f"  - **{sc_name}**{sc_ts_str} — {sc_exp}")
    else:
        lines.append("No key concepts extracted.")
    lines.append("")

    # Detailed Summary
    detailed_summary = summary_data.get("detailed_summary", "No detailed summary available.")
    lines.append("## Detailed Summary")
    lines.append("")
    lines.append(detailed_summary)
    lines.append("")

    # Takeaways
    takeaways = summary_data.get("takeaways", [])
    lines.append("## Key Takeaways")
    lines.append("")
    if takeaways:
        for t in takeaways:
            lines.append(f"- {t}")
    else:
        lines.append("No actionable takeaways extracted.")
    lines.append("")

    # Code Snippets (if present)
    code_snippets = summary_data.get("code_snippets", [])
    if code_snippets:
        lines.append("## Code Snippets")
        lines.append("")
        for cs in code_snippets:
            desc = cs.get("description", "")
            lang = cs.get("language", "")
            code = cs.get("code", "")
            ts = cs.get("timestamp", "")
            ts_str = f" ({ts})" if ts else ""
            lines.append(f"**{desc}**{ts_str}")
            lines.append("")
            lines.append(f"```{lang}")
            lines.append(code)
            lines.append("```")
            lines.append("")

    # Timestamps Index — plain text, no wikilinks
    lines.append("## Timestamps Index")
    lines.append("")
    if key_concepts:
        for kc in key_concepts:
            ts = kc.get("timestamp", "")
            concept_name = kc.get("concept", "Unknown Concept")
            lines.append(f"- {ts} — {concept_name}")
            for sc in kc.get("sub_concepts", []):
                sc_ts = sc.get("timestamp", "")
                sc_name = sc.get("concept", "")
                if sc_ts:
                    lines.append(f"  - {sc_ts} — {sc_name}")
    else:
        lines.append("No timestamps available.")
    lines.append("")

    # Related Links — plain text, no wikilinks
    suggested_links = summary_data.get("suggested_links", [])
    lines.append("## Related Links")
    lines.append("")
    if suggested_links:
        for link in suggested_links:
            lines.append(f"- {link}")
    else:
        lines.append("No related links identified.")
    lines.append("")

    content = "\n".join(lines)

    parent_filename = f"{safe_title}.md"
    parent_path = os.path.join(video_dir, parent_filename)
    with open(parent_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  Created plain note: {parent_path}")

    return parent_path
