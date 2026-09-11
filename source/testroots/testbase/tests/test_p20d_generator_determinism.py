"""
    .. module:: test_p20d_generator_determinism
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Generator drift check: regenerating the client from the embedded
        OpenAPI spec must reproduce the checked-in generated modules exactly.

    The generator runs offline from the spec snapshot committed under
    ``generation/specs``; nothing is fetched.  The regenerated tree is written
    under the repository's ``.output`` directory and removed afterwards.  A
    failure means either a generated file was edited by hand or the generator
    (restclient-base) changed its output and the tree was not regenerated.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from typing import Dict, List

import os
import shutil
import tempfile

from ccai import testbase

from ccai.errors.exceptions import SkipError

from ccai.pychestrate.rest.client.generation.pychestraterestclientgenerator import PychestrateRestClientGenerator


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "..", ".."))
CLIENT_ROOT = os.path.join(REPO_ROOT, "source", "packages", "ccai", "pychestrate", "rest", "client")
EMBEDDED_SPEC = os.path.join(CLIENT_ROOT, "generation", "specs", "pychestrate.yaml")
OUTPUT_ROOT = os.path.join(REPO_ROOT, ".output", "generator-determinism")

# Hand-written parts of the client package that the generator does not produce.
NOT_GENERATED = ("generation", "pychestraterestclientbase.py")


def _generated_files(root: str) -> Dict[str, str]:
    """
        Maps the relative path of every generated python file under ``root`` to
        its absolute path, skipping caches and the hand-written modules.
    """
    files: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__" and d not in NOT_GENERATED]
        for filename in filenames:
            if not filename.endswith(".py") or filename in NOT_GENERATED:
                continue
            full = os.path.join(dirpath, filename)
            files[os.path.relpath(full, root)] = full
    return files


def _regenerate() -> str:
    """
        Runs the package's generator against the embedded spec into a fresh
        directory under ``.output`` and returns that directory.
    """
    if not os.path.exists(EMBEDDED_SPEC):
        raise SkipError(f"Embedded OpenAPI spec not present: {EMBEDDED_SPEC}")

    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    target = tempfile.mkdtemp(prefix="regen-", dir=OUTPUT_ROOT)

    generator = PychestrateRestClientGenerator(
        openapi_spec_file=EMBEDDED_SPEC,
        clients_root=target,
        client_class_name="PychestrateRestClient",
    )
    generator.generate()
    return target


def test_regeneration_produces_the_checked_in_file_set():
    """
        The generator emits exactly the set of group, model and client modules
        that are checked in: no file missing, none extra.
    """
    target = _regenerate()
    try:
        regenerated = sorted(_generated_files(target).keys())
        checked_in = sorted(_generated_files(CLIENT_ROOT).keys())
    finally:
        shutil.rmtree(target, ignore_errors=True)

    testbase.assert_equal(regenerated, checked_in)
    return


def test_regenerated_modules_are_byte_identical_to_the_checked_in_tree():
    """
        Every regenerated module has exactly the bytes of its checked-in
        counterpart.  Lists each differing file so the report names the drift.
    """
    target = _regenerate()
    try:
        regenerated = _generated_files(target)
        checked_in = _generated_files(CLIENT_ROOT)

        differing: List[str] = []
        for relpath in sorted(set(regenerated) & set(checked_in)):
            with open(regenerated[relpath], "rb") as rf:
                fresh = rf.read()
            with open(checked_in[relpath], "rb") as cf:
                committed = cf.read()
            if fresh != committed:
                differing.append(relpath)
    finally:
        shutil.rmtree(target, ignore_errors=True)

    testbase.assert_equal(differing, [])
    return
