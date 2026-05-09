"""Shared theme classes and CSS for Streamlit and Prefab surfaces."""

from __future__ import annotations

PREFAB_APP_CLASS = "w-full bg-white text-slate-900"
PREFAB_SURFACE_CLASS = "rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
PREFAB_MUTED_TEXT_CLASS = "text-sm text-slate-600"
PREFAB_EMPHASIS_TEXT_CLASS = "text-slate-950"

PREFAB_EMBED_STYLES = """
@import url("https://fonts.googleapis.com/css2?family=Google+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap");

html,
body {
  margin: 0;
  min-height: 0;
  background: transparent;
  color: #18161e;
  font-family: "Google Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}

#root {
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  background: transparent;
}

.pf-app-root {
  min-height: 0;
  padding: 0.875rem;
  background: transparent;
  color: #18161e;
  font-family: "Google Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}
"""

STREAMLIT_THEME_CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Google+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap");

:root {
  --db-bg: #ffffff;
  --db-surface: #ffffff;
  --db-surface-2: #f4f2fa;
  --db-border: #dfdee6;
  --db-border-soft: rgba(24, 22, 30, 0.1);
  --db-text: #18161e;
  --db-text-soft: #3f3e46;
  --db-muted: #716f77;
  --db-subtle: #9f9ea6;
  --db-accent: #2d00f7;
  --db-accent-light: #4cc9f0;
  --db-accent-dark: #f72585;
  --db-accent-strong: #2d00f7;
  --db-warn: #b45309;
  --db-shadow: 0 14px 36px rgba(24, 22, 30, 0.07);
  --db-shadow-soft: 0 1px 2px rgba(24, 22, 30, 0.04);
  --db-focus: rgba(45, 0, 247, 0.14);
  --db-font: "Google Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --db-display-font: "Google Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}

html,
body {
  background: var(--db-bg);
  color: var(--db-text);
  font-family: var(--db-font) !important;
  -webkit-font-smoothing: antialiased;
  text-rendering: geometricPrecision;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  color: var(--db-text);
  font-family: var(--db-font) !important;
  -webkit-font-smoothing: antialiased;
  text-rendering: geometricPrecision;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06) 0%, rgba(255, 255, 255, 0.82) 27rem, #ffffff 46rem),
    linear-gradient(120deg, rgba(45, 0, 247, 0.18) 0%, rgba(76, 201, 240, 0.2) 36%, rgba(244, 242, 250, 0.64) 62%, rgba(247, 37, 133, 0.16) 100%),
    var(--db-bg) !important;
}

.stApp,
.stApp p,
.stApp div,
.stApp span,
.stApp label,
.stApp button,
.stApp input,
.stApp textarea {
  font-family: var(--db-font) !important;
}

.stApp::before {
  content: "";
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 999999;
  height: 3px;
  pointer-events: none;
  background: linear-gradient(90deg, var(--db-accent), var(--db-accent-light), var(--db-accent-dark));
}

[data-testid="stHeader"] {
  height: 0 !important;
  background: transparent !important;
}

[data-testid="stSidebar"],
[data-testid="collapsedControl"] {
  display: none;
}

#MainMenu,
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="manage-app-button"],
[data-testid="baseButton-header"] {
  display: none !important;
  visibility: hidden !important;
}

.main .block-container,
[data-testid="stMainBlockContainer"] {
  max-width: 1180px;
  padding: 1.65rem 2.75rem 7.25rem;
  background: transparent !important;
}

[data-testid="stVerticalBlock"] {
  gap: 0.95rem;
}

.db-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  min-height: 2.6rem;
  margin: 0 0 1.6rem;
}

.db-logo {
  color: var(--db-text);
  font-family: var(--db-display-font) !important;
  font-size: clamp(1.65rem, 2.6vw, 2rem);
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
}

.db-topbar-meta {
  color: var(--db-muted);
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--db-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
}

.db-hero {
  margin: 0 0 1rem;
  padding: 0 0 1rem;
  border-bottom: 1px solid var(--db-border);
}

.db-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.75rem;
  color: var(--db-accent);
  font-size: 0.76rem;
  font-weight: 700;
  line-height: 1;
}

.db-eyebrow::before {
  content: "";
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  background: var(--db-accent);
  box-shadow: 0 0 0 4px rgba(45, 0, 247, 0.08);
}

.db-hero h1 {
  color: var(--db-text);
  font-family: var(--db-display-font) !important;
  font-size: clamp(1.65rem, 2.55vw, 2.35rem);
  font-weight: 800;
  line-height: 1.06;
  margin: 0 0 0.55rem;
  letter-spacing: 0;
}

.db-hero p {
  max-width: 42rem;
  margin: 0;
  color: var(--db-muted) !important;
  font-size: 0.96rem;
  line-height: 1.55;
}

.db-status-caption,
.stCaptionContainer,
[data-testid="stCaptionContainer"] {
  color: var(--db-muted) !important;
}

.db-stats-grid {
  display: grid;
  grid-template-columns: minmax(15rem, 1.4fr) minmax(8rem, 0.6fr);
  gap: 0.85rem;
  width: 100%;
}

.db-stat-card {
  min-width: 0;
  background: var(--db-surface);
  border: 1px solid var(--db-border-soft);
  border-radius: 8px;
  padding: 0.68rem 0.85rem 0.75rem;
  box-shadow: var(--db-shadow-soft);
}

.db-stat-label {
  color: var(--db-muted);
  font-size: 0.7rem;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 0.45rem;
}

.db-stat-value {
  overflow: hidden;
  color: var(--db-text);
  font-family: var(--db-display-font) !important;
  font-size: clamp(1.12rem, 1.8vw, 1.48rem);
  font-weight: 800;
  line-height: 1.05;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.db-connection-line {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.55rem;
  color: var(--db-subtle);
  font-size: 0.82rem;
  font-weight: 500;
}

.db-status-dot {
  width: 0.48rem;
  height: 0.48rem;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.12);
}

[data-testid="stMetric"],
div[data-testid="stMetric"] {
  background: var(--db-surface);
  border: 1px solid var(--db-border-soft);
  border-radius: 8px;
  padding: 0.75rem 0.9rem;
  box-shadow: var(--db-shadow-soft);
}

[data-testid="stMetric"] label,
[data-testid="stMetric"] [data-testid="stMetricLabel"] {
  color: var(--db-muted) !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--db-text) !important;
}

[data-testid="stChatMessage"] {
  background: var(--db-surface);
  border: 1px solid var(--db-border-soft);
  border-radius: 8px;
  padding: 0.9rem 1rem;
  margin-bottom: 0.85rem;
  box-shadow: var(--db-shadow-soft);
}

[data-testid="stChatMessage"] [data-testid*="stChatMessageAvatar"],
[data-testid="stChatMessage"] [data-testid*="chatAvatar"],
[data-testid="stChatMessage"] [class*="Avatar"] {
  display: none !important;
}

[data-testid="stChatMessage"] > div:first-child {
  display: none !important;
}

[data-testid="stChatMessage"] > div:nth-child(2),
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
  max-width: none !important;
}

[data-testid="stChatMessage"] p,
[data-testid="stMarkdownContainer"] {
  color: var(--db-text-soft);
}

[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
  color: var(--db-text);
}

.db-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin: 1.1rem 0 0.1rem;
  color: var(--db-text);
  font-size: 0.92rem;
  font-weight: 700;
}

.db-section-title::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--db-border);
}

div.stButton > button {
  min-height: 2.7rem;
  border-radius: 8px;
  border: 1px solid var(--db-border);
  background: var(--db-surface);
  color: var(--db-text);
  font-size: 0.94rem;
  font-weight: 600;
  line-height: 1.25;
  text-align: left !important;
  justify-content: flex-start !important;
  white-space: normal;
  box-shadow: var(--db-shadow-soft);
  transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease, color 120ms ease, background 120ms ease;
}

div.stButton > button p {
  width: 100%;
  margin: 0;
  text-align: left !important;
}

div.stButton > button > div,
div.stButton > button [data-testid="stMarkdownContainer"] {
  width: 100%;
  justify-content: flex-start !important;
  text-align: left !important;
}

div.stButton > button:hover {
  border-color: rgba(45, 0, 247, 0.48);
  color: var(--db-accent);
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(45, 0, 247, 0.08);
  transform: translateY(-1px);
}

div.stButton > button:focus:not(:active),
div.stButton > button:active {
  border-color: var(--db-accent);
  box-shadow: 0 0 0 3px var(--db-focus);
}

[data-testid="stBottom"] {
  display: flex !important;
  justify-content: center !important;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), var(--db-bg) 34%) !important;
  border-top: 0 !important;
  box-shadow: none !important;
  backdrop-filter: none;
}

[data-testid="stBottom"] > div {
  box-sizing: border-box;
  flex: 0 1 1120px !important;
  min-width: 0 !important;
  width: min(100%, 1120px) !important;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0.35rem 2.75rem 0.9rem;
  background: transparent !important;
}

[data-testid="stChatInput"],
[data-testid="stChatInput"] > div {
  background: transparent !important;
  max-width: none !important;
  width: 100% !important;
}

[data-testid="stBottomBlockContainer"] {
  padding-left: 0 !important;
  padding-right: 0 !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  width: 100% !important;
}

[data-testid="stBottomBlockContainer"] [data-testid="stVerticalBlock"] {
  gap: 0 !important;
}

[data-testid="stChatInput"] > div {
  border: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
}

[data-testid="stChatInput"] > div > div,
[data-testid="stChatInput"] textarea {
  background: #ffffff !important;
}

[data-testid="stChatInput"] > div > div {
  border: 1px solid var(--db-border) !important;
  border-radius: 12px !important;
  box-shadow: 0 16px 40px rgba(24, 22, 30, 0.08) !important;
}

[data-testid="stChatInput"],
[data-testid="stChatInput"] *,
[data-testid="stChatInput"] *::before,
[data-testid="stChatInput"] *::after {
  outline-color: transparent !important;
}

[data-testid="stChatInput"] > div > div:focus,
[data-testid="stChatInput"] > div > div:focus-visible,
[data-testid="stChatInput"] > div > div:focus-within,
[data-testid="stChatInput"] textarea:focus,
[data-testid="stChatInput"] textarea:focus-visible,
[data-testid="stChatInput"] textarea[aria-invalid="true"],
[data-testid="stChatInput"] textarea:invalid {
  border-color: rgba(45, 0, 247, 0.44) !important;
  box-shadow: 0 0 0 3px var(--db-focus), 0 16px 40px rgba(24, 22, 30, 0.08) !important;
  outline: 0 !important;
}

[data-testid="stChatInput"] textarea {
  min-height: 2.7rem !important;
  color: var(--db-text) !important;
  caret-color: var(--db-accent);
  border: 0 !important;
  outline: 0 !important;
  box-shadow: none !important;
  text-decoration: none !important;
}

[data-testid="stChatInput"] textarea::placeholder {
  color: var(--db-subtle) !important;
  opacity: 1 !important;
}

[data-testid="stChatInput"] button {
  width: 2.2rem !important;
  height: 2.2rem !important;
  margin-right: 0.3rem !important;
  border-radius: 8px !important;
  background: var(--db-accent) !important;
  color: #ffffff !important;
}

[data-testid="stChatInput"] button:disabled {
  background: #efeef5 !important;
  color: #9f9ea6 !important;
  opacity: 1 !important;
}

[data-testid="stChatInput"] button svg {
  color: currentColor !important;
}

iframe {
  border: 1px solid var(--db-border-soft);
  border-radius: 8px;
  background: var(--db-bg);
  box-shadow: var(--db-shadow-soft);
}

[data-testid="stDataFrame"],
[data-testid="stTable"] {
  border: 1px solid var(--db-border-soft);
  border-radius: 8px;
  overflow: hidden;
}

[data-testid="stExpander"] {
  border-color: var(--db-border-soft);
  background: var(--db-surface);
  border-radius: 8px;
}

@media (max-width: 760px) {
  .main .block-container,
  [data-testid="stMainBlockContainer"] {
    padding: 0.85rem 1rem 6.75rem;
  }

  .db-topbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.7rem;
    margin-bottom: 1.15rem;
  }

  .db-hero {
    margin-top: 0;
  }

  .db-hero h1 {
    font-size: 1.48rem;
    line-height: 1.05;
  }

  .db-hero p {
    font-size: 0.9rem;
  }

  .db-stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  [data-testid="stBottom"] > div {
    padding: 0.25rem 1rem 0.75rem;
  }
}
</style>
"""
