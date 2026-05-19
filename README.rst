==================================================
Automation Mojo RestClient Pychestrate
==================================================

The ``automojo-restclient-pychestrate`` package is the typed Python REST
client for the Pychestrate continuous integration and orchestration
service. It is auto-generated from the OpenAPI 3.1 contract published
by ``pychestrate-service`` at
``specs/openapi/pychestrate.yaml`` and is built on top of
``automojo-restclient-base``.

Highlights
==========

- ``PychestrateRestClient`` as the top-level client for the Pychestrate REST API.
- Generated schema catalogue under ``pychestrate/models/`` modelling each
  Pychestrate resource type with ``SchemaObject`` / ``SchemaField`` bindings.
- Endpoint groupings under ``pychestrate/groups/`` covering runs, dispatch,
  progress, results, agents, pods, projects, and the rest of the Pychestrate
  REST surface.
- ``PychestrateRestClientGenerator`` under ``pychestrate/generation/`` to
  regenerate schema and group modules from the OpenAPI specification.
- Authentication via cookie session, API key header, and mTLS material — wired
  through ``automojo-credentials``.

Source of Truth
===============

The OpenAPI specification at
``pychestrate-service/specs/openapi/pychestrate.yaml`` is the single source
of truth for this client. To regenerate the client after a spec change:

.. code-block:: bash

   make generate

Repository Structure
====================

- ``development/`` - Runtime environment scripts.
- ``repository-setup/`` - Repository homing and setup scripts.
- ``source/packages/`` - Package source code.
- ``source/testroots/testbase/`` - TestBase test roots.

Environment Setup
=================

When working in a Codex container:

.. code-block:: bash

   ./development/setup-agent-container

For local development:

.. code-block:: bash

   ./repository-setup/rehome-repository
   ./development/setup-environment

Running Tests
=============

Activate the virtual environment:

.. code-block:: bash

   source .venv/bin/activate

Run the smoke tests:

.. code-block:: bash

   python -m unittest discover -s source/testroots/testbase/tests -v
