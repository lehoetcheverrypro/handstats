import streamlit as st
import pandas as pd
from hand_manager import EquipeManager, Gardienne, JoueuseDeChamp
from pdf_exporter import generer_pdf_match
from pdf_exporter_chronologique import generer_pdf_chronologique
import time
from streamlit_autorefresh import st_autorefresh 
from tactics import afficher_tableau_tactique
from auth_manager import afficher_en_tete_avec_profil
from shot_grid import afficher_grille_saisie_interactive, afficher_cage_recapitulative

def run_staff_app(equipe_assignee):
    # --- DÉTERMINATION AUTOMATIQUE DU GENRE DE L'ÉQUIPE ---
    def detecter_genre(nom_equipe):
        nom_l = nom_equipe.lower()
        if any(k in nom_l for k in ["f", "fem", "fille", "féminine"]):
            return "F"
        elif any(k in nom_l for k in ["m", "garçon", "masc", "masculin", "H"]):
            return "M"
        return "F"  # Par défaut

    genre_equipe = detecter_genre(equipe_assignee)

    # --- DICTIONNAIRE DE LIBELLÉS ADAPTÉS ---
    L = {
        "F": {
            "joueur": "joueuse", "joueurs": "joueuses",
            "effectif": "Effectif", "convoquee": "convoquée",
            "convoquees": "convoquées", "selectionnee": "sélectionnée",
            "gardien": "Gardienne", "gardiens": "Gardiennes",
            "postes_possibles": ["Arrière gauche", "Arrière droite", "Demi-centre", "Ailière gauche", "Ailière droite", "Pivot", "Gardienne"],
            "badge_ailier": "🟢 Ailière", "badge_gardien": "🟣 Gardienne"
        },
        "M": {
            "joueur": "joueur", "joueurs": "joueurs",
            "effectif": "Effectif", "convoquee": "convoqué",
            "convoquees": "convoqués", "selectionnee": "sélectionné",
            "gardien": "Gardien", "gardiens": "Gardiens",
            "postes_possibles": ["Arrière gauche", "Arrière droite", "Demi-centre", "Ailier gauche", "Ailier droit", "Pivot", "Gardien"],
            "badge_ailier": "🟢 Ailier", "badge_gardien": "🟣 Gardien"
        }
    }[genre_equipe]

    # En-tête combiné Titre + Profil
    afficher_en_tete_avec_profil(f"🎽 Espace Staff — {equipe_assignee}")
    st.info(f"Vous pilotez actuellement les données pour l'équipe **{equipe_assignee}**.")

    # --- DESIGN SYSTEM & CSS PERSONNALISÉ ---
    st.markdown("""
        <style>
        .block-container {
            padding-top: 2.8rem;
            padding-bottom: 2rem;
        }
        .top-box {
            background-color: #f8fafc;
            border: 1px solid #cbd5e1;
            padding: 10px 15px;
            border-radius: 12px;
            text-align: center;
            height: 74px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-sizing: border-box;
        }
        .top-box-dark {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 10px 15px;
            border-radius: 12px;
            text-align: center;
            color: white;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            height: 74px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-sizing: border-box;
        }
        .stButton>button {
            border-radius: 6px;
            font-weight: 600;
            padding: 4px 8px;
            font-size: 13px;
            transition: all 0.2s ease;
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- INITIALISATION DU MANAGER ---
    nom_fichier_eq = f"effectif_{equipe_assignee.replace(' ', '_').replace('-', '')}.json"

    @st.cache_resource
    def get_manager(fichier):
        return EquipeManager(fichier=fichier)

    manager = get_manager(nom_fichier_eq)

    pretes_key = f"joueurs_pretes_match_{equipe_assignee}"
    if pretes_key not in st.session_state:
        st.session_state[pretes_key] = {}

    def get_membre(nom):
        if nom in manager.joueuses:
            return manager.joueuses[nom]
        return st.session_state.get(pretes_key, {}).get(nom)

    page_key = f"page_actuelle_{equipe_assignee}"
    if page_key not in st.session_state:
        st.session_state[page_key] = "accueil"

    def aller_a(page):
        st.session_state[page_key] = page
        st.rerun()

    def get_badge_poste_html(poste):
        if "Arrière" in poste or "Demi-centre" in poste:
            return '<span style="background-color: #dbeafe; color: #1e40af; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">🔵 Base Arrière</span>'
        elif "Ailière" in poste or "Ailier" in poste:
            return f'<span style="background-color: #d1fae5; color: #065f46; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{L["badge_ailier"]}</span>'
        elif "Pivot" in poste:
            return '<span style="background-color: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">🟠 Pivot</span>'
        elif "Gardienne" in poste or "Gardien" in poste:
            return f'<span style="background-color: #f3e8ff; color: #6b21a8; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{L["badge_gardien"]}</span>'
        return f'<span style="background-color: #f3f4f6; color: #374151; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{poste}</span>'

    def get_prefix_couleur(poste):
        if "Arrière" in poste or "Demi-centre" in poste:
            return "🔵"
        elif "Ailière" in poste or "Ailier" in poste:
            return "🟢"
        elif "Pivot" in poste:
            return "🟠"
        elif "Gardienne" in poste or "Gardien" in poste:
            return "🟣"
        return "⚪"

    def enregistrer_zone_tir_live(nom_membre, zone, est_succes, est_gardien=False):
        zones_key = f"zones_tirs_match_{equipe_assignee}"
        if zones_key not in st.session_state:
            st.session_state[zones_key] = {}
        if nom_membre not in st.session_state[zones_key]:
            st.session_state[zones_key][nom_membre] = {}
        if zone not in st.session_state[zones_key][nom_membre]:
            st.session_state[zones_key][nom_membre][zone] = {"succes": 0, "echec": 0}
        
        if est_succes:
            st.session_state[zones_key][nom_membre][zone]["succes"] += 1
        else:
            st.session_state[zones_key][nom_membre][zone]["echec"] += 1

    # ==========================================
    # 1. ÉCRAN D'ACCUEIL
    # ==========================================
    if st.session_state[page_key] == "accueil":
        st.title("🤾‍♀️ HandStats Pro")
        st.markdown(f"### L'outil de performance et de suivi tactique de terrain pour **{equipe_assignee}**.")
        
        match_encours_key = f"match_en_cours_{equipe_assignee}"
        nom_m_key = f"nom_match_actuel_{equipe_assignee}"
        
        if st.session_state.get(match_encours_key, False):
            nom_m = st.session_state.get(nom_m_key, "Match")
            st.markdown("---")
            with st.container(border=True):
                st.markdown(f"### ⚡ Match en cours détecté pour {equipe_assignee} : **{nom_m}**")
                st.write("Le match précédent n'a pas été archivé. Vos données et votre chrono sont en sécurité.")
                if st.button("▶️ Reprendre le match en cours", type="primary", use_container_width=True, key=f"btn_reprendre_{equipe_assignee}"):
                    aller_a("match")
            st.markdown("---")
        else:
            st.divider()

        col1, col2, col3 = st.columns(3)
        
        with col1:
            with st.container(border=True):
                st.markdown("#### ⚡ Saisie & Match")
                st.write("Feuille de match en direct, tirs, duels, pertes de balle et discipline.")
                if st.button("Lancer / Match en direct", type="primary", use_container_width=True, key=f"btn_nav_match_{equipe_assignee}"):
                    aller_a("match")
                
        with col2:
            with st.container(border=True):
                st.markdown("#### 📈 Analyse & Saison")
                st.write("Historique des rencontres, bilans d'équipe, tendances et stats.")
                if st.button("Stats Saison", use_container_width=True, key=f"btn_nav_saison_{equipe_assignee}"):
                    aller_a("saison")
                
        with col3:
            with st.container(border=True):
                st.markdown(f"#### 👥 {L['effectif']}")
                st.write(f"Gestion des {L['joueurs']}, numéros, postes et profils.")
                if st.button("Gérer l'effectif", use_container_width=True, key=f"btn_nav_effectif_{equipe_assignee}"):
                    aller_a("effectif")

    # ==========================================
    # 2. ÉCRAN : MATCH EN DIRECT
    # ==========================================
    elif st.session_state[page_key] == "match":
        if st.button("⬅️ Retour à l'accueil", key=f"btn_retour_accueil_{equipe_assignee}"):
            aller_a("accueil")
            
        st.header(f"⚡ Cockpit de Match en Direct — {equipe_assignee}")

        if not manager.joueuses:
            st.warning(f"Aucun(e) {L['joueur']} enregistré(e). Rendez-vous dans l'onglet 'Effectif' pour en ajouter.")
        else:
            match_encours_key = f"match_en_cours_{equipe_assignee}"
            
            if not st.session_state.get(match_encours_key, False):
                with st.container(border=True):
                    st.subheader("📋 Composition de la Feuille de Match")
                    st.write(f"Saisissez le nom de la rencontre pour l'équipe **{equipe_assignee}** et sélectionnez les {L['joueurs']} {L['convoquees']} :")
                    
                    with st.form(key=f"form_config_match_{equipe_assignee}"):
                        nom_match_saisi = st.text_input("Nom / Adversaire du match", value="J1 - Match 1")
                        
                        st.markdown("---")
                        st.markdown(f"**{L['joueurs'].capitalize()} de l'effectif principal :**")
                        
                        membres_coches = {}
                        for nom, p_obj in manager.joueuses.items():
                            membres_coches[nom] = st.checkbox(
                                f"#{p_obj.numero} - {p_obj.nom} ({p_obj.poste})", 
                                value=True, 
                                key=f"chk_membre_{equipe_assignee}_{nom}"
                            )
                        
                        st.markdown("---")
                        st.markdown(f"⚡ **Convoquer des {L['joueurs']} d'autres équipes du club (Prêt / Surclassement temporaire)**")
                        
                        club_equipes = st.session_state.get("club_equipes", ["Séniors M", "Séniors F", "-18M", "-15F"])
                        autres_equipes = [eq for eq in club_equipes if eq != equipe_assignee]
                        toutes_joueuses_club = manager.recuperer_toutes_les_joueuses_du_club(autres_equipes)
                        
                        surclassements_coches = {}
                        for eq in autres_equipes:
                            membres_cette_equipe = {
                                nom: info for nom, info in toutes_joueuses_club.items() 
                                if info["equipe_origine"] == eq and nom not in manager.joueuses
                            }
                            if membres_cette_equipe:
                                with st.expander(f"📁 Équipe : {eq} ({len(membres_cette_equipe)} {L['joueur']}(s) disponible(s))"):
                                    for nom_ext, info_ext in membres_cette_equipe.items():
                                        poste_ext = info_ext["poste"]
                                        num_ext = info_ext["numero"]
                                        surclassements_coches[nom_ext] = st.checkbox(
                                            f"#{num_ext} - {nom_ext} ({poste_ext})",
                                            value=False,
                                            key=f"chk_surclassement_{equipe_assignee}_{nom_ext}"
                                        )

                        st.markdown("---")
                        valider_feuille = st.form_submit_button(
                            "Lancer le match en direct", 
                            type="primary", 
                            key=f"btn_submit_match_{equipe_assignee}"
                        )
                        
                        if valider_feuille:
                            membres_selectionnes = [nom for nom, est_coche in membres_coches.items() if est_coche]
                            membres_surclassees = [nom for nom, est_coche in surclassements_coches.items() if est_coche]
                            
                            st.session_state[pretes_key] = {}
                            for nom_s in membres_surclassees:
                                info_s = toutes_joueuses_club[nom_s]
                                if nom_s not in manager.joueuses:
                                    if info_s["type"] == "gardienne":
                                        st.session_state[pretes_key][nom_s] = Gardienne(nom_s, info_s["poste"], info_s["numero"])
                                    else:
                                        st.session_state[pretes_key][nom_s] = JoueuseDeChamp(nom_s, info_s["poste"], info_s["numero"])
                                membres_selectionnes.append(nom_s)

                            if not nom_match_saisi.strip():
                                st.error("Le nom du match ne peut pas être vide.")
                            elif not membres_selectionnes:
                                st.error(f"Vous devez sélectionner au moins un(e) {L['joueur']}.")
                            else:
                                st.session_state[f"match_en_cours_{equipe_assignee}"] = True
                                st.session_state[f"nom_match_actuel_{equipe_assignee}"] = nom_match_saisi
                                st.session_state[f"joueuses_actives_match_{equipe_assignee}"] = membres_selectionnes
                                
                                st.session_state[f"terrain_joueuses_{equipe_assignee}"] = membres_selectionnes[:7]
                                st.session_state[f"banc_joueuses_{equipe_assignee}"] = membres_selectionnes[7:]
                                
                                st.session_state[f"attaques_adversaires_match_{equipe_assignee}"] = {
                                    "Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0
                                }
                                
                                terrain_j_key = f"terrain_joueuses_{equipe_assignee}"
                                if st.session_state[terrain_j_key]:
                                    st.session_state[f"joueuse_focus_live_{equipe_assignee}"] = st.session_state[terrain_j_key][0]
                                else:
                                    st.session_state[f"joueuse_focus_live_{equipe_assignee}"] = None
                                
                                st.session_state[f"chrono_en_cours_{equipe_assignee}"] = False
                                st.session_state[f"chrono_secondes_cumulees_{equipe_assignee}"] = 0
                                st.session_state[f"chrono_debut_{equipe_assignee}"] = None
                                st.session_state[f"journal_actions_match_{equipe_assignee}"] = []
                                st.session_state[f"commentaires_staff_match_{equipe_assignee}"] = []
                                st.session_state[f"zones_tirs_match_{equipe_assignee}"] = {}
                                st.session_state[f"pop_up_active_{equipe_assignee}"] = None
                                st.rerun()
            
            else:
                nom_match_actuel = st.session_state.get(f"nom_match_actuel_{equipe_assignee}", "Match")
                joueuses_actives = st.session_state.get(f"joueuses_actives_match_{equipe_assignee}", [])
                
                terrain_key = f"terrain_joueuses_{equipe_assignee}"
                banc_key = f"banc_joueuses_{equipe_assignee}"
                zones_key = f"zones_tirs_match_{equipe_assignee}"
                popup_key = f"pop_up_active_{equipe_assignee}"
                chrono_enc_key = f"chrono_en_cours_{equipe_assignee}"
                chrono_secs_key = f"chrono_secondes_cumulees_{equipe_assignee}"
                chrono_deb_key = f"chrono_debut_{equipe_assignee}"
                journal_key = f"journal_actions_match_{equipe_assignee}"
                commentaires_key = f"commentaires_staff_match_{equipe_assignee}"
                focus_key = f"joueuse_focus_live_{equipe_assignee}"
                att_adv_key = f"attaques_adversaires_match_{equipe_assignee}"

                if terrain_key not in st.session_state:
                    st.session_state[terrain_key] = joueuses_actives[:7]
                if banc_key not in st.session_state:
                    st.session_state[banc_key] = joueuses_actives[7:]
                if zones_key not in st.session_state:
                    st.session_state[zones_key] = {}

                def formater_temps(secondes):
                    m = secondes // 60
                    s = secondes % 60
                    return f"{m:02d}:{s:02d}"

                def enregistrer_action(type_action, details, zone=None):
                    if journal_key not in st.session_state:
                        st.session_state[journal_key] = []
                    
                    secs = st.session_state.get(chrono_secs_key, 0)
                    if st.session_state.get(chrono_enc_key, False) and st.session_state.get(chrono_deb_key):
                        secs += int(time.time() - st.session_state[chrono_deb_key])
                    
                    temps_str = formater_temps(secs)
                    detail_complet = f"{details} [{zone}]" if zone else details
                    entry = {
                        "temps": temps_str,
                        "type_action": type_action,
                        "details": detail_complet
                    }
                    if zone:
                        entry["zone"] = zone
                    st.session_state[journal_key].append(entry)

                @st.dialog("🎯 Localisation de l'Action sur la Cage")
                def modal_saisie_cage(p_nom, action_type):
                    p_obj = get_membre(p_nom)
                    st.markdown(f"{L['joueur'].capitalize()} : **#{p_obj.numero} {p_obj.nom}** — Action : **{action_type}**")
                    st.write("")
                    
                    zone_sel = afficher_grille_saisie_interactive(f"modal_{equipe_assignee}_{p_nom}_{action_type}", action_type=action_type)
                    if zone_sel:
                        if action_type == "But":
                            p_obj.buts += 1
                            p_obj.tirs += 1
                            enregistrer_zone_tir_live(p_obj.nom, zone_sel, est_succes=True)
                            enregistrer_action("But", f"#{p_obj.numero} {p_obj.nom}", zone=zone_sel)
                        elif action_type == "Tir raté":
                            p_obj.tirs += 1
                            enregistrer_zone_tir_live(p_obj.nom, zone_sel, est_succes=False)
                            enregistrer_action("Tir raté", f"#{p_obj.numero} {p_obj.nom}", zone=zone_sel)
                        elif action_type == "Arrêt décisif":
                            p_obj.arrets += 1
                            p_obj.tirs_subis += 1
                            enregistrer_zone_tir_live(p_obj.nom, zone_sel, est_succes=True, est_gardien=True)
                            enregistrer_action("Arrêt décisif", f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})", zone=zone_sel)
                        elif action_type == "But encaissé":
                            p_obj.tirs_subis += 1
                            p_obj.buts_encaisses += 1
                            enregistrer_zone_tir_live(p_obj.nom, zone_sel, est_succes=False, est_gardien=True)
                            enregistrer_action("But encaissé", f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})", zone=zone_sel)
                        
                        manager.sauvegarder_donnees()
                        st.session_state[popup_key] = None
                        st.rerun()

                if st.session_state.get(popup_key):
                    p_nom_popup, act_popup = st.session_state[popup_key]
                    modal_saisie_cage(p_nom_popup, act_popup)

                secondes_totales = st.session_state.get(chrono_secs_key, 0)
                if st.session_state.get(chrono_enc_key, False) and st.session_state.get(chrono_deb_key):
                    secondes_totales += int(time.time() - st.session_state[chrono_deb_key])

                if st.session_state.get(chrono_enc_key, False) and not st.session_state.get(popup_key):
                    st_autorefresh(interval=1000, key=f"chrono_auto_refresh_{equipe_assignee}")

                total_buts_marques = sum(get_membre(n).buts for n in joueuses_actives if get_membre(n) and hasattr(get_membre(n), 'buts'))
                total_buts_encaisses = sum(get_membre(n).buts_encaisses for n in joueuses_actives if get_membre(n) and isinstance(get_membre(n), Gardienne))
                temps_actuel_str = formater_temps(secondes_totales)

                c_top_info, c_top_score_chrono, c_top_controls = st.columns([1.2, 2.6, 1.2])
                
                with c_top_info:
                    st.markdown(f"""
                        <div class="top-box">
                            <div style="font-size: 10px; color: #64748b; font-weight: bold; text-transform: uppercase;">Rencontre</div>
                            <div style="font-size: 14px; font-weight: 700; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{nom_match_actuel}</div>
                        </div>
                    """, unsafe_allow_html=True)

                with c_top_score_chrono:
                    st.markdown(f"""
                        <div class="top-box-dark">
                            <div style="display: flex; justify-content: space-around; align-items: center;">
                                <div>
                                    <div style="font-size: 9px; letter-spacing: 1px; text-transform: uppercase; color: #94a3b8; font-weight: 600;">Score</div>
                                    <div style="font-size: 22px; font-weight: 800; color: #f8fafc; line-height: 1.1;">{total_buts_marques}  —  {total_buts_encaisses}</div>
                                </div>
                                <div style="border-left: 1px solid #334155; height: 28px; margin: 0 10px;"></div>
                                <div>
                                    <div style="font-size: 9px; letter-spacing: 1px; text-transform: uppercase; color: #94a3b8; font-weight: 600;">Chrono</div>
                                    <div style="font-size: 22px; font-weight: 800; color: #38bdf8; line-height: 1.1; font-family: monospace;">{temps_actuel_str}</div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                with c_top_controls:
                    with st.container(border=True):
                        st.markdown("<div style='font-size: 9px; font-weight: bold; text-transform: uppercase; color: #64748b; text-align: center; margin-bottom: 2px;'>Contrôle Temps</div>", unsafe_allow_html=True)
                        cc1, cc2, cc3 = st.columns(3)
                        with cc1:
                            start_btn = st.button("▶️", key=f"chrono_start_{equipe_assignee}", use_container_width=True)
                        with cc2:
                            pause_btn = st.button("⏸️", key=f"chrono_pause_{equipe_assignee}", use_container_width=True)
                        with cc3:
                            reset_btn = st.button("🔄", key=f"chrono_reset_{equipe_assignee}", use_container_width=True)
                
                if start_btn:
                    if not st.session_state.get(chrono_enc_key, False):
                        st.session_state[chrono_enc_key] = True
                        st.session_state[chrono_deb_key] = time.time()
                        st.rerun()
                if pause_btn:
                    if st.session_state.get(chrono_enc_key, False):
                        st.session_state[chrono_secs_key] += int(time.time() - st.session_state[chrono_deb_key])
                        st.session_state[chrono_enc_key] = False
                        st.rerun()
                if reset_btn:
                    st.session_state[chrono_enc_key] = False
                    st.session_state[chrono_secs_key] = 0
                    st.session_state[chrono_deb_key] = None
                    st.rerun()

                st.divider()
                
                st.markdown(f"🏃‍♀️ **7 Majeur sur le Terrain (Clique pour sélectionner le/la {L['joueur']} actif(ve)) :**")
                
                st.session_state[terrain_key] = [j for j in st.session_state.get(terrain_key, []) if get_membre(j)]
                st.session_state[banc_key] = [j for j in st.session_state.get(banc_key, []) if get_membre(j)]
                
                terrain_list = st.session_state[terrain_key]
                tous_membres_dispos = list(manager.joueuses.keys()) + list(st.session_state.get(pretes_key, {}).keys())
                
                if not terrain_list and tous_membres_dispos:
                    st.session_state[terrain_key] = tous_membres_dispos[:7]
                    st.session_state[banc_key] = tous_membres_dispos[7:]
                    terrain_list = st.session_state[terrain_key]

                if not st.session_state.get(focus_key) or not get_membre(st.session_state[focus_key]):
                    if terrain_list:
                        st.session_state[focus_key] = terrain_list[0]
                    elif tous_membres_dispos:
                        st.session_state[focus_key] = tous_membres_dispos[0]

                cols_terrain = st.columns(max(len(terrain_list), 1))
                for idx, nom_j in enumerate(terrain_list):
                    p_item = get_membre(nom_j)
                    if p_item:
                        col_cible = cols_terrain[idx % len(cols_terrain)]
                        with col_cible:
                            est_actif = (nom_j == st.session_state.get(focus_key))
                            type_btn = "primary" if est_actif else "secondary"
                            prefix = get_prefix_couleur(p_item.poste)
                            label_btn = f"{prefix} #{p_item.numero} {p_item.nom.split()[0]}"
                            
                            if st.button(label_btn, key=f"terrain_j_{equipe_assignee}_{nom_j}", use_container_width=True, type=type_btn):
                                st.session_state[focus_key] = nom_j
                                st.rerun()

                with st.expander("🔄 Gérer les rotations (Remplacements rapides)"):
                    r_col1, r_col2, r_col3 = st.columns([2, 2, 1])
                    with r_col1:
                        sortant = st.selectbox("Sort du terrain ⬇️", terrain_list, key=f"sel_sortant_{equipe_assignee}")
                    with r_col2:
                        banc_dispo = st.session_state[banc_key] if st.session_state[banc_key] else ["Aucune"]
                        entrant = st.selectbox("Entre sur le terrain ⬆️", banc_dispo, key=f"sel_entrant_{equipe_assignee}")
                    with r_col3:
                        st.write("")
                        st.write("")
                        if st.button("🔄 Intervertir", type="primary", use_container_width=True, key=f"btn_intervertir_{equipe_assignee}"):
                            if st.session_state[banc_key] and sortant in terrain_list and entrant in st.session_state[banc_key]:
                                st.session_state[terrain_key].remove(sortant)
                                st.session_state[banc_key].remove(entrant)
                                st.session_state[terrain_key].append(entrant)
                                st.session_state[banc_key].append(sortant)
                                if st.session_state.get(focus_key) == sortant:
                                    st.session_state[focus_key] = entrant
                                st.success(f"Remplacement : {entrant} ➡️ {sortant}")
                                st.rerun()
                            else:
                                st.warning("Impossible d'effectuer le remplacement.")

                st.divider()
                
                nom_focus = st.session_state.get(focus_key)
                if not nom_focus or not get_membre(nom_focus):
                    if tous_membres_dispos:
                        st.session_state[focus_key] = tous_membres_dispos[0]
                        nom_focus = st.session_state[focus_key]

                if not nom_focus or not get_membre(nom_focus):
                    st.warning(f"Sélectionnez un(e) {L['joueur']} actif(ve) sur le terrain.")
                else:
                    p_obj = get_membre(nom_focus)
                    
                    with st.container(border=True):
                        h_col1, h_col2, h_col3 = st.columns([2.2, 1.8, 2.5])
                        with h_col1:
                            st.markdown(f"#### ⚡ #{p_obj.numero} - {p_obj.nom}")
                        with h_col2:
                            st.markdown(get_badge_poste_html(p_obj.poste), unsafe_allow_html=True)
                        with h_col3:
                            if isinstance(p_obj, JoueuseDeChamp):
                                st.markdown(f"<div style='font-size: 15px; font-weight: 800; color: #ffffff; background-color: #1e293b; padding: 6px 10px; border-radius: 6px; text-align: center;'>🎯 {p_obj.buts}/{p_obj.tirs} buts <span style='font-size: 11px; color: #94a3b8;'>({p_obj.efficacite_tirs()}%)</span> | Passes D. : {p_obj.passes_decisives}</div>", unsafe_allow_html=True)
                            elif isinstance(p_obj, Gardienne):
                                st.markdown(f"<div style='font-size: 15px; font-weight: 800; color: #ffffff; background-color: #1e293b; padding: 6px 10px; border-radius: 6px; text-align: center;'>🧤 {p_obj.arrets}/{p_obj.tirs_subis} arrêts <span style='font-size: 11px; color: #94a3b8;'>({p_obj.pourcentage_arrets()}%)</span></div>", unsafe_allow_html=True)

                        st.markdown("---")
                        
                        if isinstance(p_obj, JoueuseDeChamp):
                            col_atk_box, col_def_box = st.columns(2)
                            
                            with col_atk_box:
                                with st.container(border=True):
                                    st.markdown("##### ⚔️ ATTAQUE")
                                    
                                    ba1, ba2 = st.columns(2)
                                    with ba1:
                                        if st.button("🟢 +1 But", key=f"btn_but_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            st.session_state[popup_key] = (p_obj.nom, "But")
                                            st.rerun()
                                    with ba2:
                                        if st.button("🔴 Tir raté", key=f"btn_tirete_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            st.session_state[popup_key] = (p_obj.nom, "Tir raté")
                                            st.rerun()

                                    ba3, ba4 = st.columns(2)
                                    with ba3:
                                        if st.button("⚔️ Duel Gagné", key=f"btn_dog_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_off_gagnes += 1
                                            enregistrer_action("Duel Offensif Gagné", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()
                                    with ba4:
                                        if st.button("❌ Duel Perdu", key=f"btn_dop_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_off_perdus += 1
                                            enregistrer_action("Duel Offensif Perdu", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()

                                    ba5, ba6 = st.columns(2)
                                    with ba5:
                                        if st.button("📤 Perte (Passe)", key=f"btn_pb_passe_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.pertes_de_balles_passe += 1
                                            enregistrer_action("Perte de balle (Passe)", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()
                                    with ba6:
                                        if st.button("⚠️ Perte (Faute)", key=f"btn_pb_faute_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.pertes_de_balles_faute += 1
                                            enregistrer_action("Perte de balle (Faute)", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()

                                    if st.button("🤝 +1 Passe Décisive", key=f"btn_pd_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                        p_obj.passes_decisives += 1
                                        enregistrer_action("Passe Décisive", f"#{p_obj.numero} {p_obj.nom}")
                                        manager.sauvegarder_donnees()
                                        st.rerun()

                            with col_def_box:
                                with st.container(border=True):
                                    st.markdown("##### 🛡️ DÉFENSE & DISCIPLINE")
                                    
                                    bd1, bd2 = st.columns(2)
                                    with bd1:
                                        if st.button("🛡️ Duel Gagné", key=f"btn_ddg_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_def_gagnes += 1
                                            enregistrer_action("Duel Défensif Gagné", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()
                                    with bd2:
                                        if st.button("⚠️ Duel Perdu", key=f"btn_ddp_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_def_perdus += 1
                                            enregistrer_action("Duel Défensif Perdu", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()

                                    bd3, bd4 = st.columns(2)
                                    with bd3:
                                        if st.button("⚡ Interception", key=f"btn_int_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.interceptions += 1
                                            enregistrer_action("Interception", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()
                                    with bd4:
                                        if st.button("🧱 Neutralisation", key=f"btn_neut_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.neutralisations += 1
                                            enregistrer_action("Neutralisation", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()

                                    if st.button("🔥 Perte provoquée", key=f"btn_bp_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                        p_obj.pertes_balles_provoquees += 1
                                        enregistrer_action("Perte de balle provoquée", f"#{p_obj.numero} {p_obj.nom}")
                                        manager.sauvegarder_donnees()
                                        st.rerun()

                                    bs1, bs2 = st.columns(2)
                                    with bs1:
                                        if st.button("🟨 +1 Jaune", key=f"btn_jaune_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.cartons_jaunes += 1
                                            enregistrer_action("Carton Jaune", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()
                                    with bs2:
                                        if st.button("⏱️ + 2min", key=f"btn_2min_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                            p_obj.exclusions_2min += 1
                                            enregistrer_action("Exclusion 2min", f"#{p_obj.numero} {p_obj.nom}")
                                            manager.sauvegarder_donnees()
                                            st.rerun()

                        elif isinstance(p_obj, Gardienne):
                            g1, g2 = st.columns(2)
                            with g1:
                                if st.button("🧤 +1 Arrêt décisif", key=f"btn_arret_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                    st.session_state[popup_key] = (p_obj.nom, "Arrêt décisif")
                                    st.rerun()
                                if st.button("🟢 +1 But (marqué)", key=f"btn_gbut_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                    p_obj.buts += 1
                                    p_obj.tirs += 1
                                    enregistrer_action(f"But ({L['gardien']})", f"#{p_obj.numero} {p_obj.nom}")
                                    manager.sauvegarder_donnees()
                                    st.rerun()
                                if st.button("🟨 +1 Jaune", key=f"btn_gjaune_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                    p_obj.cartons_jaunes += 1
                                    enregistrer_action("Carton Jaune", f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})")
                                    manager.sauvegarder_donnees()
                                    st.rerun()
                            with g2:
                                if st.button("🥅 But encaissé", key=f"btn_enc_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                    st.session_state[popup_key] = (p_obj.nom, "But encaissé")
                                    st.rerun()
                                if st.button("🔴 Tir raté", key=f"btn_gtirete_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                    p_obj.tirs += 1
                                    enregistrer_action(f"Tir raté ({L['gardien']})", f"#{p_obj.numero} {p_obj.nom}")
                                    manager.sauvegarder_donnees()
                                    st.rerun()
                                if st.button("⏱️ + 2min", key=f"btn_g2min_{equipe_assignee}_{p_obj.nom}", use_container_width=True):
                                    p_obj.exclusions_2min += 1
                                    enregistrer_action("Exclusion 2min", f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})")
                                    manager.sauvegarder_donnees()
                                    st.rerun()

                # --- SUIVI TACTIQUE & NOTES DU BANC ---
                with st.container(border=True):
                    st.subheader("📋 Suivi Tactique — Attaques Adverses & Notes du Staff")
                    
                    if att_adv_key not in st.session_state:
                        st.session_state[att_adv_key] = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}

                    t_col1, t_col2, t_col3, t_col4, t_col5, t_col6 = st.columns([1, 1, 1, 1, 1, 2])
                    with t_col1:
                        if st.button("🔄 Yago", use_container_width=True, key=f"att_btn_yago_{equipe_assignee}"):
                            st.session_state[att_adv_key]["Yago"] += 1
                            enregistrer_action("Attaque adverse", "Système Yago")
                            st.toast("Système Yago enregistré !", icon="📊")
                            st.rerun()
                    with t_col2:
                        if st.button("🔄 Yego", use_container_width=True, key=f"att_btn_yego2_{equipe_assignee}"):
                            st.session_state[att_adv_key]["Yego"] += 1
                            enregistrer_action("Attaque adverse", "Système Yego")
                            st.toast("Système Yego enregistré !", icon="📊")
                            st.rerun()
                    with t_col3:
                        if st.button("🔄 Montp.", use_container_width=True, key=f"att_btn_montpellier_{equipe_assignee}"):
                            st.session_state[att_adv_key]["Montpellier"] += 1
                            enregistrer_action("Attaque adverse", "Système Montpellier")
                            st.toast("Système Montpellier enregistré !", icon="📊")
                            st.rerun()
                    with t_col4:
                        if st.button("🔄 Croisé", use_container_width=True, key=f"att_btn_croise_{equipe_assignee}"):
                            st.session_state[att_adv_key]["Croisé"] += 1
                            enregistrer_action("Attaque adverse", "Système Croisé")
                            st.toast("Système Croisé enregistré !", icon="📊")
                            st.rerun()
                    with t_col5:
                        if st.button("🔄 Autre", use_container_width=True, key=f"att_btn_autre_{equipe_assignee}"):
                            st.session_state[att_adv_key]["Autre"] += 1
                            enregistrer_action("Attaque adverse", "Système Autre")
                            st.toast("Autre système enregistré !", icon="📊")
                            st.rerun()
                    
                    st.write("")
                    df_att_compact = pd.DataFrame([st.session_state[att_adv_key]])
                    st.dataframe(df_att_compact, use_container_width=True, hide_index=True)

                    with st.form(key=f"form_commentaire_staff_bottom_{equipe_assignee}", clear_on_submit=True):
                        txt_com_bot = st.text_input("💬 Ajouter un fait de match / note rapide", placeholder="Ex: Temps mort tactique, changement de défense...")
                        if st.form_submit_button("Ajouter au journal de match") and txt_com_bot.strip():
                            if commentaires_key not in st.session_state:
                                st.session_state[commentaires_key] = []
                            st.session_state[commentaires_key].append({
                                "temps": temps_actuel_str, "texte": txt_com_bot.strip()
                            })
                            st.success("Note enregistrée !")

                st.divider()

                # --- DASHBOARD & SYNTHÈSE LIVE ---
                with st.container(border=True):
                    st.subheader("📊 Dashboard & Synthèse Live de la Rencontre")
                    
                    champ_actives = [get_membre(n) for n in joueuses_actives if get_membre(n) and isinstance(get_membre(n), JoueuseDeChamp)]
                    gard_actives = [get_membre(n) for n in joueuses_actives if get_membre(n) and isinstance(get_membre(n), Gardienne)]
                    
                    tot_b = sum(j.buts for j in champ_actives) + sum(g.buts for g in gard_actives)
                    tot_t = sum(j.tirs for j in champ_actives) + sum(g.tirs for g in gard_actives)
                    eff_eq = round((tot_b / tot_t * 100), 1) if tot_t > 0 else 0.0
                    
                    tot_pp = sum(j.pertes_de_balles_passe for j in champ_actives)
                    tot_pf = sum(j.pertes_de_balles_faute for j in champ_actives)
                    tot_pertes = tot_pp + tot_pf
                    
                    tot_dog = sum(j.duels_off_gagnes for j in champ_actives)
                    tot_dop = sum(j.duels_off_perdus for j in champ_actives)
                    
                    tot_arrets = sum(g.arrets for g in gard_actives)
                    tot_subis = sum(g.tirs_subis for g in gard_actives)
                    pct_arrets = round((tot_arrets / tot_subis * 100), 1) if tot_subis > 0 else 0.0

                    d_col1, d_col2, d_col3, d_col4 = st.columns(4)
                    d_col1.metric("Efficacité Tirs Équipe", f"{eff_eq}%", f"{tot_b} buts / {tot_t} tirs")
                    d_col2.metric("Pertes de Balle", tot_pertes, f"Passes: {tot_pp} | Fautes: {tot_pf}")
                    d_col3.metric(f"Arrêts {L['gardiens'].capitalize()}", f"{pct_arrets}%", f"{tot_arrets} arrêts / {tot_subis} tirs")
                    d_col4.metric("Duels Offensifs Gagnés", f"{tot_dog} / {tot_dog + tot_dop}" if (tot_dog + tot_dop) > 0 else "0/0")

                    st.markdown("---")
                    st.markdown("**🏃‍♀️ Feuille de Match en Temps Réel**")
                    
                    terrain_objs = [get_membre(n) for n in st.session_state[terrain_key] if get_membre(n)]
                    data_terrain = []
                    for j in terrain_objs:
                        if isinstance(j, JoueuseDeChamp):
                            data_terrain.append({
                                "N°": j.numero, "Nom": j.nom, "Poste": j.poste, 
                                "Buts/Tirs": f"{j.buts}/{j.tirs} ({j.efficacite_tirs()}%)", 
                                "Passes D.": j.passes_decisives, "Pertes": j.pertes_de_balles_passe + j.pertes_de_balles_faute,
                                "🟨": j.cartons_jaunes, "⏱️": j.exclusions_2min
                            })
                        elif isinstance(j, Gardienne):
                            data_terrain.append({
                                "N°": j.numero, "Nom": j.nom, "Poste": L["gardien"], 
                                "Buts/Tirs": f"{j.buts}/{j.tirs} ({round(j.buts/j.tirs*100,1) if j.tirs>0 else 0.0}%)",
                                "Arrêts/Subis": f"{j.arrets}/{j.tirs_subis} ({j.pourcentage_arrets()}%)",
                                "🟨": j.cartons_jaunes, "⏱️": j.exclusions_2min
                            })
                    if data_terrain:
                        st.dataframe(data_terrain, use_container_width=True, hide_index=True)

                    if commentaires_key in st.session_state and st.session_state[commentaires_key]:
                        st.markdown("**💬 Journal des faits de match enregistrés :**")
                        for note in st.session_state[commentaires_key]:
                            st.markdown(f"- **`{note['temps']}`** : {note['texte']}")

                st.divider()

                # --- ESPACE MI-TEMPS & BILAN TACTIQUE ---
                with st.expander("⏱️ Espace Mi-temps & Bilan Tactique de Pause", expanded=False):
                    st.markdown("### 🎙️ Debriefing Vestiaires — Synthèse 1ère Période")
                    st.write("Analysez les indicateurs clés pour ajuster votre causerie et vos choix tactiques avant la reprise.")
                    
                    champ_actives_mi = [get_membre(n) for n in joueuses_actives if get_membre(n) and isinstance(get_membre(n), JoueuseDeChamp)]
                    gard_actives_mi = [get_membre(n) for n in joueuses_actives if get_membre(n) and isinstance(get_membre(n), Gardienne)]
                    
                    b_mi = sum(j.buts for j in champ_actives_mi) + sum(g.buts for g in gard_actives_mi)
                    t_mi = sum(j.tirs for j in champ_actives_mi) + sum(g.tirs for g in gard_actives_mi)
                    eff_mi = round((b_mi / t_mi * 100), 1) if t_mi > 0 else 0.0
                    
                    pertes_p_mi = sum(j.pertes_de_balles_passe for j in champ_actives_mi)
                    pertes_f_mi = sum(j.pertes_de_balles_faute for j in champ_actives_mi)
                    
                    arrets_mi = sum(g.arrets for g in gard_actives_mi)
                    subis_mi = sum(g.tirs_subis for g in gard_actives_mi)
                    pct_arr_mi = round((arrets_mi / subis_mi * 100), 1) if subis_mi > 0 else 0.0

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Efficacité Tirs", f"{eff_mi}%", f"{b_mi}/{t_mi} buts")
                    mc2.metric("Pertes de Balle", pertes_p_mi + pertes_f_mi, f"Passe: {pertes_p_mi} | Faute: {pertes_f_mi}")
                    mc3.metric(f"Arrêts {L['gardien']}", f"{pct_arr_mi}%", f"{arrets_mi}/{subis_mi}")
                    mc4.metric("Score Actuel", f"{total_buts_marques} - {total_buts_encaisses}")

                    st.markdown("---")
                    
                    # Agrégation live robuste depuis zones_tirs_match
                    zones_match = st.session_state.get(zones_key, {})
                    agregat_tirs_eq = {}
                    agregat_gard_eq = {}
                    
                    for nom_j, z_dict in zones_match.items():
                        j_obj = get_membre(nom_j)
                        est_gardienne_val = False
                        if j_obj:
                            est_gardienne_val = isinstance(j_obj, Gardienne) or "gardien" in j_obj.poste.lower()
                        
                        cible = agregat_gard_eq if est_gardienne_val else agregat_tirs_eq
                        for z_nom, counts in z_dict.items():
                            if z_nom not in cible:
                                cible[z_nom] = {"succes": 0, "echec": 0}
                            cible[z_nom]["succes"] += counts.get("succes", 0)
                            cible[z_nom]["echec"] += counts.get("echec", 0)

                    col_cage1, col_cage2 = st.columns(2)
                    with col_cage1:
                        afficher_cage_recapitulative(agregat_tirs_eq, titre="Impacts Tirs Équipe (✅ Buts | ❌ Ratés)", inclure_hors_cadre=True)
                    with col_cage2:
                        afficher_cage_recapitulative(agregat_gard_eq, titre=f"Impacts {L['gardiens'].capitalize()} (✅ Arrêts | ❌ Encaissés)", inclure_hors_cadre=False)

                    st.markdown("---")
                    st.markdown("**📊 Utilisation des systèmes adverses en 1ère mi-temps :**")
                    df_att_mi = pd.DataFrame([st.session_state[att_adv_key]])
                    st.dataframe(df_att_mi, use_container_width=True, hide_index=True)

                    if commentaires_key in st.session_state and st.session_state[commentaires_key]:
                        st.markdown("**💬 Remarques du staff notées à chaud :**")
                        for note in st.session_state[commentaires_key]:
                            st.markdown(f"- `{note['temps']}` : {note['texte']}")

                    st.markdown("---")
                    st.markdown("### 📋 Tableau Blanc Tactique (Vestiaires)")
                    afficher_tableau_tactique()
                
                # --- CLÔTURE DE LA RENCONTRE ---
                with st.container(border=True):
                    st.subheader("🏁 Clôture de la Rencontre")
                    
                    with st.expander(f"✏️ Ajuster des statistiques manuellement en cas d'erreur (Adapté au rôle du/de la {L['joueur']})"):
                        joueuses_existantes_actives = [n for n in joueuses_actives if get_membre(n)]
                        if joueuses_existantes_actives:
                            joueuse_a_corriger = st.selectbox(f"Choisir le/la {L['joueur']} à rectifier", joueuses_existantes_actives, key=f"select_correction_live_{equipe_assignee}")
                            p_corr = get_membre(joueuse_a_corriger)
                            
                            with st.form(key=f"form_correction_{equipe_assignee}_{p_corr.nom}"):
                                if isinstance(p_corr, JoueuseDeChamp):
                                    cc1, cc2 = st.columns(2)
                                    with cc1:
                                        c_buts = st.number_input("Buts marqués", min_value=0, value=getattr(p_corr, 'buts', 0))
                                        c_tirs = st.number_input("Tirs totaux", min_value=0, value=getattr(p_corr, 'tirs', 0))
                                        c_pd = st.number_input("Passes décisives", min_value=0, value=getattr(p_corr, 'passes_decisives', 0))
                                        c_ppasse = st.number_input("Pertes de balle (passe)", min_value=0, value=getattr(p_corr, 'pertes_de_balles_passe', 0))
                                        c_pfaute = st.number_input("Pertes de balle (faute)", min_value=0, value=getattr(p_corr, 'pertes_de_balles_faute', 0))
                                        c_dog = st.number_input("Duels off gagnés", min_value=0, value=getattr(p_corr, 'duels_off_gagnes', 0))
                                        c_dop = st.number_input("Duels off perdus", min_value=0, value=getattr(p_corr, 'duels_off_perdus', 0))
                                    with cc2:
                                        c_ddg = st.number_input("Duels déf gagnés", min_value=0, value=getattr(p_corr, 'duels_def_gagnes', 0))
                                        c_ddp = st.number_input("Duels déf perdus", min_value=0, value=getattr(p_corr, 'duels_def_perdus', 0))
                                        c_int = st.number_input("Interceptions", min_value=0, value=getattr(p_corr, 'interceptions', 0))
                                        c_neut = st.number_input("Neutralisations", min_value=0, value=getattr(p_corr, 'neutralisations', 0))
                                        c_prov = st.number_input("Pertes provoquées", min_value=0, value=getattr(p_corr, 'pertes_balles_provoquees', 0))
                                        c_jaune = st.number_input("Cartons jaunes", min_value=0, value=getattr(p_corr, 'cartons_jaunes', 0))
                                        c_2min = st.number_input("Exclusions 2min", min_value=0, value=getattr(p_corr, 'exclusions_2min', 0))

                                    if st.form_submit_button("Valider la correction", type="primary", use_container_width=True):
                                        p_corr.buts = c_buts
                                        p_corr.tirs = c_tirs
                                        p_corr.passes_decisives = c_pd
                                        p_corr.pertes_de_balles_passe = c_ppasse
                                        p_corr.pertes_de_balles_faute = c_pfaute
                                        p_corr.duels_off_gagnes = c_dog
                                        p_corr.duels_off_perdus = c_dop
                                        p_corr.duels_def_gagnes = c_ddg
                                        p_corr.duels_def_perdus = c_ddp
                                        p_corr.interceptions = c_int
                                        p_corr.neutralisations = c_neut
                                        p_corr.pertes_balles_provoquees = c_prov
                                        p_corr.cartons_jaunes = c_jaune
                                        p_corr.exclusions_2min = c_2min
                                        manager.sauvegarder_donnees()
                                        st.success("Correction enregistrée avec succès !")
                                        st.rerun()

                                elif isinstance(p_corr, Gardienne):
                                    cc1, cc2 = st.columns(2)
                                    with cc1:
                                        c_arrets = st.number_input("Arrêts décisifs", min_value=0, value=getattr(p_corr, 'arrets', 0))
                                        c_subis = st.number_input("Tirs subis", min_value=0, value=getattr(p_corr, 'tirs_subis', 0))
                                        c_encaisses = st.number_input("Buts encaissés", min_value=0, value=getattr(p_corr, 'buts_encaisses', 0))
                                        c_jaune = st.number_input("Cartons jaunes", min_value=0, value=getattr(p_corr, 'cartons_jaunes', 0))
                                    with cc2:
                                        c_buts = st.number_input("Buts marqués", min_value=0, value=getattr(p_corr, 'buts', 0))
                                        c_tirs = st.number_input("Tirs totaux pris (attaque)", min_value=0, value=getattr(p_corr, 'tirs', 0))
                                        c_2min = st.number_input("Exclusions 2min", min_value=0, value=getattr(p_corr, 'exclusions_2min', 0))

                                    if st.form_submit_button("Valider la correction", type="primary", use_container_width=True):
                                        p_corr.arrets = c_arrets
                                        p_corr.tirs_subis = c_subis
                                        p_corr.buts_encaisses = c_encaisses
                                        p_corr.cartons_jaunes = c_jaune
                                        p_corr.buts = c_buts
                                        p_corr.tirs = c_tirs
                                        p_corr.exclusions_2min = c_2min
                                        manager.sauvegarder_donnees()
                                        st.success("Correction enregistrée avec succès !")
                                        st.rerun()

                    st.write("")
                    if st.button("🏁 Archiver définitivement ce match et réinitialiser", type="primary", use_container_width=True, key=f"btn_archiver_match_{equipe_assignee}"):
                        pretes_dict = st.session_state.get(pretes_key, {})
                        for nom_p, obj_p in pretes_dict.items():
                            if nom_p not in manager.joueuses:
                                manager.joueuses[nom_p] = obj_p

                        manager.archiver_match(
                            nom_match_actuel, 
                            attaques_adv_data=st.session_state.get(att_adv_key, {}),
                            joueuses_actives=joueuses_actives,
                            journal_actions=st.session_state.get(journal_key, []),
                            commentaires_staff=st.session_state.get(commentaires_key, [])
                        )

                        for nom_p in pretes_dict.keys():
                            if nom_p in manager.joueuses:
                                del manager.joueuses[nom_p]
                        manager.sauvegarder_donnees()

                        st.session_state[f"match_en_cours_{equipe_assignee}"] = False
                        st.session_state[att_adv_key] = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}
                        st.session_state[zones_key] = {}
                        st.session_state[popup_key] = None
                        st.session_state[pretes_key] = {}
                        st.toast("Le match a été archivé avec succès !", icon="✅")
                        aller_a("accueil")

    # ==========================================
    # 3. ÉCRAN : STATS SAISON
    # ==========================================
    elif st.session_state[page_key] == "saison":
        if st.button("⬅️ Retour à l'accueil", key=f"btn_retour_saison_{equipe_assignee}"):
            aller_a("accueil")
            
        st.header(f"📈 Centre d'Analyse & Statistiques — {equipe_assignee}")
        
        tous_membres_saison = list(manager.joueuses.values())
        
        if not manager.joueuses:
            st.info(f"Aucun(e) {L['joueur']} enregistré(e) dans l'effectif.")
        else:
            matchs_archives = []
            for j in tous_membres_saison:
                for m in j.historique_matchs:
                    if m["match"] not in matchs_archives:
                        matchs_archives.append(m["match"])

            sub_tab_matchs, sub_tab_equipe, sub_tab_joueuses = st.tabs([
                "📋 Feuilles de Match Archivées", 
                "👥 Statistiques Équipe",
                f"👤 Statistiques par {L['joueur'].capitalize()}"
            ])

            # --- SOUS-ONGLET 1 : FEUILLES DE MATCH ARCHIVÉES ---
            with sub_tab_matchs:
                if not matchs_archives:
                    st.warning("Aucun match n'a encore été archivé.")
                else:
                    match_choisi = st.selectbox("Sélectionner une rencontre", matchs_archives, key=f"select_match_archive_{equipe_assignee}")
                    
                    lignes_champ = []
                    lignes_gardiennes = []
                    attaques_adv_archive = {}
                    journal_actions_archive = []
                    commentaires_staff_archive = []

                    for j in tous_membres_saison:
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
                                    "N°": j.numero, L['joueur'].capitalize(): j.nom, "Poste": j.poste,
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
                                    "N°": j.numero, L['gardien']: j.nom,
                                    "Buts/Tirs": f"{donnees_m.get('buts', 0)}/{donnees_m.get('tirs', 0)}",
                                    "Arrêts": donnees_m["arrets"], "Tirs Subis": donnees_m["tirs_subis"],
                                    "% Arrêts": f"{round((donnees_m['arrets']/donnees_m['tirs_subis']*100),1)}%" if donnees_m["tirs_subis"] > 0 else "0.0%",
                                    "Buts Encaissés": donnees_m["buts_encaisses"],
                                    "🟨": donnees_m["cartons_jaunes"], "⏱️ 2min": donnees_m["exclusions_2min"]
                                })

                    score_eq = sum(row["Buts"] for row in lignes_champ)
                    for row_g in lignes_gardiennes:
                        b_str = str(row_g["Buts/Tirs"]).split('/')[0]
                        score_eq += int(b_str) if b_str.isdigit() else 0
                    score_adv = sum(row["Buts Encaissés"] for row in lignes_gardiennes)

                    st.markdown(f"### Résultat du match : {score_eq} - {score_adv}")
                    
                    if lignes_champ:
                        st.dataframe(pd.DataFrame(lignes_champ), use_container_width=True, hide_index=True)
                    if lignes_gardiennes:
                        st.dataframe(pd.DataFrame(lignes_gardiennes), use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.markdown("### 🎯 Cartographie des Tirs & Arrêts du Match")
                    
                    agregat_tirs_match_arc = {}
                    agregat_gard_match_arc = {}
                    
                    for j in tous_membres_saison:
                        dm = next((m for m in j.historique_matchs if m["match"] == match_choisi), None)
                        if dm:
                            for act in dm.get("journal_actions", []):
                                det = act.get("details", "")
                                act_type = act.get("type_action", "")
                                if f"#{j.numero} {j.nom}" in det and "[" in det and det.endswith("]"):
                                    zone_ext = det.split("[")[-1].rstrip("]")
                                    est_gardienne_val = isinstance(j, Gardienne) or "gardien" in j.poste.lower()
                                    cible = agregat_gard_match_arc if est_gardienne_val else agregat_tirs_match_arc
                                    
                                    if zone_ext not in cible:
                                        cible[zone_ext] = {"succes": 0, "echec": 0}
                                    
                                    if not est_gardienne_val:
                                        if act_type == "But":
                                            cible[zone_ext]["succes"] += 1
                                        elif act_type == "Tir raté":
                                            cible[zone_ext]["echec"] += 1
                                    else:
                                        if act_type == "Arrêt décisif":
                                            cible[zone_ext]["succes"] += 1
                                        elif act_type == "But encaissé":
                                            cible[zone_ext]["echec"] += 1

                    col_m_c1, col_m_c2 = st.columns(2)
                    with col_m_c1:
                        afficher_cage_recapitulative(agregat_tirs_match_arc, titre="Impacts Tirs Équipe (✅ Buts | ❌ Ratés)", inclure_hors_cadre=True)
                    with col_m_c2:
                        afficher_cage_recapitulative(agregat_gard_match_arc, titre=f"Impacts {L['gardiens'].capitalize()} (✅ Arrêts | ❌ Encaissés)", inclure_hors_cadre=False)

                    st.markdown("---")
                    bilan_existant = ""
                    for j in tous_membres_saison:
                        dm = next((m for m in j.historique_matchs if m["match"] == match_choisi), None)
                        if dm and "bilan_post_match" in dm:
                            bilan_existant = dm["bilan_post_match"]
                            break

                    with st.form(key=f"form_bilan_post_{equipe_assignee}_{match_choisi}"):
                        texte_bilan = st.text_area("Bilan post-match", value=bilan_existant, height=100)
                        if st.form_submit_button("Enregistrer"):
                            manager.sauvegarder_commentaire_post_match(match_choisi, texte_bilan.strip())
                            st.success("Enregistré !")
                            st.rerun()

                    st.divider()
                    st.markdown("### 📥 Téléchargements des Rapports")
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        pdf_officiel_bytes = generer_pdf_match(
                            nom_match=match_choisi, score_eq=score_eq, score_adv=score_adv,
                            lignes_champ=lignes_champ, lignes_gardiennes=lignes_gardiennes,
                            attaques_adversaires=attaques_adv_archive,
                            club_nom=st.session_state.user_session.get("club", "Bordeaux Étudiants Club"),
                            equipe_nom=equipe_assignee
                        )
                        st.download_button("📥 Feuille de Match Officielle (PDF)", data=pdf_officiel_bytes, file_name=f"feuille_match_{match_choisi}.pdf", mime="application/pdf")
                    with col_btn2:
                        pdf_chrono_bytes = generer_pdf_chronologique(
                            nom_match=match_choisi, score_eq=score_eq, score_adv=score_adv,
                            historique_actions=journal_actions_archive, attaques_adv=attaques_adv_archive,
                            commentaires_staff=commentaires_staff_archive,
                            club_nom=st.session_state.user_session.get("club", "Bordeaux Étudiants Club"),
                            equipe_nom=equipe_assignee, bilan_post_match=bilan_existant
                        )
                        st.download_button("📥 Rapport Chronologique & Tactique (PDF)", data=pdf_chrono_bytes, file_name=f"resume_chrono_{match_choisi}.pdf", mime="application/pdf")

            # --- SOUS-ONGLET 2 : STATISTIQUES ÉQUIPE ---
            with sub_tab_equipe:
                st.subheader("👥 Bilan Global & Indicateurs Clés de la Saison")
                if not matchs_archives:
                    st.info("Aucun match archivé.")
                else:
                    total_matchs_joues = len(matchs_archives)
                    champ_list = [j for j in tous_membres_saison if isinstance(j, JoueuseDeChamp)]
                    gard_list = [j for j in tous_membres_saison if isinstance(j, Gardienne)]
                    
                    cumul_buts_eq = sum(sum(m.get("buts", 0) for m in j.historique_matchs) for j in champ_list)
                    cumul_tirs_eq = sum(sum(m.get("tirs", 0) for m in j.historique_matchs) for j in champ_list)
                    cumul_pd_eq = sum(sum(m.get("passes_decisives", 0) for m in j.historique_matchs) for j in champ_list)
                    eff_equipe = round((cumul_buts_eq / cumul_tirs_eq * 100), 1) if cumul_tirs_eq > 0 else 0.0
                    
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    col_m1.metric("Matchs joués", total_matchs_joues)
                    col_m2.metric("Total Buts Équipe", f"{cumul_buts_eq} / {cumul_tirs_eq}", f"{eff_equipe}% réussite")
                    col_m3.metric("Total Passes Décisives", cumul_pd_eq)
                    col_m4.metric(f"{L['joueurs'].capitalize()} effectif", len(manager.joueuses))
                    
                    st.divider()
                    st.markdown("### 🎯 Cartographie Globale Saison — Équipe & Gardiennes")
                    
                    # Agrégation des stats cages sur toute la saison
                    agregat_saison_tirs_eq = {}
                    agregat_saison_gard_eq = {}
                    for j in tous_membres_saison:
                        for m in j.historique_matchs:
                            for act in m.get("journal_actions", []):
                                det = act.get("details", "")
                                act_type = act.get("type_action", "")
                                if f"#{j.numero} {j.nom}" in det and "[" in det and det.endswith("]"):
                                    zone_ext = det.split("[")[-1].rstrip("]")
                                    est_gardienne_val = isinstance(j, Gardienne) or "gardien" in j.poste.lower()
                                    cible = agregat_saison_gard_eq if est_gardienne_val else agregat_saison_tirs_eq
                                    
                                    if zone_ext not in cible:
                                        cible[zone_ext] = {"succes": 0, "echec": 0}
                                    
                                    if not est_gardienne_val:
                                        if act_type == "But":
                                            cible[zone_ext]["succes"] += 1
                                        elif act_type == "Tir raté":
                                            cible[zone_ext]["echec"] += 1
                                    else:
                                        if act_type == "Arrêt décisif":
                                            cible[zone_ext]["succes"] += 1
                                        elif act_type == "But encaissé":
                                            cible[zone_ext]["echec"] += 1

                    col_eq_c1, col_eq_c2 = st.columns(2)
                    with col_eq_c1:
                        afficher_cage_recapitulative(agregat_saison_tirs_eq, titre="Impacts Tirs Globaux Saison (Équipe)", inclure_hors_cadre=True)
                    with col_eq_c2:
                        afficher_cage_recapitulative(agregat_saison_gard_eq, titre=f"Impacts Globaux Saison ({L['gardiens'].capitalize()})", inclure_hors_cadre=False)

                    st.divider()
                    st.markdown("### 📈 Dynamique & Tendances de la Saison")
                    
                    data_tendances = []
                    for m_nom in matchs_archives:
                        m_buts = 0
                        m_tirs = 0
                        m_arrets = 0
                        m_subis = 0
                        
                        for j in tous_membres_saison:
                            dm = next((m for m in j.historique_matchs if m["match"] == m_nom), None)
                            if dm:
                                if isinstance(j, JoueuseDeChamp):
                                    m_buts += dm.get("buts", 0)
                                    m_tirs += dm.get("tirs", 0)
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
                            f"% Arrêts {L['gardiens'].capitalize()} (%)": pct_arr_m
                        })
                    
                    if data_tendances:
                        df_tend = pd.DataFrame(data_tendances).set_index("Match")
                        g_col1, g_col2 = st.columns(2)
                        with g_col1:
                            st.markdown("**🎯 Efficacité Tirs Équipe (%)**")
                            st.line_chart(df_tend[["Efficacité Tirs (%)"]])
                        with g_col2:
                            st.markdown(f"**🧤 Taux d'Arrêts {L['gardiens'].capitalize()} (%)**")
                            st.line_chart(df_tend[[f"% Arrêts {L['gardiens'].capitalize()} (%)"]])

                    st.divider()
                    st.markdown("### 📋 Tableaux Récapitulatifs des Cumuls Saison")
                    
                    if champ_list:
                        st.markdown(f"**🏃‍♀️ Cumul — {L['joueurs'].capitalize()} de Champ**")
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
                        st.markdown(f"**🧤 Cumul — {L['gardiens'].capitalize()}**")
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
                                    "Buts/Tirs": f"{bm}/{tm}",
                                    "Arrêts/Subis": f"{arr}/{sub} ({pct}%)",
                                    "Buts Encaissés": enc,
                                    "🟨": cj, "⏱️": e2
                                })
                        if data_cumul_g:
                            st.dataframe(data_cumul_g, use_container_width=True, hide_index=True)

            # --- SOUS-ONGLET 3 : STATISTIQUES INDIVIDUELLES ---
            with sub_tab_joueuses:
                noms = [j.nom for j in tous_membres_saison]
                if noms:
                    membre_choisi = st.selectbox(f"Sélectionner un(e) {L['joueur']}", noms, key=f"select_saison_membre_{equipe_assignee}")
                    p = next((j for j in tous_membres_saison if j.nom == membre_choisi), None)
                    
                    if p:
                        st.markdown(f"### 🎽 #{p.numero} - {p.nom} *({p.poste})*")
                        
                        if not p.historique_matchs:
                            st.info("Aucune donnée de match enregistrée pour ce profil.")
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

                            st.markdown("### 📈 Évolution des Buts par Match")
                            data_graphe_joueuse = []
                            for m in p.historique_matchs:
                                data_graphe_joueuse.append({
                                    "Match": m["match"],
                                    "Buts": m.get("buts", 0)
                                })
                            if data_graphe_joueuse:
                                df_j_tend = pd.DataFrame(data_graphe_joueuse).set_index("Match")
                                st.line_chart(df_j_tend[["Buts"]])

                            st.divider()
                            
                            zones_saison_joueuse = {}
                            for m in p.historique_matchs:
                                for act in m.get("journal_actions", []):
                                    det = act.get("details", "")
                                    act_type = act.get("type_action", "")
                                    if f"#{p.numero} {p.nom}" in det and "[" in det and det.endswith("]"):
                                        zone_ext = det.split("[")[-1].rstrip("]")
                                        if zone_ext not in zones_saison_joueuse:
                                            zones_saison_joueuse[zone_ext] = {"succes": 0, "echec": 0}
                                        
                                        est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                                        if not est_gardienne_val:
                                            if act_type == "But":
                                                zones_saison_joueuse[zone_ext]["succes"] += 1
                                            elif act_type == "Tir raté":
                                                zones_saison_joueuse[zone_ext]["echec"] += 1
                                        else:
                                            if act_type == "Arrêt décisif":
                                                zones_saison_joueuse[zone_ext]["succes"] += 1
                                            elif act_type == "But encaissé":
                                                zones_saison_joueuse[zone_ext]["echec"] += 1

                            titre_cage_j = (
                                f"🎯 Cartographie Globale Saison — {p.nom} (✅ Arrêts | ❌ Encaissés)"
                                if isinstance(p, Gardienne)
                                else f"🎯 Cartographie Globale Saison — {p.nom} (✅ Buts | ❌ Ratés)"
                            )
                            est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                            afficher_cage_recapitulative(zones_saison_joueuse, titre=titre_cage_j, inclure_hors_cadre=not est_gardienne_val)

                            st.divider()

                            st.subheader("📅 Tableau récapitulatif match par match")
                            historique_propre = []
                            for m in p.historique_matchs:
                                ligne = {k: v for k, v in m.items() if k not in ["score_equipe", "score_adversaire", "journal_actions", "commentaires_staff", "bilan_post_match", "attaques_adversaires"]}
                                ligne["Score"] = f"{m.get('score_equipe', '-')} - {m.get('score_adversaire', '-')}"
                                historique_propre.append(ligne)
                            st.dataframe(historique_propre, use_container_width=True, hide_index=True)

                            st.divider()

                            st.subheader("🔍 Analyse détaillée par rencontre")
                            noms_matchs_joueuse = [m["match"] for m in p.historique_matchs]
                            match_selectionne_j = st.selectbox("Filtrer par rencontre", noms_matchs_joueuse, key=f"sel_match_j_{equipe_assignee}_{p.nom}")
                            
                            match_donnees_specifiques = next((m for m in p.historique_matchs if m["match"] == match_selectionne_j), None)
                            zones_match_specifique = {}
                            
                            if match_donnees_specifiques:
                                for act in match_donnees_specifiques.get("journal_actions", []):
                                    det = act.get("details", "")
                                    act_type = act.get("type_action", "")
                                    if f"#{p.numero} {p.nom}" in det and "[" in det and det.endswith("]"):
                                        zone_ext = det.split("[")[-1].rstrip("]")
                                        if zone_ext not in zones_match_specifique:
                                            zones_match_specifique[zone_ext] = {"succes": 0, "echec": 0}
                                        
                                        est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                                        if not est_gardienne_val:
                                            if act_type == "But":
                                                zones_match_specifique[zone_ext]["succes"] += 1
                                            elif act_type == "Tir raté":
                                                zones_match_specifique[zone_ext]["echec"] += 1
                                        else:
                                            if act_type == "Arrêt décisif":
                                                zones_match_specifique[zone_ext]["succes"] += 1
                                            elif act_type == "But encaissé":
                                                zones_match_specifique[zone_ext]["echec"] += 1

                            titre_cage_match_j = (
                                f"Détail du match '{match_selectionne_j}' — {p.nom} (✅ Arrêts | ❌ Encaissés)"
                                if isinstance(p, Gardienne)
                                else f"Détail du match '{match_selectionne_j}' — {p.nom} (✅ Buts | ❌ Ratés)"
                            )
                            est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                            afficher_cage_recapitulative(zones_match_specifique, titre=titre_cage_match_j, inclure_hors_cadre=not est_gardienne_val)
                else:
                    st.info("Aucun profil disponible.")

    # ==========================================
    # 4. ÉCRAN : GESTION DE L'EFFECTIF
    # ==========================================
    elif st.session_state[page_key] == "effectif":
        if st.button("⬅️ Retour à l'accueil", key=f"btn_retour_effectif_{equipe_assignee}"):
            aller_a("accueil")
            
        st.header(f"👥 Gestion de l'Effectif ({L['joueurs'].capitalize()}) — {equipe_assignee}")
        
        if manager.joueuses:
            club_equipes = st.session_state.get("club_equipes", ["Séniors M", "Séniors F", "-18M", "-15F"])
            autres_equipes_club = [eq for eq in club_equipes if eq != equipe_assignee]

            for nom, joueuse in list(manager.joueuses.items()):
                with st.container(border=True):
                    col_info1, col_info2, col_info3, col_transfert, col_suppr = st.columns([2, 1.5, 1.5, 2.5, 0.8])
                    
                    col_info1.write(f"**{nom}**")
                    col_info2.write(f"Poste : {joueuse.poste}")
                    col_info3.write(f"N° {joueuse.numero}")
                    
                    with col_transfert:
                        if autres_equipes_club:
                            with st.popover("🔄 Transférer"):
                                st.write(f"Transférer **{nom}** vers :")
                                equipe_destination = st.selectbox(
                                    "Équipe cible", 
                                    autres_equipes_club, 
                                    key=f"sel_dest_{equipe_assignee}_{nom}"
                                )
                                if st.button("Confirmer le transfert", key=f"btn_conf_trans_{equipe_assignee}_{nom}", type="primary"):
                                    nom_fichier_cible = f"effectif_{equipe_destination.replace(' ', '_').replace('-', '')}.json"
                                    manager_cible = EquipeManager(fichier=nom_fichier_cible)
                                    
                                    if nom in manager_cible.joueuses:
                                        st.error(f"Un(e) {L['joueur']} nommé(e) '{nom}' existe déjà dans {equipe_destination} !")
                                    else:
                                        manager_cible.joueuses[nom] = joueuse
                                        manager_cible.sauvegarder_donnees()
                                        manager.supprimer_joueuse(nom)
                                        st.success(f"{nom} a été transféré(e) vers {equipe_destination} avec succès !")
                                        st.rerun()
                        else:
                            st.caption("Aucune autre équipe")

                    with col_suppr:
                        if st.button("🗑️", key=f"del_{equipe_assignee}_{nom}"):
                            manager.supprimer_joueuse(nom)
                            st.rerun()
        else:
            st.info(f"Aucun(e) {L['joueur']} enregistré(e).")
        
        st.divider()
        with st.form(key=f"form_ajout_joueuse_{equipe_assignee}"):
            st.markdown(f"##### ➕ Ajouter un(e) nouveau/nouvelle {L['joueur']} à l'effectif")
            nom_input = st.text_input(f"Nom / Prénom du/de la {L['joueur']}")
            poste_input = st.selectbox("Poste", L["postes_possibles"])
            numero_input = st.number_input("Numéro de maillot", min_value=1, max_value=99, value=10)
            if st.form_submit_button("Ajouter à l'effectif"):
                if nom_input.strip():
                    type_j = "gardienne" if "Gardien" in poste_input else "champ"
                    manager.ajouter_joueuse(nom=nom_input, poste=poste_input, numero=numero_input, type_joueuse=type_j)
                    st.rerun()