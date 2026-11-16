import streamlit as st
from auth_manager import init_users_db, ecran_connexion
from manager_app import afficher_espace_manager
from staff_app import run_staff_app

# --- CONFIGURATION GLOBALE DE LA PAGE ---
st.set_page_config(
    page_title="HandStats Pro — Portail Central",
    page_icon="🤾‍♀️",
    layout="wide"
)

# Initialisation de la base de données utilisateurs et de la session
init_users_db()
session = st.session_state.user_session

# --- ROUTAGE PRINCIPAL ---
if not session["logged_in"]:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        ecran_connexion()
else:
    role = session["role"]
    
    if role == "manager":
        afficher_espace_manager()
        
    elif role == "staff":
        equipes_autorisees = session.get("equipes", [])
        
        # S'il gère plusieurs équipes et qu'aucune n'est active pour l'instant -> Écran de sélection
        if len(equipes_autorisees) > 1 and not session.get("equipe_active"):
            st.title("🎽 Sélection de l'équipe")
            st.info("Vous gérez plusieurs équipes au sein du club. Veuillez sélectionner l'équipe que vous souhaitez piloter pour cette session :")
            
            with st.form("form_selection_equipe"):
                equipe_choisie = st.selectbox("Équipe", equipes_autorisees)
                valider_choix = st.form_submit_button("Accéder à l'espace équipe", type="primary", use_container_width=True)
                
                if valider_choix:
                    st.session_state.user_session["equipe_active"] = equipe_choisie
                    st.rerun()
                    
            if st.button("🚪 Se déconnecter", type="secondary"):
                st.session_state.user_session = {
                    "logged_in": False, "username": None, "role": None, "nom": "", "club": "Bordeaux Étudiants Club", "equipes": [], "equipe_active": None
                }
                st.rerun()
        else:
            # S'il n'a qu'une seule équipe ou si elle est déjà sélectionnée
            equipe_active = session.get("equipe_active") or (equipes_autorisees[0] if equipes_autorisees else "Séniors M")
            run_staff_app(equipe_active)