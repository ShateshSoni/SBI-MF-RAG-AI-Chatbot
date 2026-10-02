"""Responsive chat shell over the facts-only SBI MF pipeline.

Layout contract
---------------
* A sticky top bar carries the brand lockup, the corpus badge and the theme
  toggle. Streamlit's own header is flattened to a transparent overlay so the
  native expand-sidebar control (left corner) lands inside the top bar.
* The native sidebar is collapsed by default and is opened from that left
  corner button. It holds the new-chat action, the recommended questions
  grouped by topic, and the corpus provenance footer.
* The transcript, the top bar and the docked chat input all share one column
  width and one gutter, so nothing drifts out of alignment on any viewport.
"""

from __future__ import annotations

import html
import logging

import streamlit as st

from src.ingest.manifest import load_manifest
from src.logging_utils import setup_logging

logger = logging.getLogger("src.app")

DISCLAIMER = "Facts-only. No investment advice."
TITLE = "SBI MF Facts"
WELCOME = "Ask about SBI Mutual Fund schemes"
TAGLINE = (
    "Answers are quoted from official SBI MF, AMFI and SEBI documents only, "
    "and every fact comes with a source link."
)
PLACEHOLDER = "Ask about expense ratio, exit load, ELSS lock-in..."

EXAMPLES = (
    "What is the expense ratio of SBI Bluechip?",
    "What is the exit load of SBI Flexicap?",
    "How do I download my capital-gains statement?",
)

SIDEBAR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Fees & costs",
        (
            "What is the expense ratio of SBI Bluechip?",
            "What is the exit load of SBI Flexicap?",
            "What changed in the base TER with effect from 30.05.2025?",
        ),
    ),
    (
        "Investing",
        (
            "What is the minimum SIP for SBI Small Cap?",
            "What is the ELSS lock-in period?",
        ),
    ),
    (
        "Scheme facts",
        (
            "What is the riskometer of SBI Long Term Equity?",
            "What is the benchmark of SBI Flexi Cap?",
        ),
    ),
    (
        "Statements & tax",
        (
            "How do I download my capital-gains statement?",
            "How do I download an account statement using AMFI CAS?",
            "What is the tax treatment of equity funds under 80C in the Tax Reckoner?",
        ),
    ),
)

STARTERS: tuple[str, ...] = (
    "What is the expense ratio of SBI Bluechip?",
    "What is the exit load of SBI Flexicap?",
    "What is the ELSS lock-in period?",
    "What is the minimum SIP for SBI Small Cap?",
    "How do I download my capital-gains statement?",
    "What is the riskometer of SBI Long Term Equity?",
)

_STATUS: dict[str, tuple[str, str]] = {
    "answered": ("Cited from official sources", "ok"),
    "refused_advice": ("No investment advice", "stop"),
    "refused_pii": ("Personal data not accepted", "stop"),
    "out_of_corpus": ("Not in my sources", "miss"),
    "error": ("Could not answer", "err"),
}

_PALETTE: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0a0c0b",
        "surface": "#101312",
        "panel": "#141917",
        "hover": "#1b201e",
        "ink": "#e9eeeb",
        "muted": "#8d9993",
        "faint": "#6a7671",
        "line": "#232927",
        "line-soft": "#1a201e",
        "accent": "#17c99b",
        "on-accent": "#04211a",
        "accent-soft": "rgba(23, 201, 155, 0.12)",
        "warn": "#e5b04b",
        "warn-soft": "rgba(229, 176, 75, 0.13)",
        "danger": "#f0717c",
        "danger-soft": "rgba(240, 113, 124, 0.13)",
        "shadow": "rgba(0, 0, 0, 0.45)",
        "fade": "rgba(10, 12, 11, 0)",
    },
    "light": {
        "bg": "#f6f8f7",
        "surface": "#ffffff",
        "panel": "#ffffff",
        "hover": "#eef2f0",
        "ink": "#131a17",
        "muted": "#5f6b66",
        "faint": "#8b958f",
        "line": "#e3e9e6",
        "line-soft": "#eef2f0",
        "accent": "#00a870",
        "on-accent": "#ffffff",
        "accent-soft": "rgba(0, 168, 112, 0.10)",
        "warn": "#b47800",
        "warn-soft": "rgba(180, 120, 0, 0.10)",
        "danger": "#d1344a",
        "danger-soft": "rgba(209, 52, 74, 0.10)",
        "shadow": "rgba(16, 24, 20, 0.08)",
        "fade": "rgba(246, 248, 247, 0)",
    },
}

_SHARED_TOKENS = """
  --topbar: 3.75rem;
  --col: 900px;
  --gutter: 1.25rem;
  --toggle-inset: 3rem;
  --avatar: 1.9rem;
  --msg-gutter: 1.1rem;
  --radius: 1rem;
  --font: "Inter", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
"""

_RULES = """
/* ---------------------------------------------------------------- shell */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--bg) !important;
}
body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  color: var(--ink) !important;
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
}
[data-testid="stSidebar"] { color: var(--ink) !important; }
[data-testid="stMain"] p, [data-testid="stMain"] span, [data-testid="stMain"] label,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
  color: inherit;
}
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {
  color: var(--ink) !important;
}
footer, #MainMenu, [data-testid="stDecoration"], [data-testid="stToolbarActions"] {
  display: none !important;
}

/* one shared column: transcript, top bar and chat input line up */
/* Streamlit sizes the bottom padding for the docked input, so leave it alone */
[data-testid="stMainBlockContainer"] {
  max-width: var(--col) !important;
  margin: 0 auto;
  padding-top: 0 !important;
  padding-left: var(--gutter) !important;
  padding-right: var(--gutter) !important;
}
[data-testid="stBottomBlockContainer"] {
  max-width: var(--col) !important;
  margin: 0 auto;
  padding-left: var(--gutter) !important;
  padding-right: var(--gutter) !important;
}
[data-testid="stVerticalBlock"] { gap: 0.4rem; }
[data-testid="stHorizontalBlock"] { gap: 0.5rem; }
[data-testid="stBottom"] { background: transparent !important; }
[data-testid="stBottom"] > div {
  background: linear-gradient(to bottom, var(--fade) 0%, var(--bg) 42%) !important;
}

/* ------------------------------------------------- native header as overlay */
/* The toolbar covers the full width of the top band and would otherwise
   swallow every click aimed at the top bar, so only its button stays live. */
[data-testid="stHeader"] {
  background: transparent !important;
  border-bottom: none !important;
  height: var(--topbar) !important;
  min-height: var(--topbar) !important;
  pointer-events: none !important;
}
[data-testid="stHeader"] [data-testid="stToolbar"] {
  background: transparent !important;
  pointer-events: none !important;
}
[data-testid="stHeader"] button { pointer-events: auto !important; }
[data-testid="stHeader"] [data-testid="stToolbarActionButton"],
[data-testid="stHeader"] [data-testid="stStatusWidget"],
[data-testid="stHeader"] [data-testid="stLogoLink"],
[data-testid="stHeader"] [data-testid="stLogoSpacer"] { display: none !important; }
/* The native toggle is position:fixed, so pinning it to the viewport edge left
   it stranded far to the left of the centred column on wide screens. Derive its
   offset from the same --col/--gutter the top bar uses so it always lands inside
   the bar, and let max() collapse to the viewport edge once the column no longer
   has gutters to spare. Streamlit only shows this button while the sidebar is
   collapsed, which is exactly when the main area is centred in the viewport. */
[data-testid="stExpandSidebarButton"] {
  position: fixed !important;
  top: 0.55rem;
  left: max(0.45rem, calc(50% - var(--col) / 2 + var(--gutter) + 0.4rem));
  z-index: 200;
  width: 2.4rem !important;
  height: 2.4rem !important;
  border-radius: 0.7rem !important;
  background: transparent !important;
  border: 1px solid transparent !important;
  color: var(--muted) !important;
  transition: background 120ms ease, color 120ms ease;
}
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stExpandSidebarButton"]:focus-visible {
  background: var(--hover) !important;
  border-color: var(--line) !important;
  color: var(--ink) !important;
}

/* --------------------------------------------------------------- top bar */
/* keyed containers render a column flexbox, so centre on the main axis */
.st-key-topbar {
  justify-content: center !important;
  min-height: var(--topbar) !important;
  margin: 0 0 0.35rem !important;
  padding: 0 0 0 var(--toggle-inset) !important;
  background: var(--surface) !important;
  border: 1px solid var(--line) !important;
  border-radius: 0 0 var(--radius) var(--radius) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
/* the keyed wrapper is only as tall as the bar, which would cap how far it can
   stick, so pin the wrapper and let the bar ride along inside it */
[data-testid="stLayoutWrapper"]:has(> .st-key-topbar) {
  position: sticky !important;
  top: 0 !important;
  z-index: 90 !important;
}
/* the toggle now derives its offset from the column, so the bar always needs
   the same inset to keep the brand clear of it */
.st-key-topbar [data-testid="stColumn"] {
  min-width: 0 !important;
}

.st-key-topbar [data-testid="stColumn"]:first-child {
  min-width: max-content !important;
}
.st-key-topbar [data-testid="stVerticalBlock"] { gap: 0.2rem; }
.st-key-topbar button {
  min-height: 2.1rem !important;
  padding: 0 0.7rem !important;
  border-radius: 0.6rem !important;
  font-size: 0.8rem !important;
  font-weight: 600 !important;
  border: 1px solid var(--line) !important;
  background: var(--panel) !important;
  color: var(--ink) !important;
  white-space: nowrap;
}
.st-key-topbar button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }
.brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  min-width: max-content;
  white-space: nowrap;
}

.brand-mark {
  display: flex;
  flex: 0 0 auto;
  line-height: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 0 0 auto;
  min-width: max-content;
  line-height: 1.2;
  white-space: nowrap;
}

.brand-name {
  font-size: 0.97rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--ink) !important;
  white-space: nowrap !important;
  word-break: keep-all !important;
  overflow-wrap: normal !important;
  word-wrap: normal !important;
}

.brand-sub {
  font-size: 0.69rem;
  color: var(--muted) !important;
  margin-top: 1px;
  white-space: nowrap !important;
  word-break: keep-all !important;
  overflow-wrap: normal !important;
}
.top-meta {
  font-size: 0.73rem; color: var(--muted) !important; text-align: right; line-height: 1.4;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.top-meta b { color: var(--ink) !important; font-weight: 600; }

/* ------------------------------------------------------------ empty state */
.hero { text-align: center; padding: 2.4rem 0 1.6rem; }
.hero-mark { display: flex; justify-content: center; margin-bottom: 1.1rem; }
.hero h1 {
  font-size: clamp(1.45rem, 4.4vw, 2.05rem) !important;
  line-height: 1.18;
  letter-spacing: -0.035em;
  font-weight: 700;
  margin: 0 0 0.55rem !important;
  color: var(--ink) !important;
}
.hero-sub {
  color: var(--muted) !important; font-size: 0.95rem; line-height: 1.6;
  margin: 0 auto; max-width: 34rem;
}
.chip-row { text-align: center; margin-top: 0.2rem; }
.chip {
  display: inline-block; margin: 0.85rem 0.2rem 0;
  border: 1px solid var(--line); background: var(--panel); color: var(--muted) !important;
  border-radius: 999px; padding: 0.3rem 0.75rem; font-size: 0.74rem; line-height: 1.5;
}
.st-key-starters { margin-top: 1.1rem; }
.st-key-starters button {
  width: 100%; height: auto !important; min-height: 2.9rem;
  justify-content: flex-start !important;
  text-align: left !important; white-space: normal !important;
  padding: 0.6rem 0.8rem !important;
  border-radius: 0.8rem !important;
  border: 1px solid var(--line) !important;
  background: var(--panel) !important;
  color: var(--ink) !important;
  font-size: 0.85rem !important; font-weight: 500 !important; line-height: 1.45 !important;
  transition: border-color 120ms ease, background 120ms ease;
}
.st-key-starters button:hover {
  background: var(--hover) !important; border-color: var(--accent) !important;
}
.st-key-starters button svg { color: var(--muted) !important; flex: 0 0 auto; }
.st-key-starters button:hover svg { color: var(--accent) !important; }

/* ------------------------------------------------------------- transcript */
/* --avatar + --msg-gutter resolves to --toggle-inset, so the assistant bubble
   and the brand text in the top bar start on the same vertical line. */
div[data-testid="stChatMessage"] {
  gap: var(--msg-gutter);
  margin-top: 0.35rem;
  padding: 0.1rem 0;
  align-items: flex-start;
}
div[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
  flex: 1 1 auto;
  min-width: 0;
}
div[data-testid="stChatMessageAvatarUser"],
div[data-testid="stChatMessageAvatarAssistant"] {
  width: var(--avatar) !important;
  height: var(--avatar) !important;
  min-width: var(--avatar) !important;
  border-radius: 0.6rem !important;
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  color: var(--accent) !important;
  margin-top: 0.15rem;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"] {
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-radius: 0.35rem var(--radius) var(--radius) var(--radius);
  padding: 0.85rem 1rem;
  box-shadow: 0 6px 22px var(--shadow);
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; }
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
  background: var(--accent-soft) !important;
  border: 1px solid transparent !important;
  border-radius: var(--radius) 0.35rem var(--radius) var(--radius);
  padding: 0.6rem 0.9rem;
  max-width: 78%;
  margin-left: auto;
}
.bubble-user {
  font-size: 0.96rem; line-height: 1.55; color: var(--ink) !important; overflow-wrap: anywhere;
}
.msg-chip {
  display: inline-block; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.07em;
  text-transform: uppercase; line-height: 1.5; border-radius: 999px;
  padding: 0.2rem 0.55rem; margin-bottom: 0.6rem; border: 1px solid transparent;
}
.msg-chip.chip-ok { color: var(--accent) !important; background: var(--accent-soft) !important; }
.msg-chip.chip-stop { color: var(--warn) !important; background: var(--warn-soft) !important; }
.msg-chip.chip-miss { color: var(--muted) !important; background: var(--hover) !important; border-color: var(--line) !important; }
.msg-chip.chip-err { color: var(--danger) !important; background: var(--danger-soft) !important; }
.msg-body { font-size: 0.97rem; line-height: 1.65; color: var(--ink) !important; overflow-wrap: anywhere; }
.src-row {
  display: flex; flex-wrap: wrap; gap: 0.4rem;
  margin-top: 0.75rem; padding-top: 0.7rem; border-top: 1px solid var(--line-soft);
}
.src {
  display: inline-flex; align-items: center; max-width: 100%;
  font-size: 0.77rem; line-height: 1.35; color: var(--accent) !important;
  background: var(--accent-soft) !important; border: 1px solid transparent !important;
  border-radius: 0.55rem; padding: 0.3rem 0.55rem; text-decoration: none !important;
  overflow-wrap: anywhere;
}
.src:hover { border-color: var(--accent) !important; color: var(--accent) !important; }
.msg-foot { margin-top: 0.6rem; font-size: 0.76rem; color: var(--muted) !important; line-height: 1.45; }
.msg-disc { margin-top: 0.45rem; font-size: 0.72rem; color: var(--faint) !important; }

/* ------------------------------------------------------------ chat input */
[data-testid="stChatInput"] {
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius) !important;
  box-shadow: 0 10px 30px var(--shadow) !important;
  padding: 0.25rem !important;
}
[data-testid="stChatInput"] div { background: transparent !important; border: none !important; }
[data-testid="stChatInput"] textarea {
  background: transparent !important;
  color: var(--ink) !important;
  caret-color: var(--accent);
  font-size: 0.96rem !important;
  line-height: 1.55 !important;
  padding-top: 0.55rem !important;
  padding-bottom: 0.55rem !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--muted) !important; opacity: 1; }
[data-testid="stChatInputSubmitButton"] {
  background: var(--accent) !important;
  color: var(--on-accent) !important;
  border-radius: 0.7rem !important;
}
[data-testid="stChatInputStopButton"] {
  background: var(--danger) !important; color: #ffffff !important; border-radius: 0.7rem !important;
}
[data-testid="stSpinner"] div { color: var(--muted) !important; font-size: 0.85rem; }

/* --------------------------------------------------------------- sidebar */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"],
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { background: var(--surface) !important; }
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { padding: 0.55rem 0.9rem 0.3rem; }
[data-testid="stSidebar"] [data-testid="stLogoLink"],
[data-testid="stSidebar"] [data-testid="stLogoSpacer"] { display: none !important; }
[data-testid="stSidebarCollapseButton"] {
  color: var(--muted) !important;
  border-radius: 0.6rem !important;
  background: transparent !important;
}
[data-testid="stSidebarCollapseButton"]:hover { background: var(--hover) !important; color: var(--ink) !important; }
[data-testid="stSidebar"] .brand { padding: 0.15rem 0.1rem 0.85rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.3rem; }
.st-key-newchat button {
  background: var(--accent) !important;
  color: var(--on-accent) !important;
  border: none !important;
  border-radius: 0.7rem !important;
  min-height: 2.45rem;
  font-weight: 650 !important;
  font-size: 0.88rem !important;
  box-shadow: 0 6px 18px var(--shadow);
}
.st-key-newchat button:hover { filter: brightness(1.08); }
.nav-head {
  font-size: 0.67rem; letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--faint) !important; font-weight: 700; margin: 1.1rem 0 0.4rem 0.4rem !important;
}
.st-key-navq button {
  width: 100%; height: auto !important; min-height: 2.2rem;
  justify-content: flex-start !important;
  text-align: left !important; white-space: normal !important;
  padding: 0.45rem 0.6rem !important;
  border-radius: 0.65rem !important;
  border: 1px solid transparent !important;
  background: transparent !important;
  color: var(--ink) !important;
  font-size: 0.84rem !important; font-weight: 500 !important; line-height: 1.45 !important;
  transition: background 120ms ease, border-color 120ms ease;
}
.st-key-navq button:hover { background: var(--hover) !important; border-color: var(--line) !important; }
.st-key-navq button:hover svg { color: var(--accent) !important; }
.nav-foot {
  margin-top: 1.3rem; padding: 0.85rem 0.4rem 0.2rem;
  border-top: 1px solid var(--line);
  font-size: 0.72rem; color: var(--faint) !important; line-height: 1.6;
}
.nav-foot b { color: var(--muted) !important; font-weight: 600; }

/* ----------------------------------------------------------- responsive */
@media (max-width: 992px) {
  [data-testid="stSidebar"] { box-shadow: 14px 0 44px var(--shadow) !important; }
}
@media (max-width: 780px) {
    .st-key-topbar {
    padding-left: var(--toggle-inset) !important;
    padding-right: 0.5rem !important;
  }

  .st-key-topbar .brand {
    min-width: max-content !important;
  }

  .st-key-topbar .brand-text {
    min-width: max-content !important;
  }

  :root {
    --gutter: 0.95rem;
    --topbar: 3.4rem;
  }
  .top-meta { display: none !important; }
  .hero { padding: 1.4rem 0 1rem; }
  .hero-sub { font-size: 0.9rem; }
  [data-testid="stChatInput"] textarea { font-size: 16px !important; }
  div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
    max-width: 88%;
  }
}
@media (max-width: 560px) {
  :root {
    --toggle-inset: 2.7rem;
  }

  .brand-sub {
    display: none !important;
  }

  .brand-name {
    font-size: 0.9rem !important;
    white-space: nowrap !important;
  }

  .st-key-topbar {
    padding-left: var(--toggle-inset) !important;
    padding-right: 0.4rem !important;
  }

  .st-key-topbar button {
    font-size: 0.74rem !important;
    padding: 0 0.5rem !important;
  }

  div[data-testid="stChatMessage"]:has(
    [data-testid="stChatMessageAvatarAssistant"]
  ) [data-testid="stChatMessageContent"] {
    padding: 0.7rem 0.8rem;
  }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
"""


def _tokens(theme: str) -> str:
    colors = _PALETTE.get(theme, _PALETTE["dark"])
    tokens = "\n".join(f"  --{name}: {value};" for name, value in colors.items())
    return f":root{{{tokens}\n{_SHARED_TOKENS}\n}}"


def _mark(size: int, uid: str) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 40 40" aria-hidden="true" focusable="false">'
        f'<defs><linearGradient id="mf{uid}" x1="4" y1="2" x2="36" y2="38" gradientUnits="userSpaceOnUse">'
        f'<stop stop-color="#3ddc97"/><stop offset="1" stop-color="#00a86b"/>'
        f"</linearGradient></defs>"
        f'<rect width="40" height="40" rx="12" fill="url(#mf{uid})"/>'
        f'<text x="20" y="26.5" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="19" font-weight="700" fill="#ffffff">S</text>'
        "</svg>"
    )


def corpus_stats() -> tuple[int, str]:
    """Number of ingested documents and the newest as-of date in the corpus."""
    docs = [doc for doc in load_manifest() if doc.ingest]
    dates = [doc.as_of_date for doc in docs if doc.as_of_date]
    return len(docs), max(dates) if dates else "unknown"


def corpus_as_of() -> str:
    return corpus_stats()[1]


def _ask(question: str):
    from src.config import Settings
    from src.query.pipeline import answer_question

    return answer_question(question, Settings.from_env())


def _brand(subtitle: str, uid: str) -> str:
    return (
        '<div class="brand">'
        f'<span class="brand-mark">{_mark(30, uid)}</span>'
        '<span class="brand-text">'
        '<span class="brand-name">SBI Mutual Fund</span>'
        f'<span class="brand-sub">{html.escape(subtitle)}</span>'
        "</span></div>"
    )


def _topbar(doc_count: int, as_of: str) -> None:
    with st.container(key="topbar"):
        brand_col, meta_col, toggle_col = st.columns(
    [8, 2.5, 1.5],
    gap="small",
    vertical_alignment="center",
    wrap=False
)
        with brand_col:
            st.markdown(_brand("Official-source assistant", "tb"), unsafe_allow_html=True)
        with meta_col:
            st.markdown(
                f"<div class='top-meta'><b>{doc_count}</b> official documents &middot; as of "
                f"<b>{html.escape(as_of)}</b></div>",
                unsafe_allow_html=True,
            )
        with toggle_col:
            target = "light" if st.session_state.theme == "dark" else "dark"
            icon = ":material/light_mode:" if target == "light" else ":material/dark_mode:"
            if st.button(
                target.capitalize(),
                icon=icon,
                key="theme-toggle",
                width="stretch",
            ):
                st.session_state.theme = target
                st.rerun()


def _sidebar(doc_count: int, as_of: str) -> None:
    with st.sidebar:
        st.markdown(_brand("Official-source assistant", "sb"), unsafe_allow_html=True)
        with st.container(key="newchat"):
            if st.button(
                "New chat",
                icon=":material/add:",
                key="new-chat",
                type="primary",
                width="stretch",
            ):
                st.session_state.messages = []
                st.session_state.pop("queued", None)
                st.rerun()
        with st.container(key="navq"):
            for index, (group, questions) in enumerate(SIDEBAR_GROUPS):
                st.markdown(f"<div class='nav-head'>{html.escape(group)}</div>", unsafe_allow_html=True)
                for position, question in enumerate(questions):
                    if st.button(
                        question,
                        key=f"nav-{index}-{position}",
                        width="stretch",
                    ):
                        st.session_state.queued = question
        st.markdown(
            f"<div class='nav-foot'><b>{doc_count}</b> official SBI MF, AMFI and SEBI documents<br>"
            f"Corpus as of {html.escape(as_of)}<br>{html.escape(DISCLAIMER)}</div>",
            unsafe_allow_html=True,
        )


def _empty_state(doc_count: int) -> None:
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-mark">{_mark(56, "hero")}</div>
          <h1>{html.escape(WELCOME)}</h1>
          <div class="hero-sub">{html.escape(TAGLINE)}</div>
          <div class="chip-row">
            <span class="chip">{doc_count} official documents</span>
            <span class="chip">Every fact cited</span>
            <span class="chip">No advice, no estimates</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="starters"):
        # Always ask for two columns so a trailing odd item keeps the same width
        # as its neighbour instead of stretching across the whole row.
        for row in range(0, len(STARTERS), 2):
            pair = STARTERS[row : row + 2]
            columns = st.columns(2, gap="small", vertical_alignment="center")
            for position, question in enumerate(pair):
                with columns[position]:
                    if st.button(
                        question,
                        key=f"starter-{row}-{position}",
                        icon=":material/north_east:",
                        width="stretch",
                    ):
                        st.session_state.queued = question


def _source_link(citation: dict) -> str:
    title = str(citation.get("title") or "Source")
    page = citation.get("page_no") or 0
    label = title if not page else f"{title} (p.{page})"
    url = html.escape(str(citation.get("url") or ""), quote=True)
    if not url:
        return ""
    return f"<a class='src' href='{url}' target='_blank' rel='noopener noreferrer'>{html.escape(label)}</a>"


def _citation_row(payload: dict) -> str:
    links = "".join(_source_link(item) for item in payload.get("citations") or [])
    return f"<div class='src-row'>{links}</div>" if links else ""


def _render_answer(payload: dict) -> None:
    status = str(payload.get("status") or "error")
    # An unrecognised status must never borrow the green "cited" chip, or a
    # failure would read as a sourced answer.
    label, tone = _STATUS.get(status, _STATUS["error"])
    body = str(payload.get("answer") or "").strip()
    if not body:
        body = "I couldn't produce an answer for that. Please rephrase the question."
    parts = [
        f"<div class='msg-chip chip-{tone}'>{html.escape(label)}</div>",
        "<div class='msg-body'>" + html.escape(body).replace("\n", "<br>") + "</div>",
    ]
    if status in ("answered", "refused_advice"):
        row = _citation_row(payload)
        if row:
            parts.append(row)
    if status == "answered":
        freshness = payload.get("freshness")
        if freshness:
            parts.append(f"<div class='msg-foot'>{html.escape(str(freshness))}</div>")
    elif status == "out_of_corpus":
        parts.append(
            "<div class='msg-foot'>Try naming a scheme and a fact, for example "
            "&ldquo;expense ratio of SBI Bluechip&rdquo;.</div>"
        )
    elif status == "error":
        parts.append("<div class='msg-foot'>You can send the question again.</div>")
    parts.append(f"<div class='msg-disc'>{html.escape(DISCLAIMER)}</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _transcript() -> None:
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(
                    f"<div class='bubble-user'>{html.escape(message['content'])}</div>",
                    unsafe_allow_html=True,
                )
        else:
            with st.chat_message("assistant"):
                _render_answer(message)


def _init_state() -> None:
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "messages" not in st.session_state:
        st.session_state.messages = []


def main() -> None:
    setup_logging()
    st.set_page_config(
        page_title=TITLE,
        page_icon=":material/account_balance:",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    _init_state()

    # one st.html call per style tag: a single markdown string carrying two
    # <style> blocks loses everything after the first rule of the second one
    st.html(f"<style>{_tokens(st.session_state.theme)}</style>")
    st.html(f"<style>{_RULES}</style>")

    doc_count, as_of = corpus_stats()
    _topbar(doc_count, as_of)
    _sidebar(doc_count, as_of)

    if st.session_state.messages:
        _transcript()
    else:
        _empty_state(doc_count)

    typed = st.chat_input(PLACEHOLDER)
    queued = st.session_state.pop("queued", None)
    question = (queued or typed or "").strip()
    if not question:
        return

    with st.spinner("Checking official sources…"):
        try:
            response = _ask(question)
            answer = {
                "answer": response.answer,
                "status": response.status,
                "freshness": response.freshness,
                "citations": [
                    {"title": item.title, "url": item.url, "page_no": item.page_no}
                    for item in response.citations
                ],
            }
        except Exception:
            # Without this the failure is invisible in both the UI and the log.
            logger.exception("unhandled failure while answering a %d-char question", len(question))
            answer = {
                "answer": "Something went wrong — please retry",
                "status": "error",
                "freshness": None,
                "citations": [],
            }

    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append({"role": "assistant", **answer})
    st.rerun()


if __name__ == "__main__":
    main()
