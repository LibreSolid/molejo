API reference
=============

The Python package's public API, from its docstrings. The JavaScript
package's API is documented in :doc:`javascript`; it deliberately has
no reference of its own beyond that page, being the evaluation-only
twin of what follows.

``molejo``
----------

.. automodule:: molejo
   :no-members:

Authoring
---------

.. autoclass:: molejo.Shape
   :members:

.. autoclass:: molejo.Circle
.. autoclass:: molejo.Polygon
.. autoclass:: molejo.Line
.. autoclass:: molejo.Arc
.. autoclass:: molejo.Helix
.. autoclass:: molejo.Spline
.. autoclass:: molejo.Wrap
.. autoclass:: molejo.Teeth
.. autoclass:: molejo.ParamRef

.. py:data:: molejo.P

   The parameter accessor: ``P.lift`` (or ``P["lift"]``) is a
   :class:`~molejo.ParamRef` to the parameter ``lift``. References
   refuse every arithmetic and comparison operator; compute derived
   values in ordinary Python and bind them at evaluation.

The spec
--------

.. automodule:: molejo.spec
   :no-members:

.. autodata:: molejo.spec.SPEC_VERSION
.. autodata:: molejo.spec.PROFILE_TYPES
.. autodata:: molejo.spec.PRIMITIVE_TYPES
.. autodata:: molejo.spec.TOOTH_FLANKS

.. autofunction:: molejo.validate
.. autofunction:: molejo.parameter_names
.. autoexception:: molejo.SpecError

Mesh evaluation
---------------

.. autofunction:: molejo.evaluate

.. autoclass:: molejo.Mesh
   :members:

.. autoexception:: molejo.EvaluationError

B-rep evaluation
----------------

.. automodule:: molejo.brep
   :no-members:

.. autofunction:: molejo.brep.evaluate

.. autoclass:: molejo.brep.BrepResult
   :members:

.. autodata:: molejo.brep.APPROXIMATION
.. autoexception:: molejo.brep.BrepUnavailable
.. autoexception:: molejo.brep.BrepError
