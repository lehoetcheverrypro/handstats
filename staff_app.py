import re
import time
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import date, datetime
from hand_manager import (
    EquipeManager,
    Gardienne,
    JoueuseDeChamp,
    calculer_indice_performance_match,
    get_dossier_club,
    get_nom_fichier_equipe,
    resumer_charge_forme_joueur,
)
from feuille_de_match_pdf import generer_pdf_match
from rapport_chrono_match_pdf import generer_pdf_chronologique
from exports_match import construire_payload_match, exporter_match_json, exporter_evenements_csv
from offline_sync import OfflineSyncManager
from tactics import afficher_tableau_tactique
from auth_manager import a_permission, afficher_en_tete_avec_profil
from shot_grid import (
    afficher_grille_saisie_interactive,
    afficher_cage_recapitulative,
    afficher_selecteur_zone_terrain,
)
from scouting_adversaire import afficher_onglet_scouting_adversaire
from saisie_rapide_tablette import afficher_cockpit_tablette_plein_ecran
from theme import hero_match, tuile_navigation, barre_laterale, masquer_barre_laterale
from accueil_dashboard import calculer_resume_saison, afficher_tableau_de_bord
from parametres_app import (
    afficher_page_parametres,
    charger_parametres,
    libelle_avec_raccourci,
)


def _action_concerne_joueur(act: dict, joueur) -> bool:
    """Retourne True si l'action concerne le joueur ciblé, quel que soit son numéro de match."""
    nom_cible = (getattr(joueur, "nom", "") or "").strip()
    if not nom_cible:
        return False

    membre_nom = (act.get("membre_nom") or "").strip()
    if membre_nom:
        return membre_nom == nom_cible

    det = str(act.get("details", "") or "")
    return f" {nom_cible}" in det or det.endswith(nom_cible) or (nom_cible in det)

def run_staff_app(equipe_assignee):
    # --- CONTRÔLE D'ENCLOISONNEMENT PAR CLUB ---
    session = st.session_state.get("user_session", {})
    club_nom_session = session.get("club") or "Bordeaux Étudiants Club"
    club_slug_session = session.get("club_slug") or "bordeaux_etudiants_club"
    dossier_club_session = get_dossier_club(club_slug_session)

    def _get_equipes_du_club_courant():
        reg = st.session_state.get("registre_app", {})
        clubs_dict = reg.get("clubs", {})
        if club_nom_session in clubs_dict:
            return list(clubs_dict[club_nom_session].get("equipes", []))
        return list(st.session_state.get("club_equipes", []))

    equipes_du_club = _get_equipes_du_club_courant()
    if equipes_du_club and equipe_assignee not in equipes_du_club:
        st.error(f"Accès refusé : l'équipe '{equipe_assignee}' n'appartient pas au club '{club_nom_session}'.")
        return

    role_session = session.get("role")
    equipes_autorisees_user = session.get("equipes", [])
    if role_session in ("staff", "analyste") and equipe_assignee not in equipes_autorisees_user:
        st.error(f"Accès refusé : vous n'êtes pas habilité sur la catégorie '{equipe_assignee}'.")
        return

    # Clé préfixée par le club pour éviter toute collision en session
    ctx_prefix = f"{club_slug_session}_{equipe_assignee}"

    # --- DÉTERMINATION AUTOMATIQUE DU GENRE DE L'ÉQUIPE ---
    def detecter_genre(nom_equipe):
        nom_l = str(nom_equipe).lower()
        if re.search(r'(^|[\s(\[_-])(f|fem|feminine|féminine|fille|filles)([\s)\]_.-]|$)', nom_l):
            return "F"
        if re.search(r'(^|[\s(\[_-])(m|masc|masculin|garcon|garçon|garcons|garçons|h)([\s)\]_.-]|$)', nom_l):
            return "M"
        return "F"

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

    sync_mgr = OfflineSyncManager(dossier_club=dossier_club_session, club_slug=club_slug_session)
    cfg_app = charger_parametres()

    # En-tête combiné Titre + Profil
    afficher_en_tete_avec_profil(equipe_assignee, sous_titre=club_nom_session)

    ZONES_TERRAIN_LISTE = [
        "Aile Gauche",
        "Exter 9m Gauche",
        "6m Centre",
        "Exter 9m Centre",
        "Aile Droite",
        "Exter 9m Droite"
    ]

    # --- DESIGN SYSTEM & CSS PERSONNALISÉ ---
    st.markdown("""
        <style>
        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 2.2rem;
        }
        .top-box {
            background-color: #121620;
            border: 1px solid #273043;
            color: #FFFFFF;
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
            background-color: #121620;
            padding: 10px 15px;
            border-radius: 12px;
            text-align: center;
            color: #FFFFFF;
            border: 1px solid #273043;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.25);
            height: 74px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-sizing: border-box;
        }
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
            padding: 6px 10px;
            font-size: 13px;
            transition: all 0.2s ease;
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- INITIALISATION DU MANAGER CLOISONNÉ PAR CLUB ---
    nom_fichier_eq = get_nom_fichier_equipe(equipe_assignee)

    def _get_fresh_manager(fichier, c_slug):
        mgr = EquipeManager(fichier=fichier, club_slug=c_slug)
        if hasattr(mgr, "charger_donnees"):
            mgr.charger_donnees()
        return mgr

    manager = _get_fresh_manager(nom_fichier_eq, club_slug_session)

    pretes_key = f"joueurs_pretes_match_{ctx_prefix}"
    if pretes_key not in st.session_state:
        st.session_state[pretes_key] = {}

    def get_membre(nom):
        if nom in manager.joueuses:
            return manager.joueuses[nom]
        return st.session_state.get(pretes_key, {}).get(nom)

    def get_numero_actif(nom):
        nums_match = st.session_state.get(f"numeros_match_{ctx_prefix}", {})
        if nom in nums_match:
            return nums_match[nom]
        p = get_membre(nom)
        return p.numero if p else 1

    page_key = f"page_actuelle_{ctx_prefix}"
    if page_key not in st.session_state:
        st.session_state[page_key] = "accueil"

    def aller_a(page):
        st.session_state[page_key] = page
        st.rerun()

    def get_badge_poste_html(poste):
        if "Arrière" in poste or "Demi-centre" in poste:
            return '<span style="background-color: #1A2030; color: #93C5FD; border: 1px solid #273043; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">🔵 Base Arrière</span>'
        elif "Ailière" in poste or "Ailier" in poste:
            return f'<span style="background-color: #1A2030; color: #86EFAC; border: 1px solid #273043; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{L["badge_ailier"]}</span>'
        elif "Pivot" in poste:
            return '<span style="background-color: #1A2030; color: #FCD34D; border: 1px solid #273043; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">🟠 Pivot</span>'
        elif "Gardienne" in poste or "Gardien" in poste:
            return f'<span style="background-color: #1A2030; color: #D8B4FE; border: 1px solid #273043; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{L["badge_gardien"]}</span>'
        return f'<span style="background-color: #1A2030; color: #FFFFFF; border: 1px solid #273043; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{poste}</span>'

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

    def enregistrer_zone_tir_live(nom_membre, zone_terrain, zone_cage, est_succes):
        zones_key = f"zones_tirs_match_{ctx_prefix}"
        if zones_key not in st.session_state:
            st.session_state[zones_key] = {}
        if nom_membre not in st.session_state[zones_key]:
            st.session_state[zones_key][nom_membre] = {}
        if zone_cage not in st.session_state[zones_key][nom_membre]:
            st.session_state[zones_key][nom_membre][zone_cage] = {"succes": 0, "echec": 0}

        if est_succes:
            st.session_state[zones_key][nom_membre][zone_cage]["succes"] += 1
        else:
            st.session_state[zones_key][nom_membre][zone_cage]["echec"] += 1

    def sauvegarder_brouillon_match_local():
        if not st.session_state.get(f"match_en_cours_{ctx_prefix}", False):
            return

        actives = st.session_state.get(f"joueuses_actives_match_{ctx_prefix}", [])
        stats_membres = {}
        for nom_m in actives:
            obj_m = get_membre(nom_m)
            if not obj_m:
                continue
            stats_membres[nom_m] = {
                "type": "gardienne" if isinstance(obj_m, Gardienne) else "champ",
                "nom": obj_m.nom,
                "poste": obj_m.poste,
                "numero": getattr(obj_m, "numero", 1),
                "buts": getattr(obj_m, "buts", 0),
                "tirs": getattr(obj_m, "tirs", 0),
                "passes_decisives": getattr(obj_m, "passes_decisives", 0),
                "pertes_de_balles_passe": getattr(obj_m, "pertes_de_balles_passe", 0),
                "pertes_de_balles_faute": getattr(obj_m, "pertes_de_balles_faute", 0),
                "duels_off_gagnes": getattr(obj_m, "duels_off_gagnes", 0),
                "duels_off_perdus": getattr(obj_m, "duels_off_perdus", 0),
                "duels_def_gagnes": getattr(obj_m, "duels_def_gagnes", 0),
                "duels_def_perdus": getattr(obj_m, "duels_def_perdus", 0),
                "interceptions": getattr(obj_m, "interceptions", 0),
                "neutralisations": getattr(obj_m, "neutralisations", 0),
                "pertes_balles_provoquees": getattr(obj_m, "pertes_balles_provoquees", 0),
                "arrets": getattr(obj_m, "arrets", 0),
                "tirs_subis": getattr(obj_m, "tirs_subis", 0),
                "buts_encaisses": getattr(obj_m, "buts_encaisses", 0),
                "cartons_jaunes": getattr(obj_m, "cartons_jaunes", 0),
                "exclusions_2min": getattr(obj_m, "exclusions_2min", 0),
                "cartons_rouges": getattr(obj_m, "cartons_rouges", 0),
            }

        secs_cum = st.session_state.get(f"chrono_secondes_cumulees_{ctx_prefix}", 0)
        if st.session_state.get(f"chrono_en_cours_{ctx_prefix}", False) and st.session_state.get(f"chrono_debut_{ctx_prefix}"):
            secs_cum += int(time.time() - st.session_state[f"chrono_debut_{ctx_prefix}"])

        temps_jeu_key = f"temps_jeu_secondes_{ctx_prefix}"
        temps_jeu_snapshot = dict(st.session_state.get(temps_jeu_key, {}))
        temps_morts_key = f"temps_morts_match_{ctx_prefix}"
        temps_morts_snapshot = dict(st.session_state.get(temps_morts_key, {"equipe": 0, "adversaire": 0}))

        state_snapshot = {
            "nom_match_actuel": st.session_state.get(f"nom_match_actuel_{ctx_prefix}", "Match"),
            "joueuses_actives": actives,
            "terrain_joueuses": st.session_state.get(f"terrain_joueuses_{ctx_prefix}", []),
            "banc_joueuses": st.session_state.get(f"banc_joueuses_{ctx_prefix}", []),
            "joueuse_focus_live": st.session_state.get(f"joueuse_focus_live_{ctx_prefix}"),
            "numeros_match": st.session_state.get(f"numeros_match_{ctx_prefix}", {}),
            "attaques_adversaires": st.session_state.get(f"attaques_adversaires_match_{ctx_prefix}", {}),
            "chrono_secondes_cumulees": secs_cum,
            "periode_match": st.session_state.get(f"periode_match_{ctx_prefix}", "1ère MT"),
            "journal_actions": st.session_state.get(f"journal_actions_match_{ctx_prefix}", []),
            "commentaires_staff": st.session_state.get(f"commentaires_staff_match_{ctx_prefix}", []),
            "zones_tirs_match": st.session_state.get(f"zones_tirs_match_{ctx_prefix}", {}),
            "stats_membres": stats_membres,
            "temps_jeu_secondes": temps_jeu_snapshot,
            "temps_morts": temps_morts_snapshot,
        }
        sync_mgr.sauvegarder_brouillon(ctx_prefix, state_snapshot)

    def restaurer_brouillon_match_local_si_besoin():
        match_enc_key = f"match_en_cours_{ctx_prefix}"
        brouillon_restaure_key = f"brouillon_restaure_{ctx_prefix}"
        if st.session_state.get(match_enc_key, False) or st.session_state.get(brouillon_restaure_key, False):
            return

        brouillon = sync_mgr.charger_brouillon(ctx_prefix)
        if not brouillon:
            return

        st_data = brouillon.get("state", {})
        actives = st_data.get("joueuses_actives", [])
        if not actives:
            return

        stats_membres = st_data.get("stats_membres", {})
        for nom_m, s_info in stats_membres.items():
            if nom_m not in manager.joueuses:
                if s_info.get("type") == "gardienne":
                    st.session_state[pretes_key][nom_m] = Gardienne(nom_m, s_info.get("poste", L["gardien"]), s_info.get("numero", 1))
                else:
                    st.session_state[pretes_key][nom_m] = JoueuseDeChamp(nom_m, s_info.get("poste", "Arrière gauche"), s_info.get("numero", 1))

            obj_m = get_membre(nom_m)
            if obj_m:
                obj_m.cartons_jaunes = s_info.get("cartons_jaunes", 0)
                obj_m.exclusions_2min = s_info.get("exclusions_2min", 0)
                obj_m.cartons_rouges = s_info.get("cartons_rouges", 0)
                if isinstance(obj_m, JoueuseDeChamp):
                    obj_m.buts = s_info.get("buts", 0)
                    obj_m.tirs = s_info.get("tirs", 0)
                    obj_m.passes_decisives = s_info.get("passes_decisives", 0)
                    obj_m.pertes_de_balles_passe = s_info.get("pertes_de_balles_passe", 0)
                    obj_m.pertes_de_balles_faute = s_info.get("pertes_de_balles_faute", 0)
                    obj_m.duels_off_gagnes = s_info.get("duels_off_gagnes", 0)
                    obj_m.duels_off_perdus = s_info.get("duels_off_perdus", 0)
                    obj_m.duels_def_gagnes = s_info.get("duels_def_gagnes", 0)
                    obj_m.duels_def_perdus = s_info.get("duels_def_perdus", 0)
                    obj_m.interceptions = s_info.get("interceptions", 0)
                    obj_m.neutralisations = s_info.get("neutralisations", 0)
                    obj_m.pertes_balles_provoquees = s_info.get("pertes_balles_provoquees", 0)
                elif isinstance(obj_m, Gardienne):
                    obj_m.arrets = s_info.get("arrets", 0)
                    obj_m.tirs_subis = s_info.get("tirs_subis", 0)
                    obj_m.buts_encaisses = s_info.get("buts_encaisses", 0)
                    obj_m.buts = s_info.get("buts", 0)
                    obj_m.tirs = s_info.get("tirs", 0)

        manager.sauvegarder_donnees()
        st.session_state[match_enc_key] = True
        st.session_state[f"nom_match_actuel_{ctx_prefix}"] = st_data.get("nom_match_actuel", "Match")
        st.session_state[f"joueuses_actives_match_{ctx_prefix}"] = actives
        st.session_state[f"terrain_joueuses_{ctx_prefix}"] = st_data.get("terrain_joueuses", actives[:7])
        st.session_state[f"banc_joueuses_{ctx_prefix}"] = st_data.get("banc_joueuses", actives[7:])
        st.session_state[f"joueuse_focus_live_{ctx_prefix}"] = st_data.get("joueuse_focus_live", actives[0])
        st.session_state[f"numeros_match_{ctx_prefix}"] = st_data.get("numeros_match", {})
        st.session_state[f"attaques_adversaires_match_{ctx_prefix}"] = st_data.get(
            "attaques_adversaires", {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}
        )
        st.session_state[f"chrono_en_cours_{ctx_prefix}"] = False
        st.session_state[f"chrono_secondes_cumulees_{ctx_prefix}"] = st_data.get("chrono_secondes_cumulees", 0)
        st.session_state[f"chrono_debut_{ctx_prefix}"] = None
        st.session_state[f"periode_match_{ctx_prefix}"] = st_data.get("periode_match", "1ère MT")
        st.session_state[f"journal_actions_match_{ctx_prefix}"] = st_data.get("journal_actions", [])
        st.session_state[f"commentaires_staff_match_{ctx_prefix}"] = st_data.get("commentaires_staff", [])
        st.session_state[f"zones_tirs_match_{ctx_prefix}"] = st_data.get("zones_tirs_match", {})
        st.session_state[f"temps_jeu_secondes_{ctx_prefix}"] = st_data.get("temps_jeu_secondes", {})
        st.session_state[f"temps_morts_match_{ctx_prefix}"] = st_data.get("temps_morts", {"equipe": 0, "adversaire": 0})
        st.session_state[brouillon_restaure_key] = True

    restaurer_brouillon_match_local_si_besoin()

    def sauvegarder_effectif_securise():
        try:
            manager.sauvegarder_donnees()
        except Exception as exc:
            sync_mgr.ajouter_operation(
                op_type="sauvegarde_effectif",
                equipe_nom=equipe_assignee,
                payload={"raison": str(exc)},
            )
            st.warning("Sauvegarde disque différée : opération placée en file d'attente.")

    def _executer_operation_file_attente(item: dict):
        op_type = item.get("op_type")
        payload = item.get("payload") or {}
        if op_type == "bilan_post_match":
            nom_m = payload.get("nom_match")
            texte_b = payload.get("bilan_post_match", "")
            if nom_m:
                manager.sauvegarder_commentaire_post_match(nom_m, texte_b)
        elif op_type == "sauvegarde_effectif":
            manager.sauvegarder_donnees()

    def afficher_bloc_synchro_hors_ligne():
        brouillon_actif = sync_mgr.charger_brouillon(ctx_prefix)
        en_attente = sync_mgr.lister_en_attente()

        if not brouillon_actif and not en_attente:
            return

        with st.container(border=True):
            st.markdown("#### État hors ligne et synchronisation")
            c_s1, c_s2 = st.columns([3, 1.5])
            with c_s1:
                if brouillon_actif:
                    maj_str = brouillon_actif.get("updated_at", "")
                    st.caption(f"Brouillon local actif pour `{ctx_prefix}` (dernière sauvegarde : `{maj_str}`).")
                if en_attente:
                    st.warning(f"{len(en_attente)} opération(s) en attente de synchronisation.")
                    for op in en_attente:
                        st.caption(
                            f"- `{op.get('op_type')}` ({op.get('equipe_nom')}) — statut : `{op.get('status')}`"
                            + (f" — `{op.get('error_msg')}`" if op.get("error_msg") else "")
                        )
            with c_s2:
                if en_attente:
                    if st.button(
                        "Synchroniser la file",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_sync_queue_{ctx_prefix}",
                    ):
                        res = sync_mgr.synchroniser_tout(_executer_operation_file_attente)
                        st.toast(
                            f"Synchronisation terminée : {res.get('synced', 0)} OK, {res.get('failed', 0)} échec(s).",
                            icon="🔄",
                        )
                        st.rerun()
                if st.button(
                    "Nettoyer l'historique synchro",
                    use_container_width=True,
                    key=f"btn_purge_sync_{ctx_prefix}",
                ):
                    nb_purges = sync_mgr.purger_synchronises()
                    st.toast(f"{nb_purges} opération(s) synchronisée(s) nettoyée(s).", icon="🧹")
                    st.rerun()

    # --- NAVIGATION LATÉRALE (masquée en mode match plein écran) ---
    _page_courante = st.session_state[page_key]
    if _page_courante == "match":
        masquer_barre_laterale()
    else:
        _choix_nav = barre_laterale(
            pages=[
                ("accueil", "Tableau de bord"),
                ("saison", "Analyse et saison"),
                ("effectif", L["effectif"]),
                ("parametres", "Paramètres"),
            ],
            page_active=_page_courante,
            equipe=equipe_assignee,
            club=club_nom_session,
            desactives=(),
            match_en_cours=bool(st.session_state.get(f"match_en_cours_{ctx_prefix}", False)),
        )
        if _choix_nav and _choix_nav != _page_courante:
            aller_a(_choix_nav)

    if st.session_state[page_key] == "accueil":
        match_en_cours = bool(st.session_state.get(f"match_en_cours_{ctx_prefix}", False))
        tm_acc = st.session_state.get(f"temps_morts_match_{ctx_prefix}", {"equipe": 0, "adversaire": 0})

        if hero_match(
            cle=ctx_prefix,
            equipe=equipe_assignee,
            peut_saisir=a_permission("saisie_match"),
            en_cours=match_en_cours,
            nom_match=st.session_state.get(f"nom_match_actuel_{ctx_prefix}", "Match"),
            tm_equipe=int(tm_acc.get("equipe", 0)),
            tm_adversaire=int(tm_acc.get("adversaire", 0)),
        ):
            aller_a("match")

        afficher_tableau_de_bord(calculer_resume_saison(manager), feminin=(genre_equipe == "F"))

        col_saison, col_effectif = st.columns(2, gap="medium")
        with col_saison:
            if tuile_navigation(
                cle=f"saison_{ctx_prefix}",
                icone="stats",
                titre="Analyse et saison",
                texte="Historique des rencontres, bilans d'équipe, tendances, charge de jeu et scouting adverse.",
                label_bouton="Ouvrir l'analyse",
            ):
                aller_a("saison")
        with col_effectif:
            if tuile_navigation(
                cle=f"effectif_{ctx_prefix}",
                icone="effectif",
                titre=L["effectif"],
                texte=f"Gestion des {L['joueurs']}, numéros, postes et profils.",
                label_bouton="Gérer l'effectif",
            ):
                aller_a("effectif")

        st.write("")
        afficher_bloc_synchro_hors_ligne()

    # ==========================================
    # 1B. PAGE : PARAMÈTRES DE L'APPLICATION
    # ==========================================
    elif st.session_state[page_key] == "parametres":
        afficher_page_parametres(on_retour=lambda: aller_a("accueil"))

    # ==========================================
    # 2. ÉCRAN : MATCH EN DIRECT
    # ==========================================
    elif st.session_state[page_key] == "match":
        col_retour_m, col_tab_m = st.columns([1.5, 1.5])
        with col_retour_m:
            if st.button("⬅️ Retour à l'accueil", key=f"btn_retour_accueil_{ctx_prefix}"):
                aller_a("accueil")
        with col_tab_m:
            if st.session_state.get(f"match_en_cours_{ctx_prefix}", False):
                if st.button(
                    "📱 Mode Saisie Rapide Tablette",
                    type="primary",
                    use_container_width=True,
                    key=f"btn_enter_tab_{ctx_prefix}",
                ):
                    st.session_state[f"mode_tablette_plein_ecran_{ctx_prefix}"] = True
                    st.rerun()

        st.header(f"⚡ Cockpit de Match en Direct — {equipe_assignee}")

        if not a_permission("saisie_match"):
            st.warning("Accès restreint : votre profil ne dispose pas de la permission de saisie de match en direct.")
            return

        if not manager.joueuses:
            st.warning(f"Aucun(e) {L['joueur']} enregistré(e). Rendez-vous dans l'onglet 'Effectif' pour en ajouter.")
        else:
            match_encours_key = f"match_en_cours_{ctx_prefix}"

            if not st.session_state.get(match_encours_key, False):
                with st.container(border=True):
                    st.subheader("📋 Composition de la Feuille de Match")
                    st.write(f"Saisissez le nom de la rencontre pour l'équipe **{equipe_assignee}** et sélectionnez les {L['joueurs']} {L['convoquees']} :")

                    with st.form(key=f"form_config_match_{ctx_prefix}"):
                        nom_match_saisi = st.text_input("Nom / Adversaire du match", value="J1 - Match 1")

                        club_equipes = _get_equipes_du_club_courant()
                        autres_equipes = [eq for eq in club_equipes if eq != equipe_assignee]
                        toutes_joueuses_club = manager.recuperer_toutes_les_joueuses_du_club(
                            autres_equipes, club_slug=club_slug_session
                        )
                        noms_surclassables = [
                            nom for nom, info in toutes_joueuses_club.items()
                            if info["equipe_origine"] in autres_equipes and nom not in manager.joueuses
                        ]
                        options_cap_init = ["Aucun"] + list(manager.joueuses.keys()) + noms_surclassables
                        cap_saisi = st.selectbox(
                            "Capitaine (C) pour cette rencontre",
                            options_cap_init,
                            index=0,
                            key=f"sel_cap_match_{ctx_prefix}",
                        )

                        st.markdown("---")
                        st.markdown(f"**{L['joueurs'].capitalize()} de l'effectif principal :**")

                        membres_coches = {}
                        numeros_match_saisis = {}

                        for nom, p_obj in manager.joueuses.items():
                            col_chk, col_num = st.columns([3, 1])
                            with col_chk:
                                est_convoquee = st.checkbox(
                                    f"{p_obj.nom} ({p_obj.poste})",
                                    value=True,
                                    key=f"chk_membre_{ctx_prefix}_{nom}"
                                )
                            with col_num:
                                num_du_jour = st.number_input(
                                    "N°", min_value=1, max_value=99,
                                    value=int(p_obj.numero),
                                    key=f"num_match_{ctx_prefix}_{nom}",
                                    label_visibility="collapsed"
                                )

                            if est_convoquee:
                                membres_coches[nom] = True
                                numeros_match_saisis[nom] = num_du_jour

                        st.markdown("---")
                        st.markdown(f"⚡ **Convoquer des {L['joueurs']} d'autres équipes du club (Prêt / Surclassement)**")

                        club_equipes = _get_equipes_du_club_courant()
                        autres_equipes = [eq for eq in club_equipes if eq != equipe_assignee]
                        toutes_joueuses_club = manager.recuperer_toutes_les_joueuses_du_club(
                            autres_equipes, club_slug=club_slug_session
                        )

                        surclassements_coches = {}
                        for eq in autres_equipes:
                            membres_cette_equipe = {
                                nom: info for nom, info in toutes_joueuses_club.items()
                                if info["equipe_origine"] == eq and nom not in manager.joueuses
                            }
                            if membres_cette_equipe:
                                with st.expander(f"📁 Équipe : {eq} ({len(membres_cette_equipe)} {L['joueur']}(s))"):
                                    for nom_ext, info_ext in membres_cette_equipe.items():
                                        poste_ext = info_ext["poste"]
                                        num_ext = info_ext["numero"]

                                        col_chk_ext, col_num_ext = st.columns([3, 1])
                                        with col_chk_ext:
                                            est_coche_ext = st.checkbox(
                                                f"{nom_ext} ({poste_ext})",
                                                value=False,
                                                key=f"chk_surclassement_{ctx_prefix}_{nom_ext}"
                                            )
                                        with col_num_ext:
                                            num_du_jour_ext = st.number_input(
                                                "N°ext", min_value=1, max_value=99,
                                                value=int(num_ext),
                                                key=f"num_match_ext_{ctx_prefix}_{nom_ext}",
                                                label_visibility="collapsed"
                                            )

                                        if est_coche_ext:
                                            surclassements_coches[nom_ext] = num_du_jour_ext

                        st.markdown("---")
                        valider_feuille = st.form_submit_button(
                            "Lancer le match en direct",
                            type="primary",
                            key=f"btn_submit_match_{ctx_prefix}"
                        )

                        if valider_feuille:
                            membres_selectionnes = list(membres_coches.keys())
                            membres_surclassees_noms = list(surclassements_coches.keys())

                            dict_nums_match = {**numeros_match_saisis, **surclassements_coches}
                            st.session_state[f"numeros_match_{ctx_prefix}"] = dict_nums_match
                            st.session_state[f"capitaine_match_{ctx_prefix}"] = (
                                cap_saisi if (cap_saisi and cap_saisi != "Aucun" and cap_saisi in membres_selectionnes) else None
                            )

                            st.session_state[pretes_key] = {}
                            for nom_s in membres_surclassees_noms:
                                info_s = toutes_joueuses_club[nom_s]
                                num_attribue = surclassements_coches[nom_s]
                                if nom_s not in manager.joueuses:
                                    if info_s["type"] == "gardienne":
                                        st.session_state[pretes_key][nom_s] = Gardienne(nom_s, info_s["poste"], num_attribue)
                                    else:
                                        st.session_state[pretes_key][nom_s] = JoueuseDeChamp(nom_s, info_s["poste"], num_attribue)
                                membres_selectionnes.append(nom_s)

                            if not nom_match_saisi.strip():
                                st.error("Le nom du match ne peut pas être vide.")
                            elif not membres_selectionnes:
                                st.error(f"Vous devez sélectionner au moins un(e) {L['joueur']}.")
                            else:
                                st.session_state[f"match_en_cours_{ctx_prefix}"] = True
                                st.session_state[f"nom_match_actuel_{ctx_prefix}"] = nom_match_saisi
                                st.session_state[f"joueuses_actives_match_{ctx_prefix}"] = membres_selectionnes

                                st.session_state[f"terrain_joueuses_{ctx_prefix}"] = membres_selectionnes[:7]
                                st.session_state[f"banc_joueuses_{ctx_prefix}"] = membres_selectionnes[7:]

                                st.session_state[f"attaques_adversaires_match_{ctx_prefix}"] = {
                                    "Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0
                                }

                                terrain_j_key = f"terrain_joueuses_{ctx_prefix}"
                                if st.session_state[terrain_j_key]:
                                    st.session_state[f"joueuse_focus_live_{ctx_prefix}"] = st.session_state[terrain_j_key][0]
                                else:
                                    st.session_state[f"joueuse_focus_live_{ctx_prefix}"] = None

                                st.session_state[f"chrono_en_cours_{ctx_prefix}"] = False
                                st.session_state[f"chrono_secondes_cumulees_{ctx_prefix}"] = 0
                                st.session_state[f"chrono_debut_{ctx_prefix}"] = None
                                st.session_state[f"periode_match_{ctx_prefix}"] = "1ère MT"
                                st.session_state[f"journal_actions_match_{ctx_prefix}"] = []
                                st.session_state[f"commentaires_staff_match_{ctx_prefix}"] = []
                                st.session_state[f"zones_tirs_match_{ctx_prefix}"] = {}
                                st.session_state[f"pop_up_active_{ctx_prefix}"] = None
                                st.session_state[f"etape_saisie_tir_{ctx_prefix}"] = "terrain"
                                st.session_state[f"temp_zone_terrain_{ctx_prefix}"] = None
                                st.rerun()

            else:
                nom_match_actuel = st.session_state.get(f"nom_match_actuel_{ctx_prefix}", "Match")
                joueuses_actives = st.session_state.get(f"joueuses_actives_match_{ctx_prefix}", [])

                terrain_key = f"terrain_joueuses_{ctx_prefix}"
                banc_key = f"banc_joueuses_{ctx_prefix}"
                zones_key = f"zones_tirs_match_{ctx_prefix}"
                popup_key = f"pop_up_active_{ctx_prefix}"
                mode_tablette_key = f"mode_tablette_plein_ecran_{ctx_prefix}"
                if mode_tablette_key not in st.session_state:
                    st.session_state[mode_tablette_key] = False
                chrono_enc_key = f"chrono_en_cours_{ctx_prefix}"
                chrono_secs_key = f"chrono_secondes_cumulees_{ctx_prefix}"
                chrono_deb_key = f"chrono_debut_{ctx_prefix}"
                journal_key = f"journal_actions_match_{ctx_prefix}"
                commentaires_key = f"commentaires_staff_match_{ctx_prefix}"
                focus_key = f"joueuse_focus_live_{ctx_prefix}"
                att_adv_key = f"attaques_adversaires_match_{ctx_prefix}"

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

                def enregistrer_action(
                    type_action,
                    details,
                    zone_terrain=None,
                    zone_cage=None,
                    membre_nom=None,
                    systeme_adv=None,
                    temps_mort_camp=None,
                ):
                    if journal_key not in st.session_state:
                        st.session_state[journal_key] = []

                    secs = st.session_state.get(chrono_secs_key, 0)
                    if st.session_state.get(chrono_enc_key, False) and st.session_state.get(chrono_deb_key):
                        secs += int(time.time() - st.session_state[chrono_deb_key])

                    temps_str = formater_temps(secs)

                    if zone_terrain and zone_cage:
                        detail_complet = f"{details} [Terrain: {zone_terrain} | Cage: {zone_cage}]"
                    elif zone_cage:
                        detail_complet = f"{details} [{zone_cage}]"
                    else:
                        detail_complet = details

                    periode_str = st.session_state.get(f"periode_match_{ctx_prefix}", "1ère MT")
                    heure_reelle = datetime.now().strftime("%H:%M:%S")

                    entry = {
                        "temps": temps_str,
                        "type_action": type_action,
                        "details": detail_complet,
                        "periode": periode_str,
                        "horodatage_reel": heure_reelle,
                    }
                    if zone_terrain:
                        entry["zone_terrain"] = zone_terrain
                    if zone_cage:
                        entry["zone_cage"] = zone_cage
                    if membre_nom:
                        entry["membre_nom"] = membre_nom
                    if systeme_adv:
                        entry["systeme_adv"] = systeme_adv
                    if temps_mort_camp:
                        entry["temps_mort_camp"] = temps_mort_camp

                    st.session_state[journal_key].append(entry)
                    sauvegarder_brouillon_match_local()

                def basculer_seconde_mi_temps():
                    score_eq_actuel = sum(
                        get_membre(n).buts for n in joueuses_actives
                        if get_membre(n) and hasattr(get_membre(n), "buts")
                    )
                    score_adv_actuel = sum(
                        get_membre(n).buts_encaisses for n in joueuses_actives
                        if get_membre(n) and isinstance(get_membre(n), Gardienne)
                    )
                    secs_1mt = st.session_state.get(chrono_secs_key, 0)
                    if st.session_state.get(chrono_enc_key, False) and st.session_state.get(chrono_deb_key):
                        secs_1mt += int(time.time() - st.session_state[chrono_deb_key])
                    temps_fin_1mt = formater_temps(max(0, secs_1mt))
                    heure_reelle = datetime.now().strftime("%H:%M:%S")

                    if journal_key not in st.session_state:
                        st.session_state[journal_key] = []

                    st.session_state[journal_key].append({
                        "temps": temps_fin_1mt,
                        "periode": "1ère MT",
                        "horodatage_reel": heure_reelle,
                        "type_action": "Repère Mi-Temps",
                        "details": f"Fin de 1ère mi-temps — Score à la pause : {score_eq_actuel} - {score_adv_actuel}",
                    })
                    st.session_state[f"periode_match_{ctx_prefix}"] = "2ème MT"
                    st.session_state[chrono_secs_key] = 30 * 60
                    st.session_state[chrono_deb_key] = time.time() if st.session_state.get(chrono_enc_key, False) else None
                    st.session_state[journal_key].append({
                        "temps": "30:00",
                        "periode": "2ème MT",
                        "horodatage_reel": heure_reelle,
                        "type_action": "Repère Mi-Temps",
                        "details": f"Début de 2ème mi-temps (Chrono calé à 30:00 — Score : {score_eq_actuel} - {score_adv_actuel})",
                    })
                    sauvegarder_brouillon_match_local()
                    st.toast("Passage en 2ème mi-temps : chrono calé à 30:00.", icon="⏱️")

                def annuler_derniere_action():
                    actions_liste = st.session_state.get(journal_key, [])
                    if not actions_liste:
                        st.toast("Aucune action à annuler.", icon="ℹ️")
                        return

                    derniere = actions_liste.pop()
                    t_act = derniere.get("type_action", "")
                    nom_m = derniere.get("membre_nom")
                    z_cage = derniere.get("zone_cage")
                    sys_adv = derniere.get("systeme_adv")

                    p_obj = get_membre(nom_m) if nom_m else None

                    if p_obj is not None:
                        if t_act == "But":
                            p_obj.buts = max(0, p_obj.buts - 1)
                            p_obj.tirs = max(0, p_obj.tirs - 1)
                        elif t_act == "Tir raté":
                            p_obj.tirs = max(0, p_obj.tirs - 1)
                        elif t_act == "Arrêt décisif":
                            p_obj.arrets = max(0, p_obj.arrets - 1)
                            p_obj.tirs_subis = max(0, p_obj.tirs_subis - 1)
                        elif t_act == "But encaissé":
                            p_obj.tirs_subis = max(0, p_obj.tirs_subis - 1)
                            p_obj.buts_encaisses = max(0, p_obj.buts_encaisses - 1)
                        elif t_act == "Duel Offensif Gagné":
                            p_obj.duels_off_gagnes = max(0, p_obj.duels_off_gagnes - 1)
                        elif t_act == "Duel Offensif Perdu":
                            p_obj.duels_off_perdus = max(0, p_obj.duels_off_perdus - 1)
                        elif t_act == "Perte de balle (Passe)":
                            p_obj.pertes_de_balles_passe = max(0, p_obj.pertes_de_balles_passe - 1)
                        elif t_act == "Perte de balle (Faute)":
                            p_obj.pertes_de_balles_faute = max(0, p_obj.pertes_de_balles_faute - 1)
                        elif t_act == "Passe Décisive":
                            p_obj.passes_decisives = max(0, p_obj.passes_decisives - 1)
                        elif t_act == "Duel Défensif Gagné":
                            p_obj.duels_def_gagnes = max(0, p_obj.duels_def_gagnes - 1)
                        elif t_act == "Duel Défensif Perdu":
                            p_obj.duels_def_perdus = max(0, p_obj.duels_def_perdus - 1)
                        elif t_act == "Interception":
                            p_obj.interceptions = max(0, p_obj.interceptions - 1)
                        elif t_act == "Neutralisation":
                            p_obj.neutralisations = max(0, p_obj.neutralisations - 1)
                        elif t_act == "Perte de balle provoquée":
                            if hasattr(p_obj, "pertes_balles_provoquees"):
                                p_obj.pertes_balles_provoquees = max(0, p_obj.pertes_balles_provoquees - 1)
                            elif hasattr(p_obj, "balles_provoquees"):
                                p_obj.balles_provoquees = max(0, p_obj.balles_provoquees - 1)
                        elif t_act == "Carton Jaune":
                            p_obj.cartons_jaunes = max(0, p_obj.cartons_jaunes - 1)
                        elif t_act == "Exclusion 2min":
                            p_obj.exclusions_2min = max(0, p_obj.exclusions_2min - 1)
                            if p_obj.exclusions_2min < 3 and getattr(p_obj, "cartons_rouges", 0) > 0:
                                p_obj.cartons_rouges = 0
                        elif t_act in ("Carton Rouge", "Carton Rouge (3x2min)"):
                            p_obj.cartons_rouges = max(0, getattr(p_obj, "cartons_rouges", 0) - 1)
                        elif t_act.startswith("But ("):
                            p_obj.buts = max(0, p_obj.buts - 1)
                            p_obj.tirs = max(0, p_obj.tirs - 1)
                        elif t_act.startswith("Tir raté ("):
                            p_obj.tirs = max(0, p_obj.tirs - 1)

                        if z_cage and z_cage != "Non précisée" and zones_key in st.session_state:
                            z_membre = st.session_state[zones_key].get(p_obj.nom, {}).get(z_cage)
                            if z_membre:
                                if t_act in ("But", "Arrêt décisif"):
                                    z_membre["succes"] = max(0, z_membre.get("succes", 0) - 1)
                                elif t_act in ("Tir raté", "But encaissé"):
                                    z_membre["echec"] = max(0, z_membre.get("echec", 0) - 1)

                    elif t_act == "Attaque adverse" and sys_adv and att_adv_key in st.session_state:
                        st.session_state[att_adv_key][sys_adv] = max(0, st.session_state[att_adv_key].get(sys_adv, 0) - 1)
                    elif t_act == "Temps mort":
                        camp_tm = derniere.get("temps_mort_camp")
                        if camp_tm in ("equipe", "adversaire") and temps_morts_key in st.session_state:
                            st.session_state[temps_morts_key][camp_tm] = max(
                                0, int(st.session_state[temps_morts_key].get(camp_tm, 0)) - 1
                            )

                    sauvegarder_effectif_securise()
                    sauvegarder_brouillon_match_local()
                    st.toast(f"Action annulée : {t_act} ({derniere.get('details', '')})", icon="↩️")

                temps_jeu_key = f"temps_jeu_secondes_{ctx_prefix}"
                if temps_jeu_key not in st.session_state:
                    st.session_state[temps_jeu_key] = {}

                temps_morts_key = f"temps_morts_match_{ctx_prefix}"
                if temps_morts_key not in st.session_state:
                    st.session_state[temps_morts_key] = {"equipe": 0, "adversaire": 0}

                def accumuler_temps_jeu_depuis_dernier_tick():
                    tick_key = f"dernier_tick_jeu_{ctx_prefix}"
                    maintenant = time.time()
                    if st.session_state.get(chrono_enc_key, False):
                        precedent = st.session_state.get(tick_key)
                        if precedent is not None:
                            delta = max(0.0, maintenant - float(precedent))
                            if delta > 0:
                                for n_ter in st.session_state.get(terrain_key, []):
                                    if get_membre(n_ter):
                                        st.session_state[temps_jeu_key][n_ter] = (
                                            float(st.session_state[temps_jeu_key].get(n_ter, 0.0)) + delta
                                        )
                    st.session_state[tick_key] = maintenant

                def appliquer_exclusion_2min(membre_obj):
                    membre_obj.exclusions_2min = getattr(membre_obj, "exclusions_2min", 0) + 1
                    enregistrer_action(
                        "Exclusion 2min",
                        f"#{membre_obj.numero} {membre_obj.nom}",
                        membre_nom=membre_obj.nom,
                    )
                    if membre_obj.exclusions_2min >= 3 and getattr(membre_obj, "cartons_rouges", 0) < 1:
                        membre_obj.cartons_rouges = 1
                        enregistrer_action(
                            "Carton Rouge (3x2min)",
                            f"#{membre_obj.numero} {membre_obj.nom} (Disqualification après 3 exclusions de 2 min)",
                            membre_nom=membre_obj.nom,
                        )
                        st.toast(f"🟥 Carton rouge automatique (3×2 min) : #{membre_obj.numero} {membre_obj.nom}", icon="🟥")
                    else:
                        st.toast(f"Exclusion 2min ({membre_obj.exclusions_2min}/3) : #{membre_obj.numero} {membre_obj.nom}", icon="⏱️")

                def appliquer_carton_rouge_direct(membre_obj):
                    membre_obj.cartons_rouges = 1
                    enregistrer_action(
                        "Carton Rouge",
                        f"#{membre_obj.numero} {membre_obj.nom} (Carton rouge direct)",
                        membre_nom=membre_obj.nom,
                    )
                    st.toast(f"🟥 Carton rouge direct : #{membre_obj.numero} {membre_obj.nom}", icon="🟥")

                def enregistrer_temps_mort(camp: str):
                    tm_dict = st.session_state.get(temps_morts_key, {"equipe": 0, "adversaire": 0})
                    cle = "equipe" if camp == "equipe" else "adversaire"
                    actuel = int(tm_dict.get(cle, 0))
                    if actuel >= 3:
                        st.toast("Maximum de 3 temps morts déjà atteint.", icon="⚠️")
                        return
                    tm_dict[cle] = actuel + 1
                    st.session_state[temps_morts_key] = tm_dict
                    lib_camp = equipe_assignee if cle == "equipe" else "Adversaire"
                    enregistrer_action(
                        "Temps mort",
                        f"Temps mort {lib_camp} ({tm_dict[cle]}/3)",
                        temps_mort_camp=cle,
                    )
                    st.toast(f"⏱️ Temps mort {lib_camp} ({tm_dict[cle]}/3) enregistré.", icon="⏱️")

                # ==========================================
                # MODALE SÉQUENTIELLE EN 2 ÉTAPES (TERRAIN ➔ CAGE)
                # ==========================================
                @st.dialog("🎯 Localisation Géographique & Frappe")
                def modal_saisie_double(p_nom, action_type):
                    p_obj = get_membre(p_nom)
                    st.markdown(f"{L['joueur'].capitalize()} : **#{p_obj.numero} {p_obj.nom}** — Action : **{action_type}**")
                    st.markdown("---")

                    etape_key = f"etape_saisie_tir_{ctx_prefix}"
                    temp_terrain_key = f"temp_zone_terrain_{ctx_prefix}"

                    if etape_key not in st.session_state:
                        st.session_state[etape_key] = "terrain"
                    if temp_terrain_key not in st.session_state:
                        st.session_state[temp_terrain_key] = None

                    if st.session_state[etape_key] == "terrain":
                        zone_ter_choisie = afficher_selecteur_zone_terrain(key_suffix=f"mod_{ctx_prefix}_{p_nom}")

                        st.write("")
                        if st.button("🤷 Ne sais pas (Zone terrain)", key=f"btn_ns_ter_{ctx_prefix}_{p_nom}_{action_type}", use_container_width=True):
                            zone_ter_choisie = "Non précisée"

                        if zone_ter_choisie:
                            st.session_state[temp_terrain_key] = zone_ter_choisie
                            st.session_state[etape_key] = "cage"
                            st.rerun()

                    elif st.session_state[etape_key] == "cage":
                        zone_ter_actuelle = st.session_state[temp_terrain_key]
                        st.info(f"📍 Zone de terrain sélectionnée : **{zone_ter_actuelle}**")

                        if st.button("🔄 Modifier la zone du terrain", key=f"btn_mod_ter_{ctx_prefix}_{p_nom}_{action_type}", use_container_width=True):
                            st.session_state[etape_key] = "terrain"
                            st.rerun()

                        st.markdown("---")
                        st.markdown("##### 🎯 2. Localiser l'impact ou le raté dans la cage :")
                        zone_cage = afficher_grille_saisie_interactive(
                            f"modal_cage_{ctx_prefix}_{p_nom}_{action_type}", action_type=action_type
                        )

                        st.write("")
                        if st.button("🤷 Ne sais pas (Impact cage)", key=f"btn_ns_cage_{ctx_prefix}_{p_nom}_{action_type}", use_container_width=True):
                            zone_cage = "Non précisée"

                        if zone_cage:
                            zone_cage_valide = zone_cage if zone_cage != "Non précisée" else None

                            if action_type == "But":
                                p_obj.buts += 1
                                p_obj.tirs += 1
                                if zone_cage_valide:
                                    enregistrer_zone_tir_live(p_obj.nom, zone_ter_actuelle, zone_cage_valide, est_succes=True)
                                enregistrer_action(
                                    "But",
                                    f"#{p_obj.numero} {p_obj.nom}",
                                    zone_terrain=zone_ter_actuelle,
                                    zone_cage=zone_cage,
                                    membre_nom=p_obj.nom,
                                )
                                st.toast(f"But : #{p_obj.numero} {p_obj.nom} ({zone_ter_actuelle} -> {zone_cage})", icon="🟢")
                            elif action_type == "Tir raté":
                                p_obj.tirs += 1
                                if zone_cage_valide:
                                    enregistrer_zone_tir_live(p_obj.nom, zone_ter_actuelle, zone_cage_valide, est_succes=False)
                                enregistrer_action(
                                    "Tir raté",
                                    f"#{p_obj.numero} {p_obj.nom}",
                                    zone_terrain=zone_ter_actuelle,
                                    zone_cage=zone_cage,
                                    membre_nom=p_obj.nom,
                                )
                                st.toast(f"Tir raté : #{p_obj.numero} {p_obj.nom} ({zone_ter_actuelle} -> {zone_cage})", icon="🔴")
                            elif action_type == "Arrêt décisif":
                                p_obj.arrets += 1
                                p_obj.tirs_subis += 1
                                if zone_cage_valide:
                                    enregistrer_zone_tir_live(p_obj.nom, zone_ter_actuelle, zone_cage_valide, est_succes=True)
                                enregistrer_action(
                                    "Arrêt décisif",
                                    f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})",
                                    zone_terrain=zone_ter_actuelle,
                                    zone_cage=zone_cage,
                                    membre_nom=p_obj.nom,
                                )
                                st.toast(f"Arrêt : #{p_obj.numero} {p_obj.nom} ({zone_ter_actuelle} -> {zone_cage})", icon="🧤")
                            elif action_type == "But encaissé":
                                p_obj.tirs_subis += 1
                                p_obj.buts_encaisses += 1
                                if zone_cage_valide:
                                    enregistrer_zone_tir_live(p_obj.nom, zone_ter_actuelle, zone_cage_valide, est_succes=False)
                                enregistrer_action(
                                    "But encaissé",
                                    f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})",
                                    zone_terrain=zone_ter_actuelle,
                                    zone_cage=zone_cage,
                                    membre_nom=p_obj.nom,
                                )
                                st.toast(f"But encaissé : #{p_obj.numero} {p_obj.nom} ({zone_ter_actuelle} -> {zone_cage})", icon="🥅")

                            manager.sauvegarder_donnees()
                            st.session_state[popup_key] = None
                            st.session_state[etape_key] = "terrain"
                            st.session_state[temp_terrain_key] = None
                            st.rerun()

                if st.session_state.get(popup_key):
                    p_nom_popup, act_popup = st.session_state[popup_key]
                    modal_saisie_double(p_nom_popup, act_popup)

                secondes_totales = st.session_state.get(chrono_secs_key, 0)
                if st.session_state.get(chrono_enc_key, False) and st.session_state.get(chrono_deb_key):
                    secondes_totales += int(time.time() - st.session_state[chrono_deb_key])

                if st.session_state.get(chrono_enc_key, False) and not st.session_state.get(popup_key):
                    st_autorefresh(interval=1000, key=f"chrono_auto_refresh_{ctx_prefix}")

                accumuler_temps_jeu_depuis_dernier_tick()

                total_buts_marques = sum(get_membre(n).buts for n in joueuses_actives if get_membre(n) and hasattr(get_membre(n), 'buts'))
                total_buts_encaisses = sum(get_membre(n).buts_encaisses for n in joueuses_actives if get_membre(n) and isinstance(get_membre(n), Gardienne))
                temps_actuel_str = formater_temps(secondes_totales)

                if st.session_state[mode_tablette_key]:
                    st.session_state[terrain_key] = [j for j in st.session_state.get(terrain_key, []) if get_membre(j)]
                    st.session_state[banc_key] = [j for j in st.session_state.get(banc_key, []) if get_membre(j)]
                    tous_membres_dispos = list(manager.joueuses.keys()) + list(st.session_state.get(pretes_key, {}).keys())
                    if not st.session_state[terrain_key] and tous_membres_dispos:
                        st.session_state[terrain_key] = tous_membres_dispos[:7]
                        st.session_state[banc_key] = tous_membres_dispos[7:]
                    if not st.session_state.get(focus_key) or not get_membre(st.session_state[focus_key]):
                        st.session_state[focus_key] = st.session_state[terrain_key][0] if st.session_state[terrain_key] else None

                    def _start_chrono_tab():
                        if not st.session_state.get(chrono_enc_key, False):
                            st.session_state[chrono_enc_key] = True
                            st.session_state[chrono_deb_key] = time.time()

                    def _pause_chrono_tab():
                        if st.session_state.get(chrono_enc_key, False):
                            st.session_state[chrono_secs_key] += int(time.time() - st.session_state[chrono_deb_key])
                            st.session_state[chrono_enc_key] = False

                    def _ouvrir_popup_tir_tab(nom_j, type_t):
                        st.session_state[popup_key] = (nom_j, type_t)
                        st.session_state[f"etape_saisie_tir_{ctx_prefix}"] = "terrain"
                        st.session_state[f"temp_zone_terrain_{ctx_prefix}"] = None

                    def _quitter_mode_tab():
                        st.session_state[mode_tablette_key] = False

                    afficher_cockpit_tablette_plein_ecran(
                        ctx_prefix=ctx_prefix,
                        equipe_assignee=equipe_assignee,
                        nom_match_actuel=nom_match_actuel,
                        L=L,
                        joueuses_actives=joueuses_actives,
                        terrain_list=st.session_state[terrain_key],
                        banc_list=st.session_state[banc_key],
                        get_membre=get_membre,
                        get_numero_actif=get_numero_actif,
                        manager=manager,
                        total_buts_marques=total_buts_marques,
                        total_buts_encaisses=total_buts_encaisses,
                        temps_actuel_str=temps_actuel_str,
                        periode_actuelle=st.session_state.get(f"periode_match_{ctx_prefix}", "1ère MT"),
                        chrono_en_cours=st.session_state.get(chrono_enc_key, False),
                        enregistrer_action=enregistrer_action,
                        annuler_derniere_action=annuler_derniere_action,
                        appliquer_exclusion_2min=appliquer_exclusion_2min,
                        appliquer_carton_rouge_direct=appliquer_carton_rouge_direct,
                        enregistrer_temps_mort=enregistrer_temps_mort,
                        basculer_seconde_mi_temps=basculer_seconde_mi_temps,
                        on_start_chrono=_start_chrono_tab,
                        on_pause_chrono=_pause_chrono_tab,
                        on_ouvrir_popup_tir=_ouvrir_popup_tir_tab,
                        on_quitter_mode_tablette=_quitter_mode_tab,
                        capitaine=st.session_state.get(f"capitaine_match_{ctx_prefix}"),
                        )
                    return

                c_top_info, c_top_score_chrono, c_top_controls = st.columns([1.2, 2.6, 1.2])

                with c_top_info:
                    st.markdown(f"""
                        <div class="top-box" style="background-color: #121620; border: 1px solid #273043; border-radius: 12px; padding: 10px 14px;">
                            <div style="font-size: 10px; color: #CBD5E1; font-weight: bold; text-transform: uppercase;">Rencontre</div>
                            <div style="font-size: 14px; font-weight: 700; color: #FFFFFF; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{nom_match_actuel}</div>
                        </div>
                    """, unsafe_allow_html=True)

                with c_top_score_chrono:
                    st.markdown(f"""
                        <div class="top-box-dark" style="background-color: #121620; border: 1px solid #273043; border-radius: 12px; padding: 10px 15px;">
                            <div style="display: flex; justify-content: space-around; align-items: center;">
                                <div>
                                    <div style="font-size: 9px; letter-spacing: 1px; text-transform: uppercase; color: #CBD5E1; font-weight: 600;">Score</div>
                                    <div style="font-size: 22px; font-weight: 800; color: #FFFFFF; line-height: 1.1;">{total_buts_marques}  —  {total_buts_encaisses}</div>
                                </div>
                                <div style="border-left: 1px solid #273043; height: 28px; margin: 0 10px;"></div>
                                <div>
                                    <div style="font-size: 9px; letter-spacing: 1px; text-transform: uppercase; color: #CBD5E1; font-weight: 600;">Chrono</div>
                                    <div style="font-size: 22px; font-weight: 800; color: #38BDF8; line-height: 1.1; font-family: monospace;">{temps_actuel_str}</div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                with c_top_controls:
                    with st.container(border=True):
                        st.markdown("<div style='font-size: 9px; font-weight: bold; text-transform: uppercase; color: #CBD5E1; text-align: center; margin-bottom: 2px;'>Contrôle Temps</div>", unsafe_allow_html=True)
                        cc1, cc2, cc3 = st.columns(3)
                        with cc1:
                            start_btn = st.button("▶️", key=f"chrono_start_{ctx_prefix}", use_container_width=True)
                        with cc2:
                            pause_btn = st.button("⏸️", key=f"chrono_pause_{ctx_prefix}", use_container_width=True)
                        with cc3:
                            reset_btn = st.button("🔄", key=f"chrono_reset_{ctx_prefix}", use_container_width=True)

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

                periode_actuelle = st.session_state.get(f"periode_match_{ctx_prefix}", "1ère MT")
                col_p1, col_p2 = st.columns([2.5, 2.5])
                with col_p1:
                    st.caption(f"Période active : **{periode_actuelle}**")
                with col_p2:
                    if periode_actuelle == "1ère MT":
                        if st.button("⏱️ Passer en 2ème mi-temps (Caler à 30:00)", key=f"btn_passer_2mt_{ctx_prefix}", use_container_width=True):
                            basculer_seconde_mi_temps()
                            st.rerun()
                    else:
                        if st.button("↩️ Revenir en 1ère mi-temps", key=f"btn_revenir_1mt_{ctx_prefix}", use_container_width=True):
                            st.session_state[f"periode_match_{ctx_prefix}"] = "1ère MT"
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

                            num_actuel = get_numero_actif(p_item.nom)
                            nb_2m = int(getattr(p_item, "exclusions_2min", 0) or 0)
                            nb_cr = int(getattr(p_item, "cartons_rouges", 0) or 0)
                            nb_cj = int(getattr(p_item, "cartons_jaunes", 0) or 0)
                            signe_disc = ""
                            if nb_cr > 0 or nb_2m >= 3:
                                signe_disc = " 🟥"
                            elif nb_2m > 0:
                                signe_disc = f" ⏱️×{nb_2m}" if nb_2m > 1 else " ⏱️"
                            elif nb_cj > 0:
                                signe_disc = " 🟨"
                            cap_courant = st.session_state.get(f"capitaine_match_{ctx_prefix}")
                            tag_cap = " (C)" if (cap_courant and p_item.nom == cap_courant) else ""
                            label_btn = f"{prefix} #{num_actuel} {p_item.nom.split()[0]}{tag_cap}{signe_disc}"

                            if st.button(label_btn, key=f"terrain_j_{ctx_prefix}_{nom_j}", use_container_width=True, type=type_btn):
                                st.session_state[focus_key] = nom_j
                                st.rerun()

                with st.expander("🔄 Gérer les rotations (Remplacements rapides)"):
                    r_col1, r_col2, r_col3 = st.columns([2, 2, 1])
                    with r_col1:
                        sortant = st.selectbox("Sort du terrain ⬇️", terrain_list, key=f"sel_sortant_{ctx_prefix}")
                    with r_col2:
                        banc_dispo = st.session_state[banc_key] if st.session_state[banc_key] else ["Aucune"]
                        entrant = st.selectbox("Entre sur le terrain ⬆️", banc_dispo, key=f"sel_entrant_{ctx_prefix}")
                    with r_col3:
                        st.write("")
                        st.write("")
                        if st.button("🔄 Intervertir", type="primary", use_container_width=True, key=f"btn_intervertir_{ctx_prefix}"):
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

                col_undo_btn, col_undo_info = st.columns([1.4, 3.6])
                with col_undo_btn:
                    derniere_act = st.session_state.get(journal_key, [])[-1] if st.session_state.get(journal_key) else None
                    if st.button(
                        "↩️ Annuler dernière action",
                        key=f"btn_annuler_action_{ctx_prefix}",
                        use_container_width=True,
                        disabled=(derniere_act is None),
                    ):
                        annuler_derniere_action()
                        st.rerun()
                with col_undo_info:
                    if derniere_act:
                        st.caption(f"Dernière saisie ({derniere_act['temps']}) : **{derniere_act['type_action']}** — {derniere_act['details']}")
                    else:
                        st.caption("Aucune action enregistrée sur ce match.")

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
                            num_actuel = get_numero_actif(p_obj.nom)
                            st.markdown(f"#### ⚡ #{num_actuel} - {p_obj.nom}")
                        with h_col2:
                            st.markdown(get_badge_poste_html(p_obj.poste), unsafe_allow_html=True)
                        with h_col3:
                            if isinstance(p_obj, JoueuseDeChamp):
                                st.markdown(f"<div style='font-size: 15px; font-weight: 800; color: #FFFFFF; background-color: #1A2030; border: 1px solid #273043; padding: 6px 10px; border-radius: 6px; text-align: center;'>🎯 {p_obj.buts}/{p_obj.tirs} buts <span style='font-size: 11px; color: #CBD5E1;'>({p_obj.efficacite_tirs()}%)</span> | Passes D. : {p_obj.passes_decisives}</div>", unsafe_allow_html=True)
                            elif isinstance(p_obj, Gardienne):
                                st.markdown(f"<div style='font-size: 15px; font-weight: 800; color: #FFFFFF; background-color: #1A2030; border: 1px solid #273043; padding: 6px 10px; border-radius: 6px; text-align: center;'>🧤 {p_obj.arrets}/{p_obj.tirs_subis} arrêts <span style='font-size: 11px; color: #CBD5E1;'>({p_obj.pourcentage_arrets()}%)</span></div>", unsafe_allow_html=True)
                        st.markdown("---")

                        if isinstance(p_obj, JoueuseDeChamp):
                            col_atk_box, col_def_box = st.columns(2)

                            with col_atk_box:
                                with st.container(border=True):
                                    st.markdown("##### ⚔️ ATTAQUE")

                                    ba1, ba2 = st.columns(2)
                                    with ba1:
                                        if st.button("🟢 +1 But", key=f"btn_but_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            st.session_state[popup_key] = (p_obj.nom, "But")
                                            st.session_state[f"etape_saisie_tir_{ctx_prefix}"] = "terrain"
                                            st.session_state[f"temp_zone_terrain_{ctx_prefix}"] = None
                                            st.rerun()
                                    with ba2:
                                        if st.button("🔴 Tir raté", key=f"btn_tirete_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            st.session_state[popup_key] = (p_obj.nom, "Tir raté")
                                            st.session_state[f"etape_saisie_tir_{ctx_prefix}"] = "terrain"
                                            st.session_state[f"temp_zone_terrain_{ctx_prefix}"] = None
                                            st.rerun()

                                    ba3, ba4 = st.columns(2)
                                    with ba3:
                                        if st.button("⚔️ Duel Gagné", key=f"btn_dog_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_off_gagnes += 1
                                            enregistrer_action("Duel Offensif Gagné", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Duel off. gagné : #{p_obj.numero} {p_obj.nom}", icon="⚔️")
                                            st.rerun()
                                    with ba4:
                                        if st.button("❌ Duel Perdu", key=f"btn_dop_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_off_perdus += 1
                                            enregistrer_action("Duel Offensif Perdu", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Duel off. perdu : #{p_obj.numero} {p_obj.nom}", icon="❌")
                                            st.rerun()

                                    ba5, ba6 = st.columns(2)
                                    with ba5:
                                        if st.button("📤 Perte (Passe)", key=f"btn_pb_passe_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.pertes_de_balles_passe += 1
                                            enregistrer_action("Perte de balle (Passe)", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Perte (passe) : #{p_obj.numero} {p_obj.nom}", icon="📤")
                                            st.rerun()
                                    with ba6:
                                        if st.button("⚠️ Perte (Faute)", key=f"btn_pb_faute_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.pertes_de_balles_faute += 1
                                            enregistrer_action("Perte de balle (Faute)", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Perte (faute) : #{p_obj.numero} {p_obj.nom}", icon="⚠️")
                                            st.rerun()

                                    if st.button("🤝 +1 Passe Décisive", key=f"btn_pd_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                        p_obj.passes_decisives += 1
                                        enregistrer_action("Passe Décisive", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                        manager.sauvegarder_donnees()
                                        st.toast(f"Passe décisive : #{p_obj.numero} {p_obj.nom}", icon="🤝")
                                        st.rerun()

                            with col_def_box:
                                with st.container(border=True):
                                    st.markdown("##### 🛡️ DÉFENSE & DISCIPLINE")

                                    bd1, bd2 = st.columns(2)
                                    with bd1:
                                        if st.button("🛡️ Duel Gagné", key=f"btn_ddg_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_def_gagnes += 1
                                            enregistrer_action("Duel Défensif Gagné", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Duel déf. gagné : #{p_obj.numero} {p_obj.nom}", icon="🛡️")
                                            st.rerun()
                                    with bd2:
                                        if st.button("⚠️ Duel Perdu", key=f"btn_ddp_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.duels_def_perdus += 1
                                            enregistrer_action("Duel Défensif Perdu", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Duel déf. perdu : #{p_obj.numero} {p_obj.nom}", icon="⚠️")
                                            st.rerun()

                                    bd3, bd4 = st.columns(2)
                                    with bd3:
                                        if st.button("⚡ Interception", key=f"btn_int_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.interceptions += 1
                                            enregistrer_action("Interception", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Interception : #{p_obj.numero} {p_obj.nom}", icon="⚡")
                                            st.rerun()
                                    with bd4:
                                        if st.button("🧱 Neutralisation", key=f"btn_neut_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.neutralisations += 1
                                            enregistrer_action("Neutralisation", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Neutralisation : #{p_obj.numero} {p_obj.nom}", icon="🧱")
                                            st.rerun()

                                    if st.button("🔥 Perte provoquée", key=f"btn_bp_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                        p_obj.pertes_balles_provoquees += 1
                                        enregistrer_action("Perte de balle provoquée", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                        manager.sauvegarder_donnees()
                                        st.toast(f"Perte provoquée : #{p_obj.numero} {p_obj.nom}", icon="🔥")
                                        st.rerun()

                                    bs1, bs2 = st.columns(2)
                                    with bs1:
                                        if st.button("🟨 +1 Jaune", key=f"btn_jaune_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            p_obj.cartons_jaunes += 1
                                            enregistrer_action("Carton Jaune", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                            manager.sauvegarder_donnees()
                                            st.toast(f"Carton jaune : #{p_obj.numero} {p_obj.nom}", icon="🟨")
                                            st.rerun()
                                    with bs2:
                                        if st.button("⏱️ + 2min", key=f"btn_2min_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                            appliquer_exclusion_2min(p_obj)
                                            manager.sauvegarder_donnees()
                                            st.rerun()

                                    if st.button("🟥 Carton Rouge", key=f"btn_rouge_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                        appliquer_carton_rouge_direct(p_obj)
                                        manager.sauvegarder_donnees()
                                        st.rerun()

                        elif isinstance(p_obj, Gardienne):
                            g1, g2 = st.columns(2)
                            with g1:
                                if st.button("🧤 +1 Arrêt décisif", key=f"btn_arret_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    st.session_state[popup_key] = (p_obj.nom, "Arrêt décisif")
                                    st.session_state[f"etape_saisie_tir_{ctx_prefix}"] = "terrain"
                                    st.session_state[f"temp_zone_terrain_{ctx_prefix}"] = None
                                    st.rerun()
                                if st.button("🟢 +1 But (marqué)", key=f"btn_gbut_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    p_obj.buts += 1
                                    p_obj.tirs += 1
                                    enregistrer_action(f"But ({L['gardien']})", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                    manager.sauvegarder_donnees()
                                    st.toast(f"But ({L['gardien'].lower()}) : #{p_obj.numero} {p_obj.nom}", icon="🟢")
                                    st.rerun()
                                if st.button("🟨 +1 Jaune", key=f"btn_gjaune_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    p_obj.cartons_jaunes += 1
                                    enregistrer_action("Carton Jaune", f"#{p_obj.numero} {p_obj.nom} ({L['gardien']})", membre_nom=p_obj.nom)
                                    manager.sauvegarder_donnees()
                                    st.toast(f"Carton jaune : #{p_obj.numero} {p_obj.nom}", icon="🟨")
                                    st.rerun()
                            with g2:
                                if st.button("🥅 But encaissé", key=f"btn_enc_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    st.session_state[popup_key] = (p_obj.nom, "But encaissé")
                                    st.session_state[f"etape_saisie_tir_{ctx_prefix}"] = "terrain"
                                    st.session_state[f"temp_zone_terrain_{ctx_prefix}"] = None
                                    st.rerun()
                                if st.button("🔴 Tir raté", key=f"btn_gtirete_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    p_obj.tirs += 1
                                    enregistrer_action(f"Tir raté ({L['gardien']})", f"#{p_obj.numero} {p_obj.nom}", membre_nom=p_obj.nom)
                                    manager.sauvegarder_donnees()
                                    st.toast(f"Tir raté ({L['gardien'].lower()}) : #{p_obj.numero} {p_obj.nom}", icon="🔴")
                                    st.rerun()
                                if st.button("⏱️ + 2min", key=f"btn_g2min_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    appliquer_exclusion_2min(p_obj)
                                    manager.sauvegarder_donnees()
                                    st.rerun()
                                if st.button("🟥 Carton Rouge", key=f"btn_grouge_{ctx_prefix}_{p_obj.nom}", use_container_width=True):
                                    appliquer_carton_rouge_direct(p_obj)
                                    manager.sauvegarder_donnees()
                                    st.rerun()

                # --- SUIVI TACTIQUE & NOTES DU BANC ---
                with st.container(border=True):
                    st.subheader("📋 Suivi Tactique — Attaques Adverses & Notes du Staff")

                    if att_adv_key not in st.session_state:
                        st.session_state[att_adv_key] = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}

                    t_col1, t_col2, t_col3, t_col4, t_col5, t_col6 = st.columns([1, 1, 1, 1, 1, 2])
                    with t_col1:
                        if st.button("🔄 Yago", use_container_width=True, key=f"att_btn_yago_{ctx_prefix}"):
                            st.session_state[att_adv_key]["Yago"] += 1
                            enregistrer_action("Attaque adverse", "Système Yago", systeme_adv="Yago")
                            st.toast("Système Yago enregistré !", icon="📊")
                            st.rerun()
                    with t_col2:
                        if st.button("🔄 Yego", use_container_width=True, key=f"att_btn_yego2_{ctx_prefix}"):
                            st.session_state[att_adv_key]["Yego"] += 1
                            enregistrer_action("Attaque adverse", "Système Yego", systeme_adv="Yego")
                            st.toast("Système Yego enregistré !", icon="📊")
                            st.rerun()
                    with t_col3:
                        if st.button("🔄 Montp.", use_container_width=True, key=f"att_btn_montpellier_{ctx_prefix}"):
                            st.session_state[att_adv_key]["Montpellier"] += 1
                            enregistrer_action("Attaque adverse", "Système Montpellier", systeme_adv="Montpellier")
                            st.toast("Système Montpellier enregistré !", icon="📊")
                            st.rerun()
                    with t_col4:
                        if st.button("🔄 Croisé", use_container_width=True, key=f"att_btn_croise_{ctx_prefix}"):
                            st.session_state[att_adv_key]["Croisé"] += 1
                            enregistrer_action("Attaque adverse", "Système Croisé", systeme_adv="Croisé")
                            st.toast("Système Croisé enregistré !", icon="📊")
                            st.rerun()
                    with t_col5:
                        if st.button("🔄 Autre", use_container_width=True, key=f"att_btn_autre_{ctx_prefix}"):
                            st.session_state[att_adv_key]["Autre"] += 1
                            enregistrer_action("Attaque adverse", "Système Autre", systeme_adv="Autre")
                            st.toast("Autre système enregistré !", icon="📊")
                            st.rerun()

                    st.write("")
                    df_att_compact = pd.DataFrame([st.session_state[att_adv_key]])
                    st.dataframe(df_att_compact, use_container_width=True, hide_index=True)

                    with st.form(key=f"form_commentaire_staff_bottom_{ctx_prefix}", clear_on_submit=True):
                        txt_com_bot = st.text_input("💬 Ajouter un fait de match / note rapide", placeholder="Ex: Temps mort tactique, changement de défense...")
                        if st.form_submit_button("Ajouter au journal de match") and txt_com_bot.strip():
                            if commentaires_key not in st.session_state:
                                st.session_state[commentaires_key] = []
                            st.session_state[commentaires_key].append({
                                "temps": temps_actuel_str,
                                "periode": periode_actuelle,
                                "horodatage_reel": datetime.now().strftime("%H:%M:%S"),
                                "texte": txt_com_bot.strip(),
                            })
                            sauvegarder_brouillon_match_local()
                            st.rerun()

                st.divider()

                # --- DASHBOARD & SYNTHÈSE LIVE ---
                with st.container(border=True):
                    st.subheader("📊 Dashboard & Synthèse Live de la Rencontre")

                    tous_actifs_objs = [get_membre(n) for n in joueuses_actives if get_membre(n)]
                    champ_actives = [j for j in tous_actifs_objs if isinstance(j, JoueuseDeChamp)]
                    gard_actives = [j for j in tous_actifs_objs if isinstance(j, Gardienne)]

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
                        num_actuel = get_numero_actif(j.nom)
                        if isinstance(j, JoueuseDeChamp):
                            data_terrain.append({
                                "N°": num_actuel, "Nom": j.nom, "Poste": j.poste,
                                "Min": round(float(st.session_state.get(temps_jeu_key, {}).get(j.nom, 0.0)) / 60.0, 1),
                                "Buts/Tirs": f"{j.buts}/{j.tirs} ({j.efficacite_tirs()}%)",
                                "Passes D.": j.passes_decisives, "Pertes": j.pertes_de_balles_passe + j.pertes_de_balles_faute,
                                "🟨": j.cartons_jaunes, "⏱️": j.exclusions_2min, "🟥": getattr(j, "cartons_rouges", 0)
                            })
                        elif isinstance(j, Gardienne):
                            data_terrain.append({
                                "N°": num_actuel, "Nom": j.nom, "Poste": L["gardien"],
                                "Min": round(float(st.session_state.get(temps_jeu_key, {}).get(j.nom, 0.0)) / 60.0, 1),
                                "Buts/Tirs": f"{j.buts}/{j.tirs} ({round(j.buts / j.tirs * 100, 1) if j.tirs > 0 else 0.0}%)",
                                "Arrêts/Subis": f"{j.arrets}/{j.tirs_subis} ({j.pourcentage_arrets()}%)",
                                "🟨": j.cartons_jaunes, "⏱️": j.exclusions_2min, "🟥": getattr(j, "cartons_rouges", 0)
                            })
                    if data_terrain:
                        st.dataframe(data_terrain, use_container_width=True, hide_index=True)

                    if commentaires_key in st.session_state and st.session_state[commentaires_key]:
                        st.markdown("**💬 Journal des faits de match enregistrés :**")
                        for note in st.session_state[commentaires_key]:
                            st.markdown(f"- **`{note['temps']}`** (`{note.get('periode', '')}`) : {note['texte']}")

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
                    st.markdown("### ⏱️ Temps Morts (Max 3 par camp)")
                    tm_etat = st.session_state.get(temps_morts_key, {"equipe": 0, "adversaire": 0})
                    tm_eq_val = int(tm_etat.get("equipe", 0))
                    tm_adv_val = int(tm_etat.get("adversaire", 0))
                    tm_c1, tm_c2 = st.columns(2)
                    with tm_c1:
                        if st.button(
                            f"⏱️ Temps mort {equipe_assignee} ({tm_eq_val}/3)",
                            key=f"btn_tm_eq_{ctx_prefix}",
                            disabled=(tm_eq_val >= 3),
                            use_container_width=True,
                        ):
                            enregistrer_temps_mort("equipe")
                            st.rerun()
                    with tm_c2:
                        if st.button(
                            f"⏱️ Temps mort Adversaire ({tm_adv_val}/3)",
                            key=f"btn_tm_adv_{ctx_prefix}",
                            disabled=(tm_adv_val >= 3),
                            use_container_width=True,
                        ):
                            enregistrer_temps_mort("adversaire")
                            st.rerun()

                    st.markdown("---")
                    st.markdown("### 📋 Tableau Blanc Tactique (Vestiaires)")
                    afficher_tableau_tactique()

                # --- CLÔTURE DE LA RENCONTRE ---
                with st.container(border=True):
                    st.subheader("🏁 Clôture & Annulation de la Rencontre")

                    with st.expander(f"✏️ Ajuster des statistiques manuellement en cas d'erreur (Adapté au rôle du/de la {L['joueur']})"):
                        joueuses_existantes_actives = [n for n in joueuses_actives if get_membre(n)]
                        if joueuses_existantes_actives:
                            joueuse_a_corriger = st.selectbox(
                                f"Choisir le/la {L['joueur']} à rectifier",
                                joueuses_existantes_actives,
                                key=f"select_correction_live_{ctx_prefix}"
                            )
                            p_corr = get_membre(joueuse_a_corriger)

                            with st.form(key=f"form_correction_{ctx_prefix}_{p_corr.nom}"):
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
                                        c_rouge = st.number_input("Cartons rouges", min_value=0, value=getattr(p_corr, 'cartons_rouges', 0))

                                    if st.form_submit_button("Valider la correction", type="primary", use_container_width=True, key=f"btn_val_corr_champ_{ctx_prefix}_{p_corr.nom}"):
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
                                        p_corr.cartons_rouges = c_rouge
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
                                        c_rouge = st.number_input("Cartons rouges", min_value=0, value=getattr(p_corr, 'cartons_rouges', 0))

                                    if st.form_submit_button("Valider la correction", type="primary", use_container_width=True, key=f"btn_val_corr_gard_{ctx_prefix}_{p_corr.nom}"):
                                        p_corr.arrets = c_arrets
                                        p_corr.tirs_subis = c_subis
                                        p_corr.buts_encaisses = c_encaisses
                                        p_corr.cartons_jaunes = c_jaune
                                        p_corr.buts = c_buts
                                        p_corr.tirs = c_tirs
                                        p_corr.exclusions_2min = c_2min
                                        p_corr.cartons_rouges = c_rouge
                                        manager.sauvegarder_donnees()
                                        st.success("Correction enregistrée avec succès !")
                                        st.rerun()
                    afficher_bloc_synchro_hors_ligne()

                    st.write("")

                    # --- ZONE DE DANGER : ANNULER LE MATCH EN COURS ---
                    with st.expander("⚠️ Zone de danger : Annuler le match en cours (Lancé par erreur)"):
                        st.warning("Attention : Si vous annulez ce match, toutes les actions enregistrées depuis le début de la rencontre seront perdues et les compteurs des joueuses seront remis à zéro.")
                        if st.button("❌ Annuler et abandonner ce match en cours", type="primary", key=f"btn_annuler_match_en_cours_{ctx_prefix}"):
                            for nom_j_actif in joueuses_actives:
                                obj_j = get_membre(nom_j_actif)
                                if obj_j:
                                    obj_j.cartons_jaunes = 0
                                    obj_j.exclusions_2min = 0
                                    obj_j.cartons_rouges = 0
                                    if isinstance(obj_j, JoueuseDeChamp):
                                        obj_j.buts = 0
                                        obj_j.tirs = 0
                                        obj_j.passes_decisives = 0
                                        obj_j.pertes_de_balles_passe = 0
                                        obj_j.pertes_de_balles_faute = 0
                                        obj_j.duels_off_gagnes = 0
                                        obj_j.duels_off_perdus = 0
                                        obj_j.duels_def_gagnes = 0
                                        obj_j.duels_def_perdus = 0
                                        obj_j.neutralisations = 0
                                        obj_j.interceptions = 0
                                        obj_j.pertes_balles_provoquees = 0
                                    elif isinstance(obj_j, Gardienne):
                                        obj_j.arrets = 0
                                        obj_j.tirs_subis = 0
                                        obj_j.buts_encaisses = 0
                                        obj_j.buts = 0
                                        obj_j.tirs = 0

                            manager.sauvegarder_donnees()
                            sync_mgr.supprimer_brouillon(ctx_prefix)

                            st.session_state[f"match_en_cours_{ctx_prefix}"] = False
                            st.session_state[f"capitaine_match_{ctx_prefix}"] = None
                            st.session_state[att_adv_key] = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}
                            st.session_state[zones_key] = {}
                            st.session_state[popup_key] = None
                            st.session_state[mode_tablette_key] = False
                            st.session_state[pretes_key] = {}
                            if f"numeros_match_{ctx_prefix}" in st.session_state:
                                del st.session_state[f"numeros_match_{ctx_prefix}"]
                                st.session_state[f"capitaine_match_{ctx_prefix}"] = None
                            if f"journal_actions_match_{ctx_prefix}" in st.session_state:
                                del st.session_state[f"journal_actions_match_{ctx_prefix}"]

                            st.session_state[temps_jeu_key] = {}
                            st.session_state[temps_morts_key] = {"equipe": 0, "adversaire": 0}
                            st.toast("Le match a été annulé avec succès.", icon="🗑️")
                            aller_a("accueil")

                    st.write("")
                    with st.expander("🔋 Charge & Forme de fin de match (Optionnel — Alimente le suivi longitudinal)", expanded=False):
                        date_cloture_match = st.date_input(
                            "Date de la rencontre",
                            value=date.today(),
                            key=f"date_cloture_match_{ctx_prefix}",
                        )
                        lignes_cloture_init = []
                        for n_act in joueuses_actives:
                            m_obj = get_membre(n_act)
                            if m_obj:
                                secs_joues_auto = float(st.session_state.get(temps_jeu_key, {}).get(m_obj.nom, 0.0))
                                min_auto = int(round(secs_joues_auto / 60.0)) if secs_joues_auto > 0 else 0
                                lignes_cloture_init.append({
                                    "Nom": m_obj.nom,
                                    "Poste": m_obj.poste,
                                    "Temps (min)": min_auto,
                                    "RPE (1-10)": 6.0,
                                    "Forme (1-5)": 3.0,
                                })
                        df_cloture_edit = st.data_editor(
                            pd.DataFrame(lignes_cloture_init),
                            column_config={
                                "Nom": st.column_config.TextColumn(disabled=True),
                                "Poste": st.column_config.TextColumn(disabled=True),
                                "Temps (min)": st.column_config.NumberColumn(min_value=0, max_value=120, step=1),
                                "RPE (1-10)": st.column_config.NumberColumn(min_value=1.0, max_value=10.0, step=0.5),
                                "Forme (1-5)": st.column_config.NumberColumn(min_value=1.0, max_value=5.0, step=0.5),
                            },
                            hide_index=True,
                            use_container_width=True,
                            key=f"editor_cloture_longitudinal_{ctx_prefix}",
                        )

                    st.write("")
                    if st.button("🏁 Archiver définitivement ce match et réinitialiser", type="primary", use_container_width=True, key=f"btn_archiver_match_{ctx_prefix}"):
                        pretes_dict = st.session_state.get(pretes_key, {})
                        dict_nums_match = st.session_state.get(f"numeros_match_{ctx_prefix}", {})

                        indices_perf_avant_archive = {}
                        for n_act in joueuses_actives:
                            m_obj = get_membre(n_act)
                            if m_obj:
                                est_g = isinstance(m_obj, Gardienne)
                                stats_snapshot = (
                                    {
                                        "arrets": getattr(m_obj, "arrets", 0),
                                        "tirs_subis": getattr(m_obj, "tirs_subis", 0),
                                        "buts": getattr(m_obj, "buts", 0),
                                        "cartons_jaunes": getattr(m_obj, "cartons_jaunes", 0),
                                        "exclusions_2min": getattr(m_obj, "exclusions_2min", 0),
                                        "cartons_rouges": getattr(m_obj, "cartons_rouges", 0),
                                    }
                                    if est_g
                                    else {
                                        "buts": getattr(m_obj, "buts", 0),
                                        "tirs": getattr(m_obj, "tirs", 0),
                                        "passes_decisives": getattr(m_obj, "passes_decisives", 0),
                                        "interceptions": getattr(m_obj, "interceptions", 0),
                                        "neutralisations": getattr(m_obj, "neutralisations", 0),
                                        "balles_provoquees": getattr(m_obj, "pertes_balles_provoquees", 0),
                                        "duels_off_gagnes": getattr(m_obj, "duels_off_gagnes", 0),
                                        "duels_def_gagnes": getattr(m_obj, "duels_def_gagnes", 0),
                                        "pertes_passe": getattr(m_obj, "pertes_de_balles_passe", 0),
                                        "pertes_faute": getattr(m_obj, "pertes_de_balles_faute", 0),
                                        "duels_off_perdus": getattr(m_obj, "duels_off_perdus", 0),
                                        "duels_def_perdus": getattr(m_obj, "duels_def_perdus", 0),
                                        "cartons_jaunes": getattr(m_obj, "cartons_jaunes", 0),
                                        "exclusions_2min": getattr(m_obj, "exclusions_2min", 0),
                                        "cartons_rouges": getattr(m_obj, "cartons_rouges", 0),
                                    }
                                )
                                indices_perf_avant_archive[n_act] = calculer_indice_performance_match(
                                    stats_snapshot, est_gardienne=est_g
                                )

                        manager.archiver_match(
                            nom_match_actuel,
                            attaques_adv_data=st.session_state.get(att_adv_key, {}),
                            joueuses_actives=joueuses_actives,
                            journal_actions=st.session_state.get(journal_key, []),
                            commentaires_staff=st.session_state.get(commentaires_key, []),
                            numeros_match=dict_nums_match,
                            pretes_dict=pretes_dict,
                            club_equipes=_get_equipes_du_club_courant(),
                        )

                        if df_cloture_edit is not None and not df_cloture_edit.empty:
                            for _, row_c in df_cloture_edit.iterrows():
                                nom_c = row_c.get("Nom")
                                if nom_c in manager.joueuses:
                                    manager.ajouter_entree_longitudinale(
                                        nom_joueur=nom_c,
                                        date_str=date_cloture_match.isoformat(),
                                        type_entree="Match",
                                        duree_min=row_c.get("Temps (min)", 0),
                                        rpe=row_c.get("RPE (1-10)", 6.0),
                                        forme=row_c.get("Forme (1-5)", 3.0),
                                        libelle=nom_match_actuel,
                                        performance_score=indices_perf_avant_archive.get(nom_c),
                                        note="Clôture match",
                                    )
                        sync_mgr.supprimer_brouillon(ctx_prefix)

                        st.session_state[f"match_en_cours_{ctx_prefix}"] = False
                        st.session_state[f"capitaine_match_{ctx_prefix}"] = None
                        st.session_state[att_adv_key] = {"Yago": 0, "Yego": 0, "Montpellier": 0, "Croisé": 0, "Autre": 0}
                        st.session_state[zones_key] = {}
                        st.session_state[popup_key] = None
                        st.session_state[mode_tablette_key] = False
                        st.session_state[pretes_key] = {}
                        st.session_state[temps_jeu_key] = {}
                        st.session_state[temps_morts_key] = {"equipe": 0, "adversaire": 0}
                        st.toast("Le match a été archivé avec succès !", icon="✅")
                        aller_a("accueil")

    # ==========================================
    # 3. ÉCRAN : STATS SAISON
    # ==========================================
    elif st.session_state[page_key] == "saison":
        if st.button("⬅️ Retour à l'accueil", key=f"btn_retour_saison_{ctx_prefix}"):
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

            sub_tab_matchs, sub_tab_equipe, sub_tab_joueuses, sub_tab_charge, sub_tab_scouting = st.tabs([
                "📋 Feuilles de Match Archivées",
                "👥 Statistiques Équipe",
                f"👤 Statistiques par {L['joueur'].capitalize()}",
                "🔋 Charge & Forme",
                "🔎 Scouting Adversaire",
            ])

            # --- SOUS-ONGLET 1 : FEUILLES DE MATCH ARCHIVÉES ---
            with sub_tab_matchs:
                if not matchs_archives:
                    st.warning("Aucun match n'a encore été archivé.")
                else:
                    recherche_match = st.text_input("🔍 Rechercher une rencontre (ex: J1, Victoire, Adversaire...)", value="", key=f"search_match_{ctx_prefix}")
                    matchs_filtres = [m for m in matchs_archives if recherche_match.lower() in m.lower()] if recherche_match else matchs_archives

                    if not matchs_filtres:
                        st.info("Aucun match ne correspond à votre recherche.")
                    else:
                        col_sel_match, col_del_match = st.columns([3, 1])
                        with col_sel_match:
                            match_choisi = st.selectbox("Sélectionner une rencontre", matchs_filtres, key=f"select_match_archive_{ctx_prefix}")
                        with col_del_match:
                            st.write("")
                            st.write("")
                            peut_supprimer_archive = a_permission("supprimer_archive")
                            if st.button(
                                "🗑️ Supprimer",
                                key=f"btn_suppr_match_arch_{ctx_prefix}",
                                type="secondary",
                                use_container_width=True,
                                disabled=not peut_supprimer_archive,
                                help="Efface définitivement ce match de l'historique de l'équipe" if peut_supprimer_archive else "Permission 'Suppression de matchs archivés' requise",
                            ):
                                for j_del in tous_membres_saison:
                                    j_del.historique_matchs = [m for m in j_del.historique_matchs if m["match"] != match_choisi]
                                manager.sauvegarder_donnees()

                                club_equipes_sup = _get_equipes_du_club_courant()
                                for eq_c in club_equipes_sup:
                                    if eq_c != equipe_assignee:
                                        mgr_c = EquipeManager(fichier=get_nom_fichier_equipe(eq_c), club_slug=club_slug_session)
                                        modifie = False
                                        for j_c in mgr_c.joueuses.values():
                                            avant_len = len(j_c.historique_matchs)
                                            j_c.historique_matchs = [m for m in j_c.historique_matchs if m["match"] != match_choisi]
                                            if len(j_c.historique_matchs) < avant_len:
                                                modifie = True
                                        if modifie:
                                            mgr_c.sauvegarder_donnees()

                                st.success(f"Le match '{match_choisi}' a été supprimé avec succès !")
                                st.rerun()

                        lignes_champ = []
                        lignes_gardiennes = []
                        attaques_adv_archive = {}
                        journal_actions_archive = []
                        commentaires_staff_archive = []

                        club_equipes = _get_equipes_du_club_courant()

                        dictionnaires_managers = {equipe_assignee: manager}
                        for eq in club_equipes:
                            if eq != equipe_assignee:
                                nom_f_orig = get_nom_fichier_equipe(eq)
                                dictionnaires_managers[eq] = EquipeManager(fichier=nom_f_orig, club_slug=club_slug_session)

                        seen_champ_noms = set()
                        seen_gard_noms = set()

                        for nom_eq, mgr in dictionnaires_managers.items():
                            for j in mgr.joueuses.values():
                                donnees_m = next((m for m in j.historique_matchs if m["match"] == match_choisi), None)
                                if donnees_m:
                                    if not attaques_adv_archive:
                                        attaques_adv_archive = donnees_m.get("attaques_adversaires", {})
                                    if not journal_actions_archive:
                                        journal_actions_archive = donnees_m.get("journal_actions", [])
                                    if not commentaires_staff_archive:
                                        commentaires_staff_archive = donnees_m.get("commentaires_staff", [])

                                    num_affiche = donnees_m.get("numero_match", j.numero)

                                    if isinstance(j, JoueuseDeChamp):
                                        if j.nom in seen_champ_noms:
                                            continue
                                        seen_champ_noms.add(j.nom)
                                        b_val = donnees_m.get("buts", 0)
                                        t_val = donnees_m.get("tirs", 0)
                                        lignes_champ.append({
                                            "N°": num_affiche,
                                            L['joueur'].capitalize(): j.nom,
                                            "Poste": j.poste,
                                            "Buts": b_val,
                                            "Tirs": t_val,
                                            "Réussite": f"{round((b_val / t_val * 100), 1)}%" if t_val > 0 else "0.0%",
                                            "Passes D.": donnees_m.get("passes_decisives", 0),
                                            "Perte (Passe)": donnees_m.get("pertes_passe", 0),
                                            "Perte (Faute)": donnees_m.get("pertes_faute", 0),
                                            "Duels Off": f"{donnees_m.get('duels_off_gagnes', 0)}/{donnees_m.get('duels_off_gagnes', 0) + donnees_m.get('duels_off_perdus', 0)}",
                                            "Duels Déf": f"{donnees_m.get('duels_def_gagnes', 0)}/{donnees_m.get('duels_def_gagnes', 0) + donnees_m.get('duels_def_perdus', 0)}",
                                            "Interceptions": donnees_m.get("interceptions", 0),
                                            "Neutralisations": donnees_m.get("neutralisations", 0),
                                            "Provoquées": donnees_m.get("balles_provoquees", 0),
                                            "🟨": donnees_m.get("cartons_jaunes", 0),
                                            "⏱️ 2min": donnees_m.get("exclusions_2min", 0),
                                            "🟥": donnees_m.get("cartons_rouges", 0),
                                        })
                                    elif isinstance(j, Gardienne):
                                        if j.nom in seen_gard_noms:
                                            continue
                                        seen_gard_noms.add(j.nom)
                                        b_gard = donnees_m.get("buts", 0)
                                        t_gard = donnees_m.get("tirs", 0)
                                        arrets_val = donnees_m.get("arrets", 0)
                                        subis_val = donnees_m.get("tirs_subis", 0)
                                        lignes_gardiennes.append({
                                            "N°": num_affiche,
                                            L['gardien']: j.nom,
                                            "Poste": j.poste,
                                            "Buts/Tirs": f"{b_gard}/{t_gard}",
                                            "Arrêts": arrets_val,
                                            "Tirs Subis": subis_val,
                                            "% Arrêts": f"{round((arrets_val / subis_val * 100), 1)}%" if subis_val > 0 else "0.0%",
                                            "Buts Encaissés": donnees_m.get("buts_encaisses", 0),
                                            "🟨": donnees_m.get("cartons_jaunes", 0),
                                            "⏱️ 2min": donnees_m.get("exclusions_2min", 0),
                                            "🟥": donnees_m.get("cartons_rouges", 0),
                                        })

                        def _tri_ligne_num(row):
                            try:
                                return int(row.get("N°", 999))
                            except (TypeError, ValueError):
                                return 999

                        lignes_champ = sorted(lignes_champ, key=_tri_ligne_num)
                        lignes_gardiennes = sorted(lignes_gardiennes, key=_tri_ligne_num)

                        score_eq = sum(row.get("Buts", 0) for row in lignes_champ)
                        for row_g in lignes_gardiennes:
                            parts = str(row_g.get("Buts/Tirs", "0/0")).split('/')
                            if parts[0].isdigit():
                                score_eq += int(parts[0])

                        score_adv = sum(row.get("Buts Encaissés", 0) for row in lignes_gardiennes)

                        st.markdown(f"### Résultat du match : {score_eq} - {score_adv}")
                        if journal_actions_archive:
                            b1, e1, b2, e2 = 0, 0, 0, 0
                            for act in journal_actions_archive:
                                est_2mt = act.get("periode") == "2ème MT"
                                t_a = act.get("type_action", "")
                                if t_a == "But" or t_a.startswith("But ("):
                                    if est_2mt:
                                        b2 += 1
                                    else:
                                        b1 += 1
                                elif t_a == "But encaissé":
                                    if est_2mt:
                                        e2 += 1
                                    else:
                                        e1 += 1
                            if (b1 + e1 + b2 + e2) > 0:
                                st.caption(f"Découpage horodaté : **1ère MT : {b1} - {e1}** • **2ème MT : {b2} - {e2}**")

                        if lignes_champ:
                            st.dataframe(pd.DataFrame(lignes_champ), use_container_width=True, hide_index=True)
                        if lignes_gardiennes:
                            st.dataframe(pd.DataFrame(lignes_gardiennes), use_container_width=True, hide_index=True)

                        st.markdown("---")
                        st.markdown("### 🎯 Cartographie des Tirs & Arrêts du Match")

                        zone_filtre_match = st.selectbox(
                            "📍 Filtrer par zone du terrain (Optionnel)",
                            ["Toutes les zones"] + ZONES_TERRAIN_LISTE,
                            key=f"filtre_match_{ctx_prefix}_{match_choisi}"
                        )

                        agregat_tirs_match_arc = {}
                        agregat_gard_match_arc = {}

                        infos_joueuses_total = {}
                        for mgr_obj in dictionnaires_managers.values():
                            for j_obj in mgr_obj.joueuses.values():
                                is_gard = isinstance(j_obj, Gardienne) or "gardien" in j_obj.poste.lower()
                                infos_joueuses_total[j_obj.nom] = {"is_gardienne": is_gard}

                        for act in journal_actions_archive:
                            act_type = act.get("type_action", "")
                            det = act.get("details", "")

                            if "Cage: " in det:
                                try:
                                    z_ter_ext = "Inconnue"
                                    z_cage_ext = ""
                                    if "Terrain: " in det and " | Cage: " in det:
                                        z_ter_ext = det.split("Terrain: ")[1].split(" | Cage: ")[0]
                                        z_cage_ext = det.split("Cage: ")[1].rstrip("]")
                                    else:
                                        z_cage_ext = det.split("[")[-1].rstrip("]")

                                    if zone_filtre_match != "Toutes les zones" and z_ter_ext != zone_filtre_match:
                                        continue

                                    nom_trouve = None
                                    for nom_j in infos_joueuses_total.keys():
                                        if _action_concerne_joueur(act, type("JoueuseRef", (), {"nom": nom_j})()):
                                            nom_trouve = nom_j
                                            break

                                    if nom_trouve:
                                        is_gardienne = infos_joueuses_total[nom_trouve]["is_gardienne"]
                                        cible = agregat_gard_match_arc if is_gardienne else agregat_tirs_match_arc

                                        if z_cage_ext not in cible:
                                            cible[z_cage_ext] = {"succes": 0, "echec": 0}

                                        if not z_cage_ext or z_cage_ext == "Non précisée":
                                            continue

                                        if not is_gardienne:
                                            if act_type in ("But",) or act_type.startswith("But ("):
                                                cible[z_cage_ext]["succes"] += 1
                                            elif act_type in ("Tir raté",) or act_type.startswith("Tir raté ("):
                                                cible[z_cage_ext]["echec"] += 1
                                        else:
                                            if act_type == "Arrêt décisif":
                                                cible[z_cage_ext]["succes"] += 1
                                            elif act_type == "But encaissé":
                                                cible[z_cage_ext]["echec"] += 1
                                except IndexError:
                                    pass

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

                        with st.form(key=f"form_bilan_post_{ctx_prefix}_{match_choisi}"):
                            texte_bilan = st.text_area("Bilan post-match", value=bilan_existant, height=100)
                            if st.form_submit_button("Enregistrer"):
                                bilan_nettoye = texte_bilan.strip()
                                sync_mgr.ajouter_operation(
                                    op_type="bilan_post_match",
                                    equipe_nom=equipe_assignee,
                                    payload={"nom_match": match_choisi, "bilan_post_match": bilan_nettoye},
                                )
                                res_bilan = sync_mgr.synchroniser_tout(_executer_operation_file_attente)
                                if res_bilan.get("failed", 0) == 0:
                                    st.success("Enregistré !")
                                else:
                                    st.warning("Enregistré en file d'attente (synchronisation à réessayer).")
                                st.rerun()

                        st.divider()
                        st.markdown("### 📥 Téléchargements des Rapports")

                        if not a_permission("exports"):
                            st.info("🔒 L'export de rapports (PDF, CSV, JSON) n'est pas activé pour votre profil.")
                        else:
                            pdf_officiel_bytes = generer_pdf_match(
                                nom_match=match_choisi, score_eq=score_eq, score_adv=score_adv,
                                lignes_champ=lignes_champ, lignes_gardiennes=lignes_gardiennes,
                                zones_tirs=agregat_tirs_match_arc, zones_gardiennes=agregat_gard_match_arc,
                                attaques_adversaires=attaques_adv_archive,
                                club_nom=club_nom_session,
                                equipe_nom=equipe_assignee,
                                dossier_club=dossier_club_session,
                                capitaine=st.session_state.get(f"capitaine_match_{ctx_prefix}"),
                                )
                            pdf_chrono_bytes = generer_pdf_chronologique(
                                nom_match=match_choisi, score_eq=score_eq, score_adv=score_adv,
                                historique_actions=journal_actions_archive, attaques_adv=attaques_adv_archive,
                                commentaires_staff=commentaires_staff_archive,
                                club_nom=club_nom_session,
                                equipe_nom=equipe_assignee, bilan_post_match=bilan_existant,
                                dossier_club=dossier_club_session,
                            )

                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                st.download_button(
                                    "📥 Feuille de Match Officielle (PDF)",
                                    data=pdf_officiel_bytes,
                                    file_name=f"feuille_match_{match_choisi}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_pdf_off_{ctx_prefix}_{match_choisi}",
                                )
                            with col_btn2:
                                st.download_button(
                                    "📥 Rapport Chronologique & Tactique (PDF)",
                                    data=pdf_chrono_bytes,
                                    file_name=f"resume_chrono_{match_choisi}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_pdf_chrono_{ctx_prefix}_{match_choisi}",
                                )

                            payload_match = construire_payload_match(
                                nom_match=match_choisi,
                                club_nom=club_nom_session,
                                equipe_nom=equipe_assignee,
                                score_eq=score_eq,
                                score_adv=score_adv,
                                lignes_champ=lignes_champ,
                                lignes_gardiennes=lignes_gardiennes,
                                historique_actions=journal_actions_archive,
                                attaques_adv=attaques_adv_archive,
                                commentaires_staff=commentaires_staff_archive,
                                bilan_post_match=bilan_existant,
                                statut_match="archive",
                            )

                            st.write("")
                            col_exp1, col_exp2 = st.columns(2)
                            with col_exp1:
                                st.download_button(
                                    "📊 Export Événements / Vidéo (CSV)",
                                    data=exporter_evenements_csv(payload_match).encode("utf-8-sig"),
                                    file_name=f"evenements_{match_choisi}.csv",
                                    mime="text/csv",
                                    key=f"dl_csv_ev_{ctx_prefix}_{match_choisi}",
                                )
                            with col_exp2:
                                st.download_button(
                                    "🧩 Export Match Structuré / API (JSON)",
                                    data=exporter_match_json(payload_match).encode("utf-8"),
                                    file_name=f"match_{match_choisi}.json",
                                    mime="application/json",
                                    key=f"dl_json_match_{ctx_prefix}_{match_choisi}",
                                )

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

                    zone_filtre_saison_eq = st.selectbox(
                        "📍 Filtrer par zone du terrain (Optionnel)",
                        ["Toutes les zones"] + ZONES_TERRAIN_LISTE,
                        key=f"filtre_saison_equipe_{ctx_prefix}"
                    )

                    agregat_saison_tirs_eq = {}
                    agregat_saison_gard_eq = {}
                    for j in tous_membres_saison:
                        for m in j.historique_matchs:
                            for act in m.get("journal_actions", []):
                                det = act.get("details", "")
                                act_type = act.get("type_action", "")
                                if _action_concerne_joueur(act, j) and "Cage: " in det:
                                    try:
                                        z_ter_ext = "Inconnue"
                                        z_cage_ext = ""
                                        if "Terrain: " in det and " | Cage: " in det:
                                            z_ter_ext = det.split("Terrain: ")[1].split(" | Cage: ")[0]
                                            z_cage_ext = det.split("Cage: ")[1].rstrip("]")
                                        else:
                                            z_cage_ext = det.split("[")[-1].rstrip("]")

                                        if zone_filtre_saison_eq != "Toutes les zones" and z_ter_ext != zone_filtre_saison_eq:
                                            continue

                                        est_gardienne_val = isinstance(j, Gardienne) or "gardien" in j.poste.lower()
                                        cible = agregat_saison_gard_eq if est_gardienne_val else agregat_saison_tirs_eq

                                        if not z_cage_ext or z_cage_ext == "Non précisée":
                                            continue

                                        if z_cage_ext not in cible:
                                            cible[z_cage_ext] = {"succes": 0, "echec": 0}

                                        if not est_gardienne_val:
                                            if act_type == "But" or act_type.startswith("But ("):
                                                cible[z_cage_ext]["succes"] += 1
                                            elif act_type == "Tir raté" or act_type.startswith("Tir raté ("):
                                                cible[z_cage_ext]["echec"] += 1
                                        else:
                                            if act_type == "Arrêt décisif":
                                                cible[z_cage_ext]["succes"] += 1
                                            elif act_type == "But encaissé":
                                                cible[z_cage_ext]["echec"] += 1
                                    except IndexError:
                                        pass

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
                                    "Duels Off": f"{dog}/{dog + dop}", "Duels Déf": f"{ddg}/{ddg + ddp}",
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
                    membre_choisi = st.selectbox(f"Sélectionner un(e) {L['joueur']}", noms, key=f"select_saison_membre_{ctx_prefix}")
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
                            st.markdown("### 🔋 Suivi Longitudinal Individuel (Charge, Forme & Performance)")

                            suivi_j_list = list(getattr(p, "suivi_longitudinal", []) or [])
                            if not suivi_j_list and p.historique_matchs:
                                for idx_m, m_hist in enumerate(p.historique_matchs, start=1):
                                    suivi_j_list.append({
                                        "date": f"Match {idx_m}",
                                        "type": "Match",
                                        "libelle": m_hist.get("match", f"Match {idx_m}"),
                                        "duree_min": 0,
                                        "rpe": None,
                                        "charge_ua": 0.0,
                                        "forme": None,
                                        "performance_score": calculer_indice_performance_match(
                                            m_hist, est_gardienne=isinstance(p, Gardienne)
                                        ),
                                        "note": "",
                                    })

                            if suivi_j_list:
                                res_ind = resumer_charge_forme_joueur(p)
                                i_c1, i_c2, i_c3, i_c4 = st.columns(4)
                                i_c1.metric("Charge 7j", f"{res_ind['charge_7j']} UA")
                                i_c2.metric("Ratio ACWR", res_ind["acwr"] if res_ind["acwr"] is not None else "-")
                                i_c3.metric("Forme Moyenne", f"{res_ind['forme_moy']} / 5" if res_ind["forme_moy"] is not None else "-")
                                i_c4.metric("Statut", res_ind["statut"])

                                rows_courbes = []
                                rows_table = []
                                for idx_s, s_item in enumerate(suivi_j_list, start=1):
                                    etiquette = f"{s_item.get('date', '')} • {s_item.get('libelle', s_item.get('type', ''))}".strip(" •")
                                    if not etiquette:
                                        etiquette = f"Entrée {idx_s}"
                                    perf_val = s_item.get("performance_score")
                                    if perf_val is None and s_item.get("type") == "Match":
                                        m_corresp = next(
                                            (mh for mh in p.historique_matchs if mh.get("match") == s_item.get("libelle")),
                                            None,
                                        )
                                        if m_corresp:
                                            perf_val = calculer_indice_performance_match(
                                                m_corresp, est_gardienne=isinstance(p, Gardienne)
                                            )

                                    c_ua_val = float(
                                        s_item.get("charge_ua")
                                        or (float(s_item.get("duree_min", 0) or 0) * float(s_item.get("rpe", 0) or 0))
                                    )
                                    forme_val = s_item.get("forme")

                                    rows_courbes.append({
                                        "Événement": etiquette,
                                        "Charge (UA)": c_ua_val,
                                        "Forme (/5)": float(forme_val) if forme_val is not None else None,
                                        "Indice Perf. (/100)": float(perf_val) if perf_val is not None else None,
                                    })
                                    rows_table.append({
                                        "Date": s_item.get("date", ""),
                                        "Type": s_item.get("type", ""),
                                        "Événement": s_item.get("libelle", ""),
                                        "Durée (min)": s_item.get("duree_min", 0),
                                        "RPE": s_item.get("rpe") if s_item.get("rpe") is not None else "-",
                                        "Charge (UA)": c_ua_val,
                                        "Forme (/5)": forme_val if forme_val is not None else "-",
                                        "Indice Perf.": perf_val if perf_val is not None else "-",
                                        "Note": s_item.get("note", ""),
                                    })

                                df_courbes = pd.DataFrame(rows_courbes).set_index("Événement")
                                lc1, lc2 = st.columns(2)
                                with lc1:
                                    st.markdown("**⚡ Charge (UA) & Forme (/5)**")
                                    st.line_chart(df_courbes[[col for col in ["Charge (UA)", "Forme (/5)"] if col in df_courbes.columns]])
                                with lc2:
                                    st.markdown("**🏆 Indice de Performance Match (/100)**")
                                    cols_perf = [c for c in ["Indice Perf. (/100)"] if c in df_courbes.columns and df_courbes[c].notna().any()]
                                    if cols_perf:
                                        st.line_chart(df_courbes[cols_perf])
                                    else:
                                        st.caption("Aucun indice de performance match disponible sur cette sélection.")

                                st.dataframe(pd.DataFrame(rows_table), use_container_width=True, hide_index=True)
                            else:
                                st.info("Aucune donnée longitudinale enregistrée pour ce profil pour le moment.")

                            st.divider()

                            zone_filtre_saison_j = st.selectbox(
                                "📍 Filtrer par zone du terrain (Optionnel)",
                                ["Toutes les zones"] + ZONES_TERRAIN_LISTE,
                                key=f"filtre_saison_j_{ctx_prefix}_{p.nom}"
                            )

                            zones_saison_joueuse = {}
                            for m in p.historique_matchs:
                                for act in m.get("journal_actions", []):
                                    det = act.get("details", "")
                                    act_type = act.get("type_action", "")
                                    if _action_concerne_joueur(act, p) and "Cage: " in det:
                                        try:
                                            z_ter_ext = "Inconnue"
                                            z_cage_ext = ""
                                            if "Terrain: " in det and " | Cage: " in det:
                                                z_ter_ext = det.split("Terrain: ")[1].split(" | Cage: ")[0]
                                                z_cage_ext = det.split("Cage: ")[1].rstrip("]")
                                            else:
                                                z_cage_ext = det.split("[")[-1].rstrip("]")

                                            if zone_filtre_saison_j != "Toutes les zones" and z_ter_ext != zone_filtre_saison_j:
                                                continue

                                            if z_cage_ext not in zones_saison_joueuse:
                                                zones_saison_joueuse[z_cage_ext] = {"succes": 0, "echec": 0}

                                            if not z_cage_ext or z_cage_ext == "Non précisée":
                                                continue

                                            est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                                            if not est_gardienne_val:
                                                if act_type == "But":
                                                    zones_saison_joueuse[z_cage_ext]["succes"] += 1
                                                elif act_type == "Tir raté":
                                                    zones_saison_joueuse[z_cage_ext]["echec"] += 1
                                            else:
                                                if act_type == "Arrêt décisif":
                                                    zones_saison_joueuse[z_cage_ext]["succes"] += 1
                                                elif act_type == "But encaissé":
                                                    zones_saison_joueuse[z_cage_ext]["echec"] += 1
                                        except IndexError:
                                            pass

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
                            match_selectionne_j = st.selectbox("Filtrer par rencontre", noms_matchs_joueuse, key=f"sel_match_j_{ctx_prefix}_{p.nom}")

                            zone_filtre_match_j = st.selectbox(
                                "📍 Filtrer par zone du terrain (Optionnel)",
                                ["Toutes les zones"] + ZONES_TERRAIN_LISTE,
                                key=f"filtre_match_spec_j_{ctx_prefix}_{p.nom}_{match_selectionne_j}"
                            )

                            match_donnees_specifiques = next((m for m in p.historique_matchs if m["match"] == match_selectionne_j), None)
                            zones_match_specifique = {}

                            if match_donnees_specifiques:
                                for act in match_donnees_specifiques.get("journal_actions", []):
                                    det = act.get("details", "")
                                    act_type = act.get("type_action", "")
                                    if _action_concerne_joueur(act, p) and "Cage: " in det:
                                        try:
                                            z_ter_ext = "Inconnue"
                                            z_cage_ext = ""
                                            if "Terrain: " in det and " | Cage: " in det:
                                                z_ter_ext = det.split("Terrain: ")[1].split(" | Cage: ")[0]
                                                z_cage_ext = det.split("Cage: ")[1].rstrip("]")
                                            else:
                                                z_cage_ext = det.split("[")[-1].rstrip("]")

                                            if zone_filtre_match_j != "Toutes les zones" and z_ter_ext != zone_filtre_match_j:
                                                continue

                                            if not z_cage_ext or z_cage_ext == "Non précisée":
                                                continue

                                            if z_cage_ext not in zones_match_specifique:
                                                zones_match_specifique[z_cage_ext] = {"succes": 0, "echec": 0}

                                            est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                                            if not est_gardienne_val:
                                                if act_type == "But" or act_type.startswith("But ("):
                                                    zones_match_specifique[z_cage_ext]["succes"] += 1
                                                elif act_type == "Tir raté" or act_type.startswith("Tir raté ("):
                                                    zones_match_specifique[z_cage_ext]["echec"] += 1
                                            else:
                                                if act_type == "Arrêt décisif":
                                                    zones_match_specifique[z_cage_ext]["succes"] += 1
                                                elif act_type == "But encaissé":
                                                    zones_match_specifique[z_cage_ext]["echec"] += 1
                                        except IndexError:
                                            pass

                            titre_cage_match_j = (
                                f"Détail du match '{match_selectionne_j}' — {p.nom} (✅ Arrêts | ❌ Encaissés)"
                                if isinstance(p, Gardienne)
                                else f"Détail du match '{match_selectionne_j}' — {p.nom} (✅ Buts | ❌ Ratés)"
                            )
                            est_gardienne_val = isinstance(p, Gardienne) or "gardien" in p.poste.lower()
                            afficher_cage_recapitulative(zones_match_specifique, titre=titre_cage_match_j, inclure_hors_cadre=not est_gardienne_val)
                else:
                    st.info("Aucun profil disponible.")

            # --- SOUS-ONGLET 4 : CHARGE, FORME & VIGILANCE ---
            with sub_tab_charge:
                st.subheader("🔋 Suivi Longitudinal — Charge Interne (sRPE), ACWR & Forme")
                st.caption("Charge sRPE = Durée (min) × RPE (1–10) • Ratio ACWR = Charge 7j / Moyenne hebdo 28j • Forme de 1 à 5.")

                resume_lignes = []
                for j_item in tous_membres_saison:
                    res_j = resumer_charge_forme_joueur(j_item)
                    resume_lignes.append({
                        "N°": j_item.numero,
                        L["joueur"].capitalize(): j_item.nom,
                        "Poste": j_item.poste,
                        "Statut": res_j["statut"],
                        "Charge 7j (UA)": res_j["charge_7j"],
                        "Moy. 28j (UA)": res_j["moy_hebdo_28j"],
                        "ACWR": res_j["acwr"] if res_j["acwr"] is not None else "-",
                        "Forme Moy. (/5)": res_j["forme_moy"] if res_j["forme_moy"] is not None else "-",
                        "Dernier RPE": res_j["dernier_rpe"] if res_j["dernier_rpe"] is not None else "-",
                    })

                if resume_lignes:
                    st.dataframe(pd.DataFrame(resume_lignes), use_container_width=True, hide_index=True)

                st.divider()
                peut_saisir_suivi = a_permission("saisie_match") or a_permission("gerer_effectif")
                if not peut_saisir_suivi:
                    st.info("🔒 Saisie de séance / forme réservée aux profils habilités (lecture seule).")
                else:
                    st.markdown("### ➕ Saisie Rapide Séance / Bilan Forme (Effectif)")
                    c_ev1, c_ev2, c_ev3 = st.columns([1.4, 1.6, 2])
                    with c_ev1:
                        date_seance = st.date_input("Date", value=date.today(), key=f"date_suivi_long_{ctx_prefix}")
                    with c_ev2:
                        type_seance = st.selectbox(
                            "Type d'événement",
                            ["Séance Collective", "Prépa Physique", "Bilan Forme / Wellness", "Stage / Match Amical"],
                            key=f"type_suivi_long_{ctx_prefix}",
                        )
                    with c_ev3:
                        libelle_seance = st.text_input(
                            "Libellé / Contenu",
                            value=type_seance,
                            key=f"libelle_suivi_long_{ctx_prefix}",
                        )

                    lignes_saisie_init = [
                        {
                            "Présent": True,
                            "Nom": j_item.nom,
                            "Poste": j_item.poste,
                            "Durée (min)": 0 if type_seance == "Bilan Forme / Wellness" else 75,
                            "RPE (1-10)": 0.0 if type_seance == "Bilan Forme / Wellness" else 6.0,
                            "Forme (1-5)": 3.5,
                            "Note": "",
                        }
                        for j_item in tous_membres_saison
                    ]

                    df_saisie_edit = st.data_editor(
                        pd.DataFrame(lignes_saisie_init),
                        column_config={
                            "Présent": st.column_config.CheckboxColumn(default=True),
                            "Nom": st.column_config.TextColumn(disabled=True),
                            "Poste": st.column_config.TextColumn(disabled=True),
                            "Durée (min)": st.column_config.NumberColumn(min_value=0, max_value=300, step=5),
                            "RPE (1-10)": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, step=0.5),
                            "Forme (1-5)": st.column_config.NumberColumn(min_value=1.0, max_value=5.0, step=0.5),
                            "Note": st.column_config.TextColumn(),
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"editor_suivi_longitudinal_{ctx_prefix}",
                    )

                    if st.button("💾 Enregistrer le suivi du groupe", type="primary", key=f"btn_save_suivi_long_{ctx_prefix}"):
                        nb_enregistres = 0
                        for _, r_s in df_saisie_edit.iterrows():
                            if r_s.get("Présent"):
                                ok = manager.ajouter_entree_longitudinale(
                                    nom_joueur=r_s.get("Nom"),
                                    date_str=date_seance.isoformat(),
                                    type_entree=type_seance,
                                    duree_min=r_s.get("Durée (min)", 0),
                                    rpe=r_s.get("RPE (1-10)", 0.0),
                                    forme=r_s.get("Forme (1-5)", 3.0),
                                    libelle=libelle_seance,
                                    performance_score=None,
                                    note=r_s.get("Note", ""),
                                )
                                if ok:
                                    nb_enregistres += 1
                        st.success(f"Suivi enregistré pour {nb_enregistres} {L['joueur']}(s).")
                        st.rerun()

            # --- SOUS-ONGLET 5 : RAPPORT DE SCOUTING ---
            with sub_tab_scouting:
                joueuses_par_eq_scout = {equipe_assignee: manager.joueuses}
                for eq_autre in _get_equipes_du_club_courant():
                    if eq_autre != equipe_assignee:
                        mgr_autre = EquipeManager(fichier=get_nom_fichier_equipe(eq_autre), club_slug=club_slug_session)
                        joueuses_par_eq_scout[eq_autre] = mgr_autre.joueuses

                afficher_onglet_scouting_adversaire(
                    joueuses_par_equipe=joueuses_par_eq_scout,
                    club_nom=club_nom_session,
                    equipe_nom=equipe_assignee,
                    ctx_prefix=ctx_prefix,
                    dossier_club=dossier_club_session,
                    peut_exporter=a_permission("exports"),
                )

    # ==========================================
    # 4. ÉCRAN : GESTION DE L'EFFECTIF
    # ==========================================
    elif st.session_state[page_key] == "effectif":
        if st.button("⬅️ Retour à l'accueil", key=f"btn_retour_effectif_{ctx_prefix}"):
            aller_a("accueil")

        st.header(f"👥 Gestion de l'Effectif ({L['joueurs'].capitalize()}) — {equipe_assignee}")
        peut_gerer_effectif = a_permission("gerer_effectif")
        if not peut_gerer_effectif:
            st.info("🔒 Consultation de l'effectif en lecture seule pour votre profil.")

        if manager.joueuses:
            club_equipes = _get_equipes_du_club_courant()
            autres_equipes_club = [eq for eq in club_equipes if eq != equipe_assignee]

            for nom, joueuse in list(manager.joueuses.items()):
                with st.container(border=True):
                    if peut_gerer_effectif:
                        col_info1, col_info2, col_info3, col_mod, col_transfert, col_suppr = st.columns([2, 1.2, 1, 1.2, 2, 0.8])
                    else:
                        col_info1, col_info2, col_info3 = st.columns([2.5, 1.5, 1])

                    col_info1.write(f"**{nom}**")
                    col_info2.write(f"Poste : {joueuse.poste}")
                    col_info3.write(f"N° {joueuse.numero}")

                    if peut_gerer_effectif:
                        with col_mod:
                            with st.popover("✏️ Modifier"):
                                st.markdown(f"**Modifier le profil de {nom}**")
                                with st.form(key=f"form_modif_joueuse_{ctx_prefix}_{nom}"):
                                    nouveau_nom = st.text_input("Nom / Prénom", value=joueuse.nom)

                                    index_poste_actuel = L["postes_possibles"].index(joueuse.poste) if joueuse.poste in L["postes_possibles"] else 0
                                    nouveau_poste = st.selectbox("Poste", L["postes_possibles"], index=index_poste_actuel)

                                    nouveau_numero = st.number_input("Numéro de maillot", min_value=1, max_value=99, value=int(joueuse.numero))

                                    if st.form_submit_button("Enregistrer les modifications", type="primary", use_container_width=True):
                                        if not nouveau_nom.strip():
                                            st.error("Le nom ne peut pas être vide.")
                                        elif nouveau_nom != nom and nouveau_nom in manager.joueuses:
                                            st.error(f"Un(e) {L['joueur']} portant le nom '{nouveau_nom}' existe déjà.")
                                        else:
                                            joueuse.nom = nouveau_nom.strip()
                                            joueuse.poste = nouveau_poste
                                            joueuse.numero = nouveau_numero

                                            if joueuse.nom != nom:
                                                manager.joueuses[joueuse.nom] = joueuse
                                                del manager.joueuses[nom]

                                            manager.sauvegarder_donnees()
                                            st.success("Profil mis à jour avec succès !")
                                            st.rerun()

                        with col_transfert:
                            if autres_equipes_club:
                                with st.popover("🔄 Transférer"):
                                    st.write(f"Transférer **{nom}** vers :")
                                    equipe_destination = st.selectbox(
                                        "Équipe cible",
                                        autres_equipes_club,
                                        key=f"sel_dest_{ctx_prefix}_{nom}"
                                    )
                                    if st.button("Confirmer le transfert", key=f"btn_conf_trans_{ctx_prefix}_{nom}", type="primary"):
                                        nom_fichier_cible = get_nom_fichier_equipe(equipe_destination)
                                        manager_cible = EquipeManager(fichier=nom_fichier_cible, club_slug=club_slug_session)

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
                            if st.button("🗑️", key=f"del_{ctx_prefix}_{nom}"):
                                manager.supprimer_joueuse(nom)
                                st.rerun()
        else:
            st.info(f"Aucun(e) {L['joueur']} enregistré(e).")

        if peut_gerer_effectif:
            st.divider()
            with st.form(key=f"form_ajout_joueuse_{ctx_prefix}"):
                st.markdown(f"##### ➕ Ajouter un(e) nouveau/nouvelle {L['joueur']} à l'effectif")
                nom_input = st.text_input(f"Nom / Prénom du/de la {L['joueur']}")
                poste_input = st.selectbox("Poste", L["postes_possibles"])
                numero_input = st.number_input("Numéro de maillot", min_value=1, max_value=99, value=10)
                if st.form_submit_button("Ajouter à l'effectif"):
                    if nom_input.strip():
                        type_j = "gardienne" if "Gardien" in poste_input else "champ"
                        manager.ajouter_joueuse(nom=nom_input.strip(), poste=poste_input, numero=numero_input, type_joueuse=type_j)
                        st.rerun()