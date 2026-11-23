"""Restricted RFC 8785 canonical JSON for portable EvalRank identities.

EvalRank hash material deliberately excludes floating-point numbers. Decimal
measurements travel as canonical decimal strings, while counts and monetary
units use JavaScript-safe integers. This keeps Python and browser SDKs byte
identical without silently rounding evidence.

One documented exception: a decision receipt carries caller-facing unit
fractions (the query's ``max_refusal_score``, each selection's
``refusal_score``, and an abstain's ``relaxation.max_refusal_score``). ``allow_floats=True`` admits finite floats and writes them
exactly as RFC 8785 does (ECMAScript ``Number.prototype.toString``), which is
what ``JSON.stringify`` emits, so the bytes stay identical across SDKs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


MAX_SAFE_INTEGER = (1 << 53) - 1


def canonical_json(value: Any, *, allow_floats: bool = False) -> str:
    """Return restricted-JCS text, rejecting values that cannot hash portably."""

    canonical = _canonicalize(value, path="$", in_object_key=False, allow_floats=allow_floats)
    if allow_floats:
        return _dump(canonical)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def restricted_jcs(value: Any, *, allow_floats: bool = False) -> bytes:
    """Return the exact UTF-8 bytes used by EvalRank content identities."""

    return canonical_json(value, allow_floats=allow_floats).encode("utf-8")


def sha256_hex(value: Any, *, allow_floats: bool = False) -> str:
    """Hash restricted-JCS bytes as lowercase SHA-256 hexadecimal text."""

    return hashlib.sha256(restricted_jcs(value, allow_floats=allow_floats)).hexdigest()


def es_number(value: float) -> str:
    """RFC 8785 number text: ECMAScript ``Number.prototype.toString`` of a finite float."""

    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("JSON numbers must be finite")
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    mantissa, _, exponent = repr(abs(value)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    raw = whole + fraction
    digits = raw.lstrip("0")
    # value = 0.<digits> * 10**point, with repr's shortest round-trip digits.
    point = len(whole) + int(exponent or 0) - (len(raw) - len(digits))
    digits = digits.rstrip("0")
    size = len(digits)
    if size <= point <= 21:
        text = digits + "0" * (point - size)
    elif 0 < point <= 21:
        text = f"{digits[:point]}.{digits[point:]}"
    elif -6 < point <= 0:
        text = f"0.{'0' * -point}{digits}"
    else:
        power = point - 1
        head = digits if size == 1 else f"{digits[0]}.{digits[1:]}"
        text = f"{head}e{'+' if power >= 0 else '-'}{abs(power)}"
    return sign + text


def _dump(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return es_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_dump(item) for item in value) + "]"
    return "{" + ",".join(f"{json.dumps(key, ensure_ascii=False)}:{_dump(item)}" for key, item in value.items()) + "}"


def _canonicalize(value: Any, *, path: str, in_object_key: bool, allow_floats: bool = False) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError(f"{path} must be a safe integer")
        return value
    if isinstance(value, float):
        if allow_floats:
            es_number(value)
            return value
        raise TypeError(f"{path} must not be a float in restricted JCS")
    if isinstance(value, str):
        _require_valid_unicode(value, path=path)
        return value
    if isinstance(value, list):
        return [
            _canonicalize(item, path=f"{path}[{index}]", in_object_key=False, allow_floats=allow_floats)
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"{path} object keys must be strings")
            _canonicalize(key, path=f"{path} key", in_object_key=True)
        return {
            key: _canonicalize(value[key], path=f"{path}.{key}", in_object_key=False, allow_floats=allow_floats)
            for key in sorted(value, key=_utf16_sort_key)
        }
    kind = "object key" if in_object_key else "value"
    raise TypeError(f"{path} {kind} has unsupported JSON type {type(value).__name__}")


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def _require_valid_unicode(value: str, *, path: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{path} contains a lone surrogate")
