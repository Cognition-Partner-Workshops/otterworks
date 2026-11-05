# Synthetic bank documents

- `documents.json`: six static, fictional Halvergate Bank statements and KYC records.
- `seed.py`: creates missing documents by owner and title in document-service, using
  a dedicated fixed owner and folder (separate from the pinned incident fixture).
- `test_seed.py`: deterministic digest, isolation, content safety and seeder tests.

From the repository root:

```sh
uv run industries/banking/incident-documents/seed.py --dry-run
uv run industries/banking/incident-documents/seed.py
uv run --with pytest --with pyyaml pytest industries/banking/incident-documents -q
uvx ruff check industries/banking/incident-documents
uvx ruff format --check industries/banking/incident-documents
```

`INCIDENT_BASE_URL` defaults to `http://localhost:8083`. `JWT_SECRET` uses the
same local default as `incident/incident.py`; set it to the target service's
secret when needed. Repeated runs skip existing titles without changing content.
