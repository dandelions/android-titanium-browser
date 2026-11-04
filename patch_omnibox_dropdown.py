#!/usr/bin/env python3
"""Reapply Helium's Omnibox dropdown alignment after Android baseline cleanup."""

from pathlib import Path
import re
import sys


DROPDOWN_PATH = Path(
    "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/OmniboxSuggestionsDropdown.java"
)


def patch_layout_scroll_listener(path):
    text = path.read_text()
    class_start = text.find("class SuggestionLayoutScrollListener")
    if class_start < 0:
        raise SystemExit(f"SuggestionLayoutScrollListener class not found in {path}")

    reset_anchor = "/* package */ void resetScrollState() {"
    reset_pos = text.find(reset_anchor, class_start)
    if reset_pos < 0:
        raise SystemExit(f"resetScrollState anchor not found in {path}")

    field_anchor = "private boolean mCurrentGestureAffectedKeyboardState;"
    field_pos = text.find(field_anchor, class_start, reset_pos)
    if field_pos < 0:
        raise SystemExit(f"SuggestionLayoutScrollListener field anchor not found in {path}")
    if "private boolean mAlignToBottom;" not in text[class_start:reset_pos]:
        field_end = field_pos + len(field_anchor)
        text = text[:field_end] + "\n        private boolean mAlignToBottom;" + text[field_end:]
        reset_pos += len("\n        private boolean mAlignToBottom;")

    setter = """        void setAlignToBottom(boolean alignToBottom) {
            if (mAlignToBottom == alignToBottom) return;
            mAlignToBottom = alignToBottom;
            setReverseLayout(alignToBottom);
            setStackFromEnd(alignToBottom);
            if (!alignToBottom) scrollToPositionWithOffset(0, 0);
            requestLayout();
        }
"""
    setter_pattern = re.compile(
        r"        void setAlignToBottom\(boolean alignToBottom\) \{\n[\s\S]*?\n        \}"
    )
    class_region = text[class_start:reset_pos]
    matches = list(setter_pattern.finditer(class_region))
    if len(matches) > 1:
        raise SystemExit(f"Multiple setAlignToBottom methods found in {path}")
    if matches:
        match = matches[0]
        text = text[:class_start + match.start()] + setter.rstrip() + text[class_start + match.end():]
    else:
        doc_anchor = "        /**\n         * Reset the internal scroll tracker."
        doc_pos = text.find(doc_anchor, class_start, reset_pos)
        if doc_pos < 0:
            raise SystemExit(f"resetScrollState documentation anchor not found in {path}")
        text = text[:doc_pos] + setter + text[doc_pos:]
    path.write_text(text)


def patch_dropdown_wrapper(path):
    text = path.read_text()
    wrapper_pattern = re.compile(
        r"(?m)^[ \t]*(?:(?:public|protected|private)\s+)?"
        r"void heliumSetAlignToBottom\(boolean alignToBottom\) \{\n"
        r"[ \t]*mLayoutScrollListener\.setAlignToBottom\(alignToBottom\);\n"
        r"[ \t]*\}"
    )
    text = wrapper_pattern.sub("", text)

    class_pattern = re.compile(
        r"\bclass\s+OmniboxSuggestionsDropdown\b[^{}]*\{"
    )
    class_match = class_pattern.search(text)
    if class_match is None:
        raise SystemExit(f"OmniboxSuggestionsDropdown class not found in {path}")

    wrapper = """    void heliumSetAlignToBottom(boolean alignToBottom) {
        mLayoutScrollListener.setAlignToBottom(alignToBottom);
    }
"""
    suffix = text[class_match.end():].lstrip("\r\n")
    text = text[:class_match.end()] + "\n" + wrapper + suffix
    path.write_text(text)


source_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
dropdown_path = source_root / DROPDOWN_PATH
patch_layout_scroll_listener(dropdown_path)
patch_dropdown_wrapper(dropdown_path)
text = dropdown_path.read_text()
if "void heliumSetAlignToBottom(boolean alignToBottom)" not in text:
    raise SystemExit(f"Omnibox dropdown wrapper missing after patch: {dropdown_path}")
print(f"Applied Omnibox dropdown alignment patch to {dropdown_path}")
