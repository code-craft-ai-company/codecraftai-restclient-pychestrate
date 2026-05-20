"""
    .. module:: pychestraterestclientbase
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pychestrate REST client base providing cookie session, API key, and mTLS auth.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""


from __future__ import annotations

from typing import Dict, Optional

from requests import Session

from automojo.credentials.basecredential import BaseCredential

from automojo.restclient.base.aspectsrest import AspectsRest, DEFAULT_REST_ASPECTS
from automojo.restclient.base.restclientbase import RestClientBase


class PychestrateRestClientBase(RestClientBase):
    """
        The :class:`PychestrateRestClientBase` object provides Pychestrate-specific
        authentication logic.

        The Pychestrate REST API supports three security schemes declared in the
        OpenAPI specification:

        * ``pychestrate_session`` -- cookie-based session (set-cookie returned by
          the ``/auth/login`` endpoint).
        * ``pychestrate_api_key`` -- ``X-Pychestrate-Api-Key`` header.
        * ``pychestrate_mtls`` -- mutual TLS client certificate + key material.

        The active scheme is selected based on the attributes carried by the
        ``BaseCredential`` instance supplied at construction time.
    """

    def __init__(self, host: str, credential: BaseCredential, port: Optional[int] = None,
                 scheme: Optional[str] = "https", headers: Optional[Dict[str, str]] = None,
                 verify_certificate: Optional[bool] = None,
                 aspects: AspectsRest = DEFAULT_REST_ASPECTS):
        """
            Initialize the Pychestrate REST client base.

            :param host: Hostname for the REST service.
            :param credential: Credential used for authentication.
            :param port: Optional port for the service.
            :param scheme: URL scheme, default is ``https``.
            :param headers: Optional default headers applied to every request.
            :param verify_certificate: Optional flag to enable or disable TLS verification.
            :param aspects: Default REST aspects.

            :returns: None
        """
        super().__init__(host, credential, port, scheme=scheme, headers=headers,
                         verify_certificate=verify_certificate, aspects=aspects)
        self._headers.setdefault("Accept", "application/json")
        return

    def authenticate(self):
        """
            Authenticate with the Pychestrate service using the provided credential.

            The credential type drives the auth scheme selection:

            * an ``api_key`` attribute selects the ``X-Pychestrate-Api-Key`` scheme.
            * ``client_cert`` / ``client_key`` attributes select the mTLS scheme.
            * a ``username`` / ``password`` pair will POST to ``/auth/login`` to
              acquire a session cookie (handled lazily on first call by the caller).

            :raises: RuntimeError if the credential type is not supported.
        """
        credential = self._credential

        session = Session()
        session.verify = self._verify_certificate

        auth_headers = self._build_auth_headers(credential)
        if auth_headers is not None and len(auth_headers) > 0:
            session.headers.update(auth_headers)

        client_cert = getattr(credential, "client_cert", None)
        client_key = getattr(credential, "client_key", None)
        if client_cert is not None and client_key is not None:
            session.cert = (client_cert, client_key)

        self._session = session
        return

    def _build_auth_headers(self, credential: BaseCredential) -> Dict[str, str]:
        """
            Build the auth-related headers for the given credential.

            :param credential: The credential used to authenticate.

            :returns: Dictionary of headers to apply to the session.
        """
        headers: Dict[str, str] = {}

        api_key = getattr(credential, "api_key", None)
        if api_key is not None and len(str(api_key)) > 0:
            headers["X-Pychestrate-Api-Key"] = str(api_key)
            return headers

        token_value = getattr(credential, "token", None)
        if token_value is not None and len(str(token_value)) > 0:
            headers["Authorization"] = f"Bearer {token_value}"
            return headers

        return headers
