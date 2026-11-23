import json
import streamlit as st
import streamlit.components.v1 as components
from hand_manager import Gardienne, JoueuseDeChamp
from parametres_app import (
    charger_parametres,
    formater_touche_affichage,
    libelle_avec_raccourci,
)


def _injecter_css_tablette_plein_ecran():
    """Masque les éléments superflus de l'interface et agrandit les zones tactiles."""
    st.markdown(
        """
        <style>
        /* Masquage des distractions Streamlit en mode tablette plein écran */
        header[data-testid="stHeader"],
        section[data-testid="stSidebar"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        footer {
            display: none !important;
        }

        .block-container {
            padding-top: 0.6rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
            max-width: 100% !important;
        }

        /* Zones tactiles larges et anti-double-zoom */
        .stButton > button {
            min-height: 54px !important;
            font-size: 15px !important;
            font-weight: 700 !important;
            border-radius: 10px !important;
            padding: 8px 10px !important;
            touch-action: manipulation;
        }

        /* Barre supérieure compacte */
        .tab-hud-bar {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 8px 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .tab-hud-score {
            font-size: 24px;
            font-weight: 900;
            letter-spacing: 0.5px;
            color: #ffffff;
        }
        .tab-hud-chrono {
            font-size: 22px;
            font-weight: 800;
            font-family: monospace;
            color: #38bdf8;
        }
        .tab-hud-meta {
            font-size: 12px;
            color: #94a3b8;
            font-weight: 600;
        }

        /* Bandeau joueur actif */
        .tab-focus-banner {
            background-color: #121620;
            border: 1px solid #273043;
            border-left: 5px solid #0284c7;
            border-radius: 8px;
            padding: 8px 12px;
            margin: 6px 0 10px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #f8fafc;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _injecter_raccourcis_clavier(actif: bool = True, prefix: str = "", keymap: dict | None = None):
    """
    Écoute les raccourcis clavier personnalisés sur le document parent (hors champs de saisie)
    et déclenche le bouton correspondant dans l'interface avec protection anti-rebond.
    """
    actif_js = "true" if actif else "false"
    prefix_js = prefix.replace("\\", "\\\\").replace("'", "\\'")
    keymap_json = json.dumps(keymap or {}, ensure_ascii=False)

    components.html(
        f"""
        <script>
        (function() {{
            const parentDoc = window.parent.document;
            const parentWin = window.parent;
            const IS_ACTIVE = {actif_js};
            const CTX_PREFIX = '{prefix_js}';
            const KEYMAP = {keymap_json};

            parentWin.__handstatShortcutActive = IS_ACTIVE;
            parentWin.__handstatShortcutPrefix = CTX_PREFIX;
            parentWin.__handstatKeymap = KEYMAP;

            if (parentWin.__handstatShortcutHandler) {{
                parentDoc.removeEventListener('keydown', parentWin.__handstatShortcutHandler);
            }}

            if (!IS_ACTIVE) {{
                return;
            }}

            function estVisible(el) {{
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            }}

            function cliquerBoutonParTexte(substrings) {{
                const buttons = Array.from(parentDoc.querySelectorAll('button'));
                for (const btn of buttons) {{
                    if (btn.disabled || !estVisible(btn)) continue;
                    const txt = (btn.innerText || '').trim();
                    if (substrings.some(s => txt.includes(s))) {{
                        btn.click();
                        return true;
                    }}
                }}
                return false;
            }}

            function cliquerJoueurTerrain(indexZeroBased) {{
                const buttons = Array.from(parentDoc.querySelectorAll('button'));
                const playerBtns = buttons.filter(btn => {{
                    if (btn.disabled || !estVisible(btn)) continue;
                    const txt = (btn.innerText || '').trim();
                    return txt.includes('#') && (
                        txt.startsWith('🔵') ||
                        txt.startsWith('🟢') ||
                        txt.startsWith('🟠') ||
                        txt.startsWith('🟣') ||
                        txt.startsWith('⚪')
                    );
                }});
                if (playerBtns[indexZeroBased]) {{
                    playerBtns[indexZeroBased].click();
                    return true;
                }}
                return false;
            }}

            parentWin.__handstatShortcutHandler = function(e) {{
                if (!parentWin.__handstatShortcutActive) return;
                if (e.repeat) return;

                const activeEl = parentDoc.activeElement;
                const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
                const isEditable = activeEl && (
                    tag === 'input' ||
                    tag === 'textarea' ||
                    tag === 'select' ||
                    activeEl.isContentEditable
                );
                if (isEditable || e.ctrlKey || e.metaKey || e.altKey) {{
                    return;
                }}

                const now = Date.now();
                if (now - (parentWin.__handstatLastKeyTs || 0) < 120) {{
                    return;
                }}

                const key = e.key.toLowerCase();
                const km = parentWin.__handstatKeymap || {{}};

                if (['1', '2', '3', '4', '5', '6', '7'].includes(key)) {{
                    const idx = parseInt(key, 10) - 1;
                    if (cliquerJoueurTerrain(idx)) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                    return;
                }}

                const chronoKey = (km.chrono || ' ').toLowerCase();
                if (key === chronoKey) {{
                    e.preventDefault();
                    if (cliquerBoutonParTexte(['Pause', 'Chrono'])) {{
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.annuler || 'z').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['Annuler'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.but_arret || 'b').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['+1 BUT', 'ARRÊT DÉCISIF'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.rate_encaisse || 'm').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['TIR RATÉ', 'BUT ENCAISSÉ'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.passe_decisive || 'p').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['Passe Décisive'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.perte_passe || 'e').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['Perte (Passe)'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.perte_faute || 'f').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['Perte (Faute)'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }} else if (key === (km.interception || 'i').toLowerCase()) {{
                    if (cliquerBoutonParTexte(['Interception'])) {{
                        e.preventDefault();
                        parentWin.__handstatLastKeyTs = now;
                        if (activeEl && typeof activeEl.blur === 'function') activeEl.blur();
                    }}
                }}
            }};

            parentDoc.addEventListener('keydown', parentWin.__handstatShortcutHandler);
        }})();
        </script>
        """,
        height=0,
    )


def _badge_discipline_compact(p_obj) -> str:
    nb_cr = int(getattr(p_obj, "cartons_rouges", 0) or 0)
    nb_2m = int(getattr(p_obj, "exclusions_2min", 0) or 0)
    nb_cj = int(getattr(p_obj, "cartons_jaunes", 0) or 0)
    if nb_cr > 0 or nb_2m >= 3:
        return " 🟥"
    if nb_2m > 0:
        return f" ⏱️×{nb_2m}" if nb_2m > 1 else " ⏱️"
    if nb_cj > 0:
        return " 🟨"
    return ""


def _couleur_poste_pastille(poste: str) -> str:
    if "Arrière" in poste or "Demi-centre" in poste:
        return "🔵"
    if "Ailière" in poste or "Ailier" in poste:
        return "🟢"
    if "Pivot" in poste:
        return "🟠"
    if "Gardienne" in poste or "Gardien" in poste:
        return "🟣"
    return "⚪"


def afficher_cockpit_tablette_plein_ecran(
    *,
    ctx_prefix: str,
    equipe_assignee: str,
    nom_match_actuel: str,
    L: dict,
    joueuses_actives: list,
    terrain_list: list,
    banc_list: list,
    get_membre,
    get_numero_actif,
    manager,
    total_buts_marques: int,
    total_buts_encaisses: int,
    temps_actuel_str: str,
    periode_actuelle: str,
    chrono_en_cours: bool,
    enregistrer_action,
    annuler_derniere_action,
    appliquer_exclusion_2min,
    appliquer_carton_rouge_direct,
    enregistrer_temps_mort,
    basculer_seconde_mi_temps,
    on_start_chrono,
    on_pause_chrono,
    on_ouvrir_popup_tir,
    on_quitter_mode_tablette,
    capitaine: str | None = None,
):
    """
    Affiche l'interface de saisie live plein écran sans distraction optimisée pour tablette tactile.
    """
    _injecter_css_tablette_plein_ecran()

    settings = charger_parametres()
    show_badges = bool(settings.get("show_shortcut_badges", False))

    _injecter_raccourcis_clavier(
        actif=bool(settings.get("shortcuts_enabled", True)),
        prefix=ctx_prefix,
        keymap=settings.get("keymap", {}),
    )

    focus_key = f"joueuse_focus_live_{ctx_prefix}"
    terrain_key = f"terrain_joueuses_{ctx_prefix}"
    banc_key = f"banc_joueuses_{ctx_prefix}"
    journal_key = f"journal_actions_match_{ctx_prefix}"
    att_adv_key = f"attaques_adversaires_match_{ctx_prefix}"
    temps_morts_key = f"temps_morts_match_{ctx_prefix}"

    # --- 1. BANDEAU HUD COMPACT (SCORE + CHRONO + CONTRÔLES ESSENTIELS) ---
    c_hud_main, c_hud_btn1, c_hud_btn2, c_hud_btn3 = st.columns([3.2, 1.1, 1.2, 1.2])

    with c_hud_main:
        st.markdown(
            f"""
            <div class="tab-hud-bar">
                <div>
                    <div class="tab-hud-meta">{equipe_assignee} • {nom_match_actuel}</div>
                    <div class="tab-hud-score">{total_buts_marques} — {total_buts_encaisses}</div>
                </div>
                <div style="text-align: right;">
                    <div class="tab-hud-meta">{periode_actuelle}</div>
                    <div class="tab-hud-chrono">{temps_actuel_str}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_hud_btn1:
        if chrono_en_cours:
            lbl_pause = libelle_avec_raccourci("⏸️ Pause", "chrono", settings)
            if st.button(lbl_pause, key=f"tab_pause_{ctx_prefix}", use_container_width=True):
                on_pause_chrono()
                st.rerun()
        else:
            lbl_start = libelle_avec_raccourci("▶️ Chrono", "chrono", settings)
            if st.button(lbl_start, key=f"tab_start_{ctx_prefix}", type="primary", use_container_width=True):
                on_start_chrono()
                st.rerun()

    with c_hud_btn2:
        derniere_act = st.session_state.get(journal_key, [])[-1] if st.session_state.get(journal_key) else None
        lbl_undo = libelle_avec_raccourci("↩️ Annuler", "annuler", settings)
        if st.button(
            lbl_undo,
            key=f"tab_undo_{ctx_prefix}",
            use_container_width=True,
            disabled=(derniere_act is None),
        ):
            annuler_derniere_action()
            st.rerun()

    with c_hud_btn3:
        if st.button("🖥️ Vue Complète", key=f"tab_exit_{ctx_prefix}", use_container_width=True):
            on_quitter_mode_tablette()
            st.rerun()

    # --- 2. BARRE DU 7 MAJEUR SUR LE TERRAIN (SÉLECTION TACTILE EN 1 TAP) ---
    if terrain_list:
        cols_7 = st.columns(len(terrain_list))
        for idx, nom_j in enumerate(terrain_list):
            p_item = get_membre(nom_j)
            if not p_item:
                continue
            with cols_7[idx]:
                est_actif = nom_j == st.session_state.get(focus_key)
                num_j = get_numero_actif(p_item.nom)
                pastille = _couleur_poste_pastille(p_item.poste)
                disc = _badge_discipline_compact(p_item)
                prenom = p_item.nom.split()[0]
                cap_actif = capitaine or st.session_state.get(f"capitaine_match_{ctx_prefix}")
                cap_tag = " (C)" if (cap_actif and p_item.nom == cap_actif) else ""
                badge_num = f" [{idx + 1}]" if show_badges else ""
                label = f"{pastille} #{num_j}{badge_num}\n{prenom}{cap_tag}{disc}"
                if st.button(
                    label,
                    key=f"tab_7maj_{ctx_prefix}_{nom_j}",
                    type="primary" if est_actif else "secondary",
                    use_container_width=True,
                ):
                    st.session_state[focus_key] = nom_j
                    st.rerun()

    # --- 3. PROFIL ACTIF & PUPITRE D'ACTIONS TACTILES ---
    nom_focus = st.session_state.get(focus_key)
    p_obj = get_membre(nom_focus) if nom_focus else None

    if not p_obj:
        st.warning(f"Sélectionnez un(e) {L['joueur']} sur le terrain.")
        return

    num_actif = get_numero_actif(p_obj.nom)
    if isinstance(p_obj, JoueuseDeChamp):
        resume_stat = (
            f"🎯 {p_obj.buts}/{p_obj.tirs} ({p_obj.efficacite_tirs()}%)  •  "
            f"🤝 {p_obj.passes_decisives} PD  •  "
            f"📤 {p_obj.pertes_de_balles_passe + p_obj.pertes_de_balles_faute} Pertes"
        )
    else:
        resume_stat = (
            f"🧤 {p_obj.arrets}/{p_obj.tirs_subis} ({p_obj.pourcentage_arrets()}%)  •  "
            f"🥅 {p_obj.buts_encaisses} Enc."
        )

    cap_actif = capitaine or st.session_state.get(f"capitaine_match_{ctx_prefix}")
    cap_badge = " (C)" if (cap_actif and p_obj.nom == cap_actif) else ""

    st.markdown(
        f"""
        <div class="tab-focus-banner">
            <div>
                <span style="font-size: 18px; font-weight: 800; color: #ffffff;">#{num_actif} {p_obj.nom}{cap_badge}</span>
                <span style="font-size: 13px; color: #94a3b8; margin-left: 8px;">({p_obj.poste})</span>
            </div>
            <div style="font-size: 14px; font-weight: 700; color: #38bdf8;">{resume_stat}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # =========================================================
    # PUPITRE A : JOUEUSE / JOUEUR DE CHAMP
    # =========================================================
    if isinstance(p_obj, JoueuseDeChamp):
        # Ligne 1 (Haute fréquence) : Tirs
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            lbl_but = libelle_avec_raccourci("🟢 +1 BUT", "but_arret", settings)
            if st.button(lbl_but, key=f"tab_but_{ctx_prefix}_{p_obj.nom}", type="primary", use_container_width=True):
                on_ouvrir_popup_tir(p_obj.nom, "But")
                st.rerun()
        with r1_c2:
            lbl_rate = libelle_avec_raccourci("🔴 TIR RATÉ", "rate_encaisse", settings)
            if st.button(lbl_rate, key=f"tab_rate_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                on_ouvrir_popup_tir(p_obj.nom, "Tir raté")
                st.rerun()

        # Ligne 2 (Circulation & Pertes de balle)
        r2_c1, r2_c2, r2_c3 = st.columns(3)
        with r2_c1:
            lbl_pd = libelle_avec_raccourci("🤝 Passe Décisive", "passe_decisive", settings)
            if st.button(lbl_pd, key=f"tab_pd_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.passes_decisives += 1
                enregistrer_action("Passe Décisive", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Passe décisive : #{p_obj.numero} {p_obj.nom}", icon="🤝")
                st.rerun()
        with r2_c2:
            lbl_pbp = libelle_avec_raccourci("📤 Perte (Passe)", "perte_passe", settings)
            if st.button(lbl_pbp, key=f"tab_pb_p_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.pertes_de_balles_passe += 1
                enregistrer_action("Perte de balle (Passe)", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Perte (passe) : #{p_obj.numero} {p_obj.nom}", icon="📤")
                st.rerun()
        with r2_c3:
            lbl_pbf = libelle_avec_raccourci("⚠️ Perte (Faute)", "perte_faute", settings)
            if st.button(lbl_pbf, key=f"tab_pb_f_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.pertes_de_balles_faute += 1
                enregistrer_action("Perte de balle (Faute)", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Perte (faute) : #{p_obj.numero} {p_obj.nom}", icon="⚠️")
                st.rerun()

        # Ligne 3 (Duels Offensifs & Défensifs)
        r3_c1, r3_c2, r3_c3, r3_c4 = st.columns(4)
        with r3_c1:
            if st.button("⚔️ Duel Off +", key=f"tab_dog_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.duels_off_gagnes += 1
                enregistrer_action("Duel Offensif Gagné", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Duel off. gagné : #{p_obj.numero} {p_obj.nom}", icon="⚔️")
                st.rerun()
        with r3_c2:
            if st.button("❌ Duel Off -", key=f"tab_dop_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.duels_off_perdus += 1
                enregistrer_action("Duel Offensif Perdu", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Duel off. perdu : #{p_obj.numero} {p_obj.nom}", icon="❌")
                st.rerun()
        with r3_c3:
            if st.button("🛡️ Duel Déf +", key=f"tab_ddg_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.duels_def_gagnes += 1
                enregistrer_action("Duel Défensif Gagné", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Duel déf. gagné : #{p_obj.numero} {p_obj.nom}", icon="🛡️")
                st.rerun()
        with r3_c4:
            if st.button("⚠️ Duel Déf -", key=f"tab_ddp_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.duels_def_perdus += 1
                enregistrer_action("Duel Défensif Perdu", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Duel déf. perdu : #{p_obj.numero} {p_obj.nom}", icon="⚠️")
                st.rerun()

        # Ligne 4 (Récupération défensive)
        r4_c1, r4_c2, r4_c3 = st.columns(3)
        with r4_c1:
            lbl_int = libelle_avec_raccourci("⚡ Interception", "interception", settings)
            if st.button(lbl_int, key=f"tab_int_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.interceptions += 1
                enregistrer_action("Interception", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Interception : #{p_obj.numero} {p_obj.nom}", icon="⚡")
                st.rerun()
        with r4_c2:
            if st.button("🧱 Neutralisation", key=f"tab_neut_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.neutralisations += 1
                enregistrer_action("Neutralisation", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Neutralisation : #{p_obj.numero} {p_obj.nom}", icon="🧱")
                st.rerun()
        with r4_c3:
            if st.button("🔥 Perte Provoquée", key=f"tab_prov_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.pertes_balles_provoquees += 1
                enregistrer_action("Perte de balle provoquée", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Perte provoquée : #{p_obj.numero} {p_obj.nom}", icon="🔥")
                st.rerun()

        # Ligne 5 (Discipline)
        r5_c1, r5_c2, r5_c3 = st.columns(3)
        with r5_c1:
            if st.button("🟨 Carton Jaune", key=f"tab_cj_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.cartons_jaunes += 1
                enregistrer_action("Carton Jaune", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Carton jaune : #{p_obj.numero} {p_obj.nom}", icon="🟨")
                st.rerun()
        with r5_c2:
            if st.button("⏱️ Exclusion 2 min", key=f"tab_2m_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                appliquer_exclusion_2min(p_obj)
                manager.sauvegarder_donnees()
                st.rerun()
        with r5_c3:
            if st.button("🟥 Carton Rouge", key=f"tab_cr_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                appliquer_carton_rouge_direct(p_obj)
                manager.sauvegarder_donnees()
                st.rerun()

    # =========================================================
    # PUPITRE B : GARDIENNE / GARDIEN
    # =========================================================
    elif isinstance(p_obj, Gardienne):
        g1_c1, g1_c2 = st.columns(2)
        with g1_c1:
            lbl_arret = libelle_avec_raccourci("🧤 ARRÊT DÉCISIF", "but_arret", settings)
            if st.button(lbl_arret, key=f"tab_garret_{ctx_prefix}_{p_obj.nom}", type="primary", use_container_width=True):
                on_ouvrir_popup_tir(p_obj.nom, "Arrêt décisif")
                st.rerun()
        with g1_c2:
            lbl_enc = libelle_avec_raccourci("🥅 BUT ENCAISSÉ", "rate_encaisse", settings)
            if st.button(lbl_enc, key=f"tab_genc_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                on_ouvrir_popup_tir(p_obj.nom, "But encaissé")
                st.rerun()

        g2_c1, g2_c2 = st.columns(2)
        with g2_c1:
            if st.button(f"🟢 +1 But ({L['gardien']})", key=f"tab_gbut_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.buts += 1
                p_obj.tirs += 1
                enregistrer_action(f"But ({L['gardien']})", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"But ({L['gardien'].lower()}) : #{p_obj.numero} {p_obj.nom}", icon="🟢")
                st.rerun()
        with g2_c2:
            if st.button(f"🔴 Tir Raté ({L['gardien']})", key=f"tab_grate_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.tirs += 1
                enregistrer_action(f"Tir raté ({L['gardien']})", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Tir raté ({L['gardien'].lower()}) : #{p_obj.numero} {p_obj.nom}", icon="🔴")
                st.rerun()

        g3_c1, g3_c2, g3_c3 = st.columns(3)
        with g3_c1:
            if st.button("🟨 Carton Jaune", key=f"tab_gcj_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                p_obj.cartons_jaunes += 1
                enregistrer_action("Carton Jaune", f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})", membre_nom=p_obj.nom)
                manager.sauvegarder_donnees()
                st.toast(f"Carton jaune : #{p_obj.numero} {p_obj.nom}", icon="🟨")
                st.rerun()
        with g3_c2:
            if st.button("⏱️ Exclusion 2 min", key=f"tab_g2m_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                appliquer_exclusion_2min(p_obj)
                manager.sauvegarder_donnees()
                st.rerun()
        with g3_c3:
            if st.button("🟥 Carton Rouge", key=f"tab_gcr_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                appliquer_carton_rouge_direct(p_obj)
                manager.sauvegarder_donnees()
                st.rerun()

    # --- 4. TIROIR REPLIABLE : ROTATIONS, TEMPS MORTS & SYSTÈMES ADVERSES ---
    with st.expander("🔄 Rotations Banc, Temps Morts & Systèmes Adverses", expanded=False):
        rot_c1, rot_c2, rot_c3 = st.columns([2, 2, 1.3])
        with rot_c1:
            sortant_t = st.selectbox("Sort ⬇️", terrain_list, key=f"tab_sort_{ctx_prefix}")
        with rot_c2:
            banc_opts = banc_list if banc_list else ["Aucun"]
            entrant_t = st.selectbox("Entre ⬆️", banc_opts, key=f"tab_ent_{ctx_prefix}")
        with rot_c3:
            st.write("")
            if st.button("🔄 Changer", key=f"tab_swap_{ctx_prefix}", type="primary", use_container_width=True):
                if banc_list and sortant_t in terrain_list and entrant_t in banc_list:
                    st.session_state[terrain_key].remove(sortant_t)
                    st.session_state[banc_key].remove(entrant_t)
                    st.session_state[terrain_key].append(entrant_t)
                    st.session_state[banc_key].append(sortant_t)
                    if st.session_state.get(focus_key) == sortant_t:
                        st.session_state[focus_key] = entrant_t
                    st.toast(f"{entrant_t} ➡️ {sortant_t}", icon="🔄")
                    st.rerun()

        st.markdown("---")
        tm_dict = st.session_state.get(temps_morts_key, {"equipe": 0, "adversaire": 0})
        tm_eq = int(tm_dict.get("equipe", 0))
        tm_adv = int(tm_dict.get("adversaire", 0))

        tm_col1, tm_col2, tm_col3 = st.columns(3)
        with tm_col1:
            if st.button(
                f"⏱️ TM {equipe_assignee} ({tm_eq}/3)",
                key=f"tab_tmeq_{ctx_prefix}",
                disabled=(tm_eq >= 3),
                use_container_width=True,
            ):
                enregistrer_temps_mort("equipe")
                st.rerun()
        with tm_col2:
            if st.button(
                f"⏱️ TM Adversaire ({tm_adv}/3)",
                key=f"tab_tmadv_{ctx_prefix}",
                disabled=(tm_adv >= 3),
                use_container_width=True,
            ):
                enregistrer_temps_mort("adversaire")
                st.rerun()
        with tm_col3:
            if periode_actuelle == "1ère MT":
                if st.button("⏭️ 2ème MT (30:00)", key=f"tab_2mt_{ctx_prefix}", use_container_width=True):
                    basculer_seconde_mi_temps()
                    st.rerun()
            else:
                if st.button("↩️ 1ère MT", key=f"tab_1mt_{ctx_prefix}", use_container_width=True):
                    st.session_state[f"periode_match_{ctx_prefix}"] = "1ère MT"
                    st.rerun()

        st.markdown("**Systèmes offensifs adverses :**")
        if att_adv_key not in st.session_state:
            st.session_state[att_adv_key] = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}
        sys_cols = st.columns(5)
        for idx_s, sys_nom in enumerate(["Yago", "Yego", "Montpellier", "Croisé", "Autre"]):
            with sys_cols[idx_s]:
                cnt_s = st.session_state[att_adv_key].get(sys_nom, 0)
                if st.button(f"{sys_nom} ({cnt_s})", key=f"tab_sys_{ctx_prefix}_{sys_nom}", use_container_width=True):
                    st.session_state[att_adv_key][sys_nom] = cnt_s + 1
                    enregistrer_action("Attaque adverse", f"Système {sys_nom}", systeme_adv=sys_nom)
                    st.toast(f"Système {sys_nom} (+1)", icon="📊")
                    st.rerun()

    # Rappel de la dernière saisie tout en bas pour vérification visuelle instantanée
    if derniere_act:
        st.caption(
            f"Dernière action ({derniere_act['temps']}) : **{derniere_act['type_action']}** — {derniere_act['details']}"
        )
