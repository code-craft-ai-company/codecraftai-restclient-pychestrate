# Implementation Plan — Pychestrate Client

## Package Skeleton

- [x] 1. Create `source/packages/ccai/pychestrate/rest/client/` with `generation/`, `groups/`, and `models/` subpackages.
- [x] 2. Declare `codecraftai-errors`, `codecraftai-credentials`, `codecraftai-restclient-base`, and `pyyaml` as dependencies in `pyproject.toml`.
- [x] 3. Add `Makefile` targets for `setup`, `test`, and `generate`.

## Authentication (hand-written)

- [x] 4. Implement `PychestrateRestClientBase(RestClientBase)` defaulting the `Accept` header to `application/json`.
- [x] 5. Implement `authenticate()` building a `requests.Session` with no login round trip.
- [x] 6. Implement the `pychestrate_api_key` scheme: `api_key` attribute → `X-Pychestrate-Api-Key` header.
- [x] 7. Implement the `pychestrate_mtls` scheme: `client_cert` + `client_key` attributes → `session.cert`.
- [x] 8. Implement the bearer-token fallback: `token` attribute → `Authorization: Bearer`.

## Generation (hand-written)

- [x] 9. Vendor the service contract as `generation/specs/pychestrate.yaml` (OpenAPI 3.1, `Pychestrate Service API` `0.0.7-preview`).
- [x] 10. Implement `PychestrateRestClientGenerator(RestClientGenerator)` binding `REST_CLIENT_BASE_CLASS` and the three module roots.
- [x] 11. Override `generate()` to emit schema modules into `models/` instead of the base generator's `schemas/`.
- [x] 12. Implement `pychestrate_rest_client_generator_main()` with a `FileNotFoundError` that names both the expected path and the `pychestrate-service` source to copy from.

## Generated Output

- [x] 13. Generate `pychestraterestclient.py` exposing 25 API groups as read-only properties.
- [x] 14. Generate 25 group modules covering the identity, configuration, project, fleet, and execution surfaces — 97 methods against the contract's 97 operations.
- [x] 15. Generate 46 model modules holding 94 `SchemaObject` classes.
- [x] 16. Generate the typed page envelopes (`Runpage`, `Artifactentrypage`, `Testcatalogentrypage`) over `Pagemeta`.
- [x] 17. Generate the pod-client ingestion path: `dispatch_ack_run`, `progress_post_frame`, `results_post_complete`, `artifacts_presign_upload`, `clients_dispatches_next`.

## Tests

- [x] 18. Add `test_p20a_client_smoke.py` asserting the client exposes `runs`, `clients`, and `pods` with the right group types, using an inert `BaseCredential` subclass and no HTTP.
- [x] 19. Assert the generated `Run` model's required fields equal the contract's `Run.required` list.
- [x] 20. Assert the contract's `RunState` enum values survive and `Run.state` exists.

## Open Items

- [ ] 21. **Generated client docstring is wrong.** `PychestrateRestClient` is documented as "GitHub public REST API client generated from the OpenAPI specification." The string is hardcoded in `RestClientGenerator._generate_client_module` in `codecraftai-restclient-base`; fix it there (derive from the spec's `info.title`) rather than editing generated output.
- [ ] 22. **Model class names lose their camel humps.** `RunPage` generates as `Runpage`, `PageMeta` as `Pagemeta`, `LogoutRequest` as `Logoutrequest`. `RestClientGenerator._safe_pascal` splits on non-alphanumerics and calls `str.capitalize()` on each part, which works for GitHub's hyphenated schema names but flattens Pychestrate's CamelCase ones. Fix in the base generator.
- [ ] 23. **`PagedList` is a dead import in all 25 group modules.** No operation in this contract is classified as paged (paging is carried by named page schemas, not `page`/`per_page` query parameters), so the import is never used.
- [ ] 24. **24 of 97 methods return `Dict[str, Any]`.** These are the list endpoints whose 200 response is an inline `{items: [...]}` object rather than a named schema — `clients_list`, `projects_list_members`, `flags_list`, and so on. Promoting those envelopes to named `*Page` schemas in the contract would type them without any generator change.
- [ ] 25. **Three contract schemas generate no class.** `RunState` and `TerminalOutcome` are string enums, and `EnrollmentTokenWithSecret` is an `allOf` composition; `_schema_can_generate_class` requires a `properties` key, so all three are skipped. The enums are emitted as plain `str` fields (already asserted in the smoke test) and the enrollment issuance response stays untyped.
- [ ] 26. **The `Problem` model is generated but never used.** Every 4xx/5xx response in the contract is `application/problem+json` with the RFC 7807 shape, but errors are raised through the base `raise_for_http_status`, which discards the problem document. Reclassifying into a typed error that carries `type`/`title`/`detail`/`instance` would make failures diagnosable.
- [ ] 27. **19 operations are marked `x-pychestrate-status: planned` in the contract and are generated as if live** — for example `results.artifacts_local_upload`. The generator ignores the extension, so callers cannot distinguish implemented endpoints from placeholders.
- [ ] 28. **`authenticate()`'s docstring describes behaviour that does not exist.** It states that a `username`/`password` credential "will POST to `/auth/login` to acquire a session cookie" and that an unsupported credential raises `RuntimeError`. Neither happens: `_build_auth_headers` returns an empty dict and the client silently builds an unauthenticated session. `/auth/login` is also not in the contract — the only auth path is `POST /auth/logout`, since login is an HTML form at `/login` outside the REST surface. Either raise on an unusable credential or correct the docstring.
- [ ] 29. **Test coverage reaches 3 of 25 groups.** There are no mock-transport tests of path/query composition, no coverage of the pod-client ingestion path, and no coverage of the auth-scheme selection in `_build_auth_headers`.
