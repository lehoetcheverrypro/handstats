import streamlit as st

def init_users_db():
    """Initialise une base de données utilisateurs de test dans le session_state si elle n'existe pas."""
    if "users_db" not in st.session_state:
        st.session_state.users_db = {
            "admin": {"password": "123", "role": "manager", "nom": "Direction du Club", "club": "Bordeaux Étudiants Club", "equipe": None},
            "leho": {"password": "123", "role": "staff", "nom": "Lého", "club": "Bordeaux Étudiants Club", "equipe": "Séniors M"},
            "coach_f": {"password": "123", "role": "staff", "nom": "Marc", "club": "Bordeaux Étudiants Club", "equipe": "-18M"}
        }

    if "user_session" not in st.session_state:
        st.session_state.user_session = {
            "logged_in": False,
            "username": None,
            "role": None,
            "nom": "",
            "club": "Bordeaux Étudiants Club",
            "equipe": None
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
                st.session_state.user_session = {
                    "logged_in": True,
                    "username": username,
                    "role": user_info["role"],
                    "nom": user_info["nom"],
                    "club": user_info.get("club", "Bordeaux Étudiants Club"),
                    "equipe": user_info["equipe"]
                }
                st.success(f"Bienvenue, {user_info['nom']} !")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")

    with st.expander("ℹ️ Comptes de test par défaut"):
        st.markdown("- **Manager** : `admin` / `123`")
        st.markdown("- **Staff Séniors M** : `leho` / `123`")
        st.markdown("- **Staff -18M** : `coach_f` / `123`")

def afficher_en_tete_avec_profil(titre_principal):
    """Affiche un en-tête propre avec le titre à gauche et le bouton de profil pop-over à droite."""
    session = st.session_state.user_session
    
    # Petit espace de sécurité invisible au-dessus pour éviter toute coupe
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
                st.markdown(f"**Équipe entraînée :** `{session['equipe']}`")
                st.markdown(f"**Nombre d'équipes gérées :** 1")
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
                    "logged_in": False, "username": None, "role": None, "nom": "", "equipe": None
                }
                st.rerun()