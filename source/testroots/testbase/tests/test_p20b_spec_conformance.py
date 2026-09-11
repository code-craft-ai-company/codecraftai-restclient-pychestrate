"""
    .. module:: test_p20b_spec_conformance
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Spec-conformance checks generalised over every group and model of
        the generated Pychestrate REST client.

    Each test is one property over the whole OpenAPI specification: every tag has
    a group, every operation has a method with the spec's path, HTTP method, status
    and parameters, no method lacks a spec entry, and every object schema has a
    model with the spec's fields.  A failure lists every offending entry so the
    report names what drifted.  No HTTP calls are made.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from typing import Any, Dict, List, Set, Tuple

import importlib
import inspect
import os
import pkgutil
import re

import yaml

from ccai import testbase

from ccai.credentials.basecredential import BaseCredential

from ccai.interfaces.schemaobject import SchemaObject

from ccai.pychestrate.rest.client.generation.pychestraterestclientgenerator import PychestrateRestClientGenerator
from ccai.pychestrate.rest.client.pychestraterestclient import PychestrateRestClient

import ccai.pychestrate.rest.client.groups as groups_package
import ccai.pychestrate.rest.client.models as models_package


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "..", ".."))
CLIENT_ROOT = os.path.join(REPO_ROOT, "source", "packages", "ccai", "pychestrate", "rest", "client")
EMBEDDED_SPEC = os.path.join(CLIENT_ROOT, "generation", "specs", "pychestrate.yaml")

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options")

LEAF_PATTERN = re.compile(r'(?:leaf_template|call_leaf) = "([^"]+)"')
HTTP_METHOD_PATTERN = re.compile(r'method="([A-Z]+)"')
EXP_STATUS_PATTERN = re.compile(r'exp_status = \[([0-9, ]+)\]')
PLACEHOLDER_PATTERN = re.compile(r"\{([^}]+)\}")


class _InertCredential(BaseCredential):
    """
        Credential that satisfies the client constructor; nothing authenticates.
    """

    def __init__(self):
        super().__init__(identifier="conformance", categories=["rest"])
        return


def _load_spec() -> Dict[str, Any]:
    with open(EMBEDDED_SPEC, "r", encoding="utf-8") as sf:
        spec = yaml.safe_load(sf)
    return spec


SPEC = _load_spec()

# The generator owns the tag/operationId to Python name rules; borrow them rather
# than restate them here.  Constructing the generator only parses the spec.
NAMING = PychestrateRestClientGenerator(
    openapi_spec_file=EMBEDDED_SPEC,
    clients_root=CLIENT_ROOT,
    client_class_name="PychestrateRestClient",
)


def _snake(name: str) -> str:
    return NAMING._safe_snake(name)


def _pascal(name: str) -> str:
    return NAMING._safe_pascal(name)


def _resolve_ref(ref: str) -> Dict[str, Any]:
    node: Any = SPEC
    for segment in ref.lstrip("#/").split("/"):
        node = node[segment]
    return node


def _spec_operations() -> List[Dict[str, Any]]:
    """
        Flattens the spec's paths into one record per operation, carrying the
        derived group and method names alongside the raw spec facts.
    """
    operations: List[Dict[str, Any]] = []

    for path, path_item in SPEC["paths"].items():
        path_level_params = path_item.get("parameters", [])

        for http_method, op in path_item.items():
            if http_method not in HTTP_METHODS:
                continue

            tags = op.get("tags", [])
            operation_id = op.get("operationId", "")

            group_name = tags[0] if tags else "default"
            method_name = operation_id
            if "/" in operation_id:
                group_name, method_name = operation_id.split("/", 1)

            parameters = []
            for entry in list(path_level_params) + list(op.get("parameters", [])):
                if "$ref" in entry:
                    entry = _resolve_ref(entry["$ref"])
                parameters.append(entry)

            success_codes = sorted(
                int(code) for code in op.get("responses", {}).keys()
                if str(code).isdigit() and 200 <= int(code) <= 299
            )

            operations.append({
                "path": path,
                "http_method": http_method.upper(),
                "operation_id": operation_id,
                "group": _snake(group_name),
                "method": _snake(method_name),
                "path_params": [_snake(p["name"]) for p in parameters if p.get("in") == "path"],
                "required_query_params": [
                    _snake(p["name"]) for p in parameters if p.get("in") == "query" and p.get("required", False)
                ],
                "optional_query_params": [
                    _snake(p["name"]) for p in parameters if p.get("in") == "query" and not p.get("required", False)
                ],
                "success_codes": success_codes,
            })

    return operations


SPEC_OPERATIONS = _spec_operations()

SPEC_TAGS = sorted({op["group"] for op in SPEC_OPERATIONS})


def _group_class(group_name: str) -> type:
    """
        Resolves the generated group class for a spec tag through the client
        property that exposes it.
    """
    client = PychestrateRestClient(host="pychestrate.invalid", credential=_InertCredential())
    group = getattr(client, group_name)
    return type(group)


def _group_methods(group_class: type) -> Dict[str, Any]:
    """
        Public methods defined on the group class itself, excluding anything
        inherited from ``RestApiGroup``.
    """
    methods = {}
    for name, member in vars(group_class).items():
        if inspect.isfunction(member) and not name.startswith("_"):
            methods[name] = member
    return methods


def _method_source_facts(func: Any) -> Tuple[str, str, List[int]]:
    """
        Reads the leaf template, HTTP method and default expected status list
        out of a generated method's source.
    """
    source = inspect.getsource(func)

    leaf_match = LEAF_PATTERN.search(source)
    method_match = HTTP_METHOD_PATTERN.search(source)
    status_match = EXP_STATUS_PATTERN.search(source)

    leaf = leaf_match.group(1) if leaf_match else ""
    http_method = method_match.group(1) if method_match else ""
    statuses = []
    if status_match:
        statuses = sorted(int(code.strip()) for code in status_match.group(1).split(",") if code.strip())

    return leaf, http_method, statuses


def _model_classes() -> Dict[str, type]:
    """
        Every ``SchemaObject`` subclass defined by a module under ``models/``.
    """
    classes: Dict[str, type] = {}
    for module_info in pkgutil.iter_modules(models_package.__path__):
        module = importlib.import_module(f"{models_package.__name__}.{module_info.name}")
        for name, member in vars(module).items():
            is_model = (
                isinstance(member, type)
                and issubclass(member, SchemaObject)
                and member is not SchemaObject
                and member.__module__ == module.__name__
            )
            if is_model:
                classes[name] = member
    return classes


def _object_schemas() -> Dict[str, Dict[str, Any]]:
    """
        The spec's component schemas that describe objects with properties;
        enums and composites do not become model classes.
    """
    schemas = {}
    for name, schema in SPEC["components"]["schemas"].items():
        if schema.get("type") == "object" and "properties" in schema:
            schemas[name] = schema
    return schemas


# ----------------------------------------------------------------------
# Groups
# ----------------------------------------------------------------------

def test_every_spec_tag_is_exposed_as_a_client_group():
    """
        For every tag used by an operation in the spec the client exposes a
        property of that name returning the ``<Tag>ApiGroup`` class.
    """
    client = PychestrateRestClient(host="pychestrate.invalid", credential=_InertCredential())

    problems = []
    for tag in SPEC_TAGS:
        expected_class_name = f"{_pascal(tag)}ApiGroup"
        group = getattr(client, tag, None)
        if group is None:
            problems.append(f"{tag}: no client property")
        elif type(group).__name__ != expected_class_name:
            problems.append(f"{tag}: property returns {type(group).__name__}, expected {expected_class_name}")

    testbase.assert_equal(problems, [])
    return


def test_every_group_module_has_a_spec_tag():
    """
        No generated group module exists for a tag the spec does not use.
    """
    module_names = sorted(info.name for info in pkgutil.iter_modules(groups_package.__path__))
    expected_modules = sorted(NAMING._file_slug(tag) for tag in SPEC_TAGS)

    testbase.assert_equal(module_names, expected_modules)
    return


def test_every_spec_operation_has_a_group_method():
    """
        Every operation in the spec has a method named after its operationId on
        the group named after its first tag.
    """
    missing = []
    for op in SPEC_OPERATIONS:
        methods = _group_methods(_group_class(op["group"]))
        if op["method"] not in methods:
            missing.append(f"{op['group']}.{op['method']} for {op['http_method']} {op['path']}")

    testbase.assert_equal(missing, [])
    return


def test_every_group_method_has_a_spec_operation():
    """
        No group defines a public method the spec does not describe.
    """
    expected: Set[Tuple[str, str]] = {(op["group"], op["method"]) for op in SPEC_OPERATIONS}

    orphans = []
    for tag in SPEC_TAGS:
        for method_name in _group_methods(_group_class(tag)):
            if (tag, method_name) not in expected:
                orphans.append(f"{tag}.{method_name}")

    testbase.assert_equal(orphans, [])
    return


def test_group_methods_call_the_spec_path_with_the_spec_http_method():
    """
        Each generated method formats the spec's path template and sends it with
        the spec's HTTP method.
    """
    mismatches = []
    for op in SPEC_OPERATIONS:
        func = _group_methods(_group_class(op["group"])).get(op["method"])
        if func is None:
            continue

        leaf, http_method, _ = _method_source_facts(func)
        if leaf != op["path"] or http_method != op["http_method"]:
            mismatches.append(
                f"{op['group']}.{op['method']}: sends {http_method} {leaf}, spec says {op['http_method']} {op['path']}"
            )

    testbase.assert_equal(mismatches, [])
    return


def test_group_methods_expect_the_spec_success_status():
    """
        Each generated method's default expected status list is the set of 2xx
        responses the spec declares for the operation.
    """
    mismatches = []
    for op in SPEC_OPERATIONS:
        func = _group_methods(_group_class(op["group"])).get(op["method"])
        if func is None:
            continue

        _, _, statuses = _method_source_facts(func)
        if statuses != op["success_codes"]:
            mismatches.append(f"{op['group']}.{op['method']}: expects {statuses}, spec declares {op['success_codes']}")

    testbase.assert_equal(mismatches, [])
    return


def test_group_method_signatures_take_the_spec_path_parameters():
    """
        Every ``{placeholder}`` in an operation's path is a positional parameter
        of the generated method, in path order, ahead of any keyword-only options.
    """
    mismatches = []
    for op in SPEC_OPERATIONS:
        func = _group_methods(_group_class(op["group"])).get(op["method"])
        if func is None:
            continue

        placeholders = [_snake(name) for name in PLACEHOLDER_PATTERN.findall(op["path"])]
        signature = inspect.signature(func)
        positional = [
            name for name, param in signature.parameters.items()
            if name != "self" and param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        ]

        if positional[:len(placeholders)] != placeholders:
            mismatches.append(f"{op['group']}.{op['method']}: positional {positional}, path needs {placeholders}")

    testbase.assert_equal(mismatches, [])
    return


def test_group_method_signatures_take_the_spec_query_parameters():
    """
        Query parameters the spec marks ``required`` are positional arguments of
        the generated method; optional ones are keyword-only arguments, so a
        caller cannot omit a required filter or mis-order an optional one.
    """
    mismatches = []
    for op in SPEC_OPERATIONS:
        if len(op["required_query_params"]) == 0 and len(op["optional_query_params"]) == 0:
            continue

        func = _group_methods(_group_class(op["group"])).get(op["method"])
        if func is None:
            continue

        signature = inspect.signature(func)
        positional = {
            name for name, param in signature.parameters.items()
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        }
        keyword_only = {
            name for name, param in signature.parameters.items()
            if param.kind == inspect.Parameter.KEYWORD_ONLY
        }

        not_positional = [name for name in op["required_query_params"] if name not in positional]
        not_keyword = [name for name in op["optional_query_params"] if name not in keyword_only]
        if len(not_positional) > 0 or len(not_keyword) > 0:
            mismatches.append(
                f"{op['group']}.{op['method']}: required query parameters {not_positional} are not positional, "
                f"optional query parameters {not_keyword} are not keyword-only"
            )

    testbase.assert_equal(mismatches, [])
    return


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------

def test_every_object_schema_has_a_model_with_the_spec_properties():
    """
        Every object schema in ``components.schemas`` has a generated model whose
        fields are exactly the schema's properties.
    """
    classes = _model_classes()

    problems = []
    for schema_name, schema in _object_schemas().items():
        model = classes.get(_pascal(schema_name))
        if model is None:
            problems.append(f"{schema_name}: no model class {_pascal(schema_name)}")
            continue

        expected_fields = set(schema["properties"].keys())
        actual_fields = set(model._fields.keys())
        if expected_fields != actual_fields:
            problems.append(f"{schema_name}: fields differ by {sorted(expected_fields ^ actual_fields)}")

    testbase.assert_equal(problems, [])
    return


def test_model_required_fields_match_the_spec():
    """
        For every generated model the fields flagged ``required`` are exactly
        the schema's ``required`` list.  Generalises the single-model check in
        the smoke tests.
    """
    classes = _model_classes()

    problems = []
    for schema_name, schema in _object_schemas().items():
        model = classes.get(_pascal(schema_name))
        if model is None:
            continue

        expected_required = set(schema.get("required", []))
        actual_required = {name for name, descriptor in model._fields.items() if descriptor.required}
        if expected_required != actual_required:
            problems.append(f"{schema_name}: required differs by {sorted(expected_required ^ actual_required)}")

    testbase.assert_equal(problems, [])
    return


def test_every_model_class_corresponds_to_a_spec_schema():
    """
        No model class exists without an object schema in the spec.
    """
    expected_names = {_pascal(name) for name in _object_schemas()}
    orphans = sorted(name for name in _model_classes() if name not in expected_names)

    testbase.assert_equal(orphans, [])
    return
