# SBI MF FAQ Assistant — Product Requirements Document

**One-line description:**
A facts-only RAG chatbot that answers mutual fund scheme questions (expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, statement download) using only official SBI Mutual Fund / SEBI / AMFI / CAMS public documents, with one source link in every answer and no investment advice.

| Field | Value |
|---|---|
| **Project Name** | SBI MF FAQ Assistant |
| **Team** | Cohort 52 |
| **Contributors** | Shatesh Soni |
| **Status** | In Review |
| **Launching on** | November 2026 (5-week build from PRD approval) |
| **Milestone** | MileStone 04 |
| **Resources** | [Milestone Brief](./Doc/ProblemStatement.txt) · [Milestone 01](../01) · [Milestone 02](../02) · [Milestone 03](../03) · [3-Pager Template](../3-Pager%20Template.pdf) |

**Corpus scope (locked for v1):** AMC = **SBI Mutual Fund** · Schemes = **SBI Bluechip Fund (Large Cap)**, **SBI Long Term Equity Fund (ELSS)**, **SBI Flexicap Fund**, **SBI Small Cap Fund**.

**Tech stack (fixed by brief):** `sentence-transformers/all-MiniLM-L6-v2` (embeddings, local, 384-dim) · **ChromaDB** (persistent vector store) · **Groq** (LLM, key in `.env`) · Python.

> **Assumptions flagged for approver:** launch date is indicative; status "In Review"; contributors list is single-author as in Milestones 01–03. Items marked **[OPEN]** in *Open Questions* need a decision before build start.

---

## 1. Problem Definition

Retail investors comparing mutual fund schemes cannot get a single reliable, scheme-specific fact quickly: expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer and benchmark all live inside long, unsearchable PDFs (factsheets, SID, KIM) spread across the AMC, SEBI, AMFI and CAMS websites. Support and content teams answer the same handful of questions repeatedly, which is slow, inconsistent and expensive.

**What is the problem?**
- Official MF scheme facts are fragmented across 20+ PDF/HTML documents with no site-level search, so a user cannot answer "what is the expense ratio of SBI Bluechip?" in one place.
- Generic AI chatbots **hallucinate fee figures and lock-in periods** and freely give buy/sell opinions — unacceptable for regulated financial product data.
- AMC pages change monthly (factsheets, TER revisions), so stale or mis-copied numbers spread easily across content and support replies.

**Who is facing the problem?**
- Retail investors comparing schemes (first-time and active SIP investors).
- AMC support and content teams answering repetitive MF questions.

**What business value is unlocked?**
- A reusable, auditable factual answer layer with a source link on every claim — the base requirement for any regulated (SEBI-aligned) surface that touches MF product data.
- Support/content teams deflect repetitive fact queries, and every answer is traceable to a primary document instead of a person's memory.

**How will target users benefit?**
- One accurate, cited fact in under ~10 seconds instead of downloading and searching five PDFs, with clear "as of" freshness so users know how current the number is.

**Why is it urgent now?**
- SEBI's expense-ratio regime and monthly TER disclosures keep schemes' fee data in constant flux (e.g., SBI MF's Base TER change w.e.f. 30.05.2025), so manual/FAQ-page upkeep is already breaking down.
- LLM-based answer engines are proliferating faster than compliance guardrails — shipping a **facts-only, cited, advice-refusing** reference implementation now is a differentiator.

---

## 2. Goals

| # | Priority | Goal | Measurable Metric | Why it matters |
|---|---|---|---|---|
| G1 | **P0** | Every answer is grounded and cited | 100% of answers contain ≥1 official source URL from the locked corpus (0 unsourced claims in the 10-question sample Q&A) | Trust and auditability are the entire product; an uncited answer is a defect |
| G2 | **P0** | Correct scheme-specific facts | Grounded-answer rate ≥ 90% on the 10-question sample Q&A; retrieved chunk contains the answer in ≥ 90% of cases | Proves the RAG pipeline (ingest → chunk → embed → retrieve) works, not just the UI |
| G3 | **P0** | Refuses advice with a graceful redirect | 100% refusal on a 20-question adversarial set ("should I buy…", "which is better…", "is now a good time…"), each refusal links to an official educational page | SEBI compliance posture; prevents the assistant from being quoted as advice |
| G4 | **P0** | Zero PII handling | Regex PII guard rejects 100% of seeded inputs (PAN, Aadhaar-like, account/folio, OTP, email, phone); nothing PII-like persisted to Chroma or logs | Hard constraint from the brief; also the reason we never need login or account linkage |
| G5 | **P1** | Answers are short and honest | 100% of answers ≤ 3 sentences and include "Last updated from sources: `<as_of_date>`" | Brevity and freshness are the credibility cues users rely on |
| G6 | **P1** | Covers all 7 mandatory topics | ≥ 1 answerable cited question each for: expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, statement/tax-doc download | This is the brief's definition of done for content coverage |
| G7 | **P1** | Fast, repeatable prototype | P95 end-to-end latency < 8 s; ingestion runs **once** and persists to disk; cold setup documented in README | A re-embedding pipeline on every restart is the most common RAG prototype failure |
| G8 | **P2** | Answers are useful, not just correct | ≥ 4/5 usefulness rating on the 10-question sample Q&A; ≥ 80% of answers need no follow-up query | Separates a demo that retrieves from one users would keep using |

### Non-functional requirements
| Requirement | Target |
|---|---|
| Chunk auditability | 100% of chunks dumped to a human-readable `.txt` file before embedding, with metadata visible |
| Reproducibility | Same corpus + same model ⇒ same embeddings; model ID and versions pinned in README |
| Secret hygiene | Groq key only in `.env`, `.env` gitignored, never echoed in logs or UI |
| Public sources only | No third-party blogs, no screenshots of back-ends; every URL resolves from sbimf.com / sebi.gov.in / amfiindia.com / camsonline.com / mfcentral.com |
| Offline-safe embeddings | Embeddings computed locally with no external API call |

---

## 3. Non-Goals (out of scope for v1)

1. **No investment advice or recommendations** — no "should I buy/sell/hold", no portfolio allocation, no fund-of-funds suggestions, no goal planning.
2. **No performance claims** — no computing, comparing or ranking returns; if asked, link to the official factsheet and stop.
3. **No NAV, portfolio or transaction data** — no live prices, no holdings, no unit balances, no folio/account linkage.
4. **No PII of any kind** — PAN, Aadhaar, account/folio numbers, OTPs, emails, phone numbers are neither requested, accepted nor stored.
5. **No multi-AMC scope** — SBI Mutual Fund only in v1; the corpus stays small enough to audit.
6. **No live crawling / auto-refresh of sources** — ingestion runs from a locked, human-reviewed URL list on an explicit trigger.
7. **No multilingual, voice or Hinglish support** — English text only.
8. **No auth, multi-tenancy, analytics dashboards or mobile app** — a tiny single-user prototype UI.
9. **No embedding fine-tuning or reranker model** — MiniLM + metadata filters only.
10. **Not an SEBI-registered investment adviser** — educational facts layer only.

---

## 4. Validation of the Problem

**Evidence reviewed (primary sources only, as required):**
- The 23 URLs in the [milestone brief](./Doc/ProblemStatement.txt) were reviewed to confirm that every mandatory fact exists **only** inside long PDFs: SBI factsheets (Jun 2026, Jan 2026, Aug 2025, Jul 2024), SID/KIM documents, the TER page and Base TER change notice, disclosure hub, ways-to-invest, Tax Reckoner FY 2026-27, plus CAMS/AMFI/MFCentral statement guides and SEBI/AMFI educational FAQs.
- **Structural finding:** a factsheet is a 2–4 page multi-scheme PDF and the SID is a 50+ page legal document. There is no cross-document search, so "expense ratio + exit load + benchmark for one scheme" requires opening 3 documents. This is the friction the assistant removes.
- **Freshness finding:** TER data is versioned by date (Base TER change w.e.f. 30.05.2025; monthly factsheets). Static FAQ pages drift out of date, which is why every chunk must carry an `as_of_date`.

**Competitive / landscape insights:**
| Alternative | Gap |
|---|---|
| AMC website (sbimf.com) | Authoritative but PDF-heavy, unsearched across documents |
| AMFI / SEBI education pages | Authoritative and well-structured, but **categorical** ("what is a flexi-cap fund?") not **scheme-specific** ("expense ratio of SBI Flexicap") |
| CAMS / MFCentral | Account & transaction platforms; require login and hold PII — out of scope by design |
| General AI chatbots | Answer instantly and fluently, but **hallucinate fee/lock-in numbers** and give opinions with no citation — the risk this product removes |
| Brokerage / comparison apps | Advice-led and recommendation-led; not facts-only, not source-linked |

**Honest limitation:** no primary user research (survey/interviews) has been run for this milestone. Validation so far is source-based, not user-based. Primary research is descoped (see §11) — the sample Q&A + usefulness rating in §10 is the substitute evidence.

---

## 5. Understanding the Target Audience

### User segments

| Segment | Who | Size | Why they matter |
|---|---|---|---|
| **Retail investors comparing schemes** | Salaried/small-business investors, 25–45, evaluating large-cap / flexi-cap / ELSS / small-cap funds, typically via a 1–2 page factsheet they were sent | Large; to be quantified from AMFI/industry primary data before v1.1 | This is the audience the facts-only + cited design exists for |
| **AMC support / content teams** | Agents answering "exit load?", "how do I download my capital-gains statement?" dozens of times a week | Small but high-frequency | Highest time-saved per query; also the internal accuracy check on the assistant's answers |

> Segment sizing to be filled from primary sources (AMFI monthly data / industry reports) — intentionally left blank rather than estimated, per the "public sources only" constraint.

### Key personas

**Persona 1 — "Riya", first-time equity allocator (28, salaried, Tier-1)**
- Goal: understand a scheme's *fees, lock-in and category* before starting a SIP.
- Journey: sees SBI ELSS campaign page → asks "what's the lock-in period and exit load?" → reads 3-sentence cited answer → reads linked SID → starts SIP on her own.
- Pain: doesn't know which of 5 PDFs is authoritative; fears being sold something; can't tell if a number she's read online is current.

**Persona 2 — "Arjun", AMC support agent (31)**
- Goal: answer a repetitive fact query correctly and fast, with something citable to attach.
- Journey: types the exact same question 20× a day → copies answer + source link → escalates only true edge cases.
- Pain: slow PDF hunting; inconsistent answers between agents; risk of quoting a stale TER.

**Persona 3 — "Content/ops reviewer" (internal)**
- Goal: verify the assistant never states a number that isn't in the current official document.
- Journey: asks a known-fact question → clicks the citation → checks the page/table → signs off.
- Pain: hallucinated figures in AI-assisted content are invisible unless every claim is linked.

### Unmet needs (goals & pain points)
- **Need:** a single, trustworthy place for scheme-specific facts. **Pain:** fragmented, unsearchable PDFs.
- **Need:** proof of freshness. **Pain:** numbers quoted without a date go stale silently.
- **Need:** a hard boundary against advice. **Pain:** generic assistants blur facts into recommendations.
- **Need:** zero data collection. **Pain:** most MF tools require login, PAN and OTPs — the highest-PII surface in finance.
- **Need:** brevity. **Pain:** a 3-page legal SID is the wrong answer to "what's the minimum SIP?".

### User journey (happy path)
1. **Land** → welcome line + 3 example questions + "Facts-only. No investment advice."
2. **Ask** a factual question in plain English ("Expense ratio of SBI Flexicap Fund?").
3. **Guardrails** run → PII check → advice-intent check.
4. **Retrieve** → embed question → top-k chunks from ChromaDB.
5. **Generate** → Groq answers **only** from chunks, ≤3 sentences, ≥1 citation, `Last updated from sources:` line.
6. **Verify** → user clicks the citation and lands on the exact official page/PDF.
7. **Out of scope?** → polite facts-only refusal + relevant educational link (AMFI Types / Categorization, SEBI FAQ).

---

## 6. Solution

### 6.1 Product overview
A small, single-purpose chat surface over a **locked corpus of official SBI MF / SEBI / AMFI / CAMS documents**. Retrieval-Augmented Generation keeps the LLM grounded: the model never answers from memory, only from retrieved document chunks, and every answer carries the source URL. A deterministic guardrail layer (PII filter + advice-intent refusal) runs *before* and *around* generation so compliance behaviour does not depend on the model "remembering" to behave.

### 6.2 Architecture — RAG pipeline (all stages from the brief, tracked separately)

**Ingestion (runs once, offline, persisted):**
```
Lock URL list (CSV)
      │
      ▼
[1] LOAD ──────────► Downloader + parsers
      │               • PDF  → text per page (factsheets, SID, KIM, TER notice, Tax Reckoner)
      │               • HTML → boilerplate-stripped sections (TER page, hubs, CAMS/AMFI/SEBI guides)
      ▼
[2] CHUNK ─────────► Document-type-aware splitter  (agent-proposed, §7.2)
      │               • emit artifacts/chunks.txt for human inspection  ◄── mandatory gate
      ▼
[3] EMBED ─────────► all-MiniLM-L6-v2, local, 384-dim, L2-normalised
      ▼
[4] STORE ─────────► ChromaDB PersistentClient → ./chroma_db  (collection: mf_faq_v1)
```
**Query (every question):**
```
Question
  → PII guard (regex) ───fail──► neutral rejection, no retrieval
  → Advice-intent guard ──fail──► polite refusal + educational link
  → Embed question (same MiniLM model)
  → Chroma query top-k=5 (cosine) + optional scheme metadata filter
  → similarity floor check (max_sim < threshold ⇒ "not in my sources")
  → Groq prompt: answer ONLY from context, ≤3 sentences, cite URL, add freshness line
  → Post-check: citation present? length ≤3 sentences? no numeric performance claim?
      fail ⇒ fall back to "I can't answer that from my sources" + link
```

### 6.3 Key design decisions behind the solution
| Decision | Rationale |
|---|---|
| Facts-only + mandatory citation | The product's credibility contract; also the SEBI-safe posture |
| Locked, human-reviewed URL list instead of live crawling | Reproducible corpus, auditable sources, no surprise content changes |
| Same embedding model for chunks and questions | Required for meaningful cosine similarity; no model mismatch |
| ChromaDB persisted to disk | Ingestion is expensive (~minutes) and must not repeat per restart |
| Guardrails **outside** the LLM (regex + intent rules) | Compliance cannot depend on model compliance |
| `as_of_date` surfaced in every answer | Users can tell whether a TER/lock-in figure is current |
| Chunk dump to `.txt` before embedding | Required by the brief; catches bad chunking before it silently ruins retrieval |

### 6.4 User flow / wireframe (tiny UI, as specified)

```
┌────────────────────────────────────────────────────────────┐
│  SBI MF FAQ Assistant                     Facts-only.      │
│  Ask me factual questions about SBI Mutual Fund schemes.   │  ← welcome line
│  I answer only from official sources and always cite them. │  ← disclaimer
│                                                             │
│  Try asking:                                                │
│   1. What is the exit load of SBI Flexicap Fund?           │  ← 3 example
│   2. What is the lock-in period for SBI Long Term Equity?   │     questions
│   3. How do I download my capital-gains statement?          │
│                                                             │
│  ┌───────────────────────────────────────┐   ┌───────────┐   │
│  │ Ask a factual question…              │   │  Ask  →   │   │
│  └───────────────────────────────────────┘   └───────────┘   │
│                                                             │
│  ── Assistant ──────────────────────────────                │
│  SBI Long Term Equity Fund has a lock-in period of 3 years, │
│  after which redemptions are permitted without an exit load.│  ≤3 sentences
│  Source: SID — SBI Long Term Equity Fund                    │  ← 1 citation link
│  Last updated from sources: 30-05-2025                       │  ← freshness
│                                                             │
│  ── User ───────────────────────────────────                │
│  Should I buy the ELSS one or go for the Bluechip fund?     │
│  ── Assistant ──────────────────────────────                │
│  I only share documented facts and don't give investment    │
│  advice. For how these fund categories work, see AMFI:      │  ← refusal
│  [Types of Mutual Fund Schemes]                             │  ← educational link
└────────────────────────────────────────────────────────────┘
```

**UI states:** idle (welcome + examples) · thinking (retrieval/generation) · answered (text + citation + freshness) · refused (advice/PII) · out-of-corpus (no confident retrieval) · error (LLM/API failure with retry).

### 6.5 Key features (and the user benefit each delivers)
1. **Cited factual answers** — 1–3 sentences, always with the official link. *Benefit: verifiable, no guessing.*
2. **Seven-topic coverage** — expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, statement/tax-doc download. *Benefit: covers the questions users actually ask.*
3. **Freshness line** — "Last updated from sources: `<date>`" on every answer. *Benefit: user knows how current the figure is.*
4. **Advice refusal + education** — polite facts-only message plus an AMFI/SEBI link. *Benefit: compliant and still helpful.*
5. **PII block** — rejects PAN/Aadhaar/phone/email/OTP/account-number inputs before retrieval. *Benefit: no sensitive data ever touches the system.*
6. **No-performance-claims rule** — return questions link to the official factsheet, nothing computed. *Benefit: no misleading comparisons.*
7. **Discoverable start** — welcome line + 3 example questions. *Benefit: no "blank box" anxiety.*
8. **Transparent failure** — low-confidence retrieval says "not in my sources" instead of inventing. *Benefit: honest behaviour, easier to trust.*
9. **Inspectable corpus** — `chunks.txt` + source list CSV shipped with the app. *Benefit: reviewers can audit what the model can see.*

---

## 7. Key Logic

### 7.1 Module map
```
src/
  config.py            # paths, model IDs, corpus lock, thresholds
  sources.csv          # locked URL list (id, title, doc_type, scheme, url, as_of_date)
  ingest/load.py       # download + PDF/HTML parsing → data/raw_text/*.txt
  ingest/chunk.py      # doc-type-aware splitter → artifacts/chunks.txt
  ingest/embed_store.py# MiniLM embed + ChromaDB persist
  query/guards.py      # PII regex + advice-intent refusal + post-answer checks
  query/answer.py      # retrieve → Groq prompt → validated answer
  app.py               # tiny UI (Streamlit or Gradio — [OPEN])
tests/                 # eval_set.csv (10 Q&A) + adversarial_set.csv (20 advice questions)
scripts/               # run_ingest.py, run_eval.py, record_demo.sh
```

### 7.2 Chunking strategy (to be validated against the real corpus before coding)

The brief asks the AI agent to **inspect the data first, then propose and justify the strategy**. Proposed starting point, with the reasoning that must be re-confirmed after dumping parsed text:

**Constraint that drives everything:** `all-MiniLM-L6-v2` truncates at **256 wordpiece tokens** (~900–1,000 chars). Chunks larger than that are silently truncated, losing the tail of fee tables and lock-in clauses. Therefore:

| Document type | Splitting rule | Target size | Overlap | Rationale |
|---|---|---|---|---|
| **Factsheets** (multi-scheme, tabular) | Split **per scheme section**, keep each table intact; never split a row | ~900 chars | ~120 chars | A scheme's fee/benchmark block must stay whole or numbers detach from labels |
| **SID / KIM** (long legal prose) | Split on numbered section headings first (`Investment objective`, `Fees and expenses`, `Exit load`), then window | ~900 chars | ~120 chars | Headings are the user's actual question boundaries |
| **TER page / HTML tables** | One chunk **per scheme row** (scheme, regular TER, direct, IDCW) | Row-sized | None | Makes "expense ratio of X" a near-exact match instead of a needle in a table dump |
| **Guides & FAQs** (CAMS/AMFI/SEBI/Ways-to-Invest) | Strip nav/footer boilerplate, split on `<h*>` headings and list items | ~900 chars | ~120 chars | Steps get separated from their page context otherwise |
| **Short campaign/disclosure pages** | Whole page if < 900 chars | as-is | None | Chunking short text only destroys context |

**Global settings:** chunk_size ≈ 900 chars (≈220 tokens, under the 256 limit) · overlap ≈ 120 chars (~13%) · separators ordered by document structure, not a generic recursive splitter.

**Chunk metadata schema (stored in Chroma):**
```json
{
  "chunk_id": "fct_jun2026_bluechip_004",
  "doc_id": "sbimf_factsheet_2026_06",
  "source_url": "https://www.sbimf.com/docs/.../all-sbimf-schemes-factsheet-june-2026.pdf",
  "doc_title": "All SBI MF Schemes Factsheet — June 2026",
  "doc_type": "factsheet | sid | kim | ter_page | ter_notice | guide | regulator_faq | campaign",
  "scheme": "SBI Bluechip Fund",
  "scheme_category": "Large Cap",
  "section": "Fees and charges",
  "page_no": 3,
  "as_of_date": "2026-06-30",
  "ingested_at": "<ISO timestamp>",
  "char_len": 870,
  "text": "<chunk text>"
}
```
`as_of_date` is what powers the "Last updated from sources:" line; `scheme` enables metadata filtering so "SBI Bluechip's exit load" can't be answered from the Small Cap factsheet.

### 7.3 Retrieval logic
| Parameter | Value | Reason |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2`, L2-normalised, 384-dim | Fixed by brief; same model on both sides |
| Distance metric | Cosine | Normalised vectors; semantic-similarity appropriate |
| `top_k` | 5 | Enough context for a fee+charge question, few enough to stay focused |
| Metadata filter | If the query names a scheme, filter `scheme == <detected>` (fall back to unfiltered) | Prevents cross-scheme number mixing — the highest-risk failure here |
| Similarity floor | If `max_sim < τ` ⇒ out-of-corpus response | [OPEN] τ initial value to be tuned on the eval set |
| Query expansion | Scheme-name alias map (e.g., "SBI Bluechip" / "Blue Chip" / "Bluechip Fund") | Users type variant names |

### 7.4 Guardrail logic (compliance-critical)
```
INPUT:
  1. PII regex scan → PAN [A-Z]{5}[0-9]{4}[A-Z]; 12-digit; 10-digit phone;
     email; keywords (OTP, folio no., account no., CVV) → REJECT before embedding
  2. Advice-intent classifier (keyword/regex first, LLM fallback) for:
     "should I", "which is better", "best fund", "is now a good time",
     "recommend", "allocate", "compare returns", "worth it"
     → REFUSAL + educational link
  3. Performance-intent check: "return", "CAGR", "% gain", "performance"
     → NO computation; link official factsheet
PROMPT (Groq, temp 0–0.2):
  • Use ONLY the provided context. If it does not contain the answer, say so.
  • Maximum 3 sentences. No advice, no predictions, no return calculations.
  • End with "Last updated from sources: <as_of_date from context>".
  • Include at least one `source_url` from the context, verbatim.
OUTPUT VALIDATION (deterministic):
  • contains ≥1 whitelisted official URL  → else fall back to out-of-corpus
  • ≤3 sentences                          → else truncate/regenerate
  • no uncited numeric claim               → else re-prompt or refuse
  • refusal for advice intent             → else override with refusal
```

### 7.5 Storage / schema changes
- New Chroma collection `mf_faq_v1`, persistent at `./chroma_db` (ids = `chunk_id`, documents = chunk text, metadatas = schema above).
- `sources.csv` is the single source of truth for the corpus: `doc_id, title, doc_type, scheme, scheme_category, source_url, as_of_date, local_filename, fetched_at`.
- `artifacts/chunks.txt` — flat, readable dump of every chunk with its metadata (mandatory inspection gate).
- `.env` (gitignored) holds `GROQ_API_KEY`; `config.py` reads it and never logs it.
- `data/raw_text/` keeps parsed text per document so re-chunking needs no re-download.

### 7.6 Freshness & update path
Re-ingestion is **manual and explicit** (`--refresh`): update `sources.csv` `as_of_date`, re-run load → chunk → embed (only changed docs) → re-embed questions not needed (stateless). The UI shows the newest `as_of_date` among retrieved chunks, so a stale corpus is visible to the user rather than silent.

---

## 8. Launch Readiness

### 8.1 Key milestones & timeline (5 weeks from approval → November 2026)

| Week | Milestone | Key activities | Exit criteria |
|---|---|---|---|
| **W0** | Approval & source freeze | PRD sign-off; **5-source list decision** ([OPEN] §11); confirm 4 schemes; verify all URLs resolve | Corpus scope + source list locked |
| **W1** | Corpus ingestion | Download & parse all PDFs/HTML; **inspect parsed text**; propose + justify chunking strategy; generate `chunks.txt` for review | `chunks.txt` reviewed; no chunk exceeds 256 tokens; chunk-size decision recorded |
| **W2** | Embed & store | MiniLM embeddings; ChromaDB persist; retrieval smoke test per scheme | Retrieval returns correct-scheme chunks for 10/10 probe queries |
| **W3** | Generation & guardrails | Groq prompt; citation/length/freshness validators; PII + refusal guards; "not in sources" path | 10-question sample Q&A passing on citations & brevity |
| **W4** | UI + packaging | Tiny UI (welcome + 3 examples + disclaimer); README; source list CSV; 20-question adversarial run | Adversarial set 100% refusal; README setup verified on a clean machine |
| **W5** | QA, demo & submission | Latency check (P95 < 8 s); link-liveness check; record ≤3-min demo video; assemble deliverables | All deliverables in §12 submitted |

### 8.2 Launch checklist

**A. Product, compliance & content readiness**
- [ ] Every answer carries ≥1 official citation from the locked whitelist
- [ ] All 7 mandatory topics return a cited, correct answer
- [ ] 20-question advice set: 100% refusal, each with an educational link
- [ ] Performance questions: no computed/comparative returns, factsheet link only
- [ ] Answers ≤3 sentences + "Last updated from sources:" on every answer
- [ ] Disclaimer visible in UI: **"Facts-only. No investment advice."**
- [ ] No third-party blogs, no aggregator sites, no back-end screenshots in any asset

**B. Technical readiness**
- [ ] `chunks.txt` inspected; chunking rationale written down
- [ ] ChromaDB persists to disk; second run does **not** re-embed
- [ ] Same embedding model used for chunks and queries (verified vector dims = 384)
- [ ] PII guard tested against seeded PAN/Aadhaar/phone/email/OTP/folio inputs
- [ ] `GROQ_API_KEY` only in `.env`; `.env` gitignored; no key in logs, screenshots or notebook output
- [ ] P95 latency < 8 s; graceful error state when the LLM API fails
- [ ] All corpus URLs return HTTP 200 at submission time
- [ ] Clean-machine setup verified from README alone

**C. Deliverable readiness**
- [ ] Working prototype link or ≤3-min demo video
- [ ] Source list CSV/MD (see §11 [OPEN] on the "5 URLs" requirement)
- [ ] README: setup steps, scope (AMC + schemes), known limits
- [ ] Sample Q&A file: 5–10 queries with answers + links
- [ ] Disclaimer snippet used in the UI

### 8.3 Internal stakeholders

| Stakeholder | Role in launch |
|---|---|
| Product Manager | Owns problem framing, scope lock, prioritisation, final launch decision |
| AI/ML Engineer (Shatesh Soni) | Owns ingestion, chunking, embeddings, ChromaDB, prompt & guardrails |
| Compliance reviewer | Verifies no-advice stance, citation whitelist, disclaimer, and refusal quality |
| QA / evaluator | Runs sample Q&A + adversarial sets, latency, link-liveness, clean-setup check |
| Content owner | Confirms `as_of_date` values and scheme/category mapping are correct |

---

## 9. Data & Success Reporting

| Metric | Definition | Target | Why |
|---|---|---|---|
| Citation coverage | Answers with ≥1 whitelisted official URL / total answers | 100% | Core contract |
| Grounded-answer rate | Answers fully supported by retrieved chunks / total | ≥ 90% | Proves RAG quality |
| Retrieval recall@5 | Eval queries where a correct-scheme chunk is in top-5 | ≥ 90% | Isolates retrieval vs generation failures |
| Refusal accuracy (advice) | Correct refusals / 20 adversarial queries | 100% | Compliance |
| Refusal accuracy (PII) | Blocked PII inputs / seeded PII inputs | 100% | Hard constraint |
| Brevity compliance | Answers ≤3 sentences / total | 100% | Brief requirement |
| Freshness compliance | Answers with `Last updated from sources:` / total | 100% | Trust requirement |
| Out-of-corpus honesty rate | Correct "not in my sources" on unanswerable questions | 100% | Prevents hallucination |
| P95 latency | End-to-end question → answer | < 8 s | Usable prototype |
| Usefulness rating | Human rating on 10 sample Q&A | ≥ 4/5 | Qualitative usefulness proxy |

---

## 10. Experimentation Plan

Run offline on the fixed eval set (`tests/eval_set.csv`, 10 factual + 10 out-of-corpus + 20 adversarial), scoring groundedness, recall@5, refusal accuracy and brevity. No production A/B testing — the prototype has no traffic.

| # | Experiment | Variants | Primary metric | Decision rule |
|---|---|---|---|---|
| E1 | **Chunk size** | 600 chars vs 900 chars vs 1,200 chars (with proportional overlap) | recall@5 + groundedness | Keep the smallest size with no loss in recall; must stay under 256 tokens |
| E2 | **Chunking strategy** | generic recursive vs document-type-aware (§7.2) | recall@5 on table/row questions ("expense ratio of…") | Adopt the winner; document the evidence |
| E3 | **top_k** | 3 vs 5 vs 8 | groundedness + brevity violations | Highest k that doesn't increase wrong-scheme answers |
| E4 | **Metadata filter** | filtered by scheme vs unfiltered | cross-scheme number errors (must be 0) | Ship filtered-with-fallback if it removes cross-scheme errors |
| E5 | **Similarity floor τ** | 0.20 / 0.30 / 0.40 / 0.50 | hallucination rate on out-of-corpus set | Pick τ that yields 0 hallucination with acceptable coverage |
| E6 | **Prompt & temperature** | temp 0 vs 0.2; with/without explicit refusal clause | refusal accuracy + citation coverage | Ship the variant with 100% on both guardrail metrics |
| E7 | **Freshness line source** | max chunk `as_of_date` vs doc-level `as_of_date` | correctness on TER-change questions | Ship the variant matching the source document's own date |
| E8 | **Chunk dump inspection** | with/without reviewing `chunks.txt` before embedding | groundedness | Demonstrates the brief's mandated gate is load-bearing, not ceremonial |

**Kill criteria:** if grounded-answer rate < 80% after E1–E3, descope to 2 schemes (Bluechip + Long Term Equity) and deepen document-type-aware chunking rather than shipping a broad but unreliable corpus.

---

## 11. Open Questions & Decisions Taken

| # | Open Question | Decision / Next Step | Owner |
|---|---|---|---|
| 1 | The brief lists **23 URLs** but deliverables ask for a "source list of the 5 URLs you used" | **Decision:** treat the 5 *core corpora* as (1) All-Schemes Factsheet Jun 2026, (2) Factsheet Jan 2026, (3) SID — SBI Bluechip, (4) SID — SBI Long Term Equity, (5) TER page; publish **all** ingested URLs in `sources.csv` + README. **Needs confirmation.** | PM |
| 2 | SEBI risk-o-meter circular link is a **mirror** (caalley.com), and the brief says to replace it with the sebi.gov.in original | **Decision:** exclude the mirror entirely. If no official SEBI copy is locatable, answer riskometer questions from the scheme factsheet/riskometer page only. Third-party mirrors are banned by the "public sources only" rule. **Action: locate the official SEBI circular.** | AI/ML |
| 3 | Factsheets and TERs change **monthly** — what is the refresh cadence? | **Decision:** v1 is manual `--refresh` on demand; `as_of_date` surfaced to users. No scheduler in v1. | AI/ML |
| 4 | ELSS lock-in (3 years) and exit-load slabs must come from documents, **not model memory** | **Decision:** lock this as an eval question and verify the answer traces to the SID chunk; if retrieval fails, it is a chunking bug to fix, not a prompt bug. | AI/ML |
| 5 | Which Groq model? | **Decision:** default `llama-3.3-70b-versatile` (instruction-following for citation format), with `llama-3.1-8b-instant` as a low-latency fallback. **Needs confirmation.** | AI/ML |
| 6 | UI framework — Streamlit, Gradio or notebook? | **Decision:** Streamlit (tinyest path to a shareable link). **Needs confirmation.** | AI/ML |
| 7 | Hosting for the prototype link? | **Decision:** deploy to Streamlit Community Cloud if quota allows; otherwise submit the ≤3-min demo video as the brief permits. | AI/ML |
| 8 | Similarity floor τ initial value? | **Decision:** start at 0.35 and tune via E5. | AI/ML |
| 9 | Does the TER page's HTML table survive boilerplate stripping? | **Decision:** verify in W1 during parse; if the table is JS-rendered, fall back to the Base TER change notice PDF + factsheet TER rows. | AI/ML |

### Decisions taken (locked)
1. **One AMC, four schemes.** SBI MF — Bluechip (Large Cap), Long Term Equity (ELSS), Flexicap, Small Cap. Enough breadth to prove the approach, small enough to audit every chunk.
2. **Facts-only, hard stop on advice.** Refusals are polite, always paired with an official educational link, never a reworded opinion.
3. **Citation is mandatory.** A missing whitelisted URL converts the response into an "I can't answer that from my sources" — fail-closed, never fail-open.
4. **Guardrails outside the LLM.** PII regex and advice-intent rules run in code; the prompt alone is not trusted for compliance.
5. **No PII, no login, ever.** No account linkage means no PAN/Aadhaar/OTP surface at all.
6. **No performance computation.** Return questions get a factsheet link, full stop.
7. **Ingestion runs once, persisted to disk.** `run_ingest.py` is separate from the app; restarts are instant.
8. **Chunks dumped to `chunks.txt` before embedding** — mandatory review gate.
9. **Document-type-aware chunking under the 256-token MiniLM limit** (~900 chars, ~120 overlap), with per-row chunks for TER tables.
10. **Vector DB = ChromaDB, persisted.** No vector-store alternatives in v1.

### Descoped (explicitly out)
1. Performance/return comparison and any return computation
2. Investment advice, recommendations, portfolio allocation, fund ranking
3. PII capture and account/FOLIO integration (CAMS login, OTP, PAN, statements-by-account)
4. AMCs beyond SBI Mutual Fund
5. Live NAV, portfolio tracking, transaction history
6. Live crawling / scheduled re-ingestion / change detection
7. Multilingual & Hinglish Q&A, voice input
8. Auth, multi-user, multi-tenant, saved chat history, analytics dashboards
9. Embedding fine-tuning, rerankers, hybrid BM25+vector search
10. Native mobile app; CI/CD and production observability
11. Primary user research (surveys/interviews) — replaced by the sample Q&A usefulness rating
12. SEBI RAI registration / full regulatory compliance programme — out of scope; the assistant is educational only

### Key trade-offs

| Trade-off | Option A | Option B | Decision |
|---|---|---|---|
| Corpus breadth vs depth | 5+ schemes, shallow | 4 schemes, deep document-type chunking | Choose **B** — the brief's ask is a correct, cited answer, and depth is where hallucination is killed |
| Retrieval quality vs latency | Higher-quality reranker / bigger k | MiniLM + `top_k=5` + metadata filter | Choose **B** — fixed stack, P95 < 8 s, and metadata filtering removes the main error mode |
| Chunk size | Large chunks, more context per hit | ~900 chars, under MiniLM's 256-token limit | Choose **B** — larger chunks get silently truncated by the encoder, losing fee tables |
| Answer style | Rich, explanatory prose | ≤3 sentences + citation + freshness | Choose **B** — brevity and citation are the brief's non-negotiables |
| Guardrails | Prompt-only instructions | Deterministic code guards around the LLM | Choose **B** — compliance must not depend on model compliance |
| Compliance failure mode | Answer anyway (fail-open) | Refuse / say "not in my sources" (fail-closed) | Choose **B** — a missing answer is a much smaller failure than a fabricated TER |
| Refusal UX | Hard "I can't help with that" | Polite facts-only message + educational link | Choose **B** — still helpful, still compliant |
| Freshness handling | Auto-refresh on a schedule | Manual `--refresh` + visible `as_of_date` | Choose **B** for v1; revisit if the corpus grows beyond one AMC |
| Delivery artifact | Hosted link | Demo video if hosting fails | Both acceptable per the brief — build to the link, fall back to video |

---

## 12. Deliverables (per milestone brief)

| # | Deliverable | Format | Notes |
|---|---|---|---|
| 1 | Working prototype | Streamlit app link **or** ≤3-min demo video | Video is the documented fallback if hosting isn't possible |
| 2 | Source list | `sources.csv` (and mirrored in README) | Core 5 highlighted; all ingested URLs included ([OPEN] #1) |
| 3 | README | `README.md` | Setup steps, scope (AMC + 4 schemes), architecture, known limits |
| 4 | Sample Q&A | `docs/sample_qa.md` | 5–10 queries with the assistant's actual answers + links |
| 5 | Disclaimer snippet | `docs/disclaimer.md` + in-UI text | "Facts-only. No investment advice." |
| 6 | Audit artefacts | `artifacts/chunks.txt`, `tests/eval_set.csv`, `tests/adversarial_set.csv` | Supports the inspection and compliance claims |

---

## 13. Abbreviations

| Term | Full Form | Meaning |
|---|---|---|
| AMC | Asset Management Company | The fund manager, e.g. SBI Mutual Fund |
| MF | Mutual Fund | Pooled investment vehicle |
| TER | Total Expense Ratio | Annual fund charge as a % of assets |
| Exit load | Exit Load | Penalty charged on redemption, usually slab-wise and time-based |
| SIP | Systematic Investment Plan | Fixed periodic investment |
| ELSS | Equity Linked Savings Scheme | Tax-saving equity fund with a mandatory lock-in |
| KIM | Key Information Memorandum | Short investor-facing summary document |
| SID | Statement of Additional Information | Detailed legal scheme document |
| Factsheet | Scheme Factsheet | Periodic 2–4 page performance/fee snapshot |
| Riskometer | Risk-o-meter | SEBI-mandated 1–5 risk category shown per scheme |
| Benchmark | Benchmark Index | The index a scheme is measured against |
| Folio | Folio Number | Investor's account identifier with a registrar |
| CAMS | Computer Age Management Services | Registrar providing statements/transactions |
| AMFI | Association of Mutual Funds of India | Industry body; publishes CAS, categorisation, scheme types |
| CAS | Consolidated Account Statement | Single statement across AMCs |
| SEBI | Securities and Exchange Board of India | Regulator; publishes investor FAQs |
| RAG | Retrieval-Augmented Generation | Answer generation grounded in retrieved documents |
| LLM | Large Language Model | Groq-hosted generation model |
| Reranker | Re-ranking model | Sorts retrieved chunks (descoped in v1) |
| PII | Personally Identifiable Information | PAN, Aadhaar, phone, email, account/folio, OTP |
| MVP | Minimum Viable Product | Smallest version that tests the core idea |
| top_k | top-k retrieval | Number of chunks passed to the LLM (k = 5) |
| Recall@5 | Recall at k | Share of eval queries where a correct-scheme chunk appears in top-5 |
| ChromaDB | Chroma | Embedded vector database with on-disk persistence |

---

*End of PRD — SBI MF FAQ Assistant · Milestone 04 · Cohort 52 · Source: [Doc/ProblemStatement.txt](./Doc/ProblemStatement.txt)*