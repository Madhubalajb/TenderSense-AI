"""
tendra_theme.py — Tendra AI Slate & Teal Theme
------------------------------------------------
Call inject_theme() once in main.py after set_page_config.
"""

import streamlit as st

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

:root {
    --slate-900: #0F172A;
    --slate-800: #1E293B;
    --slate-600: #475569;
    --slate-400: #94A3B8;
    --slate-200: #E2E8F0;
    --slate-100: #F1F5F9;
    --teal-700:  #0F766E;
    --teal-600:  #0D9488;
    --teal-50:   #F0FDFA;
    --green-600: #059669;
    --green-50:  #ECFDF5;
    --red-600:   #DC2626;
    --red-50:    #FEF2F2;
    --amber-600: #D97706;
    --amber-50:  #FFFBEB;
    --blue-600:  #2563EB;
    --blue-50:   #EFF6FF;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stSidebarNav"] { display: none !important; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

section[data-testid="stSidebar"] {
    background-color: #1E293B !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    min-width: 268px !important;
    max-width: 268px !important;
}
section[data-testid="stSidebar"] > div { padding: 0 !important; }
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label {
    color: #CBD5E1 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.07) !important;
    margin: 6px 0 !important;
}

/* Nav click-overlay buttons — invisible, just capture clicks */
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    color: transparent !important;
    font-size: 1px !important;
    padding: 0 !important;
    width: 100% !important;
    height: 36px !important;
    margin-top: -36px !important;
    position: relative !important;
    box-shadow: none !important;
    cursor: pointer !important;
}

/* Sign out button — last button in sidebar, must be visible */
section[data-testid="stSidebar"] .stButton:last-of-type > button {
    color: #94A3B8 !important;
    font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 400 !important;
    padding: 8px 14px !important;
    height: auto !important;
    margin-top: 0 !important;
    border-top: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 0 !important;
    text-align: left !important;
    width: 100% !important;
    background: transparent !important;
}
section[data-testid="stSidebar"] .stButton:last-of-type > button:hover {
    color: #FFFFFF !important;
    background: rgba(255,255,255,0.05) !important;
}

.main .block-container {
    padding: 1.75rem 2.5rem !important;
    max-width: 1120px !important;
}

h1 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: #0F172A !important;
    margin-bottom: 0.15rem !important;
    letter-spacing: -0.015em !important;
}
h2 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    color: #1E293B !important;
}
h3 {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: #334155 !important;
}

.stButton > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {
    background-color: #0D9488 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 0.45rem 1.2rem !important;
    transition: background 0.15s ease !important;
}
.stButton > button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    background-color: #0F766E !important;
}

.stInfo    { background-color: #EFF6FF !important; border-left: 3px solid #2563EB !important; border-radius: 0 6px 6px 0 !important; }
.stSuccess { background-color: #ECFDF5 !important; border-left: 3px solid #059669 !important; border-radius: 0 6px 6px 0 !important; }
.stWarning { background-color: #FFFBEB !important; border-left: 3px solid #D97706 !important; border-radius: 0 6px 6px 0 !important; }
.stError   { background-color: #FEF2F2 !important; border-left: 3px solid #DC2626 !important; border-radius: 0 6px 6px 0 !important; }

[data-testid="stFileUploader"] {
    border: 1.5px dashed #0D9488 !important;
    border-radius: 8px !important;
    background: #F0FDFA !important;
    padding: 1.25rem !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] span {
    color: #0D9488 !important;
    font-weight: 500 !important;
}

[data-testid="metric-container"] {
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    padding: 0.9rem 1.1rem !important;
}
[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 10.5px !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 600 !important;
    color: #0F172A !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

.stSelectbox > div > div,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-color: #CBD5E1 !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #0D9488 !important;
    box-shadow: 0 0 0 2px rgba(13,148,136,0.15) !important;
}

details summary { font-weight: 500 !important; color: #334155 !important; font-size: 13px !important; }

/* Hide Streamlit's native toggle completely — we replace it */
[data-testid="collapsedControl"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* Our custom toggle tab — always pinned to left edge */
#tendra-sidebar-toggle {
    position: fixed !important;
    left: 268px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    width: 20px !important;
    height: 52px !important;
    background: #0D9488 !important;
    border-radius: 0 8px 8px 0 !important;
    cursor: pointer !important;
    z-index: 99999 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 2px 2px 8px rgba(0,0,0,0.25) !important;
    transition: background 0.15s ease, left 0.3s ease !important;
    border: none !important;
}
#tendra-sidebar-toggle:hover {
    background: #0F766E !important;
    width: 24px !important;
}
#tendra-sidebar-toggle svg {
    fill: white !important;
    stroke: white !important;
    width: 12px !important;
    height: 12px !important;
    transition: transform 0.3s ease !important;
}
#tendra-sidebar-toggle.collapsed {
    left: 0 !important;
}
#tendra-sidebar-toggle.collapsed svg {
    transform: rotate(180deg) !important;
}

.stProgress > div > div > div { background-color: #0D9488 !important; }

.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid #E2E8F0 !important; }
.stTabs [data-baseweb="tab"] { font-family: 'Inter', sans-serif !important; font-size: 13px !important; }
.stTabs [aria-selected="true"] { color: #0D9488 !important; border-bottom-color: #0D9488 !important; }

hr { border-color: #E2E8F0 !important; margin: 10px 0 !important; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #0D9488; }
</style>
"""

SIDEBAR_HEADER = """
<div style="padding:18px 14px 12px;border-bottom:1px solid rgba(255,255,255,0.07);">
  <div style="display:flex;align-items:center;gap:9px;margin-bottom:7px;">
    <div style="width:32px;height:32px;background:#0D9488;border-radius:6px;
                display:flex;align-items:center;justify-content:center;flex-shrink:0;">
      <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24"
           fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/>
      </svg>
    </div>
    <span style="font-family:'Inter',sans-serif;font-size:17px;font-weight:600;
                 color:#FFFFFF;letter-spacing:-0.01em;">Tendra AI</span>
  </div>
  <div style="font-size:10px;color:#64748B;line-height:1.4;margin-bottom:7px;font-family:'Inter',sans-serif;">
    Intelligent Tender Evaluation for a Transparent Bharat
  </div>
  <div style="font-size:9.5px;color:#0D9488;font-style:italic;line-height:1.5;
              border-left:2px solid #0D9488;padding-left:6px;font-family:'Inter',sans-serif;">
    Turning paperwork into clarity — one tender at a time.
  </div>
</div>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    # Inject a custom always-visible sidebar toggle button
    st.markdown("""
    <button id="tendra-sidebar-toggle" title="Toggle sidebar" onclick="tendraToggleSidebar()">
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M15 18l-6-6 6-6" stroke="white" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      </svg>
    </button>

    <script>
    (function() {
        var SIDEBAR_WIDTH = 268;
        var isCollapsed = false;

        function tendraToggleSidebar() {
            // Click Streamlit's native hidden toggle button
            var nativeBtn = document.querySelector('[data-testid="collapsedControl"]');
            if (nativeBtn) {
                nativeBtn.click();
            }
            isCollapsed = !isCollapsed;
            updateTogglePosition();
        }
        window.tendraToggleSidebar = tendraToggleSidebar;

        function updateTogglePosition() {
            var btn = document.getElementById('tendra-sidebar-toggle');
            if (!btn) return;
            if (isCollapsed) {
                btn.style.left = '0px';
                btn.classList.add('collapsed');
            } else {
                btn.style.left = SIDEBAR_WIDTH + 'px';
                btn.classList.remove('collapsed');
            }
        }

        function detectSidebarState() {
            var sidebar = document.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return;
            var rect = sidebar.getBoundingClientRect();
            // Sidebar is collapsed when its right edge is at or near 0
            var nowCollapsed = rect.right < 10;
            if (nowCollapsed !== isCollapsed) {
                isCollapsed = nowCollapsed;
                updateTogglePosition();
            }
        }

        // Poll sidebar state every 300ms to stay in sync
        setInterval(detectSidebarState, 300);

        // Initial position check after DOM settles
        setTimeout(function() {
            detectSidebarState();
            updateTogglePosition();
        }, 500);
    })();
    </script>
    """, unsafe_allow_html=True)


def render_sidebar_header():
    st.sidebar.markdown(SIDEBAR_HEADER, unsafe_allow_html=True)


def sidebar_section(label):
    st.sidebar.markdown(
        f'<div style="font-size:9px;font-weight:600;letter-spacing:0.1em;color:#64748B;'
        f'text-transform:uppercase;padding:10px 14px 3px;font-family:\'Inter\',sans-serif;">'
        f'{label}</div>',
        unsafe_allow_html=True,
    )


def render_active_nav(label, step_num=""):
    badge = str(step_num) if step_num != "" else "→"
    st.sidebar.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;padding:7px 12px 7px 14px;'
        f'background:rgba(13,148,136,0.12);border-left:2px solid #0D9488;'
        f'font-family:\'Inter\',sans-serif;font-size:13px;font-weight:500;color:#FFFFFF;">'
        f'<span style="min-width:17px;height:17px;background:#0D9488;border-radius:50%;'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:9px;font-weight:600;color:#fff;flex-shrink:0;">{badge}</span>'
        f'{label}</div>',
        unsafe_allow_html=True,
    )


def render_nav_item(label, step_num, done=False):
    badge     = "✓" if done else str(step_num)
    badge_bg  = "#134E4A" if done else "rgba(255,255,255,0.08)"
    badge_col = "#5EEAD4" if done else "#64748B"
    st.sidebar.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;padding:7px 12px 7px 14px;'
        f'font-family:\'Inter\',sans-serif;font-size:13px;color:#CBD5E1;">'
        f'<span style="min-width:17px;height:17px;background:{badge_bg};border-radius:50%;'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:9px;color:{badge_col};flex-shrink:0;">{badge}</span>'
        f'{label}</div>',
        unsafe_allow_html=True,
    )


def render_disabled_nav(label, step_num):
    st.sidebar.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;padding:7px 12px 7px 14px;'
        f'opacity:0.38;cursor:not-allowed;font-family:\'Inter\',sans-serif;'
        f'font-size:13px;color:#94A3B8;">'
        f'<span style="min-width:17px;height:17px;background:rgba(255,255,255,0.05);'
        f'border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:9px;color:#64748B;flex-shrink:0;">{step_num}</span>'
        f'{label}</div>',
        unsafe_allow_html=True,
    )


def render_session_summary(tender_filename, num_criteria, criteria_locked,
                            eligible, ineligible, review):
    if not tender_filename:
        return
    lock = "Locked" if criteria_locked else "Unlocked"
    cline = (
        f'<div style="font-size:10.5px;color:#94A3B8;margin-bottom:2px;">'
        f'{lock} &middot; {num_criteria} criteria</div>'
    ) if num_criteria else ""
    vline = ""
    if eligible or ineligible or review:
        vline = (
            f'<div style="display:flex;gap:8px;margin-top:3px;">'
            f'<span style="font-size:10px;color:#34D399;">&#10003; {eligible}</span>'
            f'<span style="font-size:10px;color:#F87171;">&#10007; {ineligible}</span>'
            f'<span style="font-size:10px;color:#FBBF24;">&#9651; {review}</span>'
            f'</div>'
        )
    fname = tender_filename if len(tender_filename) <= 24 else tender_filename[:22] + "…"
    st.sidebar.markdown(
        f'<div style="padding:6px 14px 10px;font-family:\'Inter\',sans-serif;">'
        f'<div style="font-size:10.5px;color:#94A3B8;">{fname}</div>'
        f'{cline}{vline}</div>',
        unsafe_allow_html=True,
    )


def render_user_block(name, role, email):
    initials = "".join(w[0].upper() for w in name.split()[:2]) if name else "?"
    st.sidebar.markdown(
        f'<div style="border-top:1px solid rgba(255,255,255,0.07);'
        f'padding:10px 14px 7px;display:flex;align-items:center;gap:8px;">'
        f'<div style="width:28px;height:28px;border-radius:50%;background:#134E4A;'
        f'flex-shrink:0;display:flex;align-items:center;justify-content:center;'
        f'font-size:10px;font-weight:600;color:#5EEAD4;font-family:\'Inter\',sans-serif;">'
        f'{initials}</div>'
        f'<div><div style="font-size:12px;font-weight:500;color:#E2E8F0;">{name}</div>'
        f'<div style="font-size:10px;color:#64748B;">{role.title()} &middot; {email}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def verdict_badge_html(verdict):
    cfg = {
        "eligible":   ("Eligible",     "#ECFDF5", "#059669", "#A7F3D0"),
        "ineligible": ("Ineligible",   "#FEF2F2", "#DC2626", "#FECACA"),
        "review":     ("Needs Review", "#FFFBEB", "#D97706", "#FDE68A"),
        "pass":       ("Pass",         "#ECFDF5", "#059669", "#A7F3D0"),
        "fail":       ("Fail",         "#FEF2F2", "#DC2626", "#FECACA"),
    }
    label, bg, color, border = cfg.get(verdict, ("Unknown", "#F8FAFC", "#64748B", "#E2E8F0"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {border};'
        f'padding:2px 9px;border-radius:10px;font-size:11px;font-weight:500;">{label}</span>'
    )