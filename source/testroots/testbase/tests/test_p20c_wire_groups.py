"""
    .. module:: test_p20c_wire_groups
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Wire-level tests for the four largest generated groups (pods,
        projects, flags, rbac) plus the hand-written client base.

    Every test injects a :class:`FakeSession` as the client's ``_session`` (the
    attribute ``RestClientBase._get_session`` resolves) and asserts the request
    the generated method produced: HTTP method, path, query parameters, headers
    and JSON body, and that the canned response parses into the declared model.
    No network is touched.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from typing import Any, Dict, Optional

from ccai import testbase

from ccai.testbase.properties import run_property
from ccai.testbase.properties import strategies as st

from ccai.credentials.basecredential import BaseCredential

from ccai.errors.exceptions import HttpNotFoundError

from ccai.pychestrate.rest.client.pychestraterestclient import PychestrateRestClient

from ccai.pychestrate.rest.client.models.flags import Featureflag, Featureflagcreaterequest
from ccai.pychestrate.rest.client.models.pods import Poddefinition, Poddefinitioncreaterequest, Podtemplate
from ccai.pychestrate.rest.client.models.projects import Project, Projectpatchrequest
from ccai.pychestrate.rest.client.models.rbac import Rbaccheckrequest, Rbacrolebindingcreaterequest

from testbase.testshared.fakesession import FakeSession


HOST = "pychestrate.invalid"


class _InertCredential(BaseCredential):
    """
        Credential carrying no authentication attributes.
    """

    def __init__(self):
        super().__init__(identifier="wire-tests", categories=["rest"])
        return


class _ApiKeyCredential(BaseCredential):
    """
        Credential selecting the ``X-Pychestrate-Api-Key`` scheme.
    """

    def __init__(self, api_key: str, token: Optional[str] = None):
        super().__init__(identifier="api-key", categories=["rest"])
        self.api_key = api_key
        self.token = token
        return


class _TokenCredential(BaseCredential):
    """
        Credential selecting the bearer token scheme.
    """

    def __init__(self, token: str):
        super().__init__(identifier="token", categories=["rest"])
        self.token = token
        return


class _MtlsCredential(BaseCredential):
    """
        Credential selecting the mutual-TLS scheme.
    """

    def __init__(self, client_cert: str, client_key: str):
        super().__init__(identifier="mtls", categories=["rest"])
        self.client_cert = client_cert
        self.client_key = client_key
        return


def _make_client(session: FakeSession, credential: Optional[BaseCredential] = None) -> PychestrateRestClient:
    """
        Builds a client whose HTTP session is the fake, so no authentication or
        network activity happens.
    """
    if credential is None:
        credential = _InertCredential()

    client = PychestrateRestClient(host=HOST, credential=credential)
    client._session = session
    return client


def _pod_definition(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "pod_id": "pod-7",
        "project_id": "proj-1",
        "name": "edge-rack",
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _project(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "project_id": "prj-0001",
        "slug": "widgets",
        "display_name": "Widgets",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _feature_flag(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "flag_key": "dark-mode",
        "enabled": True,
        "created_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


# ----------------------------------------------------------------------
# pods
# ----------------------------------------------------------------------

def test_pods_get_definition_hits_the_definition_path_and_parses_the_model():
    """
        ``pods.pods_get_definition(project_id, pod_id)`` hits
        ``GET /projects/{project_id}/pod-definitions/{pod_id}`` with no body and
        returns the response as a ``Poddefinition``.
    """
    session = FakeSession([(200, _pod_definition(), None)])
    client = _make_client(session)

    result = client.pods.pods_get_definition("proj-1", "pod-7")

    call = session.assert_call(0, "GET", "/projects/{project_id}/pod-definitions/{pod_id}",
                               project_id="proj-1", pod_id="pod-7")
    testbase.assert_equal(len(session.calls), 1)
    testbase.assert_true(call.body is None)
    testbase.assert_true(isinstance(result, Poddefinition))
    testbase.assert_equal(result.pod_id, "pod-7")
    testbase.assert_equal(result.name, "edge-rack")
    return


def test_pods_create_definition_posts_the_request_model_as_json():
    """
        ``pods.pods_create_definition(project_id, body)`` hits
        ``POST /projects/{project_id}/pod-definitions`` with the request model
        serialised as the JSON body, expects 201 and returns the reply payload.
    """
    session = FakeSession([(201, _pod_definition(), None)])
    client = _make_client(session)
    body = Poddefinitioncreaterequest(name="edge-rack", description="two hosts")

    result = client.pods.pods_create_definition("proj-1", body)

    call = session.assert_call(0, "POST", "/projects/{project_id}/pod-definitions", project_id="proj-1")
    testbase.assert_equal(call.body, {"name": "edge-rack", "description": "two hosts"})
    testbase.assert_equal(call.headers["Content-Type"], "application/json")
    testbase.assert_equal(result, _pod_definition())
    return


def test_pods_update_template_parameters_puts_a_dict_body_unchanged():
    """
        A method declared with a plain ``Dict`` body sends that dictionary as the
        JSON body and parses the reply into ``Podtemplate``.
    """
    reply = {"template_id": "tpl-1", "project_id": "proj-1", "name": "base", "parameters": {"cpu": 4}}
    session = FakeSession([(200, reply, None)])
    client = _make_client(session)

    result = client.pods.pods_update_template_parameters("proj-1", "tpl-1", {"cpu": 4})

    call = session.assert_call(0, "PUT", "/projects/{project_id}/pod-templates/{template_id}/parameters",
                               project_id="proj-1", template_id="tpl-1")
    testbase.assert_equal(call.body, {"cpu": 4})
    testbase.assert_true(isinstance(result, Podtemplate))
    testbase.assert_equal(result.parameters, {"cpu": 4})
    return


def test_pods_path_parameters_format_into_the_leaf_for_any_identifier():
    """
        For any URL-safe project and pod identifiers ``pods.pods_get_state`` hits
        ``GET /projects/{project_id}/pods/{pod_id}/state``.
    """
    identifier = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=16)

    def check(project_id: str, pod_id: str) -> None:
        reply = {"pod_id": pod_id, "state": "running", "updated_at": "2026-01-01T00:00:00Z"}
        session = FakeSession([(200, reply, None)])
        client = _make_client(session)

        result = client.pods.pods_get_state(project_id, pod_id)

        session.assert_call(0, "GET", "/projects/{project_id}/pods/{pod_id}/state",
                            project_id=project_id, pod_id=pod_id)
        assert result.pod_id == pod_id
        return

    examples = run_property(check, max_examples=40, project_id=identifier, pod_id=identifier)

    testbase.assert_equal(examples, 40)
    return


# ----------------------------------------------------------------------
# projects
# ----------------------------------------------------------------------

def test_projects_get_by_slug_hits_the_project_path_and_parses_the_model():
    """
        ``projects.projects_get_by_slug(slug)`` hits ``GET /projects/{slug}`` and
        returns a ``Project``.
    """
    session = FakeSession([(200, _project(), None)])
    client = _make_client(session)

    result = client.projects.projects_get_by_slug("widgets")

    call = session.assert_call(0, "GET", "/projects/{slug}", slug="widgets")
    testbase.assert_true(call.body is None)
    testbase.assert_equal(call.params, {})
    testbase.assert_true(isinstance(result, Project))
    testbase.assert_equal(result.slug, "widgets")
    testbase.assert_equal(result.display_name, "Widgets")
    return


def test_projects_patch_sends_the_patch_body_and_parses_the_model():
    """
        ``projects.projects_patch(slug, body)`` hits ``PATCH /projects/{slug}``
        with the patch request as JSON and returns the updated ``Project``.
    """
    session = FakeSession([(200, _project(display_name="Widgets v2"), None)])
    client = _make_client(session)

    result = client.projects.projects_patch("widgets", Projectpatchrequest(display_name="Widgets v2"))

    call = session.assert_call(0, "PATCH", "/projects/{slug}", slug="widgets")
    testbase.assert_equal(call.body, {"display_name": "Widgets v2"})
    testbase.assert_true(isinstance(result, Project))
    testbase.assert_equal(result.display_name, "Widgets v2")
    return


def test_projects_delete_returns_none_on_204():
    """
        ``projects.projects_delete(slug)`` hits ``DELETE /projects/{slug}``, sends
        no body, and returns ``None`` for the empty 204 reply instead of trying to
        decode it.
    """
    session = FakeSession([(204, None, None)])
    client = _make_client(session)

    result = client.projects.projects_delete("widgets")

    call = session.assert_call(0, "DELETE", "/projects/{slug}", slug="widgets")
    testbase.assert_true(call.body is None)
    testbase.assert_true(result is None)
    return


# ----------------------------------------------------------------------
# flags
# ----------------------------------------------------------------------

def test_flags_get_by_key_hits_the_flag_path_and_parses_the_model():
    """
        ``flags.flags_get_by_key(flag_key)`` hits ``GET /flags/{flag_key}`` and
        returns a ``Featureflag``.
    """
    session = FakeSession([(200, _feature_flag(), None)])
    client = _make_client(session)

    result = client.flags.flags_get_by_key("dark-mode")

    session.assert_call(0, "GET", "/flags/{flag_key}", flag_key="dark-mode")
    testbase.assert_true(isinstance(result, Featureflag))
    testbase.assert_equal(result.flag_key, "dark-mode")
    testbase.assert_true(result.enabled)
    return


def test_flags_create_posts_the_request_model_and_expects_201():
    """
        ``flags.flags_create(body)`` hits ``POST /flags`` with the create request
        as JSON, accepts 201 and returns the reply payload.
    """
    session = FakeSession([(201, _feature_flag(), None)])
    client = _make_client(session)

    result = client.flags.flags_create(Featureflagcreaterequest(flag_key="dark-mode", enabled=True))

    call = session.assert_call(0, "POST", "/flags")
    testbase.assert_equal(call.body, {"flag_key": "dark-mode", "enabled": True})
    testbase.assert_equal(result, _feature_flag())
    return


# ----------------------------------------------------------------------
# rbac
# ----------------------------------------------------------------------

def test_rbac_list_bindings_sends_the_filters_as_query_parameters():
    """
        ``rbac.rbac_list_bindings(user_id=..., project_id=...)`` hits
        ``GET /rbac/bindings`` with both filters in the query string and returns
        the reply payload.
    """
    reply = {"items": [{"binding_id": "b-1", "user_id": "u-1", "role_name": "viewer"}]}
    session = FakeSession([(200, reply, None)])
    client = _make_client(session)

    result = client.rbac.rbac_list_bindings(user_id="u-1", project_id="p-1")

    call = session.assert_call(0, "GET", "/rbac/bindings")
    testbase.assert_equal(call.params, {"user_id": "u-1", "project_id": "p-1"})
    testbase.assert_equal(result, reply)
    return


def test_rbac_list_bindings_omits_absent_filters_from_the_query():
    """
        Filters left at ``None`` do not appear in the query string at all.
    """
    session = FakeSession([(200, {"items": []}, None)])
    client = _make_client(session)

    client.rbac.rbac_list_bindings()

    call = session.assert_call(0, "GET", "/rbac/bindings")
    testbase.assert_equal(call.params, {})
    testbase.assert_true("?" not in call.url)
    return


def test_rbac_create_binding_posts_the_request_model_and_expects_201():
    """
        ``rbac.rbac_create_binding(body)`` hits ``POST /rbac/bindings`` with the
        binding request as JSON, including an explicit ``null`` project scope.
    """
    reply = {"binding_id": "b-1", "user_id": "u-1", "role_name": "admin", "project_id": None}
    session = FakeSession([(201, reply, None)])
    client = _make_client(session)

    result = client.rbac.rbac_create_binding(Rbacrolebindingcreaterequest(user_id="u-1", role_name="admin"))

    call = session.assert_call(0, "POST", "/rbac/bindings")
    testbase.assert_equal(call.body, {"user_id": "u-1", "role_name": "admin"})
    testbase.assert_equal(result, reply)
    return


def test_rbac_delete_binding_returns_none_on_204():
    """
        ``rbac.rbac_delete_binding(binding_id)`` hits
        ``DELETE /rbac/bindings/{binding_id}`` and returns ``None`` for 204.
    """
    session = FakeSession([(204, None, None)])
    client = _make_client(session)

    result = client.rbac.rbac_delete_binding("b-1")

    session.assert_call(0, "DELETE", "/rbac/bindings/{binding_id}", binding_id="b-1")
    testbase.assert_true(result is None)
    return


# ----------------------------------------------------------------------
# Cross-cutting client behaviour
# ----------------------------------------------------------------------

def test_unexpected_status_raises_the_mapped_http_error_carrying_the_body():
    """
        A status outside the method's expected list raises the ``ccai.errors``
        type mapped to it (404 -> ``HttpNotFoundError``) and the message carries
        the response body and URL.
    """
    session = FakeSession([(404, {"title": "Not Found", "detail": "no flag named missing"}, None)])
    client = _make_client(session)

    error: Optional[BaseException] = None
    try:
        client.flags.flags_get_by_key("missing")
    except HttpNotFoundError as nferr:
        error = nferr

    testbase.assert_true(error is not None)
    testbase.assert_true("no flag named missing" in str(error))
    testbase.assert_true("/flags/missing" in str(error))
    return


def test_client_sends_the_default_accept_header():
    """
        The client base installs ``Accept: application/json`` as a default header
        and the generated methods send the client defaults on every call.
    """
    session = FakeSession([(200, {"items": []}, None)])
    client = _make_client(session)

    client.flags.flags_list()

    call = session.assert_call(0, "GET", "/flags")
    testbase.assert_equal(call.headers["Accept"], "application/json")
    return


def test_explicit_headers_replace_the_client_defaults_for_that_call():
    """
        Passing ``headers=`` to a generated method sends those headers in place
        of the client defaults for that call only.
    """
    session = FakeSession([(200, {"items": []}, None), (200, {"items": []}, None)])
    client = _make_client(session)

    client.flags.flags_list(headers={"Accept": "text/plain", "X-Trace": "abc123"})
    client.flags.flags_list()

    first = session.calls[0]
    second = session.calls[1]
    testbase.assert_equal(first.headers["Accept"], "text/plain")
    testbase.assert_equal(first.headers["X-Trace"], "abc123")
    testbase.assert_equal(second.headers["Accept"], "application/json")
    testbase.assert_true("X-Trace" not in second.headers)
    return


def test_perform_call_serialises_a_schema_object_body_to_json():
    """
        ``PychestrateRestClientBase.perform_call`` converts a ``SchemaObject``
        body with ``to_dict`` before the request is prepared.  Regression for
        the typed request models being handed to ``requests`` unserialised.
    """
    session = FakeSession([(200, {"allowed": True, "permission": "runs.read"}, None)])
    client = _make_client(session)

    response = client.perform_call(
        leaf="/rbac/check",
        method="POST",
        params=None,
        body=Rbaccheckrequest(permission="runs.read", user_id="u-1"),
        exp_status=[200],
        aspects=None,
    )

    call = session.assert_call(0, "POST", "/rbac/check")
    testbase.assert_equal(call.body, {"permission": "runs.read", "user_id": "u-1"})
    testbase.assert_equal(response.json()["allowed"], True)
    return


def test_call_passes_the_aspects_timeouts_to_the_session():
    """
        The connection and inactivity timeouts from the client's aspects reach
        ``session.send`` as the ``timeout`` tuple.
    """
    session = FakeSession([(200, {"items": []}, None)])
    client = _make_client(session)
    aspects = client.aspects

    client.flags.flags_list()

    call = session.calls[0]
    testbase.assert_equal(call.send_kwargs["timeout"], (aspects.connection_timeout, aspects.inactivity_timeout))
    return


# ----------------------------------------------------------------------
# Authentication scheme selection (hand-written client base)
# ----------------------------------------------------------------------

def test_authenticate_with_api_key_credential_sets_the_api_key_header():
    """
        An ``api_key`` credential selects the ``X-Pychestrate-Api-Key`` scheme on
        the session ``authenticate`` builds.
    """
    client = PychestrateRestClient(host=HOST, credential=_ApiKeyCredential(api_key="key-123"))

    client.authenticate()

    session = client._session
    testbase.assert_equal(session.headers["X-Pychestrate-Api-Key"], "key-123")
    testbase.assert_true("Authorization" not in session.headers)
    return


def test_authenticate_with_token_credential_sets_the_bearer_header():
    """
        A ``token`` credential selects the bearer scheme.
    """
    client = PychestrateRestClient(host=HOST, credential=_TokenCredential(token="tok-456"))

    client.authenticate()

    session = client._session
    testbase.assert_equal(session.headers["Authorization"], "Bearer tok-456")
    testbase.assert_true("X-Pychestrate-Api-Key" not in session.headers)
    return


def test_authenticate_prefers_api_key_over_token():
    """
        When a credential carries both, the API key scheme wins and no bearer
        header is added.
    """
    credential = _ApiKeyCredential(api_key="key-123", token="tok-456")
    client = PychestrateRestClient(host=HOST, credential=credential)

    client.authenticate()

    session = client._session
    testbase.assert_equal(session.headers["X-Pychestrate-Api-Key"], "key-123")
    testbase.assert_true("Authorization" not in session.headers)
    return


def test_authenticate_with_mtls_credential_sets_the_session_certificate():
    """
        A credential with ``client_cert`` and ``client_key`` selects mutual TLS by
        installing the certificate pair on the session.
    """
    credential = _MtlsCredential(client_cert="/etc/pychestrate/client.crt", client_key="/etc/pychestrate/client.key")
    client = PychestrateRestClient(host=HOST, credential=credential)

    client.authenticate()

    session = client._session
    testbase.assert_equal(session.cert, ("/etc/pychestrate/client.crt", "/etc/pychestrate/client.key"))
    testbase.assert_true("Authorization" not in session.headers)
    return


def test_authenticate_with_plain_credential_adds_no_auth_headers():
    """
        A credential without any scheme attributes yields a session with neither
        an API key nor a bearer header and no client certificate.
    """
    client = PychestrateRestClient(host=HOST, credential=_InertCredential())

    client.authenticate()

    session = client._session
    testbase.assert_true("X-Pychestrate-Api-Key" not in session.headers)
    testbase.assert_true("Authorization" not in session.headers)
    testbase.assert_true(session.cert is None)
    testbase.assert_equal(session.verify, client._verify_certificate)
    return
