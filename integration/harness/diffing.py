from __future__ import annotations

from fnmatch import fnmatchcase


def differences(expected, actual, ignore=(), path="") -> list[dict]:
    """Compare ordered arrays and typed fields; ignore patterns use slash paths."""
    if any(fnmatchcase(path, pattern) for pattern in ignore):
        return []
    if type(expected) is not type(actual):
        return [{"path": path, "reason": "type", "expected": expected, "actual": actual}]
    if isinstance(expected, dict):
        result = []
        for key in sorted(expected.keys() | actual.keys()):
            child = f"{path}/{key}"
            if any(fnmatchcase(child, pattern) for pattern in ignore):
                continue
            if key not in expected or key not in actual:
                result.append({"path": child, "reason": "unexpected" if key in actual else "missing",
                               "expected": expected.get(key), "actual": actual.get(key)})
            else:
                result.extend(differences(expected[key], actual[key], ignore, child))
        return result
    if isinstance(expected, list):
        result = []
        for index in range(max(len(expected), len(actual))):
            child = f"{path}/{index}"
            if index >= len(expected) or index >= len(actual):
                result.append({"path": child, "reason": "unexpected" if index < len(actual) else "missing",
                               "expected": expected[index] if index < len(expected) else None,
                               "actual": actual[index] if index < len(actual) else None})
            else:
                result.extend(differences(expected[index], actual[index], ignore, child))
        return result
    if expected != actual:
        return [{"path": path, "reason": "value", "expected": expected, "actual": actual}]
    return []
