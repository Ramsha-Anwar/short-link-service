# Short Link Service

A small HTTP service that turns long URLs into short codes, redirects short codes back to the original URL, and counts how many times each short link was followed.

Built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, **Alembic** and **Pytest**.

## Features

- Create a short link from a long URL
- Follow a short link and be redirected to the original URL
- Count every follow, safely under concurrent requests
- Submitting the same URL twice returns the same short code
- Malformed URLs are rejected with `400` before anything is stored
- Unknown short codes return `404`

## Requirements

- Python 3.11 or newer
- PostgreSQL 14 or newer (developed against PostgreSQL 18)

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repository-url>
cd short-link-service

python -m venv .venv
```

Activate it:

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create the databases

```bash
psql -U postgres -c "CREATE DATABASE shortlinks;"
psql -U postgres -c "CREATE DATABASE shortlinks_test;"
```

The second database is used only by the test suite.

### 4. Configure the environment

Copy the example file and fill in your own credentials:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

`.env` needs two variables:

```text
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/shortlinks
TEST_DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/shortlinks_test
```

The URL format is `dialect+driver://user:password@host:port/database`. If your password contains characters such as `@`, `/`, `:`, `#` or `?`, URL-encode them (`%40`, `%2F`, `%3A`, `%23`, `%3F`).

`.env` is listed in `.gitignore` and must never be committed.

### 5. Create the schema

```bash
alembic upgrade head
```

### 6. Run the service

```bash
uvicorn app.main:app --reload
```

The API is now at `http://127.0.0.1:8000`, and interactive documentation is at `http://127.0.0.1:8000/docs`.

## API

### `POST /links`

Create a short link.

Request:

```json
{ "url": "https://example.com" }
```

Response `200`:

```json
{ "code": "aB3xY9", "url": "https://example.com/" }
```

- The URL is normalized by Pydantic (`https://example.com` becomes `https://example.com/`).
- If the URL was already shortened, the existing code is returned and no new row is created.
- Invalid input returns `400` (see [Validation](#validation)).

### `GET /links/{code}`

Redirect to the original URL and count the follow.

- `302 Found` with a `Location` header pointing at the original URL.
- `404 Not Found` with `{"detail": "Short link not found"}` for an unknown code.

### `GET /links/{code}/stats`

Return information about a link **without** counting a follow.

Response `200`:

```json
{ "code": "aB3xY9", "url": "https://example.com/", "clicks": 3 }
```

- `404 Not Found` for an unknown code.

### Example session

```bash
# Create
curl -X POST http://127.0.0.1:8000/links \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Follow (shows the 302 and Location header)
curl -i http://127.0.0.1:8000/links/aB3xY9

# Stats
curl http://127.0.0.1:8000/links/aB3xY9/stats
```

> **Note:** Swagger UI's "Try it out" cannot display the redirect. It follows the `302` with `fetch`, and the browser blocks the cross-origin request to the destination site, so it reports "Failed to fetch". Test redirects in a browser tab or with `curl -i`.

## Validation

Malformed input is rejected with **`400 Bad Request`** before anything is stored. The error body names the offending field and where it was found:

```json
{
  "detail": [
    {
      "field": "url",
      "location": "body",
      "message": "Input should be a valid URL, relative URL without a base"
    }
  ]
}
```

Validation is performed by Pydantic (`HttpUrl`) at the API boundary, so the endpoint code never runs for invalid input. FastAPI returns `422` for validation errors by default; a custom exception handler converts these to `400`.

## Design decisions

### Why `302` and not `301`

A `301` is a *permanent* redirect and browsers cache it. After the first visit, a browser can send later visits straight to the destination without contacting this service, so those visits would never be counted. A `302` is a *temporary* redirect that browsers do not cache the same way, so every follow passes through the service and the click count stays accurate. Because counting follows is a core requirement, `302` is the right choice.

### Same URL returns the same code

`POST /links` first looks the URL up and returns the existing code if there is one. The `original_url` column also has a **unique constraint**, so the database enforces the rule even if two identical requests arrive at the same moment: the request that loses the race catches the integrity error and returns the winner's code.

### Short-code generation and collisions

Codes are six characters from `a-z`, `A-Z`, `0-9` (62^6, about 56 billion combinations), generated with Python's `secrets` module. The `code` column has a unique constraint. On insert, a collision raises an integrity error; the service rolls back and retries with a new code (up to five attempts). Letting the database decide, rather than checking first and inserting afterwards, makes this safe under concurrent requests.

### Atomic click counting

Following a link runs one statement:

```sql
UPDATE links SET clicks = clicks + 1 WHERE code = :code RETURNING original_url;
```

The increment happens inside the database, so simultaneous follows cannot overwrite each other's counts. If no row matches, the code is unknown and the service returns `404`.

### Separate stats endpoint

A redirect response cannot carry the count, and inspecting a link should not count as following it. `GET /links/{code}/stats` is read-only.

## Data model

Table `links`, managed by Alembic:

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer | Primary key |
| `code` | string(12) | Unique, indexed |
| `original_url` | text | Unique |
| `clicks` | integer | Defaults to 0 |
| `created_at` | timestamp with time zone | Set by the database on insert |

### Migrations

```bash
alembic upgrade head                                   # apply migrations
alembic revision --autogenerate -m "describe change"   # create a new migration
```

Always read a generated migration before applying it.

## Tests

The suite runs against a separate PostgreSQL database so it never touches real data.

```bash
pytest -v
```

It covers:

- Create returns a six-character code and the normalized URL
- The same URL twice returns the same code and stores one row
- Different URLs get different codes
- Malformed URL, empty body and wrong type return `400` and store nothing
- Following a code returns `302` with the correct `Location`
- Each follow increments the click count; calling stats does not
- Unknown codes return `404` on both endpoints
- A code collision generates another code and does not overwrite the existing link

`tests/conftest.py` refuses to run unless `TEST_DATABASE_URL` is set, differs from `DATABASE_URL`, and names a database ending in `_test`. Before each test the `links` table is emptied, and the app's database dependency is replaced with one that points at the test database.

## Project structure

```text
short-link-service/
├── app/
│   ├── main.py        # routes and validation error handler
│   ├── schemas.py     # Pydantic request model
│   ├── database.py    # engine, session factory, get_db dependency
│   └── models.py      # Link table model
├── alembic/           # migrations
├── alembic.ini
├── tests/
│   ├── conftest.py    # test database and fixtures
│   └── test_links.py  # test suite
├── pytest.ini
├── requirements.txt
├── .env.example       # template for required environment variables
└── README.md
```

## Known limitations

- There is no rate limiting or authentication; any caller can create links.
- Each distinct URL gets exactly one code, so two callers cannot have separate links (and separate counts) for the same URL.
- Only `http` and `https` URLs are accepted by validation, but destinations are not checked for reachability or safety.