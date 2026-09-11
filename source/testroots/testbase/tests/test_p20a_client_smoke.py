"""
    .. module:: test_p20a_client_smoke
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Structure-level smoke tests for the generated Pychestrate REST client.

    These tests perform NO HTTP calls. They verify that the generator produced
    a client object whose shape matches the OpenAPI specification.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from ccai import testbase

import os

import yaml

from ccai.pychestrate.rest.client.pychestraterestclient import PychestrateRestClient  # noqa: F401  (import smoke)

from ccai.pychestrate.rest.client.models.runs import Run


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "..", ".."))
EMBEDDED_SPEC = os.path.join(
    REPO_ROOT,
    "source", "packages", "ccai", "pychestrate", "rest", "client",
    "generation", "specs", "pychestrate.yaml",
)


# ----------------------------------------------------------------------
# PychestrateRestClientSmokeTests
# ----------------------------------------------------------------------

"""
    Verify the generated schemas reflect the OpenAPI specification.  Group
    exposure is checked for every spec tag in test_p20b_spec_conformance.
"""

def test_run_schema_required_fields_match_spec():
    """
        The generated `Run` model should declare the required fields
        advertised by the OpenAPI spec.
    """
    with open(EMBEDDED_SPEC, "r", encoding="utf-8") as sf:
        spec = yaml.safe_load(sf)

    run_schema = spec["components"]["schemas"]["Run"]
    expected_required = set(run_schema.get("required", []))

    actual_required = set()
    for field_name, field_descriptor in Run._fields.items():
        if field_descriptor.required:
            actual_required.add(field_name)

    testbase.assert_equal(actual_required, expected_required)
    return

def test_runstate_enum_values_present_in_spec():
    """
        `RunState` is declared as a string enum in the OpenAPI spec.
        The generator emits it as a plain `str` Field (no enum class is
        currently produced), so we verify the spec-level enum list is
        intact and the `Run.state` field exists.
    """
    with open(EMBEDDED_SPEC, "r", encoding="utf-8") as sf:
        spec = yaml.safe_load(sf)

    runstate = spec["components"]["schemas"]["RunState"]
    enum_values = runstate.get("enum", [])

    expected_subset = {
        "pending", "dispatching", "running", "completed",
        "failed", "cancelled",
    }
    testbase.assert_true(expected_subset.issubset(set(enum_values)))

    testbase.assert_true("state" in Run._fields)
    return
