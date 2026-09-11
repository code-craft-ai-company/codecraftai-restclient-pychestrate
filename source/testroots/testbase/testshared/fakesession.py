"""
    .. module:: fakesession
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: A canned-response stand-in for the ``requests`` session that
        ``RestClientBase`` resolves through its ``_session`` attribute, so the
        generated group methods can be driven without a Pychestrate server.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

import json

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from requests import PreparedRequest, Request, Response, Session
from requests.structures import CaseInsensitiveDict
from requests.utils import requote_uri


# A canned reply: (status code, JSON payload or None, response headers or None).
CannedResponse = Tuple[int, Any, Optional[Dict[str, str]]]


@dataclass
class RecordedCall:
    """
        One request that reached the fake session, captured from the prepared
        request so it reflects exactly what would have gone on the wire.
    """

    method: str
    url: str
    path: str
    params: Dict[str, Any]
    headers: Dict[str, str]
    body: Any
    prepared: PreparedRequest
    send_kwargs: Dict[str, Any] = field(default_factory=dict)


class FakeSession:
    """
        Stands in for the ``requests.Session`` held by ``RestClientBase._session``.

        ``RestClientBase`` only ever calls ``prepare_request`` and ``send`` on the
        session, so those are the two methods provided.  Requests are prepared by
        a real ``requests.Session`` so the URL, query string, headers and JSON body
        recorded are what ``requests`` itself would have sent.  Each ``send`` pops
        the next canned ``(status, json, headers)`` tuple, in order, and returns it
        as a real ``requests.Response``.

        Usage::

            session = FakeSession([(200, {"pod_id": "pod-1"}, None)])
            client = PychestrateRestClient(host="pychestrate.invalid", credential=cred)
            client._session = session

            client.pods.pods_get_definition("proj-1", "pod-1")

            session.assert_call(0, "GET", "/projects/{project_id}/pod-definitions/{pod_id}",
                                project_id="proj-1", pod_id="pod-1")
    """

    def __init__(self, responses: Sequence[CannedResponse]):
        """
            :param responses: The canned replies, consumed one per ``send`` in order.
        """
        self._responses: List[CannedResponse] = list(responses)
        self._preparer = Session()
        self.calls: List[RecordedCall] = []
        return

    @property
    def remaining(self) -> int:
        """
            The number of canned responses not yet consumed.
        """
        return len(self._responses)

    def prepare_request(self, request: Request) -> PreparedRequest:
        """
            Prepares the request exactly as a real session would.

            :param request: The un-prepared request built by the client.

            :returns: The prepared request that will be handed to :meth:`send`.
        """
        prepared = self._preparer.prepare_request(request)
        return prepared

    def send(self, request: PreparedRequest, **kwargs) -> Response:
        """
            Records the prepared request and returns the next canned response.

            :param request: The prepared request the client is sending.
            :param kwargs: Transport options the client passed (``timeout``, ``verify``).

            :returns: A :class:`requests.Response` built from the next canned tuple.

            :raises AssertionError: When the canned responses are exhausted.
        """
        call = self._record(request, kwargs)

        if len(self._responses) == 0:
            errmsg = (
                f"FakeSession has no canned response left for call {len(self.calls)}: "
                f"{call.method} {call.url}"
            )
            raise AssertionError(errmsg)

        status, payload, headers = self._responses.pop(0)

        response = Response()
        response.status_code = status
        response.url = request.url
        response.request = request
        response.encoding = "utf-8"
        response.headers = CaseInsensitiveDict(headers or {})

        if payload is None:
            response._content = b""
        elif isinstance(payload, (bytes, bytearray)):
            response._content = bytes(payload)
        else:
            response._content = json.dumps(payload).encode("utf-8")
            response.headers.setdefault("Content-Type", "application/json")

        return response

    def assert_call(self, index: int, method: str, template: str, **path_params: Any) -> RecordedCall:
        """
            Asserts that the recorded call at ``index`` used ``method`` against the
            path obtained by filling the generator's leaf ``template`` with
            ``path_params``.

            :param index: Position of the call in :attr:`calls`.
            :param method: The expected HTTP method, upper case.
            :param template: The leaf template from the OpenAPI path, for example
                             ``/projects/{project_id}/pods/{pod_id}``.
            :param path_params: Values for the template's placeholders.

            :returns: The recorded call, for further assertions.
        """
        if index >= len(self.calls):
            errmsg = f"FakeSession recorded {len(self.calls)} call(s); there is no call at index {index}."
            raise AssertionError(errmsg)

        call = self.calls[index]
        assert_call_hits(call, method, template, **path_params)
        return call

    def _record(self, request: PreparedRequest, send_kwargs: Dict[str, Any]) -> RecordedCall:
        """
            Captures the method, URL, path, query parameters, headers and decoded JSON
            body of a prepared request.
        """
        split = urlsplit(request.url)

        params: Dict[str, Any] = {}
        for name, values in parse_qs(split.query, keep_blank_values=True).items():
            params[name] = values[0] if len(values) == 1 else values

        body: Any = request.body
        if isinstance(body, (bytes, bytearray)):
            content_type = request.headers.get("Content-Type", "")
            if content_type.startswith("application/json") and len(body) > 0:
                body = json.loads(bytes(body).decode("utf-8"))

        call = RecordedCall(
            method=request.method,
            url=request.url,
            path=split.path,
            params=params,
            headers=dict(request.headers),
            body=body,
            prepared=request,
            send_kwargs=dict(send_kwargs),
        )
        self.calls.append(call)
        return call


def assert_call_hits(call: RecordedCall, method: str, template: str, **path_params: Any) -> None:
    """
        Asserts that a recorded call used ``method`` on the path obtained by filling
        ``template`` with ``path_params``, so a test reads as "calling
        ``pods.pods_get_definition(project_id, pod_id)`` hits
        ``GET /projects/{project_id}/pod-definitions/{pod_id}``".

        The expected path is re-quoted the way ``requests`` quotes URLs so values
        with characters outside the unreserved set compare correctly.

        :param call: The recorded call to check.
        :param method: The expected HTTP method, upper case.
        :param template: The leaf template with ``{name}`` placeholders.
        :param path_params: Values for the placeholders.
    """
    expected_path = requote_uri(template.format(**path_params))

    if call.method != method or call.path != expected_path:
        errmsg = (
            f"Expected {method} {expected_path} (template {template!r}) "
            f"but the client sent {call.method} {call.path}."
        )
        raise AssertionError(errmsg)

    return
