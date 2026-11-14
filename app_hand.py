import streamlit as st
import pandas as pd
from hand_manager import EquipeManager, Gardienne, JoueuseDeChamp
from pdf_exporter import generer_pdf_match
from pdf_exporter_chronologique import generer_pdf_chronologique
import time
from streamlit_autorefresh import st_autorefresh 

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="HandStats Pro",
    page_icon="🤾‍♀️",
    layout="wide"
)

# --- INITIALISATION DU MANAGER ---
@st.cache_resource
def get_manager():
    return EquipeManager()

manager = get_manager()

# --- GESTION DE LA NAVIGATION (ÉCRANS) ---
if "page_actuelle" not in st.session_state:
    st.session_state.page_actuelle = "accueil"

def aller_a(page):
    st.session_state.page_actuelle = page
    st.rerun()

# --- FONCTION UTILITAIRE : BADGES COULEURS PAR POSTE ---
def get_badge_poste_html(poste):
    if "Arrière" in poste or "Demi-centre" in poste:
        return '<span style="background-color: #dbeafe; color: #1e40af; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;">🔵 Base Arrière</span>'
    elif "Ailière" in poste:
        return '<span style="background-color: #d1fae5; color: #065f46; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;">🟢 Ailière</span>'
    elif "Pivot" in poste:
        return '<span style="background-color: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;">🟠 Pivot</span>'
    elif "Gardienne" in poste:
        return '<span style="background-color: #f3e8ff; color: #6b21a8; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;">🟣 Gardienne</span>'
    return f'<span style="background-color: #f3f4f6; color: #374151; padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;">{poste}</span>'

def get_prefix_couleur(poste):
    if "Arrière" in poste or "Demi-centre" in poste:
        return "🔵"
    elif "Ailière" in poste:
        return "🟢"
    elif "Pivot" in poste:
        return "🟠"
    elif "Gardienne" in poste:
        return "🟣"
    return "⚪"

# ==========================================
# 1. ÉCRAN D'ACCUEIL (MENU PRINCIPAL)
# ==========================================
if st.session_state.page_actuelle == "accueil":
    st.markdown("""
        <style>
        [data-testid="stColumn"] {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        [data-testid="stColumn"] > div {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🤾‍♀️ HandStats Pro")
    st.markdown("### L'outil de performance et de suivi tactique de terrain.")
    st.divider()

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### ⚡ Saisie & Match")
        st.write("Feuille de match en direct, tirs, duels, pertes de balle et discipline.")
        if st.button("Lancer / Match en direct", type="primary", use_container_width=True):
            aller_a("match")
            
    with col2:
        st.markdown("#### 📈 Analyse & Saison")
        st.write("Historique des rencontres, bilans d'équipe et stats individuelles.")
        if st.button("Stats Saison", use_container_width=True):
            aller_a("saison")
            
    with col3:
        st.markdown("#### 👥 Effectif")
        st.write("Gestion des joueuses, numéros et postes.")
        if st.button("Gérer l'effectif", use_container_width=True):
            aller_a("effectif")

# ==========================================
# 2. ÉCRAN : MATCH EN DIRECT & FEUILLE DE MATCH
# ==========================================
elif st.session_state.page_actuelle == "match":
    if st.button("⬅️ Retour à l'accueil", key="btn_retour_accueil"):
        st.session_state.match_en_cours = False
        aller_a("accueil")
        
    st.header("⚡ Feuille de Match & Saisie en Direct")

    if not manager.joueuses:
        st.warning("Aucune joueuse enregistrée. Rendez-vous dans l'onglet 'Effectif' pour en ajouter.")
    else:
        # ÉTAPE 1 : CONFIGURATION DE LA FEUILLE DE MATCH SI NON LANCÉ
        if not st.session_state.get("match_en_cours", False):
            st.subheader("📋 Composition de la Feuille de Match")
            st.write("Saisissez le nom de la rencontre et sélectionnez les joueuses convoquées :")
            
            with st.form("form_config_match"):
                nom_match_saisi = st.text_input("Nom / Adversaire du match", value="J1 - Match 1")
                
                st.markdown("---")
                st.markdown("**Joueuses présentes pour cette rencontre :**")
                
                joueuses_coches = {}
                for nom, p_obj in manager.joueuses.items():
                    joueuses_coches[nom] = st.checkbox(
                        f"#{p_obj.numero} - {p_obj.nom} ({p_obj.poste})", 
                        value=True, 
                        key=f"chk_joueuse_{nom}"
                    )
                
                st.markdown("---")
                valider_feuille = st.form_submit_button("Lancer le match en direct", type="primary")
                
                if valider_feuille:
                    joueuses_selectionnees = [nom for nom, est_coche in joueuses_coches.items() if est_coche]
                    
                    if not nom_match_saisi.strip():
                        st.error("Le nom du match ne peut pas être vide.")
                    elif not joueuses_selectionnees:
                        st.error("Vous devez sélectionner au moins une joueuse.")
                    else:
                        st.session_state.match_en_cours = True
                        st.session_state.nom_match_actuel = nom_match_saisi
                        st.session_state.joueuses_actives_match = joueuses_selectionnees
                        
                        st.session_state.terrain_joueuses = joueuses_selectionnees[:7]
                        st.session_state.banc_joueuses = joueuses_selectionnees[7:]
                        
                        st.session_state.attaques_adversaires_match = {
                            "Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0
                        }
                        
                        if st.session_state.terrain_joueuses:
                            st.session_state.joueuse_focus_live = st.session_state.terrain_joueuses[0]
                        else:
                            st.session_state.joueuse_focus_live = None
                        
                        st.session_state.chrono_en_cours = False
                        st.session_state.chrono_secondes_cumulees = 0
                        st.session_state.chrono_debut = None
                        st.session_state.journal_actions_match = []
                        st.session_state.commentaires_staff_match = []
                        st.rerun()
        
        # ÉTAPE 2 : MATCH EN COURS
        else:
            nom_match_actuel = st.session_state.get("nom_match_actuel", "Match")
            joueuses_actives = st.session_state.get("joueuses_actives_match", [])
            
            if "terrain_joueuses" not in st.session_state:
                st.session_state.terrain_joueuses = joueuses_actives[:7]
            if "banc_joueuses" not in st.session_state:
                st.session_state.banc_joueuses = joueuses_actives[7:]

            st.markdown(f"**Rencontre en cours :** `{nom_match_actuel}` | **Effectif feuille :** {len(joueuses_actives)} joueuses")
            st.divider()

            # --- FONCTIONS DU CHRONO ET DU JOURNAL ---
            def formater_temps(secondes):
                m = secondes // 60
                s = secondes % 60
                return f"{m:02d}:{s:02d}"

            def enregistrer_action(type_action, details):
                if "journal_actions_match" not in st.session_state:
                    st.session_state.journal_actions_match = []
                
                secs = st.session_state.get("chrono_secondes_cumulees", 0)
                if st.session_state.get("chrono_en_cours", False) and st.session_state.get("chrono_debut"):
                    secs += int(time.time() - st.session_state.chrono_debut)
                
                temps_str = formater_temps(secs)
                st.session_state.journal_actions_match.append({
                    "temps": temps_str,
                    "type_action": type_action,
                    "details": details
                })

            secondes_totales = st.session_state.get("chrono_secondes_cumulees", 0)
            if st.session_state.get("chrono_en_cours", False) and st.session_state.get("chrono_debut"):
                secondes_totales += int(time.time() - st.session_state.chrono_debut)

            if st.session_state.get("chrono_en_cours", False):
                st_autorefresh(interval=1000, key="chrono_auto_refresh")

            # Affichage du Chrono et des Notes du Staff
            col_chrono1, col_chrono2, col_chrono3 = st.columns([2, 2, 3])
            with col_chrono1:
                temps_actuel_str = formater_temps(secondes_totales)
                st.markdown(f"### ⏱️ Chrono : `{temps_actuel_str}`")
            
            with col_chrono2:
                c_b1, c_b2, c_b3 = st.columns(3)
                with c_b1:
                    if st.button("▶️", key="chrono_start"):
                        if not st.session_state.get("chrono_en_cours", False):
                            st.session_state.chrono_en_cours = True
                            st.session_state.chrono_debut = time.time()
                            st.rerun()
                with c_b2:
                    if st.button("⏸️", key="chrono_pause"):
                        if st.session_state.get("chrono_en_cours", False):
                            st.session_state.chrono_secondes_cumulees += int(time.time() - st.session_state.chrono_debut)
                            st.session_state.chrono_en_cours = False
                            st.rerun()
                with c_b3:
                    if st.button("🔄", key="chrono_reset"):
                        st.session_state.chrono_en_cours = False
                        st.session_state.chrono_secondes_cumulees = 0
                        st.session_state.chrono_debut = None
                        st.rerun()

            with col_chrono3:
                with st.form("form_commentaire_staff", clear_on_submit=True):
                    txt_com = st.text_input("💬 Note / Fait de match staff", placeholder="Ex: Temps mort tactique...")
                    if st.form_submit_button("Ajouter au journal") and txt_com.strip():
                        if "commentaires_staff_match" not in st.session_state:
                            st.session_state.commentaires_staff_match = []
                        st.session_state.commentaires_staff_match.append({
                            "temps": temps_actuel_str, "texte": txt_com.strip()
                        })
                        st.success("Note ajoutée !")
            
            st.divider()
            
            # ==========================================
            # 🚀 GESTION DU TERRAIN / BANC ET ROTATIONS
            # ==========================================
            st.markdown("🏃‍♀️ **7 Majeur sur le Terrain (Clique pour changer de joueuse active instantanément) :**")
            
            terrain_list = st.session_state.terrain_joueuses
            if not terrain_list and st.session_state.banc_joueuses:
                st.session_state.terrain_joueuses.append(st.session_state.banc_joueuses.pop(0))
                terrain_list = st.session_state.terrain_joueuses

            if not st.session_state.get("joueuse_focus_live") or st.session_state.joueuse_focus_live not in terrain_list:
                if terrain_list:
                    st.session_state.joueuse_focus_live = terrain_list[0]

            cols_terrain = st.columns(max(len(terrain_list), 1))
            for idx, nom_j in enumerate(terrain_list):
                p_item = manager.joueuses[nom_j]
                col_cible = cols_terrain[idx % len(cols_terrain)]
                with col_cible:
                    est_actif = (nom_j == st.session_state.get("joueuse_focus_live"))
                    type_btn = "primary" if est_actif else "secondary"
                    
                    prefix = get_prefix_couleur(p_item.poste)
                    label_btn = f"{prefix} #{p_item.numero} {p_item.nom.split()[0]}"
                    
                    if st.button(label_btn, key=f"terrain_j_{nom_j}", use_container_width=True, type=type_btn):
                        st.session_state.joueuse_focus_live = nom_j
                        st.rerun()

            with st.expander("🔄 Gérer les rotations (Remplacements rapides)"):
                r_col1, r_col2, r_col3 = st.columns([2, 2, 1])
                with r_col1:
                    sortant = st.selectbox("Sort du terrain ⬇️", terrain_list, key="sel_sortant")
                with r_col2:
                    banc_dispo = st.session_state.banc_joueuses if st.session_state.banc_joueuses else ["Aucune"]
                    entrant = st.selectbox("Entre sur le terrain ⬆️", banc_dispo, key="sel_entrant")
                with r_col3:
                    st.write("")
                    st.write("")
                    if st.button("🔄 Intervertir", type="primary", use_container_width=True):
                        if st.session_state.banc_joueuses and sortant in terrain_list and entrant in st.session_state.banc_joueuses:
                            st.session_state.terrain_joueuses.remove(sortant)
                            st.session_state.banc_joueuses.remove(entrant)
                            st.session_state.terrain_joueuses.append(entrant)
                            st.session_state.banc_joueuses.append(sortant)
                            if st.session_state.get("joueuse_focus_live") == sortant:
                                st.session_state.joueuse_focus_live = entrant
                            st.success(f"Remplacement : {entrant} ➡️ {sortant}")
                            st.rerun()
                        else:
                            st.warning("Impossible d'effectuer le remplacement (banc vide ou sélection invalide).")

            st.divider()
            
            col_saisie, col_feuille = st.columns([1, 1.5])
            
            with col_saisie:
                nom_focus = st.session_state.get("joueuse_focus_live")
                if not nom_focus or nom_focus not in manager.joueuses:
                    st.warning("Sélectionnez une joueuse active sur le terrain.")
                else:
                    p_obj = manager.joueuses[nom_focus]
                    
                    st.subheader(f"⚡ Fiche Action : #{p_obj.numero} - {p_obj.nom}")
                    st.markdown(get_badge_poste_html(p_obj.poste), unsafe_allow_html=True)
                    st.write("")
                    
                    if isinstance(p_obj, JoueuseDeChamp):
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            st.metric("Buts / Tirs", f"{p_obj.buts} / {p_obj.tirs}", f"{p_obj.efficacite_tirs()}% réussite")
                        with col_m2:
                            st.metric("Passes Décisives", p_obj.passes_decisives)

                        st.markdown("---")
                        st.markdown("⚔️ **ATTAQUE**")
                        
                        atk_c1, atk_c2 = st.columns(2)
                        with atk_c1:
                            if st.button("🟢 +1 But", key=f"btn_but_{p_obj.nom}", use_container_width=True):
                                p_obj.buts += 1
                                p_obj.tirs += 1
                                enregistrer_action("But", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()
                        with atk_c2:
                            if st.button("🔴 Tir raté", key=f"btn_tirete_{p_obj.nom}", use_container_width=True):
                                p_obj.tirs += 1
                                enregistrer_action("Tir raté", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                        atk_c3, atk_c4 = st.columns(2)
                        with atk_c3:
                            if st.button("⚔️ Duel Off. Gagné", key=f"btn_dog_{p_obj.nom}", use_container_width=True):
                                p_obj.duels_off_gagnes += 1
                                enregistrer_action("Duel Offensif Gagné", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()
                        with atk_c4:
                            if st.button("❌ Duel Off. Perdu", key=f"btn_dop_{p_obj.nom}", use_container_width=True):
                                p_obj.duels_off_perdus += 1
                                enregistrer_action("Duel Offensif Perdu", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                        atk_c5, atk_c6 = st.columns(2)
                        with atk_c5:
                            if st.button("📤 Perte (Passe)", key=f"btn_pb_passe_{p_obj.nom}", use_container_width=True):
                                p_obj.pertes_de_balles_passe += 1
                                enregistrer_action("Perte de balle (Passe)", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()
                        with atk_c6:
                            if st.button("⚠️ Perte (Faute)", key=f"btn_pb_faute_{p_obj.nom}", use_container_width=True):
                                p_obj.pertes_de_balles_faute += 1
                                enregistrer_action("Perte de balle (Faute)", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                        atk_c7, _ = st.columns(2)
                        with atk_c7:
                            if st.button("🤝 +1 Passe D.", key=f"btn_pd_{p_obj.nom}", use_container_width=True):
                                p_obj.passes_decisives += 1
                                enregistrer_action("Passe Décisive", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                        st.markdown("---")
                        st.markdown("🛡️ **DÉFENSE**")
                        
                        def_c1, def_c2 = st.columns(2)
                        with def_c1:
                            if st.button("🛡️ Duel Déf. Gagné", key=f"btn_ddg_{p_obj.nom}", use_container_width=True):
                                p_obj.duels_def_gagnes += 1
                                enregistrer_action("Duel Défensif Gagné", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()
                        with def_c2:
                            if st.button("⚠️ Duel Déf. Perdu", key=f"btn_ddp_{p_obj.nom}", use_container_width=True):
                                p_obj.duels_def_perdus += 1
                                enregistrer_action("Duel Défensif Perdu", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                        def_c3, def_c4 = st.columns(2)
                        with def_c3:
                            if st.button("⚡ Interception", key=f"btn_int_{p_obj.nom}", use_container_width=True):
                                p_obj.interceptions += 1
                                enregistrer_action("Interception", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()
                        with def_c4:
                            if st.button("🧱 Neutralisation", key=f"btn_neut_{p_obj.nom}", use_container_width=True):
                                p_obj.neutralisations += 1
                                enregistrer_action("Neutralisation", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                        def_c5, _ = st.columns(2)
                        with def_c5:
                            if st.button("🔥 Perte de balle provoquée", key=f"btn_bp_{p_obj.nom}", use_container_width=True):
                                p_obj.pertes_balles_provoquees += 1
                                enregistrer_action("Perte de balle provoquée", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                    elif isinstance(p_obj, Gardienne):
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            st.metric("Arrêts / Tirs subis", f"{p_obj.arrets} / {p_obj.tirs_subis}", f"{p_obj.pourcentage_arrets()}% arrêts")
                        with col_m2:
                            st.metric("Buts marqués", f"{p_obj.buts} / {p_obj.tirs}")

                        st.divider()
                        st.write("🛡️ **Actions de la Gardienne :**")
                        
                        g1, g2 = st.columns(2)
                        with g1:
                            if st.button("🧤 +1 Arrêt décisif", key=f"btn_arret_{p_obj.nom}", use_container_width=True):
                                p_obj.arrets += 1
                                p_obj.tirs_subis += 1
                                enregistrer_action("Arrêt décisif", f"#{p_obj.numero} {p_obj.nom} (Gardienne)")
                                manager.sauvegarder_donnees()
                                st.rerun()
                            if st.button("🟢 +1 But (marqué)", key=f"btn_gbut_{p_obj.nom}", use_container_width=True):
                                p_obj.buts += 1
                                p_obj.tirs += 1
                                enregistrer_action("But (Gardienne)", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()
                        with g2:
                            if st.button("🥅 But encaissé", key=f"btn_enc_{p_obj.nom}", use_container_width=True):
                                p_obj.tirs_subis += 1
                                p_obj.buts_encaisses += 1
                                enregistrer_action("But encaissé", f"#{p_obj.numero} {p_obj.nom} (Gardienne)")
                                manager.sauvegarder_donnees()
                                st.rerun()
                            if st.button("🔴 Tir raté (buteur)", key=f"btn_gtirete_{p_obj.nom}", use_container_width=True):
                                p_obj.tirs += 1
                                enregistrer_action("Tir raté (Gardienne)", f"#{p_obj.numero} {p_obj.nom}")
                                manager.sauvegarder_donnees()
                                st.rerun()

                    st.markdown("---")
                    st.write("⚖️ **Sanctions :**")
                    s1, s2 = st.columns(2)
                    with s1:
                        if st.button("🟨 +1 Jaune", key=f"btn_jaune_{p_obj.nom}", use_container_width=True):
                            p_obj.cartons_jaunes += 1
                            enregistrer_action("Carton Jaune (Avertissement)", f"#{p_obj.numero} {p_obj.nom}")
                            manager.sauvegarder_donnees()
                            st.rerun()
                    with s2:
                        if st.button("⏱️ + 2min", key=f"btn_2min_{p_obj.nom}", use_container_width=True):
                            p_obj.exclusions_2min += 1
                            enregistrer_action("Exclusion 2 minutes", f"#{p_obj.numero} {p_obj.nom}")
                            manager.sauvegarder_donnees()
                            st.rerun()

            with col_feuille:
                st.subheader("📋 Feuille de Match en Temps Réel")
                
                total_buts_marques = sum(manager.joueuses[n].buts for n in joueuses_actives if hasattr(manager.joueuses[n], 'buts'))
                total_buts_encaisses = sum(manager.joueuses[n].buts_encaisses for n in joueuses_actives if isinstance(manager.joueuses[n], Gardienne))

                st.markdown(
                    f"""
                    <div style="background-color: #f02; padding: 15px; border-radius: 10px; text-align: center; color: white; margin-bottom: 20px;">
                        <h2 style="margin: 0; font-size: 24px;">SCORE ACTUEL</h2>
                        <h1 style="margin: 0; font-size: 40px; font-weight: bold;">{total_buts_marques} - {total_buts_encaisses}</h1>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                st.markdown("**🏃‍♀️ Sur le Terrain (7 Majeur)**")
                terrain_objs = [manager.joueuses[n] for n in st.session_state.terrain_joueuses if n in manager.joueuses]
                
                data_terrain = []
                for j in terrain_objs:
                    if isinstance(j, JoueuseDeChamp):
                        poste_badge = "Base Arrière" if ("Arrière" in j.poste or "Demi" in j.poste) else ("Ailière" if "Ailière" in j.poste else ("Pivot" if "Pivot" in j.poste else j.poste))
                        data_terrain.append({
                            "N°": j.numero, "Nom": j.nom, "Poste": poste_badge, 
                            "Buts/Tirs": f"{j.buts}/{j.tirs} ({j.efficacite_tirs()}%)", 
                            "Arrêts/Subis": "-",
                            "PD": j.passes_decisives, 
                            "🟨": j.cartons_jaunes, "⏱️": j.exclusions_2min
                        })
                    elif isinstance(j, Gardienne):
                        data_terrain.append({
                            "N°": j.numero, "Nom": j.nom, "Poste": "Gardienne", 
                            "Buts/Tirs": f"{j.buts}/{j.tirs}",
                            "Arrêts/Subis": f"{j.arrets}/{j.tirs_subis} ({j.pourcentage_arrets()}%)",
                            "PD": "-",
                            "🟨": j.cartons_jaunes, "⏱️": j.exclusions_2min
                        })
                if data_terrain:
                    st.dataframe(data_terrain, use_container_width=True, hide_index=True)

                if st.session_state.banc_joueuses:
                    st.markdown("**🪑 Sur le Banc (Remplaçantes)**")
                    banc_objs = [manager.joueuses[n] for n in st.session_state.banc_joueuses if n in manager.joueuses]
                    data_banc = []
                    for b in banc_objs:
                        if isinstance(b, JoueuseDeChamp):
                            data_banc.append({
                                "N°": b.numero, "Nom": b.nom, "Poste": b.poste, 
                                "Buts/Tirs": f"{b.buts}/{b.tirs} ({b.efficacite_tirs()}%)", 
                                "Arrêts/Subis": "-"
                            })
                        elif isinstance(b, Gardienne):
                            data_banc.append({
                                "N°": b.numero, "Nom": b.nom, "Poste": "Gardienne", 
                                "Buts/Tirs": f"{b.buts}/{b.tirs}", 
                                "Arrêts/Subis": f"{b.arrets}/{b.tirs_subis} ({b.pourcentage_arrets()}%)"
                            })
                    st.dataframe(data_banc, use_container_width=True, hide_index=True)

            # ==========================================
            # 📊 DASHBOARD DE MI-TEMPS / SYNTHÈSE INSTANTANÉE
            # ==========================================
            st.divider()
            with st.expander("📊 Ouvrir le Dashboard de Mi-Temps / Synthèse Live (Indicateurs clés)"):
                st.markdown("### 📈 Analyse Statistique Instantanée (Bilan de Rupture)")
                
                champ_actives = [manager.joueuses[n] for n in joueuses_actives if isinstance(manager.joueuses[n], JoueuseDeChamp)]
                gard_actives = [manager.joueuses[n] for n in joueuses_actives if isinstance(manager.joueuses[n], Gardienne)]
                
                tot_b = sum(j.buts for j in champ_actives)
                tot_t = sum(j.tirs for j in champ_actives)
                eff_eq = round((tot_b / tot_t * 100), 1) if tot_t > 0 else 0.0
                
                tot_pp = sum(j.pertes_de_balles_passe for j in champ_actives)
                tot_pf = sum(j.pertes_de_balles_faute for j in champ_actives)
                tot_pertes = tot_pp + tot_pf
                
                tot_dog = sum(j.duels_off_gagnes for j in champ_actives)
                tot_dop = sum(j.duels_off_perdus for j in champ_actives)
                tot_ddg = sum(j.duels_def_gagnes for j in champ_actives)
                tot_ddp = sum(j.duels_def_perdus for j in champ_actives)
                
                tot_arrets = sum(g.arrets for g in gard_actives)
                tot_subis = sum(g.tirs_subis for g in gard_actives)
                pct_arrets = round((tot_arrets / tot_subis * 100), 1) if tot_subis > 0 else 0.0

                d_col1, d_col2, d_col3, d_col4 = st.columns(4)
                d_col1.metric("Efficacité Tirs Équipe", f"{eff_eq}%", f"{tot_b} buts / {tot_t} tirs")
                d_col2.metric("Pertes de Balle", tot_pertes, f"Passes: {tot_pp} | Fautes: {tot_pf}")
                d_col3.metric("Arrêts Gardiennes", f"{pct_arrets}%", f"{tot_arrets} arrêts / {tot_subis} tirs")
                d_col4.metric("Duels Offensifs Gagnés", f"{tot_dog} / {tot_dog + tot_dop}" if (tot_dog + tot_dop) > 0 else "0/0")

                st.markdown("---")
                st.markdown("#### 🧠 Point Tactique & Attaques Adverses rencontrées")
                df_att_dash = pd.DataFrame([st.session_state.attaques_adversaires_match])
                st.dataframe(df_att_dash, use_container_width=True, hide_index=True)

                if "commentaires_staff_match" in st.session_state and st.session_state.commentaires_staff_match:
                    st.markdown("#### 💬 Notes du Staff enregistrées :")
                    for note in st.session_state.commentaires_staff_match:
                        st.markdown(f"- **`{note['temps']}`** : {note['texte']}")

            # ==========================================
            # 🧠 MODULE TACTIQUE : ATTAQUES ADVERSES
            # ==========================================
            st.divider()
            st.subheader("📋 Suivi Tactique — Attaques Adverses (Yago, Yego...)")
            
            t_col1, t_col2, t_col3, t_col4, t_col5 = st.columns(5)
            with t_col1:
                if st.button("🔄 Yago", use_container_width=True, key="att_btn_yago"):
                    st.session_state.attaques_adversaires_match["Yago"] += 1
                    enregistrer_action("Attaque adverse", "Système Yago")
                    st.toast("Attaque Yago (Adverse) enregistrée !", icon="📊")
                    st.rerun()
            with t_col2:
                if st.button("🔄 Yego", use_container_width=True, key="att_btn_yego2"):
                    st.session_state.attaques_adversaires_match["Yego"] += 1
                    enregistrer_action("Attaque adverse", "Système Yego")
                    st.toast("Attaque Yego (Adverse) enregistrée !", icon="📊")
                    st.rerun()
            with t_col3:
                if st.button("🔄 Montp.", use_container_width=True, key="att_btn_montpellier"):
                    st.session_state.attaques_adversaires_match["Montpellier"] += 1
                    enregistrer_action("Attaque adverse", "Système Montpellier")
                    st.toast("Attaque Montpellier (Adverse) enregistrée !", icon="📊")
                    st.rerun()
            with t_col4:
                if st.button("🔄 Croisé", use_container_width=True, key="att_btn_croise"):
                    st.session_state.attaques_adversaires_match["Croisé"] += 1
                    enregistrer_action("Attaque adverse", "Système Croisé")
                    st.toast("Attaque Croisé (Adverse) enregistrée !", icon="📊")
                    st.rerun()
            with t_col5:
                if st.button("🔄 Autre", use_container_width=True, key="att_btn_autre"):
                    st.session_state.attaques_adversaires_match["Autre"] += 1
                    enregistrer_action("Attaque adverse", "Système Autre")
                    st.toast("Autre attaque adverse enregistrée !", icon="📊")
                    st.rerun()
            
            df_att_compact = pd.DataFrame([st.session_state.attaques_adversaires_match])
            st.dataframe(df_att_compact, use_container_width=True, hide_index=True)

            st.divider()
            
            # --- SECTION DE CORRECTION MANUELLE ---
            with st.expander("✏️ Ajuster les statistiques manuellement (Correction d'erreur)"):
                st.write("Modifie directement les compteurs d'une joueuse de la feuille de match.")
                
                joueuse_a_corriger = st.selectbox("Choisir la joueuse à rectifier", joueuses_actives, key="select_correction_live")
                p_corr = manager.joueuses[joueuse_a_corriger]
                
                with st.form(key=f"form_correction_{p_corr.nom}"):
                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        c_buts = st.number_input("Buts", min_value=0, value=getattr(p_corr, 'buts', 0))
                        c_arrets = st.number_input("Arrêts", min_value=0, value=getattr(p_corr, 'arrets', 0))
                    with col_c2:
                        c_tirs = st.number_input("Tirs totaux", min_value=0, value=getattr(p_corr, 'tirs', 0))
                        c_tirs_subis = st.number_input("Tirs subis", min_value=0, value=getattr(p_corr, 'tirs_subis', 0))
                    with col_c3:
                        c_pd = st.number_input("Passes décisives", min_value=0, value=getattr(p_corr, 'passes_decisives', 0))
                        c_be = st.number_input("Buts encaissés", min_value=0, value=getattr(p_corr, 'buts_encaisses', 0))

                    col_c4, col_c5 = st.columns(2)
                    with col_c4:
                        c_cj = st.number_input("Cartons jaunes", min_value=0, value=p_corr.cartons_jaunes)
                    with col_c5:
                        c_2min = st.number_input("Exclusions 2min", min_value=0, value=p_corr.exclusions_2min)

                    submit_correction = st.form_submit_button("Valider les modifications")
                    
                    if submit_correction:
                        if hasattr(p_corr, 'buts'): p_corr.buts = c_buts
                        if hasattr(p_corr, 'arrets'): p_corr.arrets = c_arrets
                        if hasattr(p_corr, 'tirs'): p_corr.tirs = c_tirs
                        if hasattr(p_corr, 'tirs_subis'): p_corr.tirs_subis = c_tirs_subis
                        if hasattr(p_corr, 'passes_decisives'): p_corr.passes_decisives = c_pd
                        if hasattr(p_corr, 'buts_encaisses'): p_corr.buts_encaisses = c_be
                        p_corr.cartons_jaunes = c_cj
                        p_corr.exclusions_2min = c_2min
                        
                        manager.sauvegarder_donnees()
                        st.success(f"Les stats de {p_corr.nom} ont été mises à jour avec succès !")
                        st.rerun()

            st.divider()
            
            # --- CLÔTURE DE LA RENCONTRE ---
            st.subheader("🏁 Clôture de la Rencontre")
            if st.button("Archiver ce match et réinitialiser les compteurs", type="primary", key="btn_archiver_match"):
                manager.archiver_match(
                    nom_match_actuel, 
                    attaques_adv_data=st.session_state.get("attaques_adversaires_match", {}),
                    joueuses_actives=joueuses_actives,
                    journal_actions=st.session_state.get("journal_actions_match", []),
                    commentaires_staff=st.session_state.get("commentaires_staff_match", [])
                )
                st.session_state.match_en_cours = False
                st.session_state.attaques_adversaires_match = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}
                st.toast(f"Le match '{nom_match_actuel}' a été archivé avec succès !", icon="✅")
                aller_a("accueil")

# ==========================================
# 3. ÉCRAN : STATS SAISON (FEUILLES DE MATCH, ÉQUIPE & JOUEUSES)
# ==========================================
elif st.session_state.page_actuelle == "saison":
    if st.button("⬅️ Retour à l'accueil", key="btn_retour_saison"):
        aller_a("accueil")
        
    st.header("📈 Centre d'Analyse & Statistiques - Saison 2026-2027")
    
    if not manager.joueuses:
        st.info("Aucune joueuse enregistrée dans l'effectif.")
    else:
        matchs_archives = []
        for j in manager.joueuses.values():
            for m in j.historique_matchs:
                if m["match"] not in matchs_archives:
                    matchs_archives.append(m["match"])

        sub_tab_matchs, sub_tab_equipe, sub_tab_joueuses = st.tabs([
            "📋 Feuilles de Match Archivées", 
            "👥 Statistiques Équipe",
            "👤 Statistiques par Joueuse"
        ])

        with sub_tab_matchs:
            if not matchs_archives:
                st.warning("Aucun match n'a encore été archivé.")
            else:
                match_choisi = st.selectbox("Sélectionner une rencontre", matchs_archives, key="select_match_archive")
                
                lignes_champ = []
                lignes_gardiennes = []
                attaques_adv_archive = {}
                journal_actions_archive = []
                commentaires_staff_archive = []

                for j in manager.joueuses.values():
                    donnees_m = next((m for m in j.historique_matchs if m["match"] == match_choisi), None)
                    if donnees_m:
                        if not attaques_adv_archive:
                            attaques_adv_archive = donnees_m.get("attaques_adversaires", {})
                        if not journal_actions_archive:
                            journal_actions_archive = donnees_m.get("journal_actions", [])
                        if not commentaires_staff_archive:
                            commentaires_staff_archive = donnees_m.get("commentaires_staff", [])

                        if isinstance(j, JoueuseDeChamp):
                            lignes_champ.append({
                                "N°": j.numero, "Joueuse": j.nom, "Poste": j.poste,
                                "Buts": donnees_m["buts"], "Tirs": donnees_m["tirs"], 
                                "Réussite": f"{round((donnees_m['buts']/donnees_m['tirs']*100),1)}%" if donnees_m["tirs"] > 0 else "0.0%",
                                "Passes D.": donnees_m["passes_decisives"],
                                "Perte (Passe)": donnees_m.get("pertes_passe", 0),
                                "Perte (Faute)": donnees_m.get("pertes_faute", 0),
                                "Duels Off": f"{donnees_m.get('duels_off_gagnes', 0)}/{donnees_m.get('duels_off_gagnes', 0)+donnees_m.get('duels_off_perdus', 0)}",
                                "Duels Déf": f"{donnees_m.get('duels_def_gagnes', 0)}/{donnees_m.get('duels_def_gagnes', 0)+donnees_m.get('duels_def_perdus', 0)}",
                                "Interceptions": donnees_m["interceptions"],
                                "Neutralisations": donnees_m.get("neutralisations", 0),
                                "Provoquées": donnees_m.get("balles_provoquees", 0),
                                "🟨": donnees_m["cartons_jaunes"], "⏱️ 2min": donnees_m["exclusions_2min"]
                            })
                        elif isinstance(j, Gardienne):
                            lignes_gardiennes.append({
                                "N°": j.numero, "Gardienne": j.nom,
                                "Arrêts": donnees_m["arrets"], "Tirs Subis": donnees_m["tirs_subis"],
                                "% Arrêts": f"{round((donnees_m['arrets']/donnees_m['tirs_subis']*100),1)}%" if donnees_m["tirs_subis"] > 0 else "0.0%",
                                "Buts Encaissés": donnees_m["buts_encaisses"],
                                "Buts Marqués": f"{donnees_m.get('buts', 0)}/{donnees_m.get('tirs', 0)}",
                                "🟨": donnees_m["cartons_jaunes"], "⏱️ 2min": donnees_m["exclusions_2min"]
                            })

                score_eq = sum(row["Buts"] for row in lignes_champ)
                for row_g in lignes_gardiennes:
                    b_str = str(row_g["Buts Marqués"]).split('/')[0]
                    score_eq += int(b_str) if b_str.isdigit() else 0
                score_adv = sum(row["Buts Encaissés"] for row in lignes_gardiennes)

                st.markdown(f"### Résultat du match : {score_eq} - {score_adv}")
                
                if lignes_champ:
                    st.dataframe(pd.DataFrame(lignes_champ), use_container_width=True, hide_index=True)
                if lignes_gardiennes:
                    st.dataframe(pd.DataFrame(lignes_gardiennes), use_container_width=True, hide_index=True)

                st.divider()
                st.markdown("### 📥 Téléchargements des Rapports")
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    pdf_officiel_bytes = generer_pdf_match(
                        nom_match=match_choisi,
                        score_eq=score_eq,
                        score_adv=score_adv,
                        lignes_champ=lignes_champ,
                        lignes_gardiennes=lignes_gardiennes,
                        attaques_adversaires=attaques_adv_archive
                    )
                    st.download_button(
                        label="📥 Feuille de Match Officielle (PDF)",
                        data=pdf_officiel_bytes,
                        file_name=f"feuille_match_{match_choisi.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_officiel_{match_choisi}"
                    )
                
                with col_btn2:
                    pdf_chrono_bytes = generer_pdf_chronologique(
                        nom_match=match_choisi,
                        score_eq=score_eq,
                        score_adv=score_adv,
                        historique_actions=journal_actions_archive,
                        attaques_adv=attaques_adv_archive,
                        commentaires_staff=commentaires_staff_archive
                    )
                    st.download_button(
                        label="📥 Rapport Chronologique & Tactique (PDF)",
                        data=pdf_chrono_bytes,
                        file_name=f"resume_chrono_{match_choisi.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_chrono_{match_choisi}"
                    )

        with sub_tab_equipe:
            st.subheader("👥 Bilan Global & Cumuls de l'Effectif sur la Saison")
            
            if not matchs_archives:
                st.info("Aucun match archivé pour le moment.")
            else:
                total_matchs_joues = len(matchs_archives)
                champ_list = [j for j in manager.joueuses.values() if isinstance(j, JoueuseDeChamp)]
                gard_list = [j for j in manager.joueuses.values() if isinstance(j, Gardienne)]
                
                cumul_buts_eq = sum(sum(m.get("buts", 0) for m in j.historique_matchs) for j in champ_list)
                cumul_tirs_eq = sum(sum(m.get("tirs", 0) for m in j.historique_matchs) for j in champ_list)
                cumul_pd_eq = sum(sum(m.get("passes_decisives", 0) for m in j.historique_matchs) for j in champ_list)
                eff_equipe = round((cumul_buts_eq / cumul_tirs_eq * 100), 1) if cumul_tirs_eq > 0 else 0.0
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Matchs joués", total_matchs_joues)
                col_m2.metric("Total Buts Équipe", f"{cumul_buts_eq} / {cumul_tirs_eq}", f"{eff_equipe}% réussite")
                col_m3.metric("Total Passes Décisives", cumul_pd_eq)
                col_m4.metric("Joueuses enregistrées", len(manager.joueuses))
                
                st.divider()
                
                # --- SECTION : COURBES DE TENDANCE (GRAPHIQUES SAISON) ---
                st.markdown("### 📈 Tendances & Évolution Match après Match")
                
                data_tendances = []
                for m_nom in matchs_archives:
                    m_buts = 0
                    m_tirs = 0
                    m_arrets = 0
                    m_subis = 0
                    m_pertes = 0
                    
                    for j in manager.joueuses.values():
                        dm = next((m for m in j.historique_matchs if m["match"] == m_nom), None)
                        if dm:
                            if isinstance(j, JoueuseDeChamp):
                                m_buts += dm.get("buts", 0)
                                m_tirs += dm.get("tirs", 0)
                                m_pertes += dm.get("pertes_passe", 0) + dm.get("pertes_faute", 0)
                            elif isinstance(j, Gardienne):
                                m_arrets += dm.get("arrets", 0)
                                m_subis += dm.get("tirs_subis", 0)
                                m_buts += dm.get("buts", 0)
                                m_tirs += dm.get("tirs", 0)
                    
                    eff_m = round((m_buts / m_tirs * 100), 1) if m_tirs > 0 else 0.0
                    pct_arr_m = round((m_arrets / m_subis * 100), 1) if m_subis > 0 else 0.0
                    
                    data_tendances.append({
                        "Match": m_nom,
                        "Efficacité Tirs (%)": eff_m,
                        "% Arrêts Gardiennes": pct_arr_m,
                        "Pertes de Balle": m_pertes
                    })
                
                if data_tendances:
                    df_tend = pd.DataFrame(data_tendances).set_index("Match")
                    
                    g_col1, g_col2 = st.columns(2)
                    with g_col1:
                        st.markdown("**🎯 Efficacité Tirs Équipe (%)**")
                        st.line_chart(df_tend[["Efficacité Tirs (%)"]])
                    with g_col2:
                        st.markdown("**🧤 Taux d'Arrêts Gardiennes (%)**")
                        st.line_chart(df_tend[["% Arrêts Gardiennes"]])
                        
                    st.markdown("**⚠️ Évolution des Pertes de Balle Totales**")
                    st.bar_chart(df_tend[["Pertes de Balle"]])

                st.divider()
                
                if champ_list:
                    st.markdown("### 🏃‍♀️ Cumul Saison — Joueuses de Champ")
                    data_cumul_c = []
                    for j in champ_list:
                        nb_m = len(j.historique_matchs)
                        if nb_m > 0:
                            b = sum(m.get("buts", 0) for m in j.historique_matchs)
                            t = sum(m.get("tirs", 0) for m in j.historique_matchs)
                            eff = round((b / t * 100), 1) if t > 0 else 0.0
                            pd_sum = sum(m.get("passes_decisives", 0) for m in j.historique_matchs)
                            p_passe = sum(m.get("pertes_passe", 0) for m in j.historique_matchs)
                            p_faute = sum(m.get("pertes_faute", 0) for m in j.historique_matchs)
                            dog = sum(m.get("duels_off_gagnes", 0) for m in j.historique_matchs)
                            dop = sum(m.get("duels_off_perdus", 0) for m in j.historique_matchs)
                            ddg = sum(m.get("duels_def_gagnes", 0) for m in j.historique_matchs)
                            ddp = sum(m.get("duels_def_perdus", 0) for m in j.historique_matchs)
                            inter = sum(m.get("interceptions", 0) for m in j.historique_matchs)
                            neut = sum(m.get("neutralisations", 0) for m in j.historique_matchs)
                            prov = sum(m.get("balles_provoquees", 0) for m in j.historique_matchs)
                            cj = sum(m.get("cartons_jaunes", 0) for m in j.historique_matchs)
                            e2 = sum(m.get("exclusions_2min", 0) for m in j.historique_matchs)
                            
                            data_cumul_c.append({
                                "N°": j.numero, "Nom": j.nom, "Poste": j.poste, "Matchs": nb_m,
                                "Buts/Tirs": f"{b}/{t} ({eff}%)", "Passes D.": pd_sum,
                                "Pertes (P/F)": f"{p_passe}/{p_faute}",
                                "Duels Off": f"{dog}/{dog+dop}", "Duels Déf": f"{ddg}/{ddg+ddp}",
                                "Interceptions": inter, "Neutralisations": neut, "Provoquées": prov,
                                "🟨": cj, "⏱️": e2
                            })
                    if data_cumul_c:
                        st.dataframe(data_cumul_c, use_container_width=True, hide_index=True)
                        
                if gard_list:
                    st.markdown("### 🧤 Cumul Saison — Gardiennes")
                    data_cumul_g = []
                    for g in gard_list:
                        nb_m = len(g.historique_matchs)
                        if nb_m > 0:
                            arr = sum(m.get("arrets", 0) for m in g.historique_matchs)
                            sub = sum(m.get("tirs_subis", 0) for m in g.historique_matchs)
                            pct = round((arr / sub * 100), 1) if sub > 0 else 0.0
                            enc = sum(m.get("buts_encaisses", 0) for m in g.historique_matchs)
                            bm = sum(m.get("buts", 0) for m in g.historique_matchs)
                            tm = sum(m.get("tirs", 0) for m in g.historique_matchs)
                            cj = sum(m.get("cartons_jaunes", 0) for m in g.historique_matchs)
                            e2 = sum(m.get("exclusions_2min", 0) for m in g.historique_matchs)
                            
                            data_cumul_g.append({
                                "N°": g.numero, "Nom": g.nom, "Matchs": nb_m,
                                "Arrêts/Subis": f"{arr}/{sub} ({pct}%)",
                                "Buts Encaissés": enc, "Buts Marqués": f"{bm}/{tm}",
                                "🟨": cj, "⏱️": e2
                            })
                    if data_cumul_g:
                        st.dataframe(data_cumul_g, use_container_width=True, hide_index=True)

        with sub_tab_joueuses:
            noms = list(manager.joueuses.keys())
            joueuse_choisie = st.selectbox("Sélectionner une joueuse", noms, key="select_saison_joueuse")
            p = manager.joueuses[joueuse_choisie]
            
            st.markdown(f"### 🎽 #{p.numero} - {p.nom} *({p.poste})*")
            
            if not p.historique_matchs:
                st.info("Aucune donnée de match enregistrée pour cette joueuse.")
            else:
                nb_matchs = len(p.historique_matchs)
                
                if isinstance(p, JoueuseDeChamp):
                    tot_buts = sum(m["buts"] for m in p.historique_matchs)
                    tot_tirs = sum(m["tirs"] for m in p.historique_matchs)
                    tot_pd = sum(m["passes_decisives"] for m in p.historique_matchs)
                    tot_int = sum(m["interceptions"] for m in p.historique_matchs)
                    eff_globale = round((tot_buts / tot_tirs * 100), 1) if tot_tirs > 0 else 0.0

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Matchs joués", nb_matchs)
                    c2.metric("Total Buts / Tirs", f"{tot_buts} / {tot_tirs}", f"{eff_globale}% réussite")
                    c3.metric("Passes Décisives", tot_pd)
                    c4.metric("Interceptions", tot_int)

                elif isinstance(p, Gardienne):
                    tot_arrets = sum(m["arrets"] for m in p.historique_matchs)
                    tot_subis = sum(m["tirs_subis"] for m in p.historique_matchs)
                    tot_enc = sum(m["buts_encaisses"] for m in p.historique_matchs)
                    pct_global = round((tot_arrets / tot_subis * 100), 1) if tot_subis > 0 else 0.0

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Matchs joués", nb_matchs)
                    c2.metric("Arrêts / Tirs Subis", f"{tot_arrets} / {tot_subis}", f"{pct_global}% arrêts")
                    c3.metric("Buts Encaissés", tot_enc)
                    c4.metric("Moyenne arrêts / match", round(tot_arrets / nb_matchs, 1))

                st.divider()
                st.subheader("📅 Détail match par match")
                
                historique_propre = []
                for m in p.historique_matchs:
                    ligne = {k: v for k, v in m.items() if k not in ["score_equipe", "score_adversaire", "journal_actions", "commentaires_staff"]}
                    ligne["Score"] = f"{m.get('score_equipe', '-')} - {m.get('score_adversaire', '-')}"
                    historique_propre.append(ligne)
                    
                st.dataframe(historique_propre, use_container_width=True, hide_index=True)

# ==========================================
# 4. ÉCRAN : GESTION DE L'EFFECTIF
# ==========================================
elif st.session_state.page_actuelle == "effectif":
    if st.button("⬅️ Retour à l'accueil", key="btn_retour_effectif"):
        aller_a("accueil")
    st.header("👥 Gestion de l'Effectif")
    if manager.joueuses:
        for nom, joueuse in manager.joueuses.items():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.write(f"**{nom}**")
            col2.write(f"Poste : {joueuse.poste}")
            col3.write(f"N° {joueuse.numero}")
            if col4.button("🗑️", key=f"del_{nom}"):
                manager.supprimer_joueuse(nom)
                st.rerun()
    else:
        st.info("Aucune joueuse enregistrée.")
    
    st.divider()
    with st.form("form_ajout_joueuse"):
        nom_input = st.text_input("Nom / Prénom de la joueuse")
        poste_input = st.selectbox("Poste", ["Arrière gauche", "Arrière droite", "Demi-centre", "Ailière gauche", "Ailière droite", "Pivot", "Gardienne"])
        numero_input = st.number_input("Numéro de maillot", min_value=1, max_value=99, value=10)
        if st.form_submit_button("Ajouter à l'effectif"):
            if nom_input.strip():
                type_j = "gardienne" if poste_input == "Gardienne" else "champ"
                manager.ajouter_joueuse(nom=nom_input, poste=poste_input, numero=numero_input, type_joueuse=type_j)
                st.rerun()