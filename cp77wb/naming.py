from __future__ import annotations

WB_FILENAME_REPLACEMENTS = '<>:"/\\|?*\' '


def sanitize_filename(name: str) -> str:
    """Match World Builder's utils.createFileName() exactly.

    WB replaces Windows-invalid filename characters, apostrophes, and spaces
    with underscores. It does not trim or collapse repeated underscores.
    """
    out = str(name)
    for ch in ('<', '>', ':', '"', '/', '\\', '|', '?', '*', "'", ' '):
        out = out.replace(ch, '_')
    return out


def generate_copy_name(name: str) -> str:
    """Match World Builder's utils.generateCopyName()."""
    i = len(name)
    while i > 0 and name[i - 1].isdigit():
        i -= 1
    if i < len(name):
        return name[:i] + str(int(name[i:]) + 1)
    return name + '_1'


def unique_name(name: str, existing: set[str]) -> str:
    candidate = name
    while candidate in existing:
        candidate = generate_copy_name(candidate)
    return candidate
