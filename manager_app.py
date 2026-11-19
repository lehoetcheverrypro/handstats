import streamlit as st
import pandas as pd
import os
import zipfile
import io
from auth_manager import afficher_en_tete_avec_profil, sauvegarder_registre
from hand_manager import (
    EquipeManager,
    get_dossier_club,
    get_nom_fichier_equipe,
)
from pdf_club import generer_pdf_bilan_global


def _get_club_slug_courant() -> str:
    return st.session_state.get("user_session", {}).get("club_slug") or "bordeaux_etudiants_club"


def get_team_stats(eq_name, club_slug=None):
    """Récupère et calcule les statistiques clés d'une équipe à partir de son dossier club."""
    slug = club_slug or _get_club_slug_courant()
    nom_fichier = get_nom_fichier_equipe(eq_name)
    try:
        manager_eq = EquipeManager(fichier=nom_fichier, club_slug=slug)
    except Exception:
        return {"matchs": 0, "victoires": 0, "moy_buts": 0.0, "matchs_details": []}

    matchs_dict = {}
    for j in manager_eq.joueuses.values():
        for m in j.historique_matchs:
            m_nom = m.get("match")
            if m_nom and m_nom not in matchs_dict:
                matchs_dict[m_nom] = {
                    "score_eq": m.get("score_equipe", 0),
                    "score_adversaire": m.get("score_adversaire", 0),
                }

    nb_matchs = len(matchs_dict)
    if nb_matchs == 0:
        return {"matchs": 0, "victoires": 0, "moy_buts": 0.0, "matchs_details": []}

    victoires = 0
    total_buts = 0
    matchs_details = []

    for m_nom, data in matchs_dict.items():
        s_eq = data["score_eq"]
        s_adv = data.get("score_adversaire", 0)
        total_buts += s_eq
        if s_eq > s_adv:
            victoires += 1
        matchs_details.append({"match": m_nom, "score_eq": s_eq, "score_adv": s_adv})

    moy_buts = round(total_buts / nb_matchs, 1)
    return {
        "matchs": nb_matchs,
        "victoires": victoires,
        "moy_buts": moy_buts,
        "matchs_details": matchs_details,
    }


def afficher_espace_manager():
    club_actuel = st.session_state.user_session.get("club") or "Mon Club"
    club_slug = _get_club_slug_courant()
    dossier_club = get_dossier_club(club_slug)

    reg = st.session_state.get("registre_app", {})
    clubs_reg = reg.get("clubs", {})
    if club_actuel in clubs_reg:
        st.session_state.club_equipes = list(clubs_reg[club_actuel].get("equipes", []))
    elif "club_equipes" not in st.session_state:
        st.session_state.club_equipes = ["Séniors M", "Séniors F", "-18M", "-15F"]

    # En-tête combiné Titre + Profil
    afficher_en_tete_avec_profil(f"👔 Espace Club Manager — {club_actuel}")

    st.info(
        f"Bienvenue dans le panneau de direction de **{club_actuel}**. "
        "Suivez en un coup d'œil les performances globales de toutes vos équipes et gérez les accès."
    )

    tab_stats_globales, tab_equipes, tab_staffs, tab_club_config = st.tabs([
        "📊 Tableau de Bord & Bilan",
        "🛡️ Gestion des Équipes",
        "👥 Gestion des Staffs",
        "⚙️ Configuration & Logo",
    ])

    # --- ONGLET 1 : TABLEAU DE BORD & BILAN GLOBAL ---
    with tab_stats_globales:
        st.subheader("🎯 Vue d'ensemble du Club — Performances par Équipe")
        st.write("Indicateurs clés consolidés pour un suivi présidentiel et directionnel rapide.")

        equipes = st.session_state.club_equipes

        total_matchs_club = 0
        total_victoires_club = 0
        synthese_data = []

        for eq in equipes:
            stats = get_team_stats(eq, club_slug=club_slug)
            total_matchs_club += stats["matchs"]
            total_victoires_club += stats["victoires"]

            pct_victoires = round((stats["victoires"] / stats["matchs"] * 100), 1) if stats["matchs"] > 0 else 0.0

            synthese_data.append({
                "Équipe": eq,
                "Matchs Joués": stats["matchs"],
                "Victoires": stats["victoires"],
                "% Victoires": f"{pct_victoires}%",
                "Moy. Buts / Match": stats["moy_buts"],
            })

        # Métriques globales du club
        col_g1, col_g2, col_g3, col_g4 = st.columns(4)
        col_g1.metric("Équipes Actives", len(equipes))
        col_g2.metric("Total Matchs Joués", total_matchs_club)
        col_g3.metric("Total Victoires", total_victoires_club)
        pct_global_vic = round((total_victoires_club / total_matchs_club * 100), 1) if total_matchs_club > 0 else 0.0
        col_g4.metric("Taux de Victoire Global", f"{pct_global_vic}%")

        st.markdown("---")

        # Bouton d'export PDF du Bilan Global du Club
        pdf_bilan_bytes = generer_pdf_bilan_global(
            club_actuel, synthese_data, total_matchs_club, total_victoires_club, pct_global_vic
        )
        st.download_button(
            label="📥 Télécharger le Bilan Global du Club (PDF Institutionnel)",
            data=pdf_bilan_bytes,
            file_name=f"bilan_global_club_{club_actuel.replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary",
        )

        st.markdown("---")
        st.markdown("### 📋 Blocs de Synthèse par Équipe")

        cols = st.columns(2)
        for idx, eq in enumerate(equipes):
            stats = get_team_stats(eq, club_slug=club_slug)
            col_cible = cols[idx % 2]

            with col_cible:
                with st.container(border=True):
                    st.markdown(f"#### 🤾‍♀️ Équipe : **{eq}**")

                    b_col1, b_col2, b_col3 = st.columns(3)
                    b_col1.metric("Matchs", stats["matchs"])
                    b_col2.metric("Victoires", stats["victoires"])
                    b_col3.metric("Moy. Buts/Match", stats["moy_buts"])

                    if stats["matchs"] > 0:
                        derniers = ", ".join(
                            [f"{m['match']} ({m['score_eq']}-{m['score_adv']})" for m in stats["matchs_details"][-2:]]
                        )
                        st.caption(f"📌 Derniers résultats : {derniers}")
                    else:
                        st.caption("📌 Aucun match archivé pour le moment.")

        st.markdown("---")
        st.markdown("### 📈 Graphique comparatif — Moyenne de Buts Marqués par Match")
        if synthese_data:
            df_synthese = pd.DataFrame(synthese_data).set_index("Équipe")
            st.bar_chart(df_synthese[["Moy. Buts / Match"]])

    # --- ONGLET 2 : GESTION DES ÉQUIPES (AJOUT & SUPPRESSION) ---
    with tab_equipes:
        st.subheader("🛡️ Gestion des Équipes du Club")

        if st.session_state.get("club_equipes"):
            st.markdown("### 🗑️ Supprimer une équipe existante")
            with st.form("form_supprimer_equipe"):
                equipe_a_supprimer = st.selectbox("Sélectionner l'équipe à supprimer", st.session_state.club_equipes)
                submit_supp_eq = st.form_submit_button("Supprimer cette équipe", type="secondary")

                if submit_supp_eq:
                    if equipe_a_supprimer in st.session_state.club_equipes:
                        st.session_state.club_equipes.remove(equipe_a_supprimer)

                        if club_actuel in clubs_reg:
                            clubs_reg[club_actuel]["equipes"] = list(st.session_state.club_equipes)
                            sauvegarder_registre(reg)

                        chemin_fichier = os.path.join(dossier_club, get_nom_fichier_equipe(equipe_a_supprimer))
                        if os.path.exists(chemin_fichier):
                            try:
                                os.remove(chemin_fichier)
                            except Exception:
                                pass
                        st.success(f"L'équipe '{equipe_a_supprimer}' a été supprimée avec succès !")
                        st.rerun()

        st.markdown("---")

        with st.form("form_creer_equipe"):
            st.subheader("➕ Créer une nouvelle équipe")
            nouvelle_eq = st.text_input("Nom de l'équipe (ex: Loisirs M, -13F...)")
            submit_eq = st.form_submit_button("Ajouter l'équipe au club")

            if submit_eq:
                eq_clean = nouvelle_eq.strip()
                if eq_clean and eq_clean not in st.session_state.club_equipes:
                    st.session_state.club_equipes.append(eq_clean)
                    if club_actuel in clubs_reg:
                        clubs_reg[club_actuel]["equipes"] = list(st.session_state.club_equipes)
                        sauvegarder_registre(reg)
                    st.success(f"L'équipe '{eq_clean}' a été créée avec succès !")
                    st.rerun()
                else:
                    st.error("Nom d'équipe invalide ou déjà existant.")

    # --- ONGLET 3 : GESTION DES STAFFS (ENCLOISONNÉ AU CLUB) ---
    with tab_staffs:
        st.subheader("👥 Gestion des profils Staff et Entraîneurs")

        users_dict = reg.get("users", st.session_state.users_db)
        staffs_existants = [
            uname
            for uname, data in users_dict.items()
            if data.get("role") == "staff" and data.get("club") == club_actuel
        ]

        if staffs_existants:
            st.markdown("### 🗑️ Révoquer un accès staff")
            with st.form("form_supprimer_staff"):
                staff_a_supprimer = st.selectbox(
                    "Sélectionner l'identifiant du staff à supprimer",
                    staffs_existants,
                    format_func=lambda x: (
                        f"{users_dict[x]['nom']} (ID: {x} - Équipes: "
                        f"{', '.join(users_dict[x].get('equipes', []))})"
                    ),
                )
                submit_supp_staff = st.form_submit_button("Révoquer cet accès", type="secondary")

                if submit_supp_staff:
                    if staff_a_supprimer in users_dict:
                        del users_dict[staff_a_supprimer]
                        sauvegarder_registre(reg)
                        st.success(f"L'accès pour l'identifiant '{staff_a_supprimer}' a été révoqué avec succès !")
                        st.rerun()

        st.markdown("---")

        with st.form("form_create_staff_admin"):
            st.subheader("➕ Nouveau compte Staff / Entraîneur")
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Identifiant de connexion (ex: thomas_seniors)").strip()
                new_password = st.text_input("Mot de passe", type="password")
            with col2:
                new_nom = st.text_input("Nom / Prénom du coach")
                equipes_dispos = st.session_state.get("club_equipes", [])
                new_equipes = st.multiselect("Équipes assignées (Multi-équipe)", equipes_dispos)

            submit_staff = st.form_submit_button("Créer l'accès staff")
            if submit_staff:
                if new_username and new_password and new_nom.strip() and new_username not in users_dict:
                    users_dict[new_username] = {
                        "password": new_password,
                        "role": "staff",
                        "nom": new_nom.strip(),
                        "club": club_actuel,
                        "equipes": new_equipes,
                    }
                    sauvegarder_registre(reg)
                    st.success(
                        f"Compte staff créé pour **{new_nom}** assigné aux équipes : **{', '.join(new_equipes)}** !"
                    )
                    st.rerun()
                else:
                    st.error("Champs invalides, vides ou identifiant déjà pris dans la plateforme.")

    # --- ONGLET 4 : CONFIGURATION DU CLUB & LOGO ---
    with tab_club_config:
        st.subheader("⚙️ Identité Visuelle & Logo du Club")
        st.write("Téléchargez le logo officiel de votre club pour l'intégrer sur les rapports PDF.")

        logo_path = os.path.join(dossier_club, "logo_club.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=150, caption=f"Logo actuel — {club_actuel}")

        with st.form("form_upload_logo"):
            uploaded_file = st.file_uploader("Importer un nouveau logo (PNG, JPG)", type=["png", "jpg", "jpeg"])
            submit_logo = st.form_submit_button("Enregistrer le logo du club")

            if submit_logo and uploaded_file is not None:
                with open(logo_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success("Logo du club mis à jour avec succès !")
                st.rerun()

        st.markdown("---")
        st.subheader("💾 Sauvegarde & Restauration des Données du Club")
        if st.button("📦 Préparer la Sauvegarde du Club (.zip)", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for filename in os.listdir(dossier_club):
                    chemin_f = os.path.join(dossier_club, filename)
                    if os.path.isfile(chemin_f) and (filename.endswith(".json") or filename == "logo_club.png"):
                        zip_file.write(chemin_f, arcname=filename)

            zip_buffer.seek(0)
            st.download_button(
                label="📥 Cliquer ici pour enregistrer l'archive ZIP",
                data=zip_buffer,
                file_name=f"sauvegarde_handstats_{club_actuel.replace(' ', '_')}.zip",
                mime="application/zip",
                type="primary",
            )