"""
    .. module:: pychestraterestclientgenerator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pychestrate REST client generator with project-specific configuration.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from __future__ import annotations

import os

from pathlib import Path
from typing import List

from automojo.restclient.base.restclientgenerator import RestClientGenerator

from automojo.pychestrate.rest.client.pychestraterestclientbase import PychestrateRestClientBase


class PychestrateRestClientGenerator(RestClientGenerator):
    """
        Pychestrate REST client generator.

        The base ``RestClientGenerator`` emits schema modules into a sibling
        directory named ``schemas/`` next to the generated ``groups/`` directory.
        This subclass renames that directory to ``models/`` to match the
        convention preferred by the Pychestrate consumer, while leaving the
        rest of the generator behaviour identical.
    """

    REST_CLIENT_BASE_CLASS = PychestrateRestClientBase

    CLIENT_MODULE_ROOT = "automojo.pychestrate.rest.client"
    SCHEMA_MODULE_ROOT = "automojo.pychestrate.rest.client.models"
    GROUP_MODULE_ROOT = "automojo.pychestrate.rest.client.groups"

    def generate(self):
        """
            Generate all client, group, and schema modules.

            Mirrors the parent generator but writes schemas into a
            ``models/`` directory instead of ``schemas/``.
        """
        clients_root = self._clients_root
        groups_dir = clients_root / "groups"
        schemas_dir = clients_root / "models"

        for directory in (groups_dir, schemas_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self._generate_schema_modules(schemas_dir)

        sorted_groups = sorted(self._groups.keys())

        for group in sorted_groups:
            ops = sorted(self._groups[group], key=lambda o: self._safe_snake(o.method_name))
            self._generate_group_module(group, ops, groups_dir)

        self._generate_client_module(sorted_groups, clients_root)
        self._write_simple_init(groups_dir)
        self._write_schemas_init(schemas_dir)
        self._write_simple_init(clients_root)
        return


def pychestrate_rest_client_generator_main():
    """
        Entry point used to generate the Pychestrate REST client code from the
        OpenAPI specification embedded in this package.
    """
    this_file = __file__
    this_dir = os.path.dirname(this_file)
    client_root = os.path.dirname(this_dir)

    specs_dir = os.path.join(this_dir, "specs")
    openapi_specfile = os.path.join(specs_dir, "pychestrate.yaml")

    if not os.path.exists(openapi_specfile):
        errmsg_lines = [
            "Pychestrate OpenAPI spec file not found.",
            f"    EXPECTED: {openapi_specfile}",
            "    Refresh the spec by copying it from pychestrate-service:",
            "        pychestrate-service/specs/openapi/pychestrate.yaml",
        ]
        errmsg = os.linesep.join(errmsg_lines)
        raise FileNotFoundError(errmsg)

    generator = PychestrateRestClientGenerator(
        openapi_spec_file=openapi_specfile,
        clients_root=client_root,
        client_class_name="PychestrateRestClient",
    )
    generator.generate()
    return


if __name__ == "__main__":
    pychestrate_rest_client_generator_main()
