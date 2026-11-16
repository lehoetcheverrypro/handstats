import streamlit as st

def init_users_db():
    """Initialise une base de données utilisateurs avec support multi-équipe."""
    if "users_db" not in st.session_state:
        st.session_state.users_db = {
            "admin": {"password": "123", "role": "manager", "nom": "Direction du Club", "club": "Bordeaux Étudiants Club", "equipes": []},
            "leho": {"password": "123", "role": "staff", "nom": "Lého", "club": "Bordeaux Étudiants Club", "equipes": ["Séniors M", "Séniors F"]},
            "coach_f": {"password": "123", "role": "staff", "nom": "Marc", "club": "Bordeaux Étudiants Club", "equipes": ["-18M"]}
        }

    if "user_session" not in st.session_state:
        st.session_state.user_session = {
            "logged_in": False,
            "username": None,
            "role": None,
            "nom": "",
            "club": "Bordeaux Étudiants Club",
            "equipes": [],
            "equipe_active": None
        }


def ecran_connexion():
    """Écran de login unique pour tous les profils."""
    init_users_db()
    
    st.markdown("## 🔐 Connexion à *HandStats Pro*")
    
    with st.form("login_form"):
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter", use_container_width=True)
        
        if submit:
            db = st.session_state.users_db
            if username in db and db[username]["password"] == password:
                user_info = db[username]
                equipes_liste = user_info.get("equipes", [])
                
                st.session_state.user_session = {
                    "logged_in": True,
                    "username": username,
                    "role": user_info["role"],
                    "nom": user_info["nom"],
                    "club": user_info.get("club", "Bordeaux Étudiants Club"),
                    "equipes": equipes_liste,
                    # Si une seule équipe, on l'active directement. Sinon None pour forcer le choix.
                    "equipe_active": equipes_liste[0] if len(equipes_liste) == 1 else None
                }
                st.success(f"Bienvenue, {user_info['nom']} !")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")

    with st.expander("ℹ️ Comptes de test par défaut"):
        st.markdown("- **Manager** : `admin` / `123`")
        st.markdown("- **Staff (Multi-équipe)** : `leho` / `123` *(Gère Séniors M et Séniors F)*")
        st.markdown("- **Staff (-18M)** : `coach_f` / `123`")

def afficher_en_tete_avec_profil(titre_principal):
    """Affiche un en-tête propre avec le titre à gauche et le bouton de profil pop-over à droite."""
    session = st.session_state.user_session
    
    st.write("") 
    
    col_title, col_profil = st.columns([3.4, 1.6])
    
    with col_title:
        st.markdown(f"## {titre_principal}")
        
    with col_profil:
        nom_affichage = session['nom']
        with st.popover(f"👤 {nom_affichage}", use_container_width=True):
            st.markdown(f"### 🎽 Mon Profil")
            st.markdown(f"**Nom / Prénom :** {session['nom']}")
            st.markdown(f"**Rôle :** {'Club Manager' if session['role'] == 'manager' else 'Staff / Entraîneur'}")
            
            if session['role'] == 'staff':
                st.markdown(f"**Équipe active :** `{session.get('equipe_active', 'Aucune')}`")
                st.markdown(f"**Équipes gérées :** `{', '.join(session.get('equipes', []))}`")
                
                # --- RACCOURCI DE CHANGEMENT D'ÉQUIPE ACTIVE ---
                equipes_gerees = session.get('equipes', [])
                if len(equipes_gerees) > 1:
                    st.markdown("---")
                    st.markdown("#### 🔄 Changer d'équipe active")
                    equipe_actuelle = session.get('equipe_active')
                    
                    nouvelle_equipe = st.selectbox(
                        "Basculer vers :",
                        equipes_gerees,
                        index=equipes_gerees.index(equipe_actuelle) if equipe_actuelle in equipes_gerees else 0,
                        key="popover_switch_equipe"
                    )
                    
                    if nouvelle_equipe != equipe_actuelle:
                        if st.button("Confirmer le changement", type="primary", use_container_width=True):
                            st.session_state.user_session['equipe_active'] = nouvelle_equipe
                            st.rerun()

            elif session['role'] == 'manager':
                nb_eq = len(st.session_state.get("club_equipes", ["Séniors M", "Séniors F", "-18M", "-15F"]))
                st.markdown(f"**Équipes enregistrées au club :** `{nb_eq}`")
            
            st.markdown("---")
            st.markdown("#### 🔑 Sécurité & Mot de passe")
            
            with st.form(f"form_change_password_{session['username']}"):
                nouveau_mdp = st.text_input("Nouveau mot de passe", type="password")
                confirmer_mdp = st.text_input("Confirmer le mot de passe", type="password")
                valider_changement = st.form_submit_button("Modifier mon mot de passe", use_container_width=True)
                
                if valider_changement:
                    if nouveau_mdp and nouveau_mdp == confirmer_mdp:
                        username = session['username']
                        if username in st.session_state.users_db:
                            st.session_state.users_db[username]["password"] = nouveau_mdp
                            st.success("Mot de passe mis à jour avec succès !")
                    else:
                        st.error("Les mots de passe ne correspondent pas ou sont vides.")
            
            st.markdown("---")
            if st.button("🚪 Se déconnecter", type="primary", use_container_width=True):
                st.session_state.user_session = {
                    "logged_in": False, "username": None, "role": None, "nom": "", "club": "Bordeaux Étudiants Club", "equipes": [], "equipe_active": None
                }
                st.rerun()