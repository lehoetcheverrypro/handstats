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
        equipe_assignee = session["equipe"]
        run_staff_app(equipe_assignee)