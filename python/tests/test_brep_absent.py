# molejo - analytic flexible parts for mechanical CAD
# Copyright (C) 2026 Luis Henrique Cassis Fagundes
# SPDX-License-Identifier: Apache-2.0

"""The `brep` extra's boundary, proved in an environment that has it.

The B-rep evaluator is an optional extra because the browser never needs
OCCT and a maker who only wants meshes should not install a CAD kernel to
get them. That promise has two halves and both are asserted here: asking
for a B-rep without the extra raises an error that names the extra, and
mesh evaluation in the same environment carries on untouched.

A development checkout has the extra installed, so the absence is
simulated rather than waited for: an import hook makes ``import OCP``
fail, the kernel module and its cached handle are dropped, and the
evaluator is invoked through exactly the code path a machine without the
extra would take. Testing this only on a machine that happens to lack
OCCT would mean never testing it at all.
"""

import contextlib
import sys

import pytest

import molejo
import molejo.brep

from test_evaluation import cylinder


class _NoOCP:
    """A meta-path finder that refuses ``OCP``, and nothing else."""

    def find_spec(self, name, path=None, target=None):
        if name == "OCP" or name.startswith("OCP."):
            raise ImportError("No module named 'OCP'")
        return None


@contextlib.contextmanager
def without_the_extra():
    """Run the block as if `cadquery-ocp` had never been installed."""
    hidden = {
        name: module
        for name, module in sys.modules.items()
        if name == "OCP" or name.startswith("OCP.") or name == "molejo._occt"
    }
    for name in hidden:
        del sys.modules[name]
    # The package keeps an attribute of its own for an imported submodule,
    # and `from . import _occt` would hand that back without asking the
    # import system anything at all.
    attribute = getattr(molejo, "_occt", None)
    if attribute is not None:
        delattr(molejo, "_occt")
    cached = molejo.brep._KERNEL
    molejo.brep._KERNEL = None
    finder = _NoOCP()
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
        sys.modules.update(hidden)
        if attribute is not None:
            setattr(molejo, "_occt", attribute)
        molejo.brep._KERNEL = cached


def test_the_simulation_really_hides_the_binding():
    # The other tests are worth nothing if the hook does not bite.
    with without_the_extra():
        with pytest.raises(ImportError):
            __import__("OCP")


def test_without_the_extra_the_evaluator_names_it():
    with without_the_extra():
        with pytest.raises(molejo.brep.BrepUnavailable) as caught:
            molejo.brep.evaluate(cylinder(), {})
    message = str(caught.value)
    assert "brep" in message
    assert "molejo[brep]" in message


def test_the_refusal_is_an_import_error():
    # A caller that wants to offer the mesh instead should be able to catch
    # this as the ordinary missing-dependency failure it is.
    with without_the_extra():
        with pytest.raises(ImportError):
            molejo.brep.evaluate(cylinder(), {})


def test_an_authored_shape_names_the_extra_too():
    from molejo import Circle, Line, P, Shape

    shape = Shape(
        profile=Circle(radius=5.0),
        path=[Line(to=(0.0, 0.0, P.length))],
        path_samples=4,
        profile_samples=12,
    )
    with without_the_extra():
        with pytest.raises(molejo.brep.BrepUnavailable, match="brep"):
            shape.brep(length=12.0)


def test_mesh_evaluation_is_unaffected_by_the_missing_extra():
    document = cylinder()
    expected = molejo.evaluate(document)
    with without_the_extra():
        mesh = molejo.evaluate(document)
        stl = mesh.to_stl()
    assert (mesh.vertices == expected.vertices).all()
    assert (mesh.faces == expected.faces).all()
    assert stl == expected.to_stl()


def test_the_kernel_comes_back_once_the_extra_is_there_again():
    # The cached handle must not remember the failure, or one absent
    # import would poison the evaluator for the rest of the process.
    with without_the_extra():
        with pytest.raises(molejo.brep.BrepUnavailable):
            molejo.brep.evaluate(cylinder(), {})
    pytest.importorskip("OCP", reason="the brep extra is not installed")
    assert molejo.brep.evaluate(cylinder(), {}).volume() > 0.0
