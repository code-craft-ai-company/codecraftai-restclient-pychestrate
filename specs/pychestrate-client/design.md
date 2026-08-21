# Design

## Overview

`PychestrateRestClient` is a `PychestrateRestClientBase` subclass — itself a
`RestClientBase` subclass — that talks to the Pychestrate orchestration
service. It is generated from the service's own OpenAPI 3.1 contract, vendored
into this repo at `generation/specs/pychestrate.yaml`. The contract, not this
package, is the source of truth: `pychestrate-service` publishes it at
`specs/openapi/pychestrate.yaml` and this repo carries a copy.

Two modules are hand-maintained:

- `pychestraterestclientbase.py` — the three Pychestrate security schemes.
- `generation/pychestraterestclientgenerator.py` — generator configuration and
  entry point.

Everything else — `pychestraterestclient.py`, `groups/`, `models/` — is
generated output. Fixing generated code means fixing the contract, the base
generator in `codecraftai-restclient-base`, or this repo's generator subclass,
then re-running `make generate`.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  pychestrate-service/specs/openapi/pychestrate.yaml       │
│                 (source of truth, copied in)              │
└─────────────────────────┬────────────────────────────────┘
                          │  PychestrateRestClientGenerator
                          ▼
┌──────────────────────────────────────────────────────────┐
│  pychestraterestclient.py   groups/*.py   models/*.py     │
│  (generated — DO NOT EDIT)                                │
└─────────────────────────┬────────────────────────────────┘
                          │ extends
                          ▼
┌────────────────────────────┐      ┌─────────────────────┐
│  PychestrateRestClientBase │─────▶│ codecraftai-        │
│  (hand-written auth:       │      │   credentials       │
│   api key / bearer / mTLS) │      └─────────────────────┘
└──────────┬─────────────────┘
           │ extends
           ▼
┌────────────────────────────┐
│  RestClientBase            │  perform_call / aspects /
│  (codecraftai-restclient-  │  session reuse / error raise
│   base)                    │
└──────────┬─────────────────┘
           │ HTTPS (+ optional client cert)
           ▼
     Pychestrate service
```

---

## Authentication

The contract declares three security schemes; `PychestrateRestClientBase`
implements them by inspecting attributes on the supplied `BaseCredential`
rather than by credential class, so any credential carrying the right
attributes works:

| Scheme | Contract | Selected by | Effect |
| --- | --- | --- | --- |
| `pychestrate_api_key` | `X-Pychestrate-Api-Key` header | `api_key` attribute | header on the session |
| `pychestrate_mtls` | mutual TLS | `client_cert` + `client_key` | `session.cert` pair |
| `pychestrate_session` | `pych_session` cookie | — | established out of band by the HTML login form |

`_build_auth_headers` also accepts a `token` attribute and emits
`Authorization: Bearer <token>`; that is a fourth path with no matching
security scheme in the contract. The header and certificate paths are applied
independently, so an agent credential carrying both an API key and certificate
material configures both. Header selection short-circuits: `api_key` wins over
`token`.

There is no login round trip. `authenticate()` only builds the
`requests.Session`; the `pychestrate_session` cookie scheme is not something
this client can establish, since the contract's only auth path is
`POST /auth/logout` — login is an HTML form at `/login`, outside the REST
surface.

---

## Generation Scheme

`PychestrateRestClientGenerator` is a thin subclass. It sets
`REST_CLIENT_BASE_CLASS` and the three module roots, and overrides `generate()`
for exactly one reason: to write schema modules into `models/` instead of the
base generator's `schemas/`. The rest of the pipeline is inherited unchanged.

**Grouping.** Each operation's first `tags` entry becomes its group; the module
file is the tag with underscores stripped, the class is the pascal-cased tag
plus `ApiGroup`, and the client property is the snake-cased tag. Twenty-five
groups are generated from the contract's twenty-six declared tags — `metrics`
is declared as planned and owns no operations, so no group is emitted for it.

**Method naming.** Pychestrate uses flat `operationId` values that already
carry a domain prefix (`runs_list`, `pods_get_topology`,
`enrollment_redeem`), and the generator only splits on `/` when present. The
prefix is therefore preserved verbatim, which is why calls read
`client.runs.runs_list()` rather than `client.runs.list()`.

**Return typing.** A 200 response that `$ref`s a named schema becomes that
model type; an inline anonymous object becomes `Dict[str, Any]`; an
unresolvable response becomes `Any`. Pychestrate's list endpoints split along
this line: those returning a named page schema get a typed envelope
(`Runpage`, `Artifactentrypage`, `Testcatalogentrypage`, each pairing an
`items` array with `Pagemeta`), while those declaring an inline
`{items: [...]}` object fall through to `Dict[str, Any]`.

**Scale.** The contract declares 81 paths carrying 97 operations, and the
generator emits exactly 97 methods across 25 group modules, plus 94
`SchemaObject` classes across 46 model modules. Of the 97 methods, 24 return
`Dict[str, Any]` and 29 return `Any` — roughly half the surface is untyped at
the response boundary, all of it traceable to inline schemas in the contract
rather than to a generator limitation.

---

## Generated Method Shape

Every generated method follows the same skeleton:

1. Resolve `aspects`, falling back to `client.aspects` when `None`.
2. Resolve headers — a supplied `headers` argument *replaces* `client.headers`.
3. Compose `call_leaf`, as a literal or by `str.format` over a `leaf_template`
   and a `path_params` dict.
4. Build `query_params`, skipping any parameter left at `None`.
5. Default `exp_status` to the operation's 2xx codes from the contract.
6. Call `client.perform_call(...)`.
7. Parse: `None` for 204/205 and empty-bodied 202; `SchemaObject.from_dict` for
   a typed response; the decoded JSON otherwise.

Authentication, retry strategy, session reuse, and HTTP error classification
live in `RestClientBase`, not in generated code. `_parse_item` degrades to the
raw dictionary when a payload does not match its declared model, so contract
drift surfaces as a dict rather than an exception.

---

## Module Layout

```
source/packages/ccai/pychestrate/rest/client/
├── __init__.py
├── pychestraterestclientbase.py         # hand-written: auth
├── pychestraterestclient.py             # generated: 25 group properties
├── generation/
│   ├── pychestraterestclientgenerator.py  # hand-written: generator config
│   └── specs/
│       └── pychestrate.yaml               # vendored OpenAPI 3.1 contract
├── groups/                              # generated: 25 modules, 97 methods
└── models/                              # generated: 46 modules, 94 classes
```

---

## See Also

- `codecraftai-restclient-base/specs/restapigroup-enhancements/` — the
  `RestApiGroup` shape and paging helpers this client builds on.
- `codecraftai-restclient-github-public/specs/github-public-client/` — the
  sibling generated client, same generator, different contract and layout.
- `codecraftai-credentials` — `BaseCredential`, the construction-time input.

---

## Testing Strategy

Because the code under test is generated, the tests are structural rather than
behavioural: they verify that the emitted shape still matches the contract, and
they issue no HTTP.

`source/testroots/testbase/tests/test_p20a_client_smoke.py` covers three
properties:

1. **Group wiring.** The client exposes `runs`, `clients`, and `pods` returning
   the corresponding `*ApiGroup` types, constructed with an inert
   `BaseCredential` subclass that performs no authentication.
2. **Schema fidelity.** The generated `Run` model's required-field set equals
   the `required` list of the `Run` schema read back out of the contract, so a
   contract change that is not regenerated fails the suite.
3. **Enum survival.** The contract's `RunState` enum still carries the expected
   terminal and non-terminal values, and `Run.state` exists — the generator
   currently emits enums as plain `str` fields, so the enum itself is asserted
   against the spec rather than against generated code.

The suite runs as `make test`, which is plain `unittest` discovery over
`source/testroots/testbase/tests` with `PYTHONPATH=source/packages`. The
testbase root (`source/testroots/testbase/__testroot__.py`) is in place for a
future testbase-driven tier; nothing runs through testbase today.
