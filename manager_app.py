import streamlit as st
import pandas as pd
import json
import os
import zipfile
import io
from auth_manager import (
    LIBELLES_PERMISSIONS,
    PERMISSIONS_DEFAUT_PAR_ROLE,
    afficher_bloc_changement_mot_de_passe,
    afficher_en_tete_avec_profil,
    hasher_mot_de_passe,
    obtenir_permissions_utilisateur,
    sauvegarder_registre,
)
from hand_manager import (
    EquipeManager,
    get_dossier_club,
    get_nom_fichier_equipe,
    resumer_charge_forme_joueur,
)
from rapport_club_pdf import generer_pdf_bilan_global
from supabase_store import dump_scope, get_bytes, set_bytes
from theme import barre_laterale


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

    nav_manager_key = f"page_manager_{club_slug}"
    if nav_manager_key not in st.session_state:
        st.session_state[nav_manager_key] = "bilan"

    page_manager = barre_laterale(
        pages=[
            ("bilan", "Tableau de bord & bilan"),
            ("equipes", "Gestion des équipes"),
            ("staffs", "Gestion des staffs"),
            ("club", "Configuration & logo"),
            ("parametres", "Paramètres"),
        ],
        page_active=st.session_state[nav_manager_key],
        equipe="Direction du club",
        club=club_actuel,
    )
    if page_manager and page_manager != st.session_state[nav_manager_key]:
        st.session_state[nav_manager_key] = page_manager
        st.rerun()

    page_active_mgr = st.session_state[nav_manager_key]

    # En-tête combiné Titre + Profil
    afficher_en_tete_avec_profil("Espace direction", sous_titre=club_actuel)

    st.info(
        f"Bienvenue dans le panneau de direction de **{club_actuel}**. "
        "Suivez en un coup d'œil les performances globales de toutes vos équipes et gérez les accès."
    )

    # --- ONGLET 1 : TABLEAU DE BORD & BILAN GLOBAL ---
    if page_active_mgr == "bilan":
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
                "Matchs": stats["matchs"],
                "Victoires": stats["victoires"],
                "% Victoire": f"{pct_victoires}%",
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
            club_actuel, synthese_data, total_matchs_club, total_victoires_club, pct_global_vic, dossier_club=dossier_club
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

        st.markdown("---")
        st.markdown("### ⚠️ Vigilance Charge & Forme du Club")
        alertes_club = []
        for eq in equipes:
            nom_f_eq = get_nom_fichier_equipe(eq)
            try:
                mgr_eq_suivi = EquipeManager(fichier=nom_f_eq, club_slug=club_slug)
            except Exception:
                continue

            for j_nom, j_obj in mgr_eq_suivi.joueuses.items():
                res_s = resumer_charge_forme_joueur(j_obj)
                if res_s["statut"] != "⚪ Sans donnée":
                    alertes_club.append({
                        "Équipe": eq,
                        "Joueur / Joueuse": j_nom,
                        "Poste": j_obj.poste,
                        "Statut": res_s["statut"],
                        "Charge 7j (UA)": res_s["charge_7j"],
                        "ACWR": res_s["acwr"] if res_s["acwr"] is not None else "-",
                        "Forme Moy. (/5)": res_s["forme_moy"] if res_s["forme_moy"] is not None else "-",
                    })

        if alertes_club:
            ordre_priorite = {"🔴 Vigilance / Charge": 0, "🟠 À surveiller": 1, "🟢 Optimal": 2}
            alertes_club.sort(key=lambda r: (ordre_priorite.get(r["Statut"], 9), r["Équipe"], r["Joueur / Joueuse"]))
            st.dataframe(pd.DataFrame(alertes_club), use_container_width=True, hide_index=True)
        else:
            st.caption("📌 Aucune donnée longitudinale de charge ou de forme enregistrée sur les équipes du club pour le moment.")

    # --- ONGLET 2 : GESTION DES ÉQUIPES (AJOUT & SUPPRESSION) ---
    elif page_active_mgr == "equipes":
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

    # --- ONGLET 3 : GESTION DES STAFFS & PERMISSIONS (ENCLOISONNÉ AU CLUB) ---
    elif page_active_mgr == "staffs":
        st.subheader("👥 Gestion des profils Staff, Analystes & Permissions")

        users_dict = reg.get("users", st.session_state.users_db)
        membres_club = [
            uname
            for uname, data in users_dict.items()
            if data.get("role") in ("staff", "analyste") and data.get("club") == club_actuel
        ]
        equipes_dispos = st.session_state.get("club_equipes", [])

        if membres_club:
            st.markdown("### 🔐 Modifier les catégories/équipes et permissions d'un membre")
            membre_cible = st.selectbox(
                "Sélectionner un membre du club",
                membres_club,
                format_func=lambda x: f"{users_dict[x]['nom']} ({x}) — Rôle : {users_dict[x].get('role')}",
                key="select_edit_membre_club",
            )
            m_data = users_dict[membre_cible]
            m_perms = obtenir_permissions_utilisateur(m_data)
            eq_actuelles_valides = [eq for eq in m_data.get("equipes", []) if eq in equipes_dispos]

            with st.form(f"form_edit_permissions_{membre_cible}"):
                role_edit = st.selectbox(
                    "Rôle",
                    ["staff", "analyste"],
                    index=0 if m_data.get("role") == "staff" else 1,
                )
                equipes_edit = st.multiselect(
                    "Équipes / Catégories autorisées",
                    equipes_dispos,
                    default=eq_actuelles_valides,
                )
                st.markdown("**Permissions détaillées :**")
                perms_edit = {}
                p_cols = st.columns(2)
                for idx_p, (p_key, p_label) in enumerate(LIBELLES_PERMISSIONS.items()):
                    with p_cols[idx_p % 2]:
                        perms_edit[p_key] = st.checkbox(
                            p_label,
                            value=bool(m_perms.get(p_key, False)),
                            key=f"chk_perm_edit_{membre_cible}_{p_key}",
                        )

                if st.form_submit_button("💾 Enregistrer les droits et équipes", type="primary"):
                    m_data["role"] = role_edit
                    m_data["equipes"] = equipes_edit
                    m_data["permissions"] = perms_edit
                    sauvegarder_registre(reg)
                    st.success(f"Droits et équipes mis à jour pour {m_data['nom']} ({membre_cible}).")
                    st.rerun()

            st.markdown("### 🗑️ Révoquer un accès")
            with st.form("form_supprimer_staff"):
                staff_a_supprimer = st.selectbox(
                    "Sélectionner l'identifiant à révoquer",
                    membres_club,
                    format_func=lambda x: (
                        f"{users_dict[x]['nom']} (ID: {x} [{users_dict[x].get('role')}] - Équipes: "
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
            st.subheader("➕ Nouveau compte Staff / Analyste")
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Identifiant de connexion (ex: thomas_seniors)").strip().lower()
                new_password = st.text_input("Mot de passe", type="password")
                new_role = st.selectbox("Rôle", ["staff", "analyste"])
            with col2:
                new_nom = st.text_input("Nom / Prénom")
                new_equipes = st.multiselect("Équipes / Catégories assignées", equipes_dispos)

            st.markdown("**Permissions initiales :**")
            new_perms = {}
            n_cols = st.columns(2)
            for idx_p, (p_key, p_label) in enumerate(LIBELLES_PERMISSIONS.items()):
                default_val = PERMISSIONS_DEFAUT_PAR_ROLE["staff"][p_key]
                with n_cols[idx_p % 2]:
                    new_perms[p_key] = st.checkbox(
                        p_label,
                        value=default_val,
                        key=f"chk_perm_new_{p_key}",
                    )

            submit_staff = st.form_submit_button("Créer l'accès")
            if submit_staff:
                identifiants_existants = {k.strip().lower() for k in users_dict.keys()}
                if not new_username or not new_password or not new_nom.strip():
                    st.error("Veuillez remplir l'identifiant, le mot de passe et le nom.")
                elif " " in new_username:
                    st.error("L'identifiant ne peut pas contenir d'espaces.")
                elif new_username in identifiants_existants:
                    st.error("Désolé, cet identifiant est déjà attribué à un autre compte.")
                else:
                    users_dict[new_username] = {
                        "password": hasher_mot_de_passe(new_password),
                        "role": new_role,
                        "nom": new_nom.strip(),
                        "club": club_actuel,
                        "equipes": new_equipes,
                        "permissions": new_perms,
                    }
                    sauvegarder_registre(reg)
                    st.success(
                        f"Compte {new_role} créé pour **{new_nom}** assigné aux équipes : **{', '.join(new_equipes)}** !"
                    )
                    st.rerun()

    # --- ONGLET 4 : CONFIGURATION DU CLUB & LOGO ---
    elif page_active_mgr == "club":
        st.subheader("⚙️ Identité Visuelle & Logo du Club")
        st.write("Téléchargez le logo officiel de votre club pour l'intégrer sur les rapports PDF.")

        logo_path = os.path.join(dossier_club, "logo_club.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=150, caption=f"Logo actuel — {club_actuel}")

        with st.form("form_upload_logo"):
            uploaded_file = st.file_uploader("Importer un nouveau logo (PNG, JPG)", type=["png", "jpg", "jpeg"])
            submit_logo = st.form_submit_button("Enregistrer le logo du club")

            if submit_logo and uploaded_file is not None:
                contenu_logo = bytes(uploaded_file.getbuffer())
                mime_logo = "image/png" if (uploaded_file.name or "").lower().endswith(".png") else "image/jpeg"
                with open(logo_path, "wb") as f:
                    f.write(contenu_logo)
                set_bytes(club_slug, "logo_club.png", contenu_logo, mime=mime_logo)
                st.success("Logo du club mis à jour avec succès !")
                st.rerun()

        st.markdown("---")
        st.subheader("💾 Sauvegarde & Restauration des Données du Club")
        if st.button("📦 Préparer la Sauvegarde du Club (.zip)", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for cle, valeur in dump_scope(club_slug).items():
                    if cle.startswith(("draft_", "offline_queue_")):
                        continue  # données temporaires du match en cours
                    if cle.endswith(".json"):
                        zip_file.writestr(cle, json.dumps(valeur, ensure_ascii=False, indent=2))
                logo_octets = get_bytes(club_slug, "logo_club.png")
                if logo_octets:
                    zip_file.writestr("logo_club.png", logo_octets)

            zip_buffer.seek(0)
            st.download_button(
                label="📥 Cliquer ici pour enregistrer l'archive ZIP",
                data=zip_buffer,
                file_name=f"sauvegarde_handstats_{club_actuel.replace(' ', '_')}.zip",
                mime="application/zip",
                type="primary",
            )

    # --- VUE 5 : PARAMÈTRES GÉNÉRAUX ---
    elif page_active_mgr == "parametres":
        st.subheader("⚙️ Paramètres du Compte & Sécurité")
        afficher_bloc_changement_mot_de_passe(key_suffix="manager")