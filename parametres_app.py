import streamlit as st

from supabase_store import SCOPE_UTILISATEURS, get_json, set_json


def _cle_parametres() -> str:
    """Les réglages (raccourcis clavier...) sont propres à chaque utilisateur."""
    username = (st.session_state.get("user_session") or {}).get("username") or "_defaut"
    return f"settings_{username}"


def _lire_parametres_stockes():
    try:
        return get_json(SCOPE_UTILISATEURS, _cle_parametres(), None)
    except Exception:
        return None

DEFAULT_KEYMAP = {
    "but_arret": "b",
    "rate_encaisse": "m",
    "passe_decisive": "p",
    "perte_passe": "e",
    "perte_faute": "f",
    "interception": "i",
    "annuler": "z",
    "chrono": " ",
}

LABELS_ACTIONS_CLAVIER = [
    ("but_arret", "🟢 +1 But / 🧤 Arrêt décisif"),
    ("rate_encaisse", "🔴 Tir raté / 🥅 But encaissé"),
    ("passe_decisive", "🤝 Passe décisive"),
    ("perte_passe", "📤 Perte de balle (Passe)"),
    ("perte_faute", "⚠️ Perte de balle (Faute)"),
    ("interception", "⚡ Interception"),
    ("annuler", "↩️ Annuler la dernière action"),
    ("chrono", "⏸️ / ▶️ Démarrer ou mettre en pause le chrono"),
]

DEFAULT_SETTINGS = {
    "shortcuts_enabled": True,
    "show_shortcut_badges": False,  # Désactivé par défaut pour garder les écrans tactiles sans clavier épurés
    "keymap": DEFAULT_KEYMAP.copy(),
}


def charger_parametres() -> dict:
    """Charge les paramètres de l'utilisateur depuis Supabase et les met en cache dans st.session_state."""
    if "handstat_settings" in st.session_state:
        return st.session_state["handstat_settings"]

    settings = {
        "shortcuts_enabled": DEFAULT_SETTINGS["shortcuts_enabled"],
        "show_shortcut_badges": DEFAULT_SETTINGS["show_shortcut_badges"],
        "keymap": DEFAULT_KEYMAP.copy(),
    }

    donnees_stockees = _lire_parametres_stockes()
    if donnees_stockees is not None:
        try:
            data = donnees_stockees
            if isinstance(data, dict):
                settings["shortcuts_enabled"] = bool(
                    data.get("shortcuts_enabled", settings["shortcuts_enabled"])
                )
                settings["show_shortcut_badges"] = bool(
                    data.get("show_shortcut_badges", settings["show_shortcut_badges"])
                )
                loaded_km = data.get("keymap", {})
                if isinstance(loaded_km, dict):
                    for k, default_v in DEFAULT_KEYMAP.items():
                        val = loaded_km.get(k, default_v)
                        if isinstance(val, str) and len(val) == 1:
                            settings["keymap"][k] = val.lower()
        except Exception:
            pass

    st.session_state["handstat_settings"] = settings
    return settings


def sauvegarder_parametres(settings: dict) -> None:
    """Sauvegarde les paramètres dans st.session_state et dans Supabase."""
    st.session_state["handstat_settings"] = settings
    try:
        set_json(SCOPE_UTILISATEURS, _cle_parametres(), settings)
    except Exception:
        pass


def formater_touche_affichage(touche: str) -> str:
    """Formate proprement une touche pour l'affichage (ex. ' ' -> 'Espace', 'b' -> 'B')."""
    if touche == " ":
        return "Espace"
    return touche.upper()


def libelle_avec_raccourci(label: str, action_key: str, settings: dict | None = None) -> str:
    """Ajoute [TOUCHE] au libellé uniquement si l'affichage des raccourcis est activé."""
    cfg = settings if settings is not None else charger_parametres()
    if not cfg.get("show_shortcut_badges", False):
        return label
    touche = cfg.get("keymap", {}).get(action_key, "")
    if not touche:
        return label
    return f"{label} [{formater_touche_affichage(touche)}]"


def afficher_page_parametres(on_retour=None):
    """
    Affiche l'écran général des paramètres de l'application.
    Structuré en onglets pour accueillir facilement de futures sections.
    """
    settings = charger_parametres()

    top_col1, top_col2 = st.columns([4, 1])
    with top_col1:
        st.markdown("## ⚙️ Paramètres de l'application")
    with top_col2:
        if on_retour is not None:
            if st.button("⬅️ Retour", key="params_btn_retour", use_container_width=True):
                on_retour()

    # Structure évolutive prête pour d'autres rubriques à l'avenir
    tab_clavier, tab_general = st.tabs(
        ["⌨️ Raccourcis & Saisie Live", "🛠️ Général & Interface (à venir)"]
    )

    with tab_clavier:
        # --- En-tête : interrupteurs demandés en haut du menu ---
        st.markdown("#### Options d'affichage et d'activation")
        c_opt1, c_opt2 = st.columns(2)
        with c_opt1:
            show_badges = st.toggle(
                "Afficher les raccourcis écrits sur les boutons",
                value=bool(settings.get("show_shortcut_badges", False)),
                help="Utile sur PC/clavier pour voir chaque touche directement sur le bouton. Laisser désactivé sur tablette tactile.",
                key="cfg_show_shortcut_badges",
            )
        with c_opt2:
            shortcuts_enabled = st.toggle(
                "Activer les raccourcis clavier en match",
                value=bool(settings.get("shortcuts_enabled", True)),
                help="Active la détection des touches clavier pendant la saisie live.",
                key="cfg_shortcuts_enabled",
            )

        st.markdown("---")
        st.markdown("#### Attribution des touches")
        st.caption(
            "Les touches **1 à 7** sont réservées à la sélection directe des joueurs sur le terrain. "
            "Saisissez 1 caractère par action (ou tapez `espace` pour la barre d'espace)."
        )

        nouveau_keymap = {}
        touches_utilisees = {}
        doublons = []

        # Grille 2 colonnes pour une lecture claire et rapide
        for idx in range(0, len(LABELS_ACTIONS_CLAVIER), 2):
            cols = st.columns(2)
            for col_offset in range(2):
                if idx + col_offset >= len(LABELS_ACTIONS_CLAVIER):
                    break
                action_id, action_label = LABELS_ACTIONS_CLAVIER[idx + col_offset]
                touche_actuelle = settings["keymap"].get(action_id, DEFAULT_KEYMAP[action_id])
                valeur_affiche = "espace" if touche_actuelle == " " else touche_actuelle.upper()

                with cols[col_offset]:
                    saisie = st.text_input(
                        action_label,
                        value=valeur_affiche,
                        max_chars=6,
                        key=f"cfg_key_{action_id}",
                    )
                    saisie_clean = (saisie or "").strip().lower()
                    if saisie_clean in ("espace", "space", ""):
                        touche_finale = " " if saisie_clean in ("espace", "space") else touche_actuelle
                    else:
                        touche_finale = saisie_clean[0]

                    if touche_finale in {"1", "2", "3", "4", "5", "6", "7"}:
                        st.warning(f"La touche `{touche_finale}` est réservée aux joueurs 1-7.")
                        touche_finale = touche_actuelle

                    nouveau_keymap[action_id] = touche_finale

                    if touche_finale in touches_utilisees:
                        doublons.append(
                            f"**{formater_touche_affichage(touche_finale)}** ({touches_utilisees[touche_finale]} & {action_label})"
                        )
                    else:
                        touches_utilisees[touche_finale] = action_label

        if doublons:
            st.error("Conflit de touches détecté sur : " + ", ".join(doublons))

        st.markdown("")
        b_save, b_reset, _ = st.columns([1.4, 1.4, 2.2])
        with b_save:
            if st.button(
                "💾 Enregistrer les réglages",
                key="cfg_save_shortcuts",
                type="primary",
                disabled=bool(doublons),
                use_container_width=True,
            ):
                new_settings = {
                    "shortcuts_enabled": shortcuts_enabled,
                    "show_shortcut_badges": show_badges,
                    "keymap": nouveau_keymap,
                }
                sauvegarder_parametres(new_settings)
                st.toast("Paramètres enregistrés !", icon="✅")

        with b_reset:
            if st.button(
                "↩️ Réinitialiser par défaut",
                key="cfg_reset_shortcuts",
                use_container_width=True,
            ):
                reset_settings = {
                    "shortcuts_enabled": True,
                    "show_shortcut_badges": False,
                    "keymap": DEFAULT_KEYMAP.copy(),
                }
                sauvegarder_parametres(reset_settings)
                for action_id, def_key in DEFAULT_KEYMAP.items():
                    st.session_state[f"cfg_key_{action_id}"] = (
                        "espace" if def_key == " " else def_key.upper()
                    )
                st.toast("Raccourcis réinitialisés.", icon="↩️")
                st.rerun()

    with tab_general:
        st.info(
            "Cet espace centralisera prochainement les préférences générales du club "
            "(durée des périodes, affichage des statistiques, exports PDF, etc.)."
        )