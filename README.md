# VCF Variants API

A FastAPI service that exposes the first five fields of VCF records (`CHROM`, `POS`, `ID`,
`REF`, `ALT`) and supports pagination, ID filtering, JSON/XML representations, conditional
GET requests, and authenticated mutations.

The submitted source intentionally does **not** contain the supplied VCF dataset.

## Features

- `GET /variants` with `page`, `page_size`, and optional `id` filtering
- navigation links and total/page metadata
- `application/json` and `application/xml` content negotiation
- `406 Not Acceptable` for unsupported response types
- ETag and `If-None-Match`; a matching request returns `304` before variant records are read
- secret-protected `POST`, `PUT`, and `DELETE`
- validation of client-supplied chromosomes, positions, IDs, and alleles
- plain `.vcf` and gzip-compressed `.vcf.gz` inputs
- atomic file mutations guarded by an inter-process lock
- functional and unit tests

## Architecture

The project uses a small feature-oriented layered architecture:

```text
src/vcf_api/
├── core/                 # environment configuration and secret comparison
├── http/                 # negotiation, ETag, errors, logging, middleware, XML
├── variants/
│   ├── api.py            # thin HTTP endpoints
│   ├── dependencies.py   # auth and request dependency composition
│   ├── context.py        # HTTP request context and representation identity
│   ├── exceptions.py     # feature error contracts
│   ├── models.py         # internal record and query/result models
│   ├── schemas.py        # HTTP input and response validation
│   ├── repository.py     # storage interface (Protocol)
│   ├── responses.py      # pagination links and JSON/XML responses
│   ├── service.py        # storage-independent use cases
│   └── vcf_repository.py # streaming VCF implementation and atomic mutations
└── main.py               # composition root and FastAPI application factory
```

The route layer does not parse or modify files. `VariantService` owns use-case behavior, while
`VariantRepository` is the boundary to storage. This keeps HTTP tests focused and allows the
file implementation to be replaced by an indexed or database-backed repository if usage grows.

Read models and write models are deliberately separate. Existing VCF files can validly contain
values such as `ID=.` or multi-base alleles, so GET returns those faithfully. The stricter rules
from the assignment are applied only to records supplied through POST and PUT.

### File consistency

Mutations stream the source into a temporary file in the same directory and then use an atomic
`os.replace`. A file lock serializes concurrent writers. Readers therefore see either the old
complete file or the new complete file, never a partially rewritten file. Additional VCF columns
are preserved by PUT. POST reads the header and fills every remaining column, including
FORMAT and sample columns, with `.` values. PUT preserves existing annotations and genotypes
as supplied; it does not recalculate them after the first five fields change.

ETags contain the request parameters, full URL used in navigation links, negotiated representation,
and file revision (`inode`, size, and nanosecond modification time). Matching conditional requests
return `304` after a metadata check. For `200` responses, the revision comes from the opened file
descriptor, so a concurrent atomic replacement cannot mix one version’s data with another ETag.
This assumes all writers replace the file atomically; external in-place editing is unsupported.

## Run locally

Python 3.11 or newer is required.

First, create the local data directory and put the supplied VCF file there. The file was omitted
from Git on purpose because it is input data for the application rather than source code:

```bash
mkdir -p data
cp /absolute/path/to/2140d2ff-7af2-4b53-949c-d0156f5a5ef3.gz data/input.vcf.gz
```

You may use a different filename or location; in that case, set `VCF_FILE` to its absolute path.
The application accepts both plain `.vcf` and compressed `.vcf.gz` files.

Then install and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

cp .env.example .env
export API_SECRET='replace-with-a-secret'
uvicorn vcf_api.main:app --reload --no-access-log
```

Because the default path is `data/input.vcf.gz`, `VCF_FILE` does not need to be exported when the
file was copied exactly as shown above. To verify that the server is running:

```bash
curl http://127.0.0.1:8000/health
curl 'http://127.0.0.1:8000/variants?page=1&page_size=10'
```

Run these commands from the project root. In `.env`, `VCF_FILE=data/input.vcf.gz` is relative
to that working directory. `/data/input.vcf.gz` is the Docker path, not the local macOS path.
If port 8000 is already occupied, stop the previous server with Ctrl+C or start on another port:

```bash
uvicorn vcf_api.main:app --reload --no-access-log --port 8001
```

OpenAPI documentation is available at <http://127.0.0.1:8000/docs>.

Configuration:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VCF_FILE` | `data/input.vcf.gz` | Path to a `.vcf` or `.vcf.gz` file |
| `API_SECRET` | `change-me` | Exact value required in `Authorization` for mutations |
| `DEFAULT_PAGE_SIZE` | `50` | Page size when the query parameter is omitted |
| `MAX_PAGE_SIZE` | `200` | Maximum accepted page size |
| `LOG_LEVEL` | `INFO` | Application log level |

The process needs write permission for both the VCF file and its parent directory when mutation
endpoints are used.

## Errors and request logs

Exceptions are translated globally, so endpoint functions do not contain repetitive
`try/except` blocks. Every error uses the same response structure and includes the request ID:

```json
{
  "error": {
    "code": "variant_not_found",
    "message": "No variants found for id 'rs404'",
    "request_id": "f6702d64312048cc870012f76032c216"
  }
}
```

The same ID is returned in the `X-Request-ID` response header. Unexpected failures return a safe
generic message. Error logs retain exception types and stack locations, without exception
messages, source snippets, or local variable values.

Application logs are structured JSON and contain the timestamp, operation, request ID, client IP,
user-agent, HTTP method, path, status, duration, target variant ID when present, and error
reason. Only `page`, `page_size`, and `id` query values are logged, with length limits. Successful
mutation requests are marked as authenticated. A shared secret identifies authorized access,
not an individual person. Authorization values and request bodies are not written to application
logs. Route names supply operation names automatically. Use `--no-access-log` as shown above
to avoid duplicate Uvicorn access logs, which otherwise contain unfiltered query strings.

```json
{"timestamp":"2026-09-02T14:00:00+00:00","level":"INFO","logger":"vcf_api.access","message":"HTTP request completed","event":"http_request","operation":"update_variant","request_id":"f6702d64312048cc870012f76032c216","client_ip":"127.0.0.1","user_agent":"curl/8.7.1","method":"PUT","path":"/variants","query":"id=rs123","status_code":200,"duration_ms":34.8,"target_id":"rs123","authenticated":true}
```

## Run with Docker

```bash
mkdir -p data
cp /absolute/path/to/source.vcf.gz data/input.vcf.gz
API_SECRET='replace-with-a-secret' docker compose up --build
```

To use another host directory containing a file named `input.vcf.gz`, set
`VCF_DIRECTORY=/absolute/path/to/directory`. The directory is mounted rather than only the file
because atomic mutations must create a temporary sibling and replace the original. When using the
non-root image, ensure UID `10001` can write to that directory.

## API examples

Default JSON response:

```bash
curl 'http://127.0.0.1:8000/variants?page=1&page_size=25'
```

XML response:

```bash
curl -H 'Accept: application/xml' \
  'http://127.0.0.1:8000/variants?id=rs62635284'
```

Conditional request:

```bash
curl -i 'http://127.0.0.1:8000/variants?page=1&page_size=25'
curl -i -H 'If-None-Match: "etag-from-the-first-response"' \
  'http://127.0.0.1:8000/variants?page=1&page_size=25'
```

Create a record:

```bash
curl -i -X POST \
  -H 'Authorization: replace-with-a-secret' \
  -H 'Content-Type: application/json' \
  -d '{"CHROM":"chr1","POS":1000,"ID":"rs123","REF":"G","ALT":"A"}' \
  http://127.0.0.1:8000/variants
```

Update every record currently identified by `rs123`:

```bash
curl -i -X PUT \
  -H 'Authorization: replace-with-a-secret' \
  -H 'Content-Type: application/json' \
  -d '{"CHROM":"chr2","POS":2000,"ID":"rs456","REF":"A","ALT":"T"}' \
  'http://127.0.0.1:8000/variants?id=rs123'
```

Delete every matching record:

```bash
curl -i -X DELETE \
  -H 'Authorization: replace-with-a-secret' \
  'http://127.0.0.1:8000/variants?id=rs456'
```

## Tests and quality checks

```bash
pytest --cov=vcf_api --cov-report=term-missing
ruff check .
ruff format --check .
```

## Trade-offs

The repository streams the VCF rather than loading it into memory, so memory consumption stays
bounded even for large inputs. Computing an exact `total` and filtering by ID still require a
full scan, and every mutation rewrites the file. Gzip output uses ordinary gzip, not BGZF;
existing Tabix indexes are not maintained.  That is appropriate for a file-manipulation exercise
and a 202k-record input. For high request or mutation volume, the repository boundary makes the
next step explicit: import the data into an indexed database (or maintain a Tabix-compatible
index) while retaining the API and service layers.
