import re


def chunks(text, delimiter=';'):
    result, start, depth, quote, i = [], 0, 0, False, 0
    while i < len(text):
        c = text[i]
        if c == "'":
            if quote and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            quote = not quote
        if not quote:
            depth += (c == '(') - (c == ')')
            if c == delimiter and depth == 0:
                result.append(text[start:i].strip())
                start = i + 1
        i += 1
    return result, text[start:].strip()


def split(text, delimiter=';'):
    result, tail = chunks(text, delimiter)
    return result + ([tail] if tail else [])


def commands(text):
    text = re.sub(r"('(?:''|[^'])*')|/\*.*?\*/|--[^\n]*", lambda m: m[1] or '', text, flags=re.S)
    pending = ''
    for line in text.splitlines():
        if line.lstrip().startswith('.') and not pending.strip():
            yield line.strip().rstrip(';')
            continue
        pending += line + '\n'
        if re.match(r'\s*(CREATE|REPLACE)\s+PROCEDURE', pending, re.I):
            if not re.search(r'END\s*;\s*$', pending, re.I):
                continue
            yield pending.strip().rstrip(';')
            pending = ''
            continue
        pieces, pending = chunks(pending)
        yield from pieces
        if pending:
            pending += '\n'
    if pending.strip():
        yield pending.strip()
