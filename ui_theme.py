
"""Shared premium Streamlit visual layer for WebQA.\n\nPresentation-only: does not change application state, API calls, or business logic.\n"""
from __future__ import annotations
import streamlit as st


def apply_theme() -> None:
    """Apply a product-specific, system/Streamlit-theme-aware visual system."""
    try:
        mode = st.context.theme.type or "light"
    except Exception:
        mode = ""
    # With no custom .streamlit theme config, Streamlit resolves the active
    # theme from the viewer's browser/OS preference (or the user's Settings).
    # Keep a safe light fallback only for older/unsupported runtimes.
    mode = str(mode or "light").lower()
    dark = mode == "dark"
    if dark:
        tokens = dict(
            page="#080c14", surface="#0f1420", surface2="#151c2b", border="rgba(148,163,184,.18)",
            text="#f4f7fb", muted="#9aa7ba", faint="#718096", field="#111827",
            shadow="0 14px 42px rgba(0,0,0,.26)", tint="#10b98114",
        )
    else:
        tokens = dict(
            page="#f7f8fc", surface="#ffffff", surface2="#f2f4f8", border="rgba(51,65,85,.14)",
            text="#172033", muted="#5f6b7d", faint="#7b8797", field="#ffffff",
            shadow="0 14px 36px rgba(15,23,42,.08)", tint="#10b9810b",
        )
    accent1 = "#10b981"; accent2 = "#06b6d4"
    css = f"""
    <style>
    :root {{
      --ui-page:{tokens['page']}; --ui-surface:{tokens['surface']}; --ui-surface-2:{tokens['surface2']};
      --ui-border:{tokens['border']}; --ui-text:{tokens['text']}; --ui-muted:{tokens['muted']};
      --ui-faint:{tokens['faint']}; --ui-field:{tokens['field']}; --ui-shadow:{tokens['shadow']};
      --ui-accent:#10b981; --ui-accent-2:#06b6d4; --ui-tint:{tokens['tint'].format(accent1=accent1)};
    }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {{
      color: var(--ui-text); background: var(--ui-page);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    [data-testid="stHeader"] {{ background: transparent; }}

    /* Keep Streamlit's native sidebar collapse/expand control usable.
       Streamlit 1.38+ uses stSidebarCollapseButton (older releases used
       collapsedControl). */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="collapsedControl"],
    [data-testid="collapsedControl"] button {{
      display: flex !important;
      visibility: visible !important;
      opacity: 1 !important;
      pointer-events: auto !important;
      position: relative;
      z-index: 100000 !important;
    }}
    [data-testid="stToolbar"] {{ visibility:hidden; height:0; }}
    #MainMenu, footer {{ visibility:hidden; }}
    .block-container {{ max-width: 1440px; padding-top: 1.4rem; padding-bottom: 7rem; }}
    section[data-testid="stSidebar"] {{
      background: linear-gradient(180deg, var(--ui-surface), var(--ui-surface-2));
      border-right: 1px solid var(--ui-border);
    }}
    section[data-testid="stSidebar"] .block-container {{ padding-top: 1.25rem; }}
    [data-testid="stCaptionContainer"] {{ color: var(--ui-muted); }}
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ color: var(--ui-text); }}
    [data-testid="stMarkdownContainer"] small {{ color: var(--ui-muted); }}
    h1, h2, h3 {{ letter-spacing:-.02em; color:var(--ui-text); }}
    h1 {{ font-weight: 800; }}
    h2, h3 {{ font-weight: 750; }}

    /* Buttons */
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {{
      border-radius: 12px !important; border:1px solid var(--ui-border) !important;
      background: var(--ui-surface) !important; color: var(--ui-text) !important;
      box-shadow: 0 2px 8px rgba(15,23,42,.05); transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
      font-weight: 650;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {{
      transform: translateY(-1px); box-shadow: 0 8px 22px rgba(15,23,42,.10); border-color: var(--ui-accent) !important;
    }}
    .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {{
      background: linear-gradient(135deg, var(--ui-accent), var(--ui-accent-2)) !important; color:#fff !important;
      border-color: transparent !important; box-shadow: 0 10px 26px var(--ui-tint);
    }}

    /* Fields */
    div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div, div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {{
      background: var(--ui-field) !important; color: var(--ui-text) !important;
      border-color: var(--ui-border) !important; border-radius: 12px !important;
    }}
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within {{
      border-color: var(--ui-accent) !important; box-shadow: 0 0 0 3px var(--ui-tint) !important;
    }}
    [data-testid="stFileUploader"] section {{
      background: linear-gradient(180deg, var(--ui-surface), var(--ui-surface-2));
      border:1px dashed color-mix(in srgb, var(--ui-accent) 48%, var(--ui-border));
      border-radius: 16px; transition: border-color .18s ease, transform .18s ease, background .18s ease;
    }}
    [data-testid="stFileUploader"] section:hover {{ transform: translateY(-1px); border-color: var(--ui-accent); }}

    /* Cards / metrics / expanders */
    [data-testid="stMetric"] {{
      background: var(--ui-surface); border:1px solid var(--ui-border); border-radius:16px;
      padding:.85rem 1rem; box-shadow: var(--ui-shadow); transition: transform .18s ease, box-shadow .18s ease;
      animation: uiFadeUp .45s ease both;
    }}
    [data-testid="stMetric"]:hover {{ transform: translateY(-2px); }}
    [data-testid="stMetricValue"] {{ color:var(--ui-text); font-weight:800; }}
    [data-testid="stExpander"] {{ border:1px solid var(--ui-border) !important; border-radius:14px !important; background:var(--ui-surface) !important; overflow:hidden; }}
    [data-testid="stExpander"] summary:hover {{ background:var(--ui-tint); }}
    [data-testid="stTabs"] [role="tab"] {{ font-weight:650; color:var(--ui-muted); }}
    [data-testid="stTabs"] [aria-selected="true"] {{ color:var(--ui-text); }}

    /* Alerts */
    [data-testid="stAlert"] {{ border-radius:14px !important; border:1px solid var(--ui-border) !important; box-shadow: 0 6px 20px rgba(15,23,42,.05); animation: uiFadeUp .35s ease both; }}

    /* Chat surfaces */
    [data-testid="stChatMessage"] {{ animation: uiFadeUp .28s ease both; }}
    [data-testid="stChatInput"] > div {{
      background: var(--ui-surface) !important; border:1px solid var(--ui-border) !important;
      border-radius:18px !important; box-shadow: var(--ui-shadow) !important;
    }}
    [data-testid="stChatInput"] textarea {{ color:var(--ui-text) !important; background:transparent !important; }}

    /* Tables */
    [data-testid="stDataFrame"] {{ border:1px solid var(--ui-border); border-radius:14px; overflow:hidden; box-shadow: 0 8px 24px rgba(15,23,42,.05); }}

    /* Utility classes used by lightweight product-specific markup */
    .premium-panel {{ background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:18px; padding:1rem 1.1rem; box-shadow:var(--ui-shadow); animation:uiFadeUp .42s ease both; }}
    .premium-kicker {{ text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; font-weight:800; color:var(--ui-accent); }}
    .premium-chip {{ display:inline-flex; align-items:center; gap:.4rem; border:1px solid var(--ui-border); background:var(--ui-tint); color:var(--ui-text); border-radius:999px; padding:.35rem .65rem; font-size:.78rem; font-weight:700; margin:.15rem .25rem .15rem 0; }}
    .premium-muted {{ color:var(--ui-muted); }}
    @keyframes uiFadeUp {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:none; }} }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation:none !important; transition:none !important; }} }}
    /* Browser/OS dark-mode fallback for the brief period before Streamlit's theme context updates. */
    @media (prefers-color-scheme: dark) {{
      :root {{
        --ui-page:#080c14; --ui-surface:#0f1420; --ui-surface-2:#151c2b;
        --ui-border:rgba(148,163,184,.18); --ui-text:#f4f7fb; --ui-muted:#9aa7ba;
        --ui-faint:#718096; --ui-field:#111827; --ui-shadow:0 14px 42px rgba(0,0,0,.26);
        --ui-tint:#10b98114;
      }}
    }}
    /* WebQA product layer */
    .webqa-hero {{ display:grid; grid-template-columns:1.45fr .8fr; gap:1rem; background:linear-gradient(135deg, var(--ui-surface), color-mix(in srgb, var(--ui-accent) 7%, var(--ui-surface))); border:1px solid var(--ui-border); border-radius:22px; padding:1.25rem 1.3rem; box-shadow:var(--ui-shadow); animation:uiFadeUp .42s ease both; }}
    .webqa-hero-main h1 {{ margin:.3rem 0 .5rem; font-size:clamp(2rem,4vw,3.5rem); line-height:1.02; }}
    .webqa-hero-main p {{ max-width:760px; color:var(--ui-muted); font-size:1.02rem; line-height:1.55; margin:0 0 .65rem; }}
    .chip-row {{ display:flex; flex-wrap:wrap; gap:.2rem; }}
    .webqa-hero-flow {{ border:1px solid var(--ui-border); background:color-mix(in srgb, var(--ui-surface-2) 84%, transparent); border-radius:17px; padding:.95rem; align-self:stretch; }}
    .flow-step {{ display:flex; gap:.7rem; align-items:flex-start; padding:.68rem .72rem; background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:12px; }}
    .flow-step b {{ color:var(--ui-accent); min-width:1.55rem; }}
    .flow-step strong, .flow-step span {{ display:block; }}
    .flow-step span {{ color:var(--ui-muted); font-size:.78rem; margin-top:.15rem; line-height:1.35; }}
    .flow-arrow {{ text-align:center; color:var(--ui-faint); line-height:1; padding:.15rem 0; }}
    /* v2 polish: stronger crawl controls and a more intentional workspace rhythm. */
    [data-testid="stForm"] {{ border-radius:18px !important; box-shadow:0 10px 28px rgba(15,23,42,.045) !important; }}
    [data-testid="stForm"] [data-testid="stTextInput"] input,
    [data-testid="stForm"] [data-testid="stTextArea"] textarea {{ border-radius:12px !important; }}
    [data-testid="stForm"] [data-testid="stSlider"] {{ padding-top:.15rem; }}
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {{ min-height:2.8rem !important; border-radius:12px !important; font-weight:800 !important; }}
    .workspace-title {{ margin-bottom:.12rem !important; }}
    .workspace-subtitle {{ margin-bottom:.65rem !important; }}
    .form-section-label {{ padding-top:.15rem; margin-bottom:.5rem !important; }}
    .form-footer {{ border-top:1px solid var(--ui-border); padding-top:.7rem !important; margin-top:.2rem !important; }}

    .webqa-ready-strip, .result-banner {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:16px; padding:.8rem 1rem; margin:.8rem 0; box-shadow:0 8px 24px rgba(15,23,42,.04); }}
    .status-dot {{ width:.55rem; height:.55rem; background:#10b981; border-radius:50%; display:inline-block; margin-right:.38rem; box-shadow:0 0 0 4px color-mix(in srgb, #10b981 14%, transparent); }}
    .webqa-muted {{ color:var(--ui-muted); }}
    .webqa-ready-metrics {{ display:flex; gap:.6rem; flex-wrap:wrap; }}
    .webqa-ready-metrics span, .result-badge {{ display:flex; gap:.16rem; flex-direction:column; padding:.38rem .58rem; border:1px solid var(--ui-border); border-radius:10px; min-width:92px; background:var(--ui-surface-2); }}
    .webqa-ready-metrics small, .result-badge small {{ color:var(--ui-faint); font-size:.62rem; letter-spacing:.08em; font-weight:800; }}
    .webqa-ready-metrics b, .result-badge b {{ color:var(--ui-text); font-size:.88rem; }}
    .workspace-kicker {{ color:var(--ui-accent); font-size:.68rem; font-weight:800; letter-spacing:.16em; margin-top:.7rem; }}
    .workspace-title {{ font-size:1.4rem; font-weight:800; letter-spacing:-.02em; margin-top:.15rem; }}
    .workspace-subtitle {{ color:var(--ui-muted); margin-bottom:.75rem; }}
    .form-section-label {{ color:var(--ui-text); font-weight:800; font-size:.8rem; letter-spacing:.04em; margin-bottom:.4rem; }}
    .form-footer {{ color:var(--ui-muted); font-size:.74rem; margin:.35rem 0 .15rem; }}
    .result-title {{ font-size:1.1rem; font-weight:800; }}
    .result-subtitle {{ color:var(--ui-muted); font-size:.78rem; margin-top:.18rem; }}
    .result-badges {{ display:flex; gap:.45rem; flex-wrap:wrap; }}
    .empty-webqa {{ display:flex; align-items:center; gap:1rem; padding:1.1rem 1.2rem; margin-top:1rem; border:1px solid var(--ui-border); border-radius:18px; background:linear-gradient(135deg,var(--ui-surface),var(--ui-surface-2)); box-shadow:var(--ui-shadow); }}
    .empty-webqa h3 {{ margin:.18rem 0 .3rem; }}
    .empty-webqa p {{ color:var(--ui-muted); margin:0; }}
    .empty-icon {{ width:3rem; height:3rem; border-radius:14px; display:grid; place-items:center; background:var(--ui-tint); color:var(--ui-accent); border:1px solid var(--ui-border); font-size:1.6rem; font-weight:800; }}
    .empty-points {{ display:flex; gap:.35rem; flex-wrap:wrap; margin-left:auto; }}
    .empty-points span {{ border:1px solid var(--ui-border); background:var(--ui-surface); padding:.34rem .52rem; border-radius:999px; font-size:.7rem; color:var(--ui-muted); font-weight:700; }}
    .sidebar-brand {{ display:flex; align-items:center; gap:.65rem; margin-bottom:.45rem; }}
    .sidebar-brand-mark {{ width:2rem; height:2rem; border-radius:.7rem; display:grid; place-items:center; background:linear-gradient(135deg,var(--ui-accent),var(--ui-accent-2)); color:#fff; font-weight:900; }}
    .sidebar-brand strong, .sidebar-brand span {{ display:block; }}
    .sidebar-brand span {{ font-size:.58rem; letter-spacing:.12em; color:var(--ui-muted); margin-top:.05rem; }}
    @media (max-width: 950px) {{ .webqa-hero {{ grid-template-columns:1fr; }} .webqa-ready-strip, .result-banner {{ flex-direction:column; align-items:flex-start; }} .empty-webqa {{ flex-direction:column; align-items:flex-start; }} .empty-points {{ margin-left:0; }} }}

    @media (max-width: 900px) {{ .block-container {{ padding-left:1rem; padding-right:1rem; }} }}
    </style>
    """
    st.html(css)
