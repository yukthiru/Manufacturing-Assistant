# Manufacturing Manual Assistant (Phase 1)

Django + Django REST Framework + PostgreSQL/MySQL, Bootstrap/vanilla-JS frontend, RAG over equipment-manual PDFs
with page-level source references and role-based access (Administrator / Engineer / Supervisor).

## Setup
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then edit DB + LLM settings
createdb manualdb                                      # PostgreSQL (or create a MySQL schema, DB_ENGINE=mysql)
python manage.py migrate
python manage.py seed_demo --samples                   # roles, demo users, sample PDFs in ./sample_manuals
python manage.py runserver                             # http://127.0.0.1:8000
```

### Demo credentials
| Role | Username | Password |
|---|---|---|
| Administrator | admin | Admin@123 |
| Engineer | engineer | Engineer@123 |
| Supervisor | supervisor | Supervisor@123 |

(`admin` is also the Django admin user at `/admin/`. Other users can be created there and put in a role Group.)

### Tests
```bash
python manage.py test            # uses your configured DB; add DB_ENGINE=sqlite for a quick run
```

## AI configuration
- Set `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `EMBEDDING_MODEL` for any OpenAI-compatible endpoint.
- With no key set, an offline fallback is used (hashed bag-of-words embeddings, extractive answer) so the app still runs.
- **If you change the embedding backend, delete and re-upload manuals** (stored vectors must come from the same model as queries).
- Tune `RAG_MIN_SCORE` (cosine threshold for "insufficient information"), `RAG_TOP_K`.

## Architecture
```
Browser (Bootstrap + JS) --session cookie + CSRF--> Django REST API
  /api/auth/*            login, logout, me
  /api/machines/         read: any role   | write: Administrator
  /api/manuals/          read: any role   | upload/edit/delete: Administrator (PDF validated, indexed on upload)
  /api/manuals/<id>/file PDF viewer (open at #page=N)
  /api/ask/              Engineer only: retrieve + generate + save Question
  /api/questions/        Engineer: own history | Supervisor/Administrator: all, ?unanswered=1 (read-only)
```
- **Roles**: Django Groups (created by migration signal). Enforced by DRF permission classes in `core/permissions.py`; the UI only hides things.
- **Ingestion** (`core/rag.py`): PyMuPDF extracts text per page -> ~700-char chunks keeping `page_number` -> embeddings stored in `Chunk.embedding`.
- **Retrieval**: cosine similarity computed only over chunks where `machine == selected machine`, so other machines' passages can never be returned.
- **Generation**: the LLM may use only the retrieved excerpts and cites them; below `RAG_MIN_SCORE`, or if the model says `INSUFFICIENT_INFORMATION`, the answer is the fixed "not enough information" message and the question is flagged unanswered for Supervisors.
- **Persistence**: `Machine`, `Manual`, `Chunk`, `Question` (answer, sources snapshot, answered flag, user, timestamp).

## Demo script (7 minutes)
1. Admin: add machines "Hydraulic Press / HP-200" and "CNC Lathe / CL-50", upload the 3 PDFs with revisions.
2. Engineer: select HP-200, ask "How often do I replace the hydraulic oil filter?" -> answer + passage, manual, revision, page; click *Open PDF at page*.
3. Engineer: still on HP-200, ask "How often should the spindle bearings be greased?" (lathe-only) -> "not enough information".
4. Engineer: ask something unrelated -> "not enough information".
5. Engineer tries uploading: no upload UI, and `POST /api/manuals/` returns 403 (see test).
6. Supervisor: history view, filter unanswered. Reload the page to show persistence.
7. http://127.0.0.1:8000/
