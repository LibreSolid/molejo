# Installation

molejo is one spec with two implementations, released together under one
version. Install the side (or sides) your project consumes.

## Python

```console
$ pip install molejo
```

Requires Python 3.10 or later. The only dependency is numpy: authoring,
validation, mesh evaluation and STL export all run on it alone.

### The `brep` extra

The optional B-rep evaluator needs the OCCT kernel, which is a heavy
install that mesh consumers should not pay for. It lives behind an
extra:

```console
$ pip install "molejo[brep]"
```

An install without the extra is not broken — it authors, validates,
meshes and exports STL exactly as before. Asking it for an exact solid
raises {class}`molejo.brep.BrepUnavailable`, naming the extra to
install. See {doc}`brep`.

## JavaScript

```console
$ npm install molejo
```

The npm package is plain ES modules with **no dependencies and no build
step**. It is evaluation-only: it parses, validates and evaluates specs
authored elsewhere (in Python, or by hand — a hand-written spec is
exactly as good an input as an authored one).

three.js is not a dependency either: the evaluator fills plain
`Float32Array`/`Uint32Array` buffers shaped for a three.js
`BufferGeometry`, but nothing imports three.js. See {doc}`javascript`.

## Versioning

A package version carries the spec version it implements. Both packages
carry spec v1 at 0.1.0 and release together for a given spec version:
neither runtime is ever published against a spec version the other has
not caught up to.
