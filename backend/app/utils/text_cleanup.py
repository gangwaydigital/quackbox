"""Text cleanup utilities for email bodies."""
import re

# Patterns for quoted text
QUOTE_LINE = re.compile(r'^(>{1,}\s?)+', re.MULTILINE)
QUOTE_HEADER = re.compile(r'^On .+ wrote:\s*$', re.MULTILINE | re.IGNORECASE)
FORWARD_HEADER = re.compile(r'^-{3,}\s*(Forwarded|Original)\s+[Mm]essage\s*-{3,}\s*$', re.MULTILINE)
SIGNATURE_MARKERS = re.compile(r'^(--|__)\s*$', re.MULTILINE)


def clean_body_text(text: str, strip_quotes: bool = True, strip_signatures: bool = True) -> str:
    """
    Clean up email body text:
    - Remove quoted reply chains (> prefixed lines)
    - Remove forwarded message headers
    - Remove signature blocks
    - Collapse excessive blank lines
    """
    if not text:
        return ""

    lines = text.split('\n')
    cleaned = []
    in_quote = False
    quote_count = 0

    for line in lines:
        # Check for "On ... wrote:" header
        if strip_quotes and QUOTE_HEADER.match(line):
            in_quote = True
            quote_count += 1
            continue

        # Check for > quoted lines
        if strip_quotes and QUOTE_LINE.match(line):
            if not in_quote:
                in_quote = True
                quote_count += 1
            continue

        # Check for forwarded message separator
        if strip_quotes and FORWARD_HEADER.match(line):
            in_quote = True
            continue

        # Check for signature marker
        if strip_signatures and SIGNATURE_MARKERS.match(line):
            break  # Everything after is signature

        # Non-quoted line
        if in_quote and line.strip():
            in_quote = False

        if not in_quote:
            cleaned.append(line)

    result = '\n'.join(cleaned)

    # Collapse 3+ blank lines to 2
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Add note about removed quotes
    if quote_count > 0:
        result = result.rstrip() + f'\n\n[{quote_count} quoted section(s) removed]'

    return result.strip()
