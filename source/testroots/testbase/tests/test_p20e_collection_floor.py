"""
    .. module:: test_p20e_collection_floor
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Floor on the number of tests the merge gate collects, so a
        discovery regression fails loudly instead of quietly running fewer tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

import os
import sys

from ccai import testbase

from ccai.testbase.testcollector import TestCollector


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
TEST_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))

# The merge gate's selection, verbatim from .github/workflows/merge_gate.yml:
#     testbase testing run --root ./source/testroots/testbase --includes=testbase.tests
GATE_INCLUDE = "testbase.tests"

# The count reached by the test-coverage roadmap (Phase 2c plus this floor).
# Raise it when tests are added; never lower it without a reason in the commit.
COLLECTED_FLOOR = 39


def test_gate_collects_at_least_the_roadmap_floor():
    """
        The gate must collect at least ``COLLECTED_FLOOR`` tests.

        Mechanism: the same ``TestCollector`` the ``testbase testing run`` entry
        point drives is pointed at this test root with the gate's include
        expression.  It walks the ``tests`` package under ``--root`` (the include
        is rooted at the parent of ``--root``, so ``testbase.tests``), imports
        every module found and collects the module-level ``test_*`` functions,
        exactly as the gate does.  A wrong ``--includes`` prefix, a test module
        that fails to import, or a module dropped from the package lowers the
        count and fails this test; an import error is reported explicitly.
    """
    root_parent = os.path.dirname(TEST_ROOT)
    if root_parent not in sys.path:
        sys.path.insert(0, root_parent)

    collector = TestCollector(root=TEST_ROOT, excludes=[], metafilters=[])
    collector.collect_references(GATE_INCLUDE)

    import_errors = [ifile for ifile in collector.import_errors]
    testbase.assert_equal(import_errors, [])

    collected = len(collector.references)
    testbase.assert_true(
        collected >= COLLECTED_FLOOR,
        api=f"gate collected {collected} tests, floor is {COLLECTED_FLOOR}",
    )
    return
