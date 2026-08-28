# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The molejo spec: schema model and structural validation.

A molejo shape is a JSON document::

    {
      "molejo": 1,
      "profile": {"type": "circle", "radius": 2.0},
      "path": [{"type": "helix", "radius": 14.0, "turns": 6.5,
                "height": {"param": "height"}}],
      "loop": false,
      "tessellation": {"path": 240, "profile": 16}
    }

Every numeric slot -- anywhere, coordinates included -- is either a JSON
number or a parameter reference ``{"param": "<name>"}``. There is no
arithmetic in a spec and no default for a parameter: consumers evaluate
their expressions to numbers and bind them at evaluation.

Validation here is *structural* and needs no parameter values. It answers
one question -- is this a v1 molejo document -- and when the answer is no
it raises :class:`SpecError` naming the offending element by its position
in the document (``path[1].to[2]``, ``tessellation.profile``). Geometric
sense (a self-intersecting sweep, an over-compressed spring) is the
author's obligation, and a dangling parameter reference is an evaluation
error, not a structural one: :func:`parameter_names` reports what a
document references so a caller can bind it.

The JavaScript twin in ``js/src/spec.js`` implements the same rules and
emits the same messages, and the shared fixtures under ``fixtures/invalid/``
hold the two to it.
"""

import math

__all__ = [
    "PRIMITIVE_TYPES",
    "PROFILE_TYPES",
    "SPEC_VERSION",
    "TOOTH_FLANKS",
    "SpecError",
    "parameter_names",
    "validate",
]

#: The spec version this implementation reads and writes.
SPEC_VERSION = 1

#: The closed v1 profile vocabulary.
PROFILE_TYPES = ("circle", "polygon")

#: The closed v1 path-primitive vocabulary.
PRIMITIVE_TYPES = ("arc", "helix", "line", "spline", "wrap")

#: The closed v1 tooth-flank vocabulary (piecewise-linear keeps a toothed
#: belt analytic in B-rep; curved flanks wait for a project to demand them).
TOOTH_FLANKS = ("trapezoid",)

_SLOT_FORM = '{"param": "<name>"}'


class SpecError(ValueError):
    """A document is not a valid molejo spec.

    The message names the offending element by its position in the
    document, so an author can find it without reading the validator.
    """


# --- describing values in messages ----------------------------------------
#
# Messages must be byte-identical to the JavaScript validator's, so values
# are described by JSON kind rather than by any runtime's type names.


def _kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, (list, tuple)):
        return "an array"
    if isinstance(value, dict):
        return "an object"
    return "a value molejo does not understand"


def _render(value):
    """A value as it appears in an error message."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _kind(value)
    if isinstance(value, float) and value.is_integer() and math.isfinite(value):
        return str(int(value))
    return str(value)


def _quote(value):
    return f"'{value}'" if isinstance(value, str) else _kind(value)


def _is_integer(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value) and value.is_integer()


# --- structural checks -----------------------------------------------------


def _check_object(value, loc):
    if not isinstance(value, dict):
        raise SpecError(f"{loc}: must be an object, got {_kind(value)}")


def _check_fields(obj, loc, required, optional=()):
    for name in required:
        if name not in obj:
            raise SpecError(f"{loc}: missing required field '{name}'")
    allowed = set(required) | set(optional)
    for name in obj:
        if name not in allowed:
            raise SpecError(f"{loc}: unknown field '{name}'")


def _check_slot(value, loc):
    """A numeric slot: a finite number or a parameter reference."""
    if isinstance(value, bool):
        raise SpecError(
            f"{loc}: must be a number or a parameter reference {_SLOT_FORM}, "
            f"got {_kind(value)}"
        )
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise SpecError(f"{loc}: must be a finite number")
        return
    if isinstance(value, dict):
        if "param" not in value:
            raise SpecError(
                f"{loc}: must be a number or a parameter reference {_SLOT_FORM}, "
                f"got an object with no 'param' field"
            )
        for name in value:
            if name != "param":
                raise SpecError(f"{loc}: unknown field '{name}' in a parameter reference")
        name = value["param"]
        if not isinstance(name, str) or not name:
            raise SpecError(
                f"{loc}: a parameter reference needs a non-empty string name for "
                f"'param', got {_render(name)}"
            )
        return
    raise SpecError(
        f"{loc}: must be a number or a parameter reference {_SLOT_FORM}, got {_kind(value)}"
    )


def _check_vector(value, loc, dimension):
    if not isinstance(value, list) or len(value) != dimension:
        got = str(len(value)) if isinstance(value, list) else _kind(value)
        raise SpecError(
            f"{loc}: must be an array of {dimension} numbers or parameter "
            f"references, got {got}"
        )
    for index, item in enumerate(value):
        _check_slot(item, f"{loc}[{index}]")


def _check_points(value, loc, dimension, minimum, what):
    if not isinstance(value, list) or len(value) < minimum:
        got = str(len(value)) if isinstance(value, list) else _kind(value)
        raise SpecError(f"{loc}: {what} needs at least {minimum} points, got {got}")
    for index, point in enumerate(value):
        _check_vector(point, f"{loc}[{index}]", dimension)


def _check_count(value, loc, minimum=1):
    label = "a positive integer" if minimum >= 1 else "a non-negative integer"
    if not _is_integer(value) or value < minimum:
        raise SpecError(f"{loc}: must be {label}, got {_render(value)}")


# --- the document ----------------------------------------------------------


def validate(document):
    """Validate a molejo document, raising :class:`SpecError` on the first
    offending element. Returns ``None`` when the document is a valid spec."""
    _check_object(document, "spec")
    _check_fields(
        document,
        "spec",
        required=("molejo", "profile", "path", "tessellation"),
        optional=("loop",),
    )

    version = document["molejo"]
    if not _is_integer(version):
        raise SpecError(f"spec.molejo: must be the integer 1, got {_render(version)}")
    if int(version) != SPEC_VERSION:
        raise SpecError(
            f"spec.molejo: unsupported spec version {_render(version)}; this "
            f"implementation reads spec version {SPEC_VERSION}"
        )

    _check_profile(document["profile"], "profile")
    _check_path(document["path"], "path")

    if "loop" in document and not isinstance(document["loop"], bool):
        raise SpecError(f"loop: must be a boolean, got {_kind(document['loop'])}")

    # A wrap is a closed loop by construction, so a document carrying one
    # must say so: no document may misdescribe the topology it has.
    if document["path"][0]["type"] == "wrap" and not document.get("loop", False):
        raise SpecError(
            'loop: a wrap is a closed loop, so its document must declare '
            '"loop": true'
        )

    _check_tessellation(document["tessellation"], "tessellation")
    _check_profile_samples(document["profile"], document["tessellation"], "tessellation")
    return None


def _check_profile(profile, loc):
    _check_object(profile, loc)
    if "type" not in profile:
        raise SpecError(f"{loc}: missing required field 'type'")
    kind = profile["type"]
    if kind == "circle":
        _check_fields(profile, loc, ("type", "radius"))
        _check_slot(profile["radius"], f"{loc}.radius")
    elif kind == "polygon":
        _check_fields(profile, loc, ("type", "points"))
        _check_points(profile["points"], f"{loc}.points", 2, 3, "a polygon")
    else:
        raise SpecError(
            f"{loc}: unknown profile type {_quote(kind)}; expected one of "
            f"{', '.join(PROFILE_TYPES)}"
        )


def _check_path(path, loc):
    if not isinstance(path, list) or not path:
        got = "0" if isinstance(path, list) else _kind(path)
        raise SpecError(f"{loc}: must be an array of at least 1 primitive, got {got}")
    for index, primitive in enumerate(path):
        _check_primitive(primitive, f"{loc}[{index}]")
    # A wrap declares where it starts, in world coordinates; every other
    # primitive continues from where the previous one ended. A path that
    # mixed them would have two starts.
    if len(path) > 1:
        for index, primitive in enumerate(path):
            if primitive["type"] == "wrap":
                raise SpecError(
                    f"{loc}[{index}]: a wrap defines its own start, so it must be "
                    f"the only primitive in its path"
                )


def _check_primitive(primitive, loc):
    _check_object(primitive, loc)
    if "type" not in primitive:
        raise SpecError(f"{loc}: missing required field 'type'")
    kind = primitive["type"]

    if kind == "line":
        _check_fields(primitive, loc, ("type", "to"))
        _check_vector(primitive["to"], f"{loc}.to", 3)
    elif kind == "arc":
        _check_fields(primitive, loc, ("type", "center", "axis", "angle"))
        _check_vector(primitive["center"], f"{loc}.center", 3)
        _check_vector(primitive["axis"], f"{loc}.axis", 3)
        _check_slot(primitive["angle"], f"{loc}.angle")
    elif kind == "helix":
        _check_fields(primitive, loc, ("type", "radius", "turns", "height"))
        _check_slot(primitive["radius"], f"{loc}.radius")
        _check_slot(primitive["turns"], f"{loc}.turns")
        _check_slot(primitive["height"], f"{loc}.height")
    elif kind == "spline":
        _check_fields(primitive, loc, ("type", "points"))
        _check_points(primitive["points"], f"{loc}.points", 3, 2, "a spline")
    elif kind == "wrap":
        _check_fields(
            primitive, loc, ("type", "around"), optional=("teeth", "anchor", "phase")
        )
        _check_wrap_circles(primitive["around"], f"{loc}.around")
        if "teeth" in primitive:
            _check_teeth(primitive["teeth"], f"{loc}.teeth")
        if "anchor" in primitive:
            _check_anchor(primitive["anchor"], f"{loc}.anchor", len(primitive["around"]))
        if "phase" in primitive:
            _check_slot(primitive["phase"], f"{loc}.phase")
        # Both name the same thing -- where the tooth pattern's material
        # origin sits -- so a document carrying the two says it twice.
        if "anchor" in primitive and "phase" in primitive:
            raise SpecError(
                f"{loc}: a wrap takes an 'anchor' or a 'phase', not both; they "
                f"name the same tooth-pattern origin"
            )
    else:
        raise SpecError(
            f"{loc}: unknown path primitive {_quote(kind)}; expected one of "
            f"{', '.join(PRIMITIVE_TYPES)}"
        )


def _check_wrap_circles(around, loc):
    if not isinstance(around, list) or len(around) < 2:
        got = str(len(around)) if isinstance(around, list) else _kind(around)
        raise SpecError(f"{loc}: a wrap needs at least 2 circles, got {got}")
    for index, circle in enumerate(around):
        circle_loc = f"{loc}[{index}]"
        _check_object(circle, circle_loc)
        _check_fields(circle, circle_loc, ("center", "radius"))
        _check_vector(circle["center"], f"{circle_loc}.center", 2)
        _check_slot(circle["radius"], f"{circle_loc}.radius")


def _check_teeth(teeth, loc):
    _check_object(teeth, loc)
    _check_fields(teeth, loc, ("pitch", "height", "flank", "count"))
    _check_slot(teeth["pitch"], f"{loc}.pitch")
    _check_slot(teeth["height"], f"{loc}.height")
    flank = teeth["flank"]
    if flank not in TOOTH_FLANKS:
        raise SpecError(
            f"{loc}.flank: unknown tooth flank {_quote(flank)}; expected one of "
            f"{', '.join(TOOTH_FLANKS)}"
        )
    # The tooth count fixes topology, so it can never follow a parameter.
    _check_count(teeth["count"], f"{loc}.count")


def _check_anchor(anchor, loc, circles):
    _check_object(anchor, loc)
    _check_fields(anchor, loc, ("span", "at"))
    # The span index picks one of the wrap's tangent spans, and a wrap
    # around k circles has exactly k of them.
    _check_count(anchor["span"], f"{loc}.span", minimum=0)
    if anchor["span"] >= circles:
        raise SpecError(
            f"{loc}.span: a wrap around {circles} circles has {circles} spans, so "
            f"'span' must be less than {circles}, got {_render(anchor['span'])}"
        )
    _check_slot(anchor["at"], f"{loc}.at")


def _check_tessellation(tessellation, loc):
    _check_object(tessellation, loc)
    _check_fields(tessellation, loc, ("path", "profile"))
    # Declared and fixed: counts never follow geometry or a parameter, which
    # is what makes vertex correspondence across evaluations free.
    _check_count(tessellation["path"], f"{loc}.path")
    _check_count(tessellation["profile"], f"{loc}.profile")


def _check_profile_samples(profile, tessellation, loc):
    """A polygon is sampled at its own points, no more and no fewer.

    Its point count already fixes its vertex count, so any other reading
    would make the declared count a lie and ``V = R*M`` false.
    """
    if profile["type"] != "polygon":
        return
    points = len(profile["points"])
    if tessellation["profile"] != points:
        raise SpecError(
            f"{loc}.profile: a polygon profile is sampled at its own points, so "
            f"'profile' must be {points}, got {_render(tessellation['profile'])}"
        )


# --- parameters ------------------------------------------------------------


def parameter_names(document):
    """The set of parameter names a document references.

    The document is validated first, so every ``{"param": name}`` object
    encountered is a well-formed reference. Whether those names are bound
    is an evaluation-time question.
    """
    validate(document)
    names = set()
    _collect(document, names)
    return frozenset(names)


def _collect(value, names):
    if isinstance(value, dict):
        if "param" in value and isinstance(value["param"], str):
            names.add(value["param"])
            return
        for item in value.values():
            _collect(item, names)
    elif isinstance(value, list):
        for item in value:
            _collect(item, names)
