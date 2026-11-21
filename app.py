import streamlit as st
from theme import injecter_theme
from auth_manager import (
    _session_vide,
    afficher_espace_super_admin,
    ecran_connexion,
    init_users_db,
)
from manager_app import afficher_espace_manager
from staff_app import run_staff_app

st.set_page_config(
    page_title="HandStats Pro — Portail Central",
    page_icon="🤾‍♀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

injecter_theme()
init_users_db()
session = st.session_state.user_session

if not session["logged_in"]:
    col1, col2, col3 = st.columns([1, 1.25, 1])
    with col2:
        ecran_connexion()
else:
    role = session["role"]

    if role == "super_admin":
        afficher_espace_super_admin()

    elif role == "manager":
        club_nom = session.get("club")
        clubs_db = st.session_state.registre_app.get("clubs", {})
        if not club_nom or not clubs_db.get(club_nom, {}).get("actif", True):
            st.error("Votre club est suspendu ou introuvable. Veuillez contacter l'administrateur.")
            if st.button("🚪 Se déconnecter"):
                st.session_state.user_session = _session_vide()
                st.rerun()
        else:
            afficher_espace_manager()

    elif role in ("staff", "analyste"):
        club_nom = session.get("club")
        clubs_db = st.session_state.registre_app.get("clubs", {})
        if not club_nom or not clubs_db.get(club_nom, {}).get("actif", True):
            st.error("Votre club est suspendu ou introuvable. Veuillez contacter l'administrateur.")
            if st.button("🚪 Se déconnecter"):
                st.session_state.user_session = _session_vide()
                st.rerun()
        else:
            equipes_club = clubs_db[club_nom].get("equipes", [])
            equipes_autorisees = [eq for eq in session.get("equipes", []) if eq in equipes_club]

            if len(equipes_autorisees) > 1 and not session.get("equipe_active"):
                st.title("🎽 Sélection de l'équipe")
                st.info("Vous gérez plusieurs équipes au sein du club. Veuillez sélectionner l'équipe à piloter :")

                with st.form("form_selection_equipe"):
                    equipe_choisie = st.selectbox("Équipe", equipes_autorisees)
                    if st.form_submit_button("Accéder à l'espace équipe", type="primary", use_container_width=True):
                        st.session_state.user_session["equipe_active"] = equipe_choisie
                        st.rerun()

                if st.button("🚪 Se déconnecter", type="secondary"):
                    st.session_state.user_session = _session_vide()
                    st.rerun()
            else:
                equipe_active = session.get("equipe_active") or (equipes_autorisees[0] if equipes_autorisees else None)
                if not equipe_active:
                    st.warning("Aucune équipe active n'est assignée à votre compte sur ce club.")
                    if st.button("🚪 Se déconnecter"):
                        st.session_state.user_session = _session_vide()
                        st.rerun()
                else:
                    run_staff_app(equipe_active)