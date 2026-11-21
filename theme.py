"""
Design system HandStats Pro.

Un seul endroit pour les couleurs, les polices et les composants d'écran
(bandeau, bloc "match en direct", tuiles de navigation).
Nécessite Streamlit >= 1.39 (st.container(key=...)).
"""
import base64
import html
import os

import streamlit as st

# ---------------------------------------------------------------------------
# Jetons de design (cohérents avec les PDF : bleu marine #0B2545)
# ---------------------------------------------------------------------------
NAVY = "#0B2545"      # identité, bandeaux, titres
BLUE = "#1E5BD8"      # actions principales
SKY = "#38BDF8"       # accent sur fond sombre
LIVE = "#D90429"      # réservé au match en cours et aux alertes
BG = "#F3F5F8"        # fond d'application
LINE = "#D9DFE7"      # bordures
INK = "#0F172A"       # texte
MUTED = "#5B6B7F"     # texte secondaire

# Demi-terrain de handball (ligne de but, zone 6 m, jet franc 9 m, point des 7 m)
_TERRAIN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 420" fill="none" '
    'stroke="rgba(56,189,248,0.20)" stroke-width="3">'
    '<path d="M0 40H800"/>'
    '<rect x="347" y="22" width="106" height="18" fill="rgba(56,189,248,0.20)" stroke="none"/>'
    '<path d="M137.5 40A210 210 0 0 0 347.5 250H452.5A210 210 0 0 0 662.5 40"/>'
    '<path d="M32.5 40A315 315 0 0 0 347.5 355H452.5A315 315 0 0 0 767.5 40" stroke-dasharray="14 12"/>'
    '<path d="M380 285H420"/>'
    "</svg>"
)

_ICONES = {
    "stats": (
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" '
        'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 20h16M7 20v-6M12 20V6M17 20v-10"/></svg>'
    ),
    "effectif": (
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" '
        'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/>'
        '<path d="M16 5.3a3 3 0 0 1 0 5.4M18 14.4c1.9.8 3 2.6 3 5.6"/></svg>'
    ),
}

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Semi+Condensed:wght@500;600;700&display=swap');
:root{color-scheme:dark;--hs-navy:#121620;--hs-navy-2:#1A2030;--hs-blue:#2563EB;--hs-sky:#38BDF8;--hs-live:#EF4444;--hs-bg:#07090E;--hs-card:#121620;--hs-line:#273043;--hs-ink:#FFFFFF;--hs-muted:#CBD5E1;--hs-win:#22C55E;--hs-loss:#F87171;--hs-font:'Barlow','Segoe UI','Helvetica Neue',Arial,sans-serif;--hs-title:'Barlow Semi Condensed','Arial Narrow','Segoe UI',sans-serif;}
html,body,.stApp,.stApp button,.stApp input,.stApp textarea,.stApp label,.stApp p,.stApp li,.stApp td,.stApp th{font-family:var(--hs-font);color:#FFFFFF;}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#07090E;color:#FFFFFF;}
.stApp p,.stApp li,.stApp label,.stApp td,.stApp th,.stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stWidgetLabel"] p,.stApp [data-testid="stExpander"] summary p{color:#FFFFFF;}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p{color:#CBD5E1;}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp [data-testid="stMetricValue"]{font-family:var(--hs-title) !important;color:#FFFFFF;}
.stApp h1{font-weight:700;font-size:2rem;letter-spacing:-0.01em;}
.stApp h2{font-weight:700;font-size:1.55rem;letter-spacing:-0.01em;}
.stApp h3{font-weight:600;font-size:1.25rem;}
.stApp h4{font-weight:600;font-size:1.08rem;}
[data-testid="stHeader"]{background:transparent;}
#MainMenu,footer,[data-testid="stAppDeployButton"],.stAppDeployButton{display:none !important;}
.block-container{max-width:1280px;padding:1.2rem 2rem 2.5rem;}
input,textarea,[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"]{background-color:#1A2030 !important;color:#FFFFFF !important;}
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border-color:#273043 !important;border-radius:8px !important;}
[data-baseweb="select"]>div,[data-baseweb="select"] *{background-color:#1A2030;color:#FFFFFF;}
[data-baseweb="popover"] ul,[data-baseweb="popover"] li,[data-baseweb="menu"],[data-baseweb="menu"] li{background-color:#1A2030 !important;color:#FFFFFF !important;}
[data-baseweb="popover"] li:hover{background-color:#242D42 !important;}
[data-testid="stPopoverBody"]{background:#121620;border:1px solid #273043;border-radius:10px;}
[data-testid="stPopoverBody"] p,[data-testid="stPopoverBody"] label,[data-testid="stPopoverBody"] li,[data-testid="stPopoverBody"] span{color:#FFFFFF;}
[data-testid="stPopoverBody"] h1,[data-testid="stPopoverBody"] h2,[data-testid="stPopoverBody"] h3,[data-testid="stPopoverBody"] h4{color:#FFFFFF;}
.stApp .stButton>button,.stApp .stDownloadButton>button,.stApp [data-testid="stFormSubmitButton"]>button,[data-testid="stPopoverBody"] .stButton>button{border-radius:8px;font-weight:600;transition:background-color .15s,border-color .15s,color .15s;}
.stApp [data-testid="stBaseButton-secondary"],.stApp button[kind="secondary"],.stApp [data-testid="stBaseButton-secondaryFormSubmit"]{background:#1A2030;color:#FFFFFF;border:1px solid #273043;}
.stApp [data-testid="stBaseButton-secondary"] *,.stApp button[kind="secondary"] *{color:#FFFFFF;}
.stApp [data-testid="stBaseButton-secondary"]:hover,.stApp button[kind="secondary"]:hover{border-color:#38BDF8;background:#232C40;}
.stApp [data-testid="stBaseButton-primary"],.stApp button[kind="primary"],.stApp [data-testid="stBaseButton-primaryFormSubmit"]{background:#2563EB;color:#FFFFFF;border:1px solid #2563EB;}
.stApp [data-testid="stBaseButton-primary"] *,.stApp button[kind="primary"] *,.stApp [data-testid="stBaseButton-primaryFormSubmit"] *{color:#FFFFFF;}
.stApp [data-testid="stBaseButton-primary"]:hover,.stApp button[kind="primary"]:hover{background:#1D4ED8;border-color:#1D4ED8;}
.stApp .stButton>button:disabled{opacity:.5;}
.stApp .stButton>button:focus-visible,.stApp [data-testid="stFormSubmitButton"]>button:focus-visible{outline:3px solid var(--hs-sky);outline-offset:2px;}
[data-testid="stMetric"]{background:#121620;border:1px solid #273043;border-radius:10px;padding:.85rem 1rem;}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{font-weight:700;font-variant-numeric:tabular-nums;color:#FFFFFF;}
[data-testid="stMetricLabel"] p{color:#CBD5E1;font-weight:500;}
.stTabs [data-baseweb="tab-list"]{gap:.25rem;border-bottom:1px solid #273043;background:transparent;}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:.6rem 1rem;background:transparent;color:#CBD5E1;}
.stTabs [aria-selected="true"]{color:#FFFFFF;}
[data-testid="stExpander"]{border-radius:10px;border:1px solid #273043;background:#121620;}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{color:#FFFFFF;}
[data-testid="stAlert"] p,[data-testid="stAlert"] li{color:inherit;}
[data-testid="stHorizontalBlock"]:has(.hs-brand){background:#121620;border:1px solid #273043;border-radius:10px;padding:.6rem 1rem;margin-bottom:1rem;align-items:center;}
.hs-brand{display:flex;align-items:center;gap:.85rem;}
.hs-brand-logo{width:44px;height:44px;border-radius:8px;object-fit:contain;background:#1A2030;border:1px solid #273043;}
.hs-brand-mono{width:44px;height:44px;border-radius:8px;background:#1A2030;border:1px solid #273043;color:#FFFFFF;display:flex;align-items:center;justify-content:center;font-family:var(--hs-title);font-weight:700;font-size:1.1rem;letter-spacing:.02em;}
.hs-brand-title{font-family:var(--hs-title);font-weight:700;font-size:1.5rem;line-height:1.1;color:#FFFFFF;}
.hs-brand-sub{font-size:.9rem;color:#CBD5E1;margin-top:2px;}
[data-testid="stSidebar"]{background:var(--hs-navy);border-right:none;}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{display:none;}
[data-testid="stSidebar"] *{color:#D6E2F2;}
[data-testid="stSidebarContent"]{padding:1.3rem .9rem;}
.hs-side-brand{font-family:var(--hs-title);font-weight:700;font-size:1.55rem;line-height:1;color:#fff !important;letter-spacing:-0.01em;}
.hs-side-team{margin:1.1rem 0 1.2rem;padding:.75rem .85rem;border-radius:8px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);}
.hs-side-team-name{font-family:var(--hs-title);font-weight:600;font-size:1.15rem;color:#fff !important;}
.hs-side-team-club{font-size:.85rem;color:#9FB4D0 !important;margin-top:2px;}
[data-testid="stSidebar"] .stButton>button{background:transparent !important;border:none !important;box-shadow:none;justify-content:flex-start;min-height:44px;padding:0 .9rem;border-radius:8px;}
[data-testid="stSidebar"] .stButton>button *{color:#C5D5EA !important;text-align:left;font-weight:500;}
[data-testid="stSidebar"] .stButton>button>div{justify-content:flex-start;}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(255,255,255,.08) !important;}
[data-testid="stSidebar"] .stButton>button:hover *{color:#fff !important;}
[data-testid="stSidebar"] button[kind="primary"],[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]{background:rgba(56,189,248,.16) !important;box-shadow:inset 3px 0 0 var(--hs-sky);}
[data-testid="stSidebar"] button[kind="primary"] *,[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] *{color:#fff !important;font-weight:600;}
[data-testid="stSidebar"] .stButton>button:disabled{opacity:.4;}
.st-key-hs-hero,.st-key-hs-hero-live{background:var(--hs-navy);border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:1rem;}
.st-key-hs-hero-live{box-shadow:inset 5px 0 0 var(--hs-live);}
.hs-hero-title{font-family:var(--hs-title);font-weight:700;font-size:1.65rem;line-height:1.1;color:#fff;margin:0 0 .35rem;}
.hs-hero-text{font-size:1rem;line-height:1.45;color:#B9C9DF;max-width:60ch;}
.hs-live-pill{display:inline-flex;align-items:center;gap:.45rem;background:rgba(217,4,41,.2);color:#FFB3C0;border-radius:999px;padding:.15rem .7rem;font-weight:600;font-size:.85rem;margin-bottom:.5rem;}
.hs-live-dot{width:9px;height:9px;border-radius:50%;background:#FF4D6A;animation:hs-pulse 1.6s ease-in-out infinite;}
@keyframes hs-pulse{0%,100%{opacity:1}50%{opacity:.35}}
@media (prefers-reduced-motion:reduce){.hs-live-dot{animation:none;}}
.hs-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.7rem;}
.hs-chip{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.18);color:#E6EEF9;border-radius:6px;padding:.25rem .65rem;font-size:.9rem;font-variant-numeric:tabular-nums;}
.hs-hero-lock{color:#B9C9DF;font-size:.85rem;text-align:center;margin-top:.5rem;}
.st-key-hs-hero [data-testid="stBaseButton-primary"],.st-key-hs-hero button[kind="primary"]{min-height:54px;font-size:1.05rem;border:none;background:#fff !important;}
.st-key-hs-hero [data-testid="stBaseButton-primary"] *,.st-key-hs-hero button[kind="primary"] *{color:var(--hs-navy) !important;}
.st-key-hs-hero [data-testid="stBaseButton-primary"]:hover,.st-key-hs-hero button[kind="primary"]:hover{background:#E4EDFA !important;}
.st-key-hs-hero-live [data-testid="stBaseButton-primary"],.st-key-hs-hero-live button[kind="primary"]{min-height:54px;font-size:1.05rem;border:none;background:var(--hs-live) !important;}
.st-key-hs-hero-live [data-testid="stBaseButton-primary"] *,.st-key-hs-hero-live button[kind="primary"] *{color:#fff !important;}
.st-key-hs-hero-live [data-testid="stBaseButton-primary"]:hover,.st-key-hs-hero-live button[kind="primary"]:hover{background:#B80322 !important;}
.hs-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin-bottom:14px;}
.hs-kpi{background:#121620;border:1px solid #273043;border-radius:10px;padding:.85rem 1rem .8rem;}
.hs-kpi-label{font-size:.88rem;font-weight:500;color:#CBD5E1;}
.hs-kpi-value{font-family:var(--hs-title);font-weight:700;font-size:2.3rem;line-height:1.1;color:#FFFFFF;font-variant-numeric:tabular-nums;margin-top:.15rem;}
.hs-kpi-value small{font-size:1.1rem;font-weight:600;color:#CBD5E1;margin-left:.15rem;}
.hs-kpi-foot{font-size:.85rem;color:#CBD5E1;margin-top:.1rem;font-variant-numeric:tabular-nums;}
.hs-cols{display:grid;grid-template-columns:1.55fr 1fr;gap:12px;margin-bottom:14px;}
@media (max-width:900px){.hs-cols{grid-template-columns:1fr;}}
.hs-card{background:#121620;border:1px solid #273043;border-radius:10px;padding:1rem 1.15rem;}
.hs-card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;}
.hs-card-title{font-family:var(--hs-title);font-weight:700;font-size:1.2rem;color:#FFFFFF;}
.hs-form{display:flex;gap:4px;}
.hs-res{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:6px;font-weight:700;font-size:.85rem;}
.hs-res-v{background:#DCFCE7;color:#166534;}
.hs-res-n{background:#E5E9EF;color:#475569;}
.hs-res-d{background:#FEE2E2;color:#991B1B;}
.hs-row{display:grid;grid-template-columns:34px 1fr auto 52px;align-items:center;gap:10px;padding:.55rem 0;border-top:1px solid #273043;}
.hs-row:first-of-type{border-top:none;}
.hs-row-name{color:#FFFFFF;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.hs-row-score{font-family:var(--hs-title);font-weight:700;font-size:1.25rem;color:#FFFFFF;font-variant-numeric:tabular-nums;}
.hs-row-diff{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;}
.hs-pos{color:#22C55E;} .hs-neg{color:#F87171;} .hs-nul{color:#CBD5E1;}
.hs-lead{margin:.55rem 0 .8rem;}
.hs-lead-top{display:flex;justify-content:space-between;color:#FFFFFF;font-weight:500;margin-bottom:4px;}
.hs-lead-top b{font-family:var(--hs-title);font-size:1.15rem;color:#FFFFFF;font-variant-numeric:tabular-nums;}
.hs-bar{height:7px;border-radius:4px;background:#1A2030;overflow:hidden;}
.hs-bar i{display:block;height:100%;background:#2563EB;border-radius:4px;}
.hs-empty{padding:1.2rem .2rem;color:#CBD5E1;line-height:1.5;}
.hs-empty b{color:#FFFFFF;}
[class*="st-key-hs-tile"]{background:#121620;border:1px solid #273043;border-radius:10px;padding:1.1rem 1.25rem 1rem;}
.hs-tile-icon{width:38px;height:38px;border-radius:8px;background:#1A2030;border:1px solid #273043;color:#38BDF8;display:flex;align-items:center;justify-content:center;margin-bottom:.7rem;}
.hs-tile-title{font-family:var(--hs-title);font-weight:700;font-size:1.25rem;color:#FFFFFF;margin-bottom:.2rem;}
.hs-tile-text{color:#CBD5E1;font-size:.95rem;line-height:1.5;min-height:3em;margin-bottom:.4rem;}
[class*="st-key-hs-tile"] .stButton>button{min-height:46px;}
"""

_CSS_CONNEXION = """
.stApp{background-color:var(--hs-navy);background-image:url("data:image/svg+xml;base64,__TERRAIN__");background-repeat:no-repeat;background-position:right -6vmin top -2vmin;background-size:min(85vw,860px);}
[data-testid="stHeader"]{display:none;}
.block-container{padding-top:7vh;}
.hs-login-brand{text-align:left;margin-bottom:1.4rem;}
.hs-login-name{font-family:var(--hs-title);font-weight:700;font-size:2.7rem;line-height:1;color:#fff;letter-spacing:-0.01em;}
.hs-login-tag{color:#B9C9DF;font-size:1.05rem;line-height:1.45;margin-top:.6rem;max-width:34ch;}
[data-testid="stForm"]{background:#121620;border:1px solid #273043;border-radius:12px;padding:1.8rem 1.8rem 1.5rem;box-shadow:0 24px 60px rgba(0,0,0,.45);}
[data-testid="stForm"] label,[data-testid="stForm"] p{color:#FFFFFF !important;}
.hs-form-title{font-family:var(--hs-title);font-weight:700;font-size:1.4rem;color:#FFFFFF;margin-bottom:.9rem;}
[data-testid="stForm"] [data-testid="stFormSubmitButton"]>button{min-height:48px;font-size:1.02rem;}
[data-testid="stExpander"]{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.18);}
[data-testid="stExpander"] summary,[data-testid="stExpander"] p,[data-testid="stExpander"] li{color:#D6E2F2;}
[data-testid="stExpander"] code{background:rgba(255,255,255,.14);color:#fff;}
"""


def injecter_theme() -> None:
    st.markdown(f"<style>{_CSS.strip()}</style>", unsafe_allow_html=True)


def injecter_theme_connexion() -> None:
    svg64 = base64.b64encode(_TERRAIN_SVG.encode("utf-8")).decode("ascii")
    css = _CSS_CONNEXION.replace("__TERRAIN__", svg64).strip()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _initiales(nom: str) -> str:
    mots = [m for m in str(nom).replace("-", " ").split() if m]
    if not mots:
        return "HS"
    if len(mots) == 1:
        return mots[0][:2].upper()
    return (mots[0][0] + mots[1][0]).upper()


def _logo_data_uri(club_slug) -> str | None:
    """Retourne le logo du club (logo_club.png) en data-URI s'il existe."""
    if not club_slug:
        return None
    try:
        from hand_manager import get_dossier_club

        chemin = os.path.join(get_dossier_club(club_slug), "logo_club.png")
        if os.path.exists(chemin):
            with open(chemin, "rb") as f:
                return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        pass
    return None


def html_bandeau_marque(titre: str, sous_titre: str | None, club_nom: str | None, club_slug) -> str:
    """HTML du bloc marque (logo ou monogramme + titre + sous-titre)."""
    logo = _logo_data_uri(club_slug)
    if logo:
        visuel = f'<img class="hs-brand-logo" src="{logo}" alt="">'
    else:
        mono = html.escape(_initiales(club_nom or titre or "HS"))
        visuel = f'<div class="hs-brand-mono">{mono}</div>'
    sous = f'<div class="hs-brand-sub">{html.escape(sous_titre)}</div>' if sous_titre else ""
    return (
        f'<div class="hs-brand">{visuel}<div>'
        f'<div class="hs-brand-title">{html.escape(titre)}</div>{sous}</div></div>'
    )


def hero_match(
    cle: str,
    equipe: str,
    peut_saisir: bool,
    en_cours: bool,
    nom_match: str = "Match",
    tm_equipe: int = 0,
    tm_adversaire: int = 0,
) -> bool:
    """Bloc principal de l'accueil. Retourne True si le bouton est cliqué."""
    with st.container(key="hs-hero-live" if en_cours else "hs-hero"):
        c_txt, c_btn = st.columns([2.4, 1], vertical_alignment="center", gap="large")
        with c_txt:
            if en_cours:
                contenu = (
                    '<div class="hs-live-pill"><span class="hs-live-dot"></span>Match en cours</div>'
                    f'<div class="hs-hero-title">{html.escape(str(nom_match))}</div>'
                    '<div class="hs-hero-text">Le match n\'a pas été archivé. Vos données et votre chrono sont sauvegardés.</div>'
                    '<div class="hs-chips">'
                    f'<span class="hs-chip">Temps morts {html.escape(equipe)} : {tm_equipe}/3</span>'
                    f'<span class="hs-chip">Temps morts adversaire : {tm_adversaire}/3</span>'
                    "</div>"
                )
            else:
                contenu = (
                    '<div class="hs-hero-title">Match en direct</div>'
                    '<div class="hs-hero-text">Saisie en temps réel des tirs, duels, pertes de balle et sanctions, '
                    "avec chrono et suivi des temps morts.</div>"
                )
            st.markdown(contenu, unsafe_allow_html=True)
        with c_btn:
            clic = st.button(
                "Reprendre le match" if en_cours else "Lancer un match",
                type="primary",
                use_container_width=True,
                disabled=not peut_saisir,
                key=f"btn_hero_{cle}",
            )
            if not peut_saisir:
                st.markdown(
                    '<div class="hs-hero-lock">Saisie de match désactivée pour votre profil</div>',
                    unsafe_allow_html=True,
                )
    return clic


def tuile_navigation(cle: str, icone: str, titre: str, texte: str, label_bouton: str) -> bool:
    """Tuile de navigation (icône, titre, description, bouton). Retourne True si cliqué."""
    with st.container(key=f"hs-tile-{cle}"):
        st.markdown(
            f'<div class="hs-tile-icon">{_ICONES.get(icone, "")}</div>'
            f'<div class="hs-tile-title">{html.escape(titre)}</div>'
            f'<div class="hs-tile-text">{html.escape(texte)}</div>',
            unsafe_allow_html=True,
        )
        return st.button(label_bouton, use_container_width=True, key=f"btn_tuile_{cle}")


def barre_laterale(pages, page_active, equipe, club, desactives=(), match_en_cours=False):
    """Navigation latérale (staff). Retourne la clé de page cliquée, sinon None."""
    choix = None
    with st.sidebar:
        st.markdown(
            '<div class="hs-side-brand">HandStats Pro</div>'
            '<div class="hs-side-team">'
            f'<div class="hs-side-team-name">{html.escape(str(equipe))}</div>'
            f'<div class="hs-side-team-club">{html.escape(str(club))}</div></div>',
            unsafe_allow_html=True,
        )
        for cle, label in pages:
            if cle == "match" and match_en_cours:
                label = f"{label} (en cours)"
            if st.button(
                label,
                key=f"hs_nav_{cle}",
                type="primary" if cle == page_active else "secondary",
                use_container_width=True,
                disabled=cle in desactives,
            ):
                choix = cle
    return choix


def masquer_barre_laterale() -> None:
    """Mode match : plein écran, sans navigation."""
    st.markdown(
        '<style>[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],'
        '[data-testid="collapsedControl"]{display:none !important;}</style>',
        unsafe_allow_html=True,
    )


def kpi_html(label: str, valeur: str, pied: str = "", unite: str = "") -> str:
    u = f"<small>{html.escape(unite)}</small>" if unite else ""
    p = f'<div class="hs-kpi-foot">{html.escape(pied)}</div>' if pied else ""
    return (
        f'<div class="hs-kpi"><div class="hs-kpi-label">{html.escape(label)}</div>'
        f'<div class="hs-kpi-value">{html.escape(str(valeur))}{u}</div>{p}</div>'
    )
