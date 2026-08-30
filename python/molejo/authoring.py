# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""Python-first authoring over the spec schema.

Authors write shapes in Python::

    from molejo import Shape, Circle, Helix, P

    spring = Shape(
        profile=Circle(radius=2.0),
        path=[Helix(radius=14.0, turns=6.5, height=P.height)],
        path_samples=240, profile_samples=16,
    )

and ``to_json()`` emits the canonical document. The constructors mirror
the JSON one-to-one -- there is no sugar that the document cannot express
and nothing the document expresses that the constructors cannot -- so a
hand-written spec is exactly as good an input as an authored one, which
is what lets the JavaScript side stay evaluation-only.

``P.height`` is a plain reference, not an expression: it refuses every
arithmetic and comparison operator so the authoring layer cannot grow an
expression language behind the spec's back. Derived values are computed
in ordinary Python and bound at evaluation.
"""

import json

from .spec import (
    SPEC_VERSION,
    SpecError,
    parameter_names,
    required_version,
    validate,
)

__all__ = [
    "Arc",
    "Circle",
    "Helix",
    "Line",
    "P",
    "ParamRef",
    "Polygon",
    "Shape",
    "Spline",
    "Teeth",
    "Wrap",
]


# --- parameter references --------------------------------------------------

_REFUSAL = (
    "molejo parameters are plain references, not expressions: {name!r} cannot "
    "take part in arithmetic or comparison. Compute the derived value in "
    "ordinary Python, outside the spec, and bind it at evaluation "
    "(shape.evaluate({name}=...))."
)

#: Every operator a parameter reference refuses, so that an author who
#: writes `P.free_length - P.lift` is told what to do instead rather than
#: silently getting something that is not a spec slot.
_REFUSED_OPERATORS = (
    "add", "radd", "sub", "rsub", "mul", "rmul", "matmul", "rmatmul",
    "truediv", "rtruediv", "floordiv", "rfloordiv", "mod", "rmod",
    "divmod", "rdivmod", "pow", "rpow", "lshift", "rlshift", "rshift",
    "rrshift", "and", "rand", "or", "ror", "xor", "rxor",
    "lt", "le", "gt", "ge",
    "neg", "pos", "abs", "invert", "round", "trunc", "floor", "ceil",
    "int", "float", "complex", "index",
)


class ParamRef:
    """A reference to a named scalar parameter, bound at evaluation."""

    __slots__ = ("name",)

    def __init__(self, name):
        if not isinstance(name, str) or not name:
            raise SpecError("a parameter reference needs a non-empty string name")
        self.name = name

    def to_dict(self):
        return {"param": self.name}

    def __repr__(self):
        return f"P.{self.name}"

    def __eq__(self, other):
        return isinstance(other, ParamRef) and other.name == self.name

    def __hash__(self):
        return hash(("molejo.ParamRef", self.name))


def _refuse(operator):
    def refusal(self, *_args, **_kwargs):
        raise TypeError(_REFUSAL.format(name=self.name))

    refusal.__name__ = f"__{operator}__"
    refusal.__qualname__ = f"ParamRef.__{operator}__"
    return refusal


for _operator in _REFUSED_OPERATORS:
    setattr(ParamRef, f"__{_operator}__", _refuse(_operator))
del _operator


class _ParamFactory:
    """``P.height`` -- the accessor that makes a parameter reference."""

    __slots__ = ()

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return ParamRef(name)

    def __getitem__(self, name):
        return ParamRef(name)

    def __repr__(self):
        return "P"


#: The parameter accessor: ``P.lift`` is a reference to the parameter ``lift``.
P = _ParamFactory()


# --- emitting and loading --------------------------------------------------


def _emit(value):
    """A constructor argument as its canonical JSON form."""
    if isinstance(value, ParamRef):
        return value.to_dict()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {key: _emit(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_emit(item) for item in value]
    return value


def _load(value):
    """A validated JSON fragment as authoring-layer values."""
    if isinstance(value, dict):
        if "param" in value:
            return ParamRef(value["param"])
        return {key: _load(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_load(item) for item in value]
    return value


class _Element:
    """Shared behaviour of the vocabulary constructors."""

    __slots__ = ()

    def __eq__(self, other):
        return type(other) is type(self) and other.to_dict() == self.to_dict()

    def __hash__(self):
        return hash((type(self).__name__, json.dumps(self.to_dict(), sort_keys=True)))

    def __repr__(self):
        fields = ", ".join(
            f"{key}={value!r}" for key, value in self.to_dict().items() if key != "type"
        )
        return f"{type(self).__name__}({fields})"


# --- profiles --------------------------------------------------------------


class Circle(_Element):
    """A circular profile of the given radius."""

    __slots__ = ("radius",)

    def __init__(self, radius):
        self.radius = radius

    def to_dict(self):
        return {"type": "circle", "radius": _emit(self.radius)}


class Polygon(_Element):
    """A closed polygonal profile through at least three (x, y) points."""

    __slots__ = ("points",)

    def __init__(self, points):
        self.points = list(points)

    def to_dict(self):
        return {"type": "polygon", "points": [_emit(point) for point in self.points]}


# --- path primitives -------------------------------------------------------


class Line(_Element):
    """A straight segment to an (x, y, z) point."""

    __slots__ = ("to",)

    def __init__(self, to):
        self.to = to

    def to_dict(self):
        return {"type": "line", "to": _emit(self.to)}


class Arc(_Element):
    """A circular arc about ``center`` and ``axis``, sweeping ``angle``."""

    __slots__ = ("center", "axis", "angle")

    def __init__(self, center, axis, angle):
        self.center = center
        self.axis = axis
        self.angle = angle

    def to_dict(self):
        return {
            "type": "arc",
            "center": _emit(self.center),
            "axis": _emit(self.axis),
            "angle": _emit(self.angle),
        }


class Helix(_Element):
    """A helix of ``turns`` turns at ``radius``, rising by ``height``."""

    __slots__ = ("radius", "turns", "height")

    def __init__(self, radius, turns, height):
        self.radius = radius
        self.turns = turns
        self.height = height

    def to_dict(self):
        return {
            "type": "helix",
            "radius": _emit(self.radius),
            "turns": _emit(self.turns),
            "height": _emit(self.height),
        }


class Spline(_Element):
    """A spline through the (x, y, z) points it runs toward.

    Like every primitive but a wrap it does not declare where it starts:
    it begins at the point the path has reached, and ``points`` are what
    it runs through and toward. ``start_tangent`` and ``end_tangent`` are
    *directions* -- their length is ignored -- and leaving one out means
    the thing no literal could state: leave the way you came, arrive
    along the final chord.
    """

    __slots__ = ("points", "start_tangent", "end_tangent")

    def __init__(self, points, start_tangent=None, end_tangent=None):
        self.points = list(points)
        self.start_tangent = start_tangent
        self.end_tangent = end_tangent

    def to_dict(self):
        document = {"type": "spline", "points": [_emit(point) for point in self.points]}
        if self.start_tangent is not None:
            document["start_tangent"] = _emit(self.start_tangent)
        if self.end_tangent is not None:
            document["end_tangent"] = _emit(self.end_tangent)
        return document


class Teeth(_Element):
    """A tooth pattern along a wrap.

    The count is declared, not derived, so tooth count -- and with it
    vertex count and ordering -- never varies with a parameter.

    ``face`` says which side of the section the teeth stand on: ``inner``
    for a belt driven from inside its own circuit, ``outer`` for one
    driven from outside it. It is emitted only when it is not the
    default, so a belt that never asked the question authors the document
    it always did.
    """

    __slots__ = ("pitch", "height", "flank", "count", "face")

    def __init__(self, pitch, height, count, flank="trapezoid", face="inner"):
        self.pitch = pitch
        self.height = height
        self.flank = flank
        self.count = count
        self.face = face

    def to_dict(self):
        document = {
            "pitch": _emit(self.pitch),
            "height": _emit(self.height),
            "flank": self.flank,
            "count": self.count,
        }
        if self.face != "inner":
            document["face"] = self.face
        return document


class Wrap(_Element):
    """A path wrapping a series of circles, optionally toothed.

    ``anchor`` pins an open belt's arc-length origin to a span (a carriage
    clamp); ``phase`` circulates the pattern of a closed loop.
    """

    __slots__ = ("around", "teeth", "anchor", "phase")

    def __init__(self, around, teeth=None, anchor=None, phase=None):
        self.around = list(around)
        self.teeth = teeth
        self.anchor = anchor
        self.phase = phase

    def to_dict(self):
        document = {"type": "wrap", "around": [_emit(circle) for circle in self.around]}
        if self.teeth is not None:
            document["teeth"] = _emit(self.teeth)
        if self.anchor is not None:
            document["anchor"] = _emit(self.anchor)
        if self.phase is not None:
            document["phase"] = _emit(self.phase)
        return document


# --- the shape -------------------------------------------------------------

_PROFILES = {
    "circle": lambda fields: Circle(radius=fields["radius"]),
    "polygon": lambda fields: Polygon(points=[tuple(point) for point in fields["points"]]),
}

_PRIMITIVES = {
    "line": lambda fields: Line(to=tuple(fields["to"])),
    "arc": lambda fields: Arc(
        center=tuple(fields["center"]),
        axis=tuple(fields["axis"]),
        angle=fields["angle"],
    ),
    "helix": lambda fields: Helix(
        radius=fields["radius"], turns=fields["turns"], height=fields["height"]
    ),
    "spline": lambda fields: Spline(
        points=[tuple(point) for point in fields["points"]],
        start_tangent=(
            tuple(fields["start_tangent"]) if "start_tangent" in fields else None
        ),
        end_tangent=tuple(fields["end_tangent"]) if "end_tangent" in fields else None,
    ),
    "wrap": lambda fields: Wrap(
        around=[
            {"center": tuple(circle["center"]), "radius": circle["radius"]}
            for circle in fields["around"]
        ],
        teeth=(
            Teeth(
                pitch=fields["teeth"]["pitch"],
                height=fields["teeth"]["height"],
                flank=fields["teeth"]["flank"],
                count=fields["teeth"]["count"],
            )
            if "teeth" in fields
            else None
        ),
        anchor=(
            {"span": fields["anchor"]["span"], "at": fields["anchor"]["at"]}
            if "anchor" in fields
            else None
        ),
        phase=fields.get("phase"),
    ),
}


class Shape(_Element):
    """A closed profile swept along a path, at a declared tessellation.

    ``path_samples`` is the number of samples along the path and
    ``profile_samples`` the number around the profile. Both are declared,
    never adaptive: that is what makes two evaluations of one shape
    correspond vertex for vertex.
    """

    __slots__ = ("profile", "path", "path_samples", "profile_samples", "loop")

    def __init__(self, profile, path, path_samples, profile_samples, loop=False):
        self.profile = profile
        self.path = list(path)
        self.path_samples = path_samples
        self.profile_samples = profile_samples
        self.loop = loop

    # -- serialization ------------------------------------------------------

    def to_dict(self):
        """The canonical document. Always a valid spec: it is validated here.

        The version written is the *lowest* the document needs, not the
        newest this implementation reads. A shape that asks nothing of a
        later vocabulary authors the document it always did, byte for
        byte, so a consumer pinned to an older molejo keeps reading
        everything it could read before and refuses only what it really
        cannot evaluate.
        """
        document = {
            "molejo": SPEC_VERSION,
            "profile": _emit(self.profile),
            "path": [_emit(primitive) for primitive in self.path],
            "loop": bool(self.loop),
            "tessellation": {
                "path": self.path_samples,
                "profile": self.profile_samples,
            },
        }
        document["molejo"] = required_version(document)
        validate(document)
        return document

    def to_json(self, **kwargs):
        """The canonical document as JSON text."""
        kwargs.setdefault("indent", 2)
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, document):
        """Parse and validate a canonical document into a shape."""
        validate(document)
        fields = _load(document)
        profile = fields["profile"]
        path = fields["path"]
        return cls(
            profile=_PROFILES[profile["type"]](profile),
            path=[_PRIMITIVES[primitive["type"]](primitive) for primitive in path],
            path_samples=fields["tessellation"]["path"],
            profile_samples=fields["tessellation"]["profile"],
            loop=fields.get("loop", False),
        )

    @classmethod
    def from_json(cls, text):
        """Parse and validate canonical JSON text into a shape."""
        try:
            document = json.loads(text)
        except ValueError as error:
            raise SpecError(f"spec: not valid JSON ({error})") from error
        return cls.from_dict(document)

    # -- parameters ---------------------------------------------------------

    @property
    def params(self):
        """The set of parameter names this shape references."""
        return parameter_names(self.to_dict())

    # -- evaluation ---------------------------------------------------------

    def evaluate(self, **values):
        """Evaluate the shape at the given parameter values.

        Exactly the evaluation of the canonical document this shape
        serializes to: authoring is sugar over the representation, never a
        second path into the geometry.
        """
        from .evaluator import evaluate

        return evaluate(self.to_dict(), values)

    def brep(self, **values):
        """Evaluate the shape to an exact B-rep solid at the given values.

        The same sugar over the same document, into the other evaluator:
        :func:`molejo.brep.evaluate` of what :meth:`to_dict` serializes.
        Needs the ``brep`` extra, and says so by name when it is missing.
        """
        from .brep import evaluate

        return evaluate(self.to_dict(), values)
