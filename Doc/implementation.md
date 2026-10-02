# SBI MF FAQ Assistant — Phase-wise Implementation Guide

**Companions:** [PRD.md](./PRD.md) · [architecture.md](./architecture.md) · **Milestone:** 04
**Purpose:** an operational, phase-by-phase build guide you (or Cursor) can execute top-to-bottom, where each phase is independently verifiable and gated before the next one starts.

---

## 0. How to use this guide

### 0.1 The workflow

```
Plan (this doc)  →  build one phase  →  verify against its acceptance criteria  →  review  →  next phase
```

For each phase below you get: **objective → dependencies → files → numbered tasks → acceptance criteria (executable) → pitfalls → a copy-pasteable Cursor kickoff prompt** (§13 has them collected; each phase also references its own).

### 0.2 Non-negotiable working rules

| Rule | Why |
|---|---|
| **Never advance a phase with a failing acceptance criterion.** | These criteria *are* the PRD launch checklist; a skipped check reappears as a compliance bug |
| **Phase 2 has a human gate.** Do not embed chunks until `artifacts/chunks.txt` has been read | Explicitly mandated by the brief (architecture §4.7/§5 gate) — bad chunking silently destroys retrieval |
| **One phase per Cursor session, ending with a commit** | Keeps diffs reviewable and makes a bad chunking/guard change cheap to revert |
| **Never edit `artifacts/chunks.txt` by hand** | It is generated evidence; a hand edit invalidates the audit trail |
| **Secrets only in `.env`**; redaction filter on all logging from Phase 0 | Non-negotiable launch criterion |
| **Ground every implementation decision in `architecture.md`** — do not redesign mid-build | Re-architecture belongs in `architecture.md` §14 as a new decision (AR-*), not in ad-hoc code |

### 0.3 Phase map

| Phase | PRD week | Deliverable | Depends on | Gate to advance |
|---|---|---|---|---|
| **0** Setup & scaffolding | W0 | Runnable repo, pinned deps, `Settings` | — | `pytest` runs, `import src.config` works |
| **1** Corpus load & parse | W1 | `data/raw/`, `data/raw_text/`, parse report | 0 | Every tier-1/2/3 doc parses non-empty |
| **2** Chunking **[HUMAN GATE]** | W1 | `artifacts/chunks.txt`, `chunk_report.md` | 1 | Zero chunks > 250 tokens; report reviewed |
| **3** Embed & store | W2 | `chroma_db/` populated, model guard | 2 | 10/10 probe queries return correct-scheme chunks |
| **4** Retrieval + guards | W2–W3 | Deterministic query layer, no LLM yet | 3 | Unit tests green: PII 100%, intent matrix 100% |
| **5** Generation & validation | W3 | Grounded answers, fail-closed validators | 4 | Citation coverage 100%, brevity 100%, groundedness ≥ 90% |
| **6** UI | W4 | Streamlit chat per PRD §6.4 | 5 | All 6 UI states render; disclaimer visible |
| **7** Eval harness & QA gates | W4–W5 | `run_eval.py`, latency, link check | 6 | 20/20 adversarial refusals; P95 < 8 s |
| **8** Experiments | W5 | Chunking/retrieval evidence | 7 | E1/E2 decision recorded in `chunk_report.md` + README |
| **9** Deliverables & demo | W5 | README, sample Q&A, sources CSV, demo video | 8 | PRD §12 checklist 6/6 |

```
0 ──► 1 ──► 2 ──► 3 ──► 4 ──► 5 ──► 6 ──► 7 ──► 8 ──► 9
            ▲       │       │
        HUMAN GATE └───────┘  phases 4–6 may be built in parallel once 3 is green
```

Phases 4, 5 and 6 can partly overlap (guards and retrieval are LLM-independent), but **Phase 7 depends on all three** and Phase 8 depends on 7.

---

## 1. Global conventions

### 1.1 Runtime & environment

| Item | Value |
|---|---|
| Python | 3.11+ (3.13 verified in this environment) |
| Shell shown | Windows PowerShell (paths use `\`) |
| Package layout | `src/` as a plain package (no install step) — run from repo root |
| Secrets | `.env` (gitignored) — `GROQ_API_KEY` |
| Logs | `logs/` (gitignored), structured JSON lines |
| Test runner | `pytest` |

### 1.2 Code style
- Type hints on all public functions; dataclasses for `Settings`, `Block`, `Chunk`, `Response`, `Citation`, `DocProfile`.
- `logger = logging.getLogger(__name__)` per module; **never** `print` in `src/`.
- No secrets, raw query text or PII in logs (architecture §11).
- Public functions return data, never print it; CLI behaviour lives in `scripts/`.
- Every module starts with a one-line docstring stating its role in the pipeline (e.g. `"""Stage 2 of ingestion: structured chunking."""`) — orientation over commentary; no inline commentary.

### 1.3 Commands you will reuse

```powershell
# run the unit suite
pytest -q

# ingestion (once, then only when sources change)
python scripts\run_ingest.py
python scripts\run_ingest.py --report
python scripts\run_ingest.py --only sbimf_ter_page

# evaluation
python scripts\run_eval.py
python scripts\run_eval.py --adversarial
python scripts\run_eval.py --latency --runs 50
python scripts\run_eval.py --diff          # regression gate vs Doc/sample_qa.md

# link liveness
python scripts\check_links.py

# UI
streamlit run src\app.py
```

---

## 2. Phase 0 — Setup & scaffolding

**Objective:** a runnable, importable repo with pinned dependencies and a single validated config object.

**Depends on:** —  | **Files:** `.gitignore`, `.env.example`, `requirements.txt`, `pytest.ini`, `src/__init__.py`, `src/config.py`, `src/logging_utils.py`, `tests/test_config.py`

### Tasks
1. `pip install -r requirements.txt` with pins (architecture §12): `sentence-transformers`, `chromadb`, `groq`, `pdfplumber`, `pypdf`, `beautifulsoup4`, `lxml`, `streamlit`, `python-dotenv`, `requests`, `pytest`.
2. Write `.gitignore` covering exactly: `.env`, `chroma_db/`, `models/`, `data/raw/`, `data/raw_text/`, `data/cache/`, `logs/`, `__pycache__/`, `.pytest_cache/`, `.venv/`.
3. `.env.example` with `GROQ_API_KEY=` and `GROQ_MODEL=llama-3.3-70b-versatile` (no values).
4. `src/config.py` — implement the `Settings` frozen dataclass **verbatim from architecture §6**, plus: `load_dotenv()` once, `api_key` property raising `ConfigurationError` when unset, `ensure_dirs()` creating `data/`, `artifacts/`, `logs/`, and `from_env()` classmethod. Add the constants `TOKENIZER_TOKEN_LIMIT = 250`, `TOP_K = 5`, `SIM_FLOOR = 0.35`, `CHUNK_TARGET_CHARS = 900`, `CHUNK_OVERLAP_CHARS = 120`, `MAX_QUERY_CHARS = 500`, `COLLECTION = "mf_faq_v1"`.
5. `src/logging_utils.py` — `setup_logging()` writing JSON lines to `logs/app.log`, with a redaction filter dropping any string matching `gsk_[A-Za-z0-9]+`, `sk-[A-Za-z0-9]{20,}`, and any PAN/10-digit-run pattern before the record is written.
6. Create the `src/ingest/`, `src/query/`, `scripts/`, `tests/` packages with empty `__init__.py`; stub `scripts/run_ingest.py`, `scripts/run_eval.py`, `scripts/check_links.py` so the entry points exist.
7. `tests/test_config.py` — assert defaults, assert `ConfigurationError` on missing key, assert `ensure_dirs()` creates paths.

### Acceptance criteria
```powershell
pytest -q                          # all green
python -c "from src.config import Settings; print(Settings().top_k)"   # → 5
git check-ignore .env              # → .env
python scripts\run_ingest.py --help   # exits 0
```

### Pitfalls
- Do **not** add a `pyproject.toml`/install step — this is a prototype run from the repo root.
- `Settings` must be frozen; Phase 1–8 code reads values, never mutates them.
- Pre-download the embedding model in this phase (`SentenceTransformer(MODEL_ID)` once, ~90 MB) so Phase 3 is not waiting on a download mid-verification.

---

## 3. Phase 1 — Corpus load & parse (Stage: LOAD)

**Objective:** every tier-1/2/3 document in `config/sources.csv` is downloaded, parsed into `Block`s, and saved as text — with a report showing anything that failed or looks JS-rendered.

**Depends on:** 0  | **Files:** `config/sources.csv`, `src/ingest/manifest.py`, `src/ingest/fetch.py`, `src/ingest/parse_pdf.py`, `src/ingest/parse_html.py`, `src/ingest/profiles.py`, `tests/test_manifest.py`, `tests/test_fetch.py`

### Tasks
1. **Build `config/sources.csv`** — header exactly:
   `doc_id,title,doc_type,scheme,scheme_category,source_url,as_of_date,tier,ingest,local_filename,fetched_at,notes`
   Populate all **24 brief URLs** using the tiering table in **architecture §4.1** (tier 1 = the 5 published sources; tier 4 = linked-only; tier 5 = the excluded mirror). Set `ingest=yes` for tiers 1–3, `no` for tiers 4–5. `as_of_date` in `YYYY-MM-DD`; dates inferable from titles (e.g. `2026-06-30`, `2026-01-31`, `2025-08-31`, `2024-07-31`, `2025-05-30`).
2. `manifest.py` — `load_manifest()` returns `list[Doc]`; validation raises on: duplicate `doc_id`, non-`https` URL, `tier` outside 1–5, malformed `as_of_date`, empty `doc_type`. Expose `allowed_hosts(docs)` (hosts of ingest=yes rows) and `doc_urls(doc_id)`.
3. `fetch.py` — `download(doc)` with: host-allowlist rejection (never fetch a host not in the manifest — this is what structurally excludes the tier-5 mirror), `User-Agent` header, 25 MB size cap, retries `3×` with backoff `1s/4s/16s`, sha256 of the file, cache skip against `data/cache/hashes.json`, and `local_filename` = `data/raw/{doc_id}{ext}`. Return `FetchResult(path, sha256, changed: bool)`.
4. `parse_pdf.py` — `parse_pdf(path, doc) -> list[Block]` using `pdfplumber`, falling back to `pypdf` when a page yields no blocks. Emit `Block` with `kind ∈ {heading, para, table_row, list_item, page_header, page_footer}`, `level`, `page_no`, `table_id`, `row_span`. Drop page headers/footers, de-hyphenate, collapse whitespace. **Raise `ParseError` if the whole document yields zero blocks.**
5. `parse_html.py` — `parse_html(path, doc) -> list[Block]`: BeautifulSoup + `lxml`, remove `script/style/nav/header/footer/aside` and cookie/popup classes, prefer `main`/`article`, split on `h1–h4`, lists → `list_item`. Keep `<form>` but drop its controls (`input/button/select/option/textarea/label`). **JS-rendered guard:** stripped text < 500 chars while the raw HTML has a table shell **or** contains a JS placeholder (`Loading...`, `No Records Found`) ⇒ set `report_flag = "POSSIBLY_JS_RENDERED"` and still return the blocks (do not silently produce an empty document).
6. `profiles.py` — the `DocProfile` dataclass and the full `DOC_TYPE → profile` mapping table from **architecture §4.3**.
7. Wire `scripts/run_ingest.py --report` to run only load+parse and print a per-document table: doc_id, blocks, chars, pages, flag, error.

### Acceptance criteria
```powershell
python scripts\run_ingest.py --report
python -m pytest tests/test_manifest.py tests/test_fetch.py tests/test_parse_html.py tests/test_coverage.py
```
- Every **ingested** tier-1/2/3 document shows `blocks > 0` and `error = -`. **Current result: 15 documents, 0 failures, 0 empty.**
- `data/raw_text/{doc_id}.txt` exists for each of the 15 and is non-empty; the directory holds **exactly** the ingested set (a demoted row is pruned).
- `artifacts/parse_report.md` lists every document with blocks/chars/pages/parser/flag plus a **mandatory-topic coverage** section.
- Each of the seven mandatory topics is supported by **≥2** documents (currently 7–10 each): `expense_ratio` 8, `exit_load` 10, `minimum_sip` 8, `elss_lockin` 9, `riskometer` 7, `benchmark` 8, `statement_download` 10.
- `allowed_hosts()` returns only manifest hosts, and the tier-5 mirror host is absent.
- `tests/test_fetch.py` proves a non-manifest host is refused, with no HTTP request issued.
- **PRD open question #9 is answered by evidence:** the TER page *is* JS-rendered (14 chrome blocks / ~314 chars of text, no scheme rows), so it is `ingest=no`. Expense-ratio coverage comes from the factsheet/SID TER column rows plus `sbimf_ter_notice_2025_05_30` and `sebi_mf_faq_2024_09`.

### Pitfalls
- Column bleed in factsheets: if `pdfplumber` merges two scheme columns into one block, fix it here — **do not** try to fix it in the chunker. Architecture §14 question 2.
- Downloaded PDFs may be HTML error pages with a `.pdf` extension; validate the magic bytes/content type and fail loudly.
- `pdfplumber` is slow on 100+ page SIDs — acceptable offline, but log per-document duration so a hang is visible.
- **Read at least 3 parsed `raw_text` files end-to-end before starting Phase 2.** This is the mandated data inspection.

### Phase 1 outcome — deviations from the plan above
Driven by what the real corpus actually returned. `config/sources.csv` remains the source of truth and `Doc/architecture.md` §4.1–§4.2 records the same findings.

| Planned | Shipped | Why |
|---|---|---|
| `ingest=yes` for all tiers 1–3 (20 docs) | **15 docs** `ingest=yes`, 9 linked-only | `sbimf_ter_page`, `sbimf_disclosure_hub`, `sbimf_factsheets_hub` are JS-rendered; both `camsonline.com` statement pages are an Angular SPA returning an empty `app-root` |
| Remove `<form>` from HTML | Remove only form **controls** | The ELSS campaign page's copy lives inside a `<form>`; dropping it deleted the ELSS lock-in answer |
| JS guard = thin text + table shell | Also flag JS placeholders (`Loading...`, `No Records Found`) | The disclosure hub has no table, only `Loading...` |
| `extract_tables()` output trusted | Page-wide table artefacts rejected; x-coordinate column clustering added | Framed factsheet pages collapsed to one 5,000+ char block per page, destroying the TER/exit-load structure |
| — | `coverage.py` + `--report` coverage section | Makes "no mandatory topic depends on one document" an enforced gate, not a claim |
| — | Stale `raw_text` pruning | A demoted page must stop contributing text and coverage counts |

---

## 4. Phase 2 — Chunking **[HUMAN GATE]**

**Objective:** document-type-aware chunks, dumped for review, with a hard guarantee that nothing exceeds the tokenizer budget.

**Depends on:** 1  | **Files:** `src/ingest/chunk.py`, `src/ingest/dump.py`, `src/ingest/report.py`, `tests/test_chunker.py`

### Tasks
1. `chunk.py` — `split_document(doc, blocks) -> list[Chunk]`, implementing architecture §4.4 in order: **group** (per scheme section for factsheets, per heading for SID/KIM/guides, per table row for the TER page) → **sectionise** (prepend the breadcrumb `"{scheme} | {section_title}"`, linearise table rows to `Field: Value` lines per §4.6) → **window** prose sections (900/120, snap the cut to the last sentence boundary in the final 15% of the window) → **table safety** (never split mid-row; group whole rows when a table exceeds the budget) → **assert** → **emit**.
2. `chunk_id = f"{doc_id}__{scheme_slug}__{section_slug}__{seq:03d}"` with slugs from a fixed vocabulary. Ids must be **stable across re-runs** — `store.upsert` idempotency depends on it.
3. `assert_within_limit(text, tok, chunk_id)` — tokenise with `AutoTokenizer.from_pretrained(MODEL_ID)`, `add_special_tokens=True`; over `TOKENIZER_TOKEN_LIMIT` ⇒ re-split at the largest boundary under the cap and recurse; still over ⇒ **do not emit for embedding**, add to an `unsplittable` list returned to the report.
4. `dump.py` — write `artifacts/chunks.txt`: one block per chunk with `chunk_id`, `doc_id`, `source_url`, `doc_title`, `doc_type`, `scheme`, `scheme_category`, `section`, `page_no`, `as_of_date`, `char_len`, `token_len`, then the chunk text. Human-readable, no machine format.
5. `report.py` — write `artifacts/chunk_report.md`: per-document chunk count, min/median/max token length, count over limit (**must be 0**), the `unsplittable` list, every parse flag, and the chunking rationale actually applied.
6. `tests/test_chunker.py` — invariants: no chunk > 250 tokens; `chunk_id` unique; no table row split mid-row; every chunk has `scheme`, `source_url`, `as_of_date`; `chunk_id` stable when re-run on identical input; TER page yields one chunk per scheme row.
7. Add `--force` to `run_ingest.py`: without it, the pipeline **stops after `dump.py`** and prints *"review artifacts/chunks.txt, then re-run with --force"*.

### Acceptance criteria
```powershell
pytest -q tests/test_chunker.py
python scripts\run_ingest.py           # stops at the review gate
python scripts\run_ingest.py --report  # inspect the numbers
```
- `chunk_report.md` shows `over_limit: 0` and an empty `unsplittable` list.
- **Human gate:** read `artifacts/chunks.txt` and confirm, by hand, that (a) an expense-ratio chunk contains label+value together, (b) an ELSS lock-in chunk states the period, (c) a statement-guide chunk retains its numbered steps, (d) each scheme's chunks are labelled with the right scheme. Record the verdict in `chunk_report.md` under "Review verdict".
- Confirm the factsheet/SID TER rows produced **row-sized** chunks (`TER | 1.50 | 0.86 | …`) rather than one giant table dump. The standalone TER *page* is not ingested (JS-rendered); its content arrives via factsheet columns and `sbimf_ter_notice_2025_05_30`.

### Pitfalls
- A factsheet chunk that mixes two schemes is worse than a missing chunk — the `scheme` metadata must be per-chunk, not per-document.
- Chunks that begin mid-sentence degrade both embedding quality and the ≤3-sentence answer; the sentence snap matters more than the exact overlap number.
- Do not "fix" a 300-token chunk by truncating its text. Re-split or exclude it.
- If `median token_len` is far below 250 (e.g. < 120), the splitter is over-fragmenting — that is a recall problem, not a safety one; note it for Phase 8 (E1/E2).

---

## 5. Phase 3 — Embedding & vector store (Stages: EMBED + STORE)

**Objective:** a persisted ChromaDB collection built from the reviewed chunks, plus a model-drift guard and a retrieval smoke test.

**Depends on:** 2 (after the gate)  | **Files:** `src/ingest/embed.py`, `src/ingest/store.py`, `scripts/run_ingest.py` (completion), `tests/test_store.py`

### Tasks
1. `embed.py` — module-level singleton `get_encoder()` returning one `SentenceTransformer(MODEL_ID)`; `encode(texts) -> np.ndarray` with `batch_size=64`, `normalize_embeddings=True`, `convert_to_numpy=True`. Assert `shape[1] == 384` on first use. Never instantiate a second encoder anywhere in the codebase.
2. `store.py` — implement architecture §4.7: `PersistentClient(path=chroma_dir)`; `get_or_create_collection(name=COLLECTION, metadata={"hnsw:space": "cosine", "embed_model": MODEL_ID, "chunk_schema": 2})`; `coerce_metadata()` mapping `None → ""` and `page_no → 0`; `upsert_chunks(chunks, vectors)`; `delete_doc(doc_id)` via `where={"doc_id": doc_id}`; `query(vector, top_k, where)` returning `documents`, `metadatas`, `distances`; and `assert_model_match()` raising `CollectionModelMismatch` when the stored `embed_model` differs from `Settings.embedding_model`.
3. Pass `embeddings=` **explicitly** on every write and every query; never let Chroma install a default embedding function.
4. Finish `run_ingest.py`: `delete_doc()` for changed docs, `upsert_chunks()`, then print collection size + corpus version (newest `as_of_date`).
5. Wire `scripts/run_ingest.py --probe`: for each of the 4 schemes, run one probe question (`expense ratio of <scheme>`) and print the top-3 chunk ids with similarity — the Phase 3 acceptance signal.
6. `tests/test_store.py` — upsert idempotency (same ids twice ⇒ same count), `None`-free metadata, `delete_doc` removes only that document's chunks, and model-mismatch raises.

### Acceptance criteria
```powershell
python scripts\run_ingest.py --force     # completes load → chunk → embed → store
python scripts\run_ingest.py --probe
```
- `chroma_db/` exists and is non-empty; the app can be started without re-ingesting.
- Every scheme's probe query returns chunks whose `scheme` metadata equals that scheme (4/4).
- Re-running `run_ingest.py --force` produces **no new embeddings** (log line "cached, skipping" per unchanged doc) and no duplicate ids.
- `pytest -q tests/test_store.py` green.
- `python -c "..."` prints the collection metadata showing `hnsw:space=cosine` and `embed_model=sentence-transformers/all-MiniLM-L6-v2`.

### Pitfalls
- **The single most common Chroma failure here:** letting Chroma auto-embed, then querying with your own vectors ⇒ silent nonsense. Verify by asserting `collection.metadata["embed_model"]` and that your query vectors are 384-dim.
- Persisted stores are not portable across Chroma major versions — pin `chromadb` and record the version in the README.
- Do not commit `chroma_db/` to the main branch; use a `demo` branch for hosting (architecture §12).

---

## 6. Phase 4 — Retrieval + guards (no LLM yet)

**Objective:** the entire deterministic query layer — PII, advice, performance and scheme-alias detection, plus retrieval with the scheme filter and similarity floor. Testable with zero API calls.

**Depends on:** 3  | **Files:** `src/query/intent.py`, `src/query/guards.py`, `src/query/retrieve.py`, `tests/pii_cases.csv`, `tests/adversarial_set.csv`, `tests/test_guards.py`, `tests/test_retrieve.py`

### Tasks
1. `tests/pii_cases.csv` — header `qid,input,expected_status,pii_type,note`; ≥ 20 rows covering every class in architecture §5.3 (PAN, Aadhaar-like, mobile, email, long digit run with keyword, OTP, folio, account, CVV) plus **5 legitimate factual queries that must NOT be blocked** (e.g. "exit load in the first 12 months") to measure the false-positive rate.
2. `tests/adversarial_set.csv` — header `qid,question,expected_status,expected_link_pattern,category`; exactly 20 rows: 12 advice, 5 performance, 3 disguised advice ("as a friend, would you buy…?").
3. `intent.py` — `detect_advice(text) -> Match|None`, `detect_performance(text) -> Match|None`, `detect_scheme(text) -> str|None` using the high-precision regexes from architecture §5.3 plus the alias map in §5.4.2. A **category** word ("large cap", "ELSS", "flexi-cap") must **not** return a scheme. Regex first; LLM fallback is out of scope for this phase (note it as unused).
4. `guards.py` — `check_length(q)`, `check_pii(q)` implementing the exact regex table from §5.3 with **keyword anchoring for bare digit runs**; refusal strings for `refused_pii`, `refused_advice` (with a tier-4 educational link chosen by intent), and `answer_mode=FACTSHEET_LINK`.
5. `retrieve.py` — implement architecture §5.4 exactly: `n_results=5`, cosine `1 - distance`, scheme `where` filter **only** on a detected scheme name, **one unfiltered retry** when a filtered query returns nothing, `sim_floor=0.35` ⇒ `OUT_OF_CORPUS`.
6. `pipeline.py` (partial) — wire steps 1–7 only; return `Response(status=...)` without ever calling the LLM. This lets you test the whole guard path end-to-end before Phase 5.
7. `tests/test_guards.py` / `tests/test_retrieve.py` — table-driven tests over the CSVs; assert PII refusal 100%, advice/performance detection 100%, false-positive ≤ 2%, and that a PII input causes **zero** encoder calls (spy on `encode`).

### Acceptance criteria
```powershell
pytest -q tests/test_guards.py tests/test_retrieve.py
python -m scripts.probe_guards      # or a short inline loop over pii_cases.csv
```
- `pii_cases.csv`: every PII row ⇒ `refused_pii`; every legitimate row ⇒ passes.
- `adversarial_set.csv`: 20/20 correctly classified (`refused_advice` / `refused_pii` / factsheet-link mode).
- No outgoing network call occurs for any PII case (verified by the `encode` spy and by the absence of any LLM client in `pipeline.py` at this point).
- Out-of-corpus probe ("what is the NAV of SBI Bluechip today?") returns `out_of_corpus`.

### Pitfalls
- Over-blocking is a real failure mode: a bare `\b\d{9,18}\b` regex without a keyword anchor will kill legitimate questions about periods and slabs. Measure the false-positive rate, do not eyeball it.
- Order is structural: PII **before** embedding. If you refactor `pipeline.py` later, keep that ordering and keep the spy test that proves it.
- Scheme detection must not fire on "SBI Mutual Fund" or on category words; a false scheme filter silently returns zero chunks.

---

## 7. Phase 5 — Generation & output validation

**Objective:** grounded answers from Groq, with the fail-closed validators and the fresh, cited, ≤3-sentence response contract.

**Depends on:** 4  | **Files:** `src/query/prompt.py`, `src/query/llm.py`, `src/query/validate.py`, `src/query/pipeline.py` (steps 8–10), `tests/test_validate.py`, `tests/eval_set.csv`

### Tasks
1. `tests/eval_set.csv` — header `qid,question,expected_scheme,expected_url,mandatory_topic,expected_status`; **20 rows**: F01–F10 covering all seven mandatory topics across all four schemes (architecture §10.2), O01–O10 out-of-corpus with `expected_status=out_of_corpus`.
2. `prompt.py` — the system prompt **verbatim from architecture §5.5** (8 rules), `build_user_message(context, question)`, and `assemble_context(hits)` implementing the `<context>` block: de-dup by `chunk_id`, score order, max 5 chunks, truncate to the token budget while **never dropping the top-ranked chunk**, per-chunk breadcrumb + `Source:` line.
3. `llm.py` — `GroqClient.complete(messages)` with `model`, `temperature=0.0`, `max_tokens=320`, `timeout=20s`; retry on `429`/`5xx`/timeout with backoff (max 2); **no retry on 401**; raise `ConfigurationError` when the key is missing; never log the key.
4. `validate.py` — implement V1–V6 from architecture §5.6:
   - V1 citation present **and** in the manifest allowlist **and** in the retrieved context → else regenerate once, then `out_of_corpus`
   - V2 ≤3 sentences (abbreviation-safe split: `e.g.`, `i.e.`, `Rs.`)
   - V3 freshness line present with a date from the retrieved `as_of_date` set → else append programmatically
   - V4 no uncited numeric performance claim
   - V5 **re-run the intent matrix on the generated answer; on a match, discard the model output** and return the canned refusal
   - V6 stale-source warning (log only)
5. `pipeline.py` — complete steps 8–10 and assemble `Response` per architecture §5.1.
6. `tests/test_validate.py` — crafted bad answers for each validator: no citation, 5 sentences, missing/wrong freshness date, invented `1.25%`, advice inside the answer. Assert each path (regenerate → fallback → override).

### Acceptance criteria
```powershell
pytest -q tests/test_validate.py
python scripts\run_eval.py
```
- **Citation coverage 100%** over F01–F10 (every answer contains ≥1 manifest URL).
- **Brevity 100%**, **freshness 100%**.
- **Groundedness ≥ 90%** — at least 9 of 10 factual answers fully supported by retrieved chunks.
- **O01–O10 all `out_of_corpus`** — zero hallucinated answers (this is the number that matters most).
- Every F-row's answer is factually correct when its citation is opened by hand (spot-check all 10).

### Pitfalls
- `temperature=0.0` still permits format drift; V1/V2/V3 exist because of it. Do not delete validators because answers "look fine".
- V2's sentence splitter will mis-handle `Rs.` / `e.g.` and truncate good answers — test it explicitly.
- V5 is a safety net that should almost never fire. If it fires often, the prompt is weak; fix the prompt, keep the validator.
- Do not let the model "helpfully" add a fourth sentence of advice — that is exactly the V2+V5 case.

---

## 8. Phase 6 — UI

**Objective:** the tiny UI from PRD §6.4, rendering only `answer`, `citations`, `freshness`.

**Depends on:** 5  | **Files:** `src/app.py`

### Tasks
1. Streamlit app, single page, `st.chat_input`. On first render: welcome line, the 3 example questions (PRD §6.4), and the disclaimer **"Facts-only. No investment advice."**
2. Example questions as clickable buttons that prefill the input.
3. Render each turn: answer text, then citations as clickable links labelled with document title + page, then `Last updated from sources: <date>`, then the disclaimer line.
4. Implement all six states from architecture §2/§7: `idle`, `thinking` (`st.spinner`), `answered`, `refused_*`, `out_of_corpus`, `error`.
5. Display the corpus freshness in the footer (`Corpus as of <newest as_of_date>`) and keep `guard`/`retrieval`/`latency_ms` **out of the UI** (eval/debug only).
6. Show a `st.spinner` while answering; no streaming in v1.

### Acceptance criteria
```powershell
streamlit run src\app.py
```
- Every state above renders without an exception, using at least one question per state (factual, advice, PII, out-of-corpus, invalid key).
- No backend/debug information visible in the UI.
- Disclaimer present on first render and at the foot of every answer.

### Pitfalls
- Never call the pipeline from module scope — it would ingest/run at import.
- `st.session_state` for the chat history only; no persistence of user queries (architecture §11).
- Reject empty input client-side; the guard also handles it, but don't waste a round trip.

---

## 9. Phase 7 — Evaluation harness & QA gates

**Objective:** the objective QA evidence behind the PRD launch checklist.

**Depends on:** 4, 5, 6  | **Files:** `scripts/run_eval.py`, `scripts/check_links.py`, `artifacts/eval_report.json`

### Tasks
1. `run_eval.py` — modes: default (F+O rows), `--adversarial`, `--latency --runs N`, `--diff`. Metrics computed exactly as PRD §9: citation coverage, groundedness, recall@5, refusal accuracy (advice), refusal accuracy (PII), brevity compliance, freshness compliance, out-of-corpus honesty, P95 latency. Emit `artifacts/eval_report.json` **and** a short markdown summary.
2. `groundedness` implementation: an answer is grounded when every number/date in it appears in the retrieved context for that query; a judge-free string check, with the known limitation documented in the README (architecture §5.6).
3. `recall@5`: an eval row passes when a chunk whose `source_url` matches `expected_url` (and `scheme` matches `expected_scheme`, when specified) appears in the top 5.
4. `--diff`: compare current F01–F10 answers to `Doc/sample_qa.md`; non-empty diff ⇒ exit non-zero unless `--accept` is passed (which rewrites `sample_qa.md`).
5. `check_links.py` — HTTP 200 for every `ingest=yes` URL in the manifest, with a small delay between requests; print a pass/fail table. This is the PRD §8.2 "all corpus URLs return 200" criterion.
6. Latency harness: 50 sequential real questions, per-stage timings from `Response.latency_ms`, report P50/P95 total.

### Acceptance criteria
```powershell
python scripts\run_eval.py
python scripts\run_eval.py --adversarial
python scripts\run_eval.py --latency --runs 50
python scripts\check_links.py
pytest -q
```
| Metric | Threshold |
|---|---|
| Citation coverage | 100% |
| Groundedness | ≥ 90% |
| recall@5 | ≥ 90% |
| Advice refusal | 20/20 |
| PII refusal | 100% |
| Brevity / freshness compliance | 100% / 100% |
| Out-of-corpus honesty | 10/10 |
| P95 latency | < 8 s |
| Link liveness | 100% HTTP 200 |
| Unit suite | all green |

### Pitfalls
- A failing metric is a phase output, not a reason to loosen the metric. Fix the pipeline (usually Phase 2/3) or record an accepted limitation.
- `check_links.py` on AMC hosts may hit bot protection; report it rather than retrying aggressively.
- Do not seed `sample_qa.md` with idealised answers — it must contain **actual** assistant output, or the regression gate is worthless.

---

## 10. Phase 8 — Experiments

**Objective:** run PRD §10 E1–E8 and record the decisions (especially chunking, which the brief requires to be justified from data).

**Depends on:** 7  | **Files:** `scripts/run_experiment.py`, `artifacts/experiments/*.json`, `artifacts/chunk_report.md` (append "Experiment outcomes")

### Tasks
1. `run_experiment.py` — sweep a single knob, run the fixed eval set, write a JSON result: `--chunk-chars {600,900,1200}`, `--top-k {3,5,8}`, `--tau {0.20,0.30,0.40,0.50}`, `--temp {0.0,0.2}`, `--filter {on,off}`.
2. Run **E1/E2 (chunk size, strategy)** and **E5 (τ)** at minimum, plus E4 (filter) since it targets the highest-severity error.
3. For each experiment record: variants, metric deltas, decision, and the reasoning. Append to `chunk_report.md` under "Experiment outcomes" and mirror the decisions into the README's architecture section.
4. Re-run the full `run_eval.py` after the winning configuration is applied, so the final numbers in `sample_qa.md`/`eval_report.json` come from the shipped configuration.

### Acceptance criteria
- Every experiment has a written decision, not just numbers.
- The chunking strategy is justified **from the inspected corpus** (quotes the specific parse/chunk problems observed in Phase 1–2), satisfying the brief's "propose a strategy, say why it suits this data".
- Final `eval_report.json` was produced by the shipped configuration.

### Pitfalls
- Change one knob at a time; two simultaneous changes make every result ambiguous.
- Re-running ingestion after a chunking change invalidates `chroma_db/` — rebuild it and re-run the full eval, never compare metrics across store versions.

---

## 11. Phase 9 — Deliverables & demo

**Objective:** PRD §12 complete, in the `Doc/` folder.

**Depends on:** 8  | **Files:** `README.md`, `Doc/sample_qa.md`, `Doc/disclaimer.md`, `config/sources.csv` (exported list), demo recording

### Tasks
1. `README.md` — setup steps (Windows PowerShell, from Phase 1's verified commands), scope (AMC + the 4 schemes), architecture summary with the phase map, **known limits** (notably: groundedness is a string heuristic not semantic verification; one AMC only; manual refresh; English only), the PII/advice posture, and the final eval metrics.
2. `Doc/sample_qa.md` — 5–10 actual queries with the assistant's real answers, citations, and freshness lines (regenerate via `run_eval.py --accept`).
3. `Doc/disclaimer.md` — the exact UI disclaimer string(s): `Facts-only. No investment advice.`
4. Export the source list from `config/sources.csv` to a readable CSV/MD, **highlighting the 5 tier-1 sources** and listing tiers 2–5 with their roles.
5. Commit `artifacts/chunks.txt` and `artifacts/chunk_report.md` (audit evidence); keep `chroma_db/` off the main branch.
6. Record the ≤3-min demo video **or** deploy to Streamlit Cloud with the key as a secret (architecture §12). Demo script: one advice question → refusal, one PII question → refusal, two factual questions → cited answers, one out-of-corpus question → honest fallback.
7. Final pass over the PRD §8.2 launch checklist A/B/C, ticking every box with evidence.

### Acceptance criteria
- All six PRD §12 deliverables exist and are current.
- Clean-machine reproduction from `README.md` alone succeeds on a fresh clone.
- Demo video ≤ 3 minutes and shows a refusal, two cited answers and the disclaimer.

### Pitfalls
- The sample Q&A and README metrics drift if the configuration changes after Phase 8 — regenerate them last.
- Never show `GROQ_API_KEY`, `guard`/`latency` internals or the back-end in the video; the brief forbids back-end screenshots.
- Confirm the tier-5 mirror is absent from every artifact you ship.

---

## 12. Cross-phase reference

### 12.1 Definition of done (every phase)
- [ ] Acceptance criteria executed and passing, command output pasted into the phase's commit message
- [ ] `pytest -q` green
- [ ] New unit tests for every non-trivial branch added
- [ ] No secrets, no raw query text, no PII in code or logs
- [ ] `architecture.md` updated if a design fact changed (new `AR-*` decision or a resolved open question)
- [ ] Phase committed with a message referencing the PRD requirement it satisfies

### 12.2 Troubleshooting
| Symptom | Likely cause | Where to look |
|---|---|---|
| Retrieval returns nothing for a scheme | scheme filter fired wrongly, or `where` used a value not in metadata | `intent.detect_scheme`, metadata `scheme` values |
| All similarities look wrong | Chroma auto-embedded, or model changed without a rebuild | `collection.metadata["embed_model"]`, assert `embeddings=` passed |
| Chunks > 250 tokens in the report | splitter measured characters instead of tokens | `assert_within_limit` |
| Answers missing citations | `assemble_context` dropped the `Source:` line, or V1 regeneration exhausted | `prompt.py`, `validate.py` V1 |
| Answers exceeding 3 sentences | abbreviation split wrong (`Rs.`, `e.g.`) | `validate.py` V2 |
| Advice leak | prompt weakened or model temperature drift | `validate.py` V5 must override; re-check the prompt |
| TER page empty | JS-rendered HTML | **Confirmed in Phase 1** — page is `ingest=no`; fall back to Base TER notice + factsheet TER columns |
| CAMS statement pages empty | "How do I download X" answers missing | **Confirmed in Phase 1** — Angular SPA, `ingest=no`; covered by `sbimf_ways_to_invest` + `amfi_cas` (10 supporting documents) |
| Ingestion re-embeds every run | `hashes.json` not written or `--force` misused | `fetch.py` cache logic |
| P95 > 8 s | generation dominating | levers in architecture §8 (max_tokens → top_k → model) |

### 12.3 Risk register
| Risk | Impact | Mitigation |
|---|---|---|
| TER page not machine-readable | Expense-ratio topic unsupported | **Resolved:** 8 ingested documents carry TER/BER text; enforced by the `coverage.py` gate (≥2 documents per mandatory topic) |
| Factsheet column bleed corrupts chunks | Wrong number-to-label pairing | **Resolved in the parser** (Phase 1): page-wide table artefacts rejected, x-coordinate column clustering added; never fix in the chunker |
| Model/refusal drift after prompt edits | Compliance regression | `--diff` regression gate + 20-row adversarial set in CI |
| Tokenizer chunk cap discovered too late | Silent truncation of fee tables | Phase 2 gate blocks embedding until the report shows `over_limit: 0` |
| Hosting unavailable | Missing deliverable #1 | Demo video is the documented fallback |

---

## 13. Cursor kickoff prompts

One prompt per phase. Each states the files, the spec source, and the verification command — so a fresh Cursor session can build a phase without the whole conversation.

**Phase 0**
> Implement Phase 0 from `Doc/implementation.md` (§2) using `Doc/architecture.md` (§6) as the spec. Create `.gitignore`, `.env.example`, `requirements.txt` (pinned), `pytest.ini`, `src/config.py` (frozen `Settings` dataclass exactly as in architecture §6, `load_dotenv()`, `api_key` raising `ConfigurationError`, `ensure_dirs()`, `from_env()`), `src/logging_utils.py` (JSON-line logging to `logs/` with a redaction filter for Groq keys), empty package `__init__.py` files under `src/ingest`, `src/query`, `scripts`, and stub entry points for `run_ingest.py`, `run_eval.py`, `check_links.py`. Add `tests/test_config.py`. Verify with `pytest -q`. Do not implement any ingestion logic.

**Phase 1** — ✅ done; see "Phase 1 outcome" in §3 for the deviations forced by the real corpus
> Implement Phase 1 (LOAD) from `Doc/implementation.md` (§3) against `Doc/architecture.md` §4.1–§4.3. Build `config/sources.csv` with all 24 URLs from `Doc/ProblemStatement.txt`, tiered exactly per architecture §4.1 (tier 1 = the 5 published sources, tiers 4–5 `ingest=no`, tier 5 = the excluded mirror). Implement `manifest.py` (validation + host allowlist), `fetch.py` (allowlist-enforcing download, retries 1s/4s/16s, 25 MB cap, sha256 cache skip, `data/cache/hashes.json`), `parse_pdf.py` (pdfplumber → `Block`s with page_header/page_footer stripping; raise `ParseError` on an empty document; pypdf fallback), `parse_html.py` (BeautifulSoup boilerplate strip + `POSSIBLY_JS_RENDERED` flag), and `profiles.py` (the `DocProfile` table from §4.3). Wire `run_ingest.py --report` to print a per-document table. Verify with `pytest -q tests/test_manifest.py tests/test_fetch.py` and `python scripts/run_ingest.py --report`; every ingested tier 1–3 document must report blocks > 0.

**Phase 2**
> Implement Phase 2 (CHUNK) from `Doc/implementation.md` (§4) against `Doc/architecture.md` §4.4–§4.7. Implement `chunk.py`: group by scheme section (factsheets) / heading (SID, KIM, guides) / table row (factsheet TER rows), prepend the breadcrumb `"{scheme} | {section_title}"`, linearise table rows to `Field: Value` lines, window prose at 900 chars with 120 overlap snapping the cut to a sentence boundary in the final 15%, never split a table row mid-way, then assert the chunk is within `TOKENIZER_TOKEN_LIMIT` (250) using the MiniLM tokenizer, re-splitting when over and excluding (listing in the report) when impossible. Emit stable ids `{doc_id}__{scheme_slug}__{section_slug}__{seq:03d}`. Implement `dump.py` (`artifacts/chunks.txt` with full metadata per chunk) and `report.py` (`artifacts/chunk_report.md` with per-document counts, min/median/max token length, `over_limit` that must be 0, and the `unsplittable` list). Make `run_ingest.py` STOP after dumping unless `--force` is passed. Add `tests/test_chunker.py` covering: no chunk over 250 tokens, unique and stable chunk ids, no mid-row table splits, every chunk carrying scheme/source_url/as_of_date, one chunk per TER row recovered from the factsheet column extraction.

**Phase 3**
> Implement Phase 3 (EMBED + STORE) from `Doc/implementation.md` (§5) against `Doc/architecture.md` §4.7. Implement `embed.py` with a single module-level `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` singleton, `encode()` with batch_size 64 and `normalize_embeddings=True`, asserting 384 dims. Implement `store.py`: `chromadb.PersistentClient(path="./chroma_db")`, `get_or_create_collection("mf_faq_v1", metadata={"hnsw":"cosine"... "hnsw:space":"cosine","embed_model":MODEL_ID,"chunk_schema":2})`, always passing `embeddings=` explicitly on writes and queries, `coerce_metadata()` mapping None→"" and page_no→0, `upsert_chunks()`, `delete_doc()` via where={"doc_id":...}, `query()` returning documents/metadatas/distances, and `assert_model_match()` raising on model drift. Finish `run_ingest.py` (delete changed docs → upsert → print collection size and corpus version) and add `--probe` printing top-3 chunks with similarity for one probe question per scheme. Add `tests/test_store.py` for idempotent upsert, None-free metadata, scoped delete, and model-mismatch.

**Phase 4**
> Implement Phase 4 (RETRIEVE + GUARDS) from `Doc/implementation.md` (§6) against `Doc/architecture.md` §5.2–§5.4. No LLM calls in this phase. Create `tests/pii_cases.csv` (20+ rows incl. 5 legitimate non-PII queries) and `tests/adversarial_set.csv` (20 rows: 12 advice, 5 performance, 3 disguised advice). Implement `intent.py` (`detect_advice`, `detect_performance`, `detect_scheme` with the alias map — note the scheme resolves as **SBI Large Cap Fund**, formerly SBI Bluechip Fund, so both names must map to one id; category words like "ELSS"/"large cap" must NOT return a scheme), `guards.py` (`check_length`, `check_pii` with the architecture §5.3 regex table and keyword anchoring for bare digit runs; refusal strings and tier-4 educational links), and `retrieve.py` (top_k 5, cosine `1-distance`, scheme `where` filter only for detected scheme names, one unfiltered retry on empty results, `sim_floor=0.35` → OUT_OF_CORPUS). Wire `pipeline.py` steps 1–7 only. Add tests that spy on `encode` to prove a PII input triggers zero encoder calls.

**Phase 5**
> Implement Phase 5 from `Doc/implementation.md` (§7) against `Doc/architecture.md` §5.5–§5.6. Create `tests/eval_set.csv` (F01–F10 covering the seven mandatory topics across four schemes, plus O01–O10 out-of-corpus). Implement `prompt.py` with the 8-rule system prompt verbatim from §5.5 and `assemble_context()` producing the `<context>` block (de-dup by chunk_id, score order, max 5, never drop the top chunk, breadcrumb + Source line each). Implement `llm.py` (Groq, temperature 0.0, max_tokens 320, timeout 20s, retry on 429/5xx/timeout only, ConfigurationError on missing key, never log the key). Implement `validate.py` V1–V6 exactly as in §5.6, including V5 discarding model output and returning the canned refusal when advice is detected in the answer. Complete `pipeline.py` steps 8–10 and the `Response` dataclass. Add `tests/test_validate.py` with crafted bad answers for each validator.

**Phase 6**
> Implement Phase 6 from `Doc/implementation.md` (§8) against PRD §6.4. Create `src/app.py`: single-page Streamlit chat with `st.chat_input`, welcome line, the three example questions as clickable buttons prefill, the disclaimer "Facts-only. No investment advice." on first render and at the foot of every answer, citations rendered as clickable links labelled with document title and page, and the `Last updated from sources:` line. Implement all six states: idle, thinking (spinner), answered, refused (advice/PII), out_of_corpus, error. Show corpus freshness in the footer; never display guard/retrieval/latency internals. Never call the pipeline at module scope.

**Phase 7**
> Implement Phase 7 from `Doc/implementation.md` (§9) against PRD §9. Create `scripts/run_eval.py` with modes default / `--adversarial` / `--latency --runs N` / `--diff`, computing citation coverage, groundedness (answer numbers/date must appear in retrieved context), recall@5 (expected_url + expected_scheme in top 5), advice refusal accuracy, PII refusal accuracy, brevity, freshness, out-of-corpus honesty and P95 latency; write `artifacts/eval_report.json` plus a markdown summary. `--diff` must exit non-zero when answers differ from `Doc/sample_qa.md` unless `--accept` rewrites it. Create `scripts/check_links.py` asserting HTTP 200 for every `ingest=yes` URL. All PRD §9 thresholds must pass.

**Phase 8**
> Implement Phase 8 from `Doc/implementation.md` (§10) against PRD §10. Create `scripts/run_experiment.py` sweeping one knob at a time: `--chunk-chars {600,900,1200}`, `--top-k {3,5,8}`, `--tau {0.20,0.30,0.40,0.50}`, `--temp {0.0,0.2}`, `--filter {on,off}`; write results to `artifacts/experiments/*.json`. Run at minimum E1 (chunk size), E2 (strategy), E4 (scheme filter) and E5 (τ). Append a "Review verdict" and "Experiment outcomes" section to `artifacts/chunk_report.md` with a decision and reasoning per experiment, and mirror the final decisions into the README. Rebuild the store and re-run the full eval after applying the winning configuration.

**Phase 9**
> Implement Phase 9 from `Doc/implementation.md` (§11). Produce `README.md` (setup from the verified PowerShell commands, scope = SBI MF + the four schemes, architecture summary, known limits — including that groundedness is a string heuristic rather than semantic verification, one AMC only, manual refresh, English only — plus final eval metrics), `Doc/sample_qa.md` (5–10 real queries with actual answers, citations and freshness lines, regenerated via `run_eval.py --accept`), `Doc/disclaimer.md`, and a readable export of the source list from `config/sources.csv` highlighting the 5 tier-1 sources. Commit `artifacts/chunks.txt` and `artifacts/chunk_report.md`; keep `chroma_db/` off the main branch. Then walk the PRD §8.2 launch checklist A/B/C with evidence for every box.

---

*End of Implementation Guide — SBI MF FAQ Assistant · Milestone 04 · Cohort 52*