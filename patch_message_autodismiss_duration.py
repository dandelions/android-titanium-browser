#!/usr/bin/env python3

from pathlib import Path
import re
import sys

src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
target_file = src_dir / "chrome/android/java/src/org/chromium/chrome/browser/messages/ChromeMessageAutodismissDurationProvider.java"

if not target_file.is_file():
    print(f"Target file not found: {target_file}", file=sys.stderr)
    sys.exit(1)

text = target_file.read_text(encoding="utf-8")

replacement_constructor = """    public ChromeMessageAutodismissDurationProvider() {
        mAutodismissDurationMs = (long) (4.5 * DateUtils.SECOND_IN_MILLIS);
        mAutodismissDurationWithA11yMs = 10 * (int) DateUtils.SECOND_IN_MILLIS;
    }"""

replacement_get = """    @Override
    public long get(@MessageIdentifier int messageIdentifier, long customDuration) {
        long nonA11yDuration =
                customDuration > 0
                        ? Math.max(mAutodismissDurationMs, customDuration)
                        : mAutodismissDurationMs;
        if (AccessibilityState.isTouchExplorationEnabled()) {
            return AccessibilityState.getRecommendedTimeoutMillis(
                    (int) mAutodismissDurationWithA11yMs, (int) nonA11yDuration);
        }
        return nonA11yDuration;
    }"""

def replace_block(content, pattern, replacement):
    match = pattern.search(content)
    if not match:
        return content
    start = content.rfind("\n", 0, match.start()) + 1
    brace = content.find("{", match.start())
    depth = 0
    end = None
    for idx in range(brace, len(content)):
        if content[idx] == "{":
            depth += 1
        elif content[idx] == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        print(f"Error: unclosed block in {target_file}", file=sys.stderr)
        sys.exit(1)
    return content[:start] + replacement + content[end:]

p_ctor = re.compile(r"(?m)^[ \t]*public[ \t]+ChromeMessageAutodismissDurationProvider\(\)[ \t]*\{")
p_get = re.compile(r"(?m)^[ \t]*@Override\s+public[ \t]+long[ \t]+get\(@MessageIdentifier[ \t]+int")

text = replace_block(text, p_ctor, replacement_constructor)
text = replace_block(text, p_get, replacement_get)

target_file.write_text(text, encoding="utf-8")

if "4.5 * DateUtils.SECOND_IN_MILLIS" not in text or "isTouchExplorationEnabled" not in text:
    print(f"Error: patch verification failed for {target_file}", file=sys.stderr)
    sys.exit(1)

print(f"Successfully patched message autodismiss duration to 4.5s in {target_file}")
