import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import streamlit as st
import copy
import time

from hand_manager import supprimer_dossier_club
from supabase_store import (
    SCOPE_PLATEFORME,
    StockageIndisponible,
    delete_json,
    dump_scope,
    importer_dossier_club,
    list_keys,
    set_json,
    _secret as secret_ou_env,
)
from theme import barre_laterale, html_bandeau_marque, injecter_theme_connexion

PERMISSIONS_DEFAUT_PAR_ROLE = {
    "super_admin": {
        "saisie_match": True,
        "gerer_effectif": True,
        "supprimer_archive": True,
        "exports": True,
    },
    "manager": {
        "saisie_match": True,
        "gerer_effectif": True,
        "supprimer_archive": True,
        "exports": True,
    },
    "staff": {
        "saisie_match": True,
        "gerer_effectif": True,
        "supprimer_archive": False,
        "exports": True,
    },
    "analyste": {
        "saisie_match": False,
        "gerer_effectif": False,
        "supprimer_archive": False,
        "exports": True,
    },
}

LIBELLES_PERMISSIONS = {
    "saisie_match": "Saisie & clôture de match en direct",
    "gerer_effectif": "Gestion & transfert de l'effectif",
    "supprimer_archive": "Suppression de matchs archivés",
    "exports": "Exports (PDF, CSV, JSON)",
}


def hasher_mot_de_passe(mot_de_passe: str) -> str:
    sel = secrets.token_hex(16)
    derive = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel.encode("utf-8"), 120_000).hex()
    return f"pbkdf2${sel}${derive}"


def verifier_mot_de_passe(mot_de_passe_saisi: str, mot_de_passe_stocke: str) -> tuple[bool, bool]:
    """Retourne (est_valide, doit_etre_migre)."""
    if not isinstance(mot_de_passe_stocke, str) or not mot_de_passe_stocke:
        return False, False
    if mot_de_passe_stocke.startswith("pbkdf2$"):
        parts = mot_de_passe_stocke.split("$", 2)
        if len(parts) != 3:
            return False, False
        _, sel, hash_attendu = parts
        calcul = hashlib.pbkdf2_hmac(
            "sha256", mot_de_passe_saisi.encode("utf-8"), sel.encode("utf-8"), 120_000
        ).hex()
        return hmac.compare_digest(calcul, hash_attendu), False
    # Compatibilité rétroactive avec mots de passe en clair existants
    valide = hmac.compare_digest(mot_de_passe_saisi, mot_de_passe_stocke)
    return valide, valide


def obtenir_permissions_utilisateur(user_info: dict) -> dict:
    role = user_info.get("role", "staff")
    base = dict(PERMISSIONS_DEFAUT_PAR_ROLE.get(role, PERMISSIONS_DEFAUT_PAR_ROLE["staff"]))
    custom = user_info.get("permissions")
    if isinstance(custom, dict):
        for cle, val in custom.items():
            if cle in base:
                base[cle] = bool(val)
    return base


def a_permission(permission_key: str) -> bool:
    session = st.session_state.get("user_session", {})
    if not session.get("logged_in"):
        return False
    role = session.get("role")
    if role in ("super_admin", "manager"):
        return True
    perms = session.get("permissions") or {}
    return bool(perms.get(permission_key, False))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(BASE_DIR, "clubs_registry.json")


def slugify_club(nom_club: str) -> str:
    """Convertit un nom de club en identifiant dossier propre (ex: 'Bordeaux Étudiants Club' -> 'bordeaux_etudiants_club')."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", nom_club.strip().lower()).strip("_")
    return slug or "club_default"


def _lignes_depuis_registre(registre: dict) -> dict:
    """Registre {clubs, users} -> lignes {clé: valeur} (une ligne par club / par compte)."""
    lignes = {}
    for nom, info in (registre.get("clubs") or {}).items():
        lignes[f"club:{nom}"] = info
    for login, info in (registre.get("users") or {}).items():
        lignes[f"user:{login}"] = info
    return lignes


def _registre_depuis_lignes(lignes: dict) -> dict:
    reg = {"clubs": {}, "users": {}}
    for cle, val in lignes.items():
        if cle.startswith("club:"):
            reg["clubs"][cle[5:]] = val
        elif cle.startswith("user:"):
            reg["users"][cle[5:]] = val
    return reg


def _enregistrer_lignes(lignes: dict) -> None:
    for cle, val in lignes.items():
        set_json(SCOPE_PLATEFORME, cle, val)


def _registre_initial() -> dict:
    """Premier démarrage sur une base vide.
    1) si un ancien clubs_registry.json existe (dépôt GitHub / poste local), on l'importe avec les données des clubs ;
    2) sinon on crée uniquement le super admin, à partir des secrets SUPER_ADMIN_USER / SUPER_ADMIN_PASSWORD."""
    from hand_manager import DATA_ROOT

    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                ancien = json.load(f)
            if isinstance(ancien, dict) and ancien.get("users"):
                for nom, info in (ancien.get("clubs") or {}).items():
                    slug = info.get("slug") or slugify_club(nom)
                    importer_dossier_club(slug, os.path.join(DATA_ROOT, "clubs", slug))
                _enregistrer_lignes(_lignes_depuis_registre(ancien))
                return ancien
        except Exception:
            pass

    login = (secret_ou_env("SUPER_ADMIN_USER") or "super_admin").strip().lower()
    mdp = secret_ou_env("SUPER_ADMIN_PASSWORD")
    if not mdp:
        raise StockageIndisponible(
            "Base vide : définissez SUPER_ADMIN_PASSWORD (et éventuellement SUPER_ADMIN_USER) dans les secrets "
            "pour créer le compte super admin."
        )
    reg = {
        "clubs": {},
        "users": {
            login: {
                "password": hasher_mot_de_passe(mdp),
                "role": "super_admin",
                "nom": "Super Admin Plateforme",
                "club": None,
                "equipes": [],
                "permissions": dict(PERMISSIONS_DEFAUT_PAR_ROLE["super_admin"]),
            }
        },
    }
    _enregistrer_lignes(_lignes_depuis_registre(reg))
    return reg


def sauvegarder_registre(registre: dict, remplacer: bool = False):
    """Enregistre uniquement ce que CETTE session a modifié (comparaison avec l'état chargé),
    afin de ne pas écraser les modifications faites au même moment par d'autres utilisateurs.
    remplacer=True : remplace tout le registre (restauration de sauvegarde)."""
    nouvelles = _lignes_depuis_registre(registre)
    snap = st.session_state.get("_registre_snap")
    for cle, val in nouvelles.items():
        if remplacer or snap is None or snap.get(cle) != val:
            set_json(SCOPE_PLATEFORME, cle, val)
    if remplacer:
        a_supprimer = [c for c in list_keys(SCOPE_PLATEFORME) if c not in nouvelles]
    else:
        a_supprimer = [c for c in (snap or {}) if c not in nouvelles]
    for cle in a_supprimer:
        delete_json(SCOPE_PLATEFORME, cle)
    st.session_state["_registre_snap"] = copy.deepcopy(nouvelles)


def charger_registre() -> dict:
    lignes = dump_scope(SCOPE_PLATEFORME)
    if lignes:
        reg = _registre_depuis_lignes(lignes)
    else:
        reg = _registre_initial()
        lignes = _lignes_depuis_registre(reg)
    st.session_state["_registre_snap"] = copy.deepcopy(_lignes_depuis_registre(reg))
    st.session_state["_registre_charge_a"] = time.time()
    return reg


def _session_vide() -> dict:
    return {
        "logged_in": False,
        "username": None,
        "role": None,
        "nom": "",
        "club": None,
        "club_slug": None,
        "equipes": [],
        "equipe_active": None,
        "permissions": {},
    }


def init_users_db():
    """Charge le registre (clubs + utilisateurs) depuis Supabase (rafraîchi toutes les 45 s) et initialise la session."""
    try:
        recent = time.time() - st.session_state.get("_registre_charge_a", 0) < 45
        if "registre_app" not in st.session_state or not recent:
            st.session_state.registre_app = charger_registre()
    except StockageIndisponible as exc:
        st.error(f"Configuration manquante : {exc}")
        st.stop()
    except Exception as exc:
        st.error("Base de données momentanément indisponible. Réessayez dans quelques secondes.")
        st.caption(f"Détail technique : {exc}")
        st.stop()

    # Compatibilité ascendante avec les références existantes à users_db / club_equipes
    st.session_state.users_db = st.session_state.registre_app["users"]

    if "user_session" not in st.session_state:
        st.session_state.user_session = _session_vide()

    club_sess = st.session_state.user_session.get("club")
    if club_sess and club_sess in st.session_state.registre_app["clubs"]:
        st.session_state.club_equipes = st.session_state.registre_app["clubs"][club_sess].get("equipes", [])
    elif "club_equipes" not in st.session_state:
        st.session_state.club_equipes = []


def ecran_connexion():
    """Écran de login avec contrôle du statut actif/suspendu du club."""
    init_users_db()
    injecter_theme_connexion()
    st.markdown(
        '<div class="hs-login-brand">'
        '<div class="hs-login-name">HandStats Pro</div>'
        '<div class="hs-login-tag">Statistiques de match et analyse tactique pour les staffs de handball.</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        st.markdown('<div class="hs-form-title">Connexion à votre espace</div>', unsafe_allow_html=True)
        username = st.text_input("Identifiant").strip().lower()
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter", type="primary", use_container_width=True)

        if submit:
            reg = st.session_state.registre_app
            users = reg["users"]
            clubs = reg["clubs"]

            matched_username = next((k for k in users.keys() if k.strip().lower() == username), None)
            mot_de_passe_db = users[matched_username].get("password", "") if matched_username else ""
            mdp_valide, doit_migrer = verifier_mot_de_passe(password, mot_de_passe_db) if matched_username else (False, False)

            if matched_username and mdp_valide:
                username = matched_username
                user_info = users[username]
                if doit_migrer:
                    user_info["password"] = hasher_mot_de_passe(password)
                    sauvegarder_registre(reg)

                role = user_info["role"]
                club_nom = user_info.get("club")

                if role != "super_admin":
                    if not club_nom or club_nom not in clubs:
                        st.error("Aucun club valide n'est associé à ce compte.")
                        return
                    if not clubs[club_nom].get("actif", True):
                        st.error(f"L'accès pour le club **{club_nom}** est actuellement suspendu. Contactez le Super Admin.")
                        return

                equipes_liste = user_info.get("equipes", [])
                if role in ("staff", "analyste") and club_nom in clubs:
                    equipes_club = clubs[club_nom].get("equipes", [])
                    equipes_liste = [eq for eq in equipes_liste if eq in equipes_club]

                perms_effectives = obtenir_permissions_utilisateur(user_info)

                st.session_state.user_session = {
                    "logged_in": True,
                    "username": username,
                    "role": role,
                    "nom": user_info["nom"],
                    "club": club_nom,
                    "club_slug": slugify_club(club_nom) if club_nom else None,
                    "equipes": equipes_liste,
                    "equipe_active": equipes_liste[0] if (role in ("staff", "analyste") and len(equipes_liste) == 1) else None,
                    "permissions": perms_effectives,
                }

                if club_nom in clubs:
                    st.session_state.club_equipes = clubs[club_nom].get("equipes", [])

                st.success(f"Bienvenue, {user_info['nom']} !")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")



def afficher_en_tete_avec_profil(titre_principal, sous_titre=None, bouton_parametres=False):
    """Bandeau de marque (logo, titre, sous-titre) + Paramètres (optionnel) + menu profil.
    Retourne True si le bouton Paramètres a été cliqué."""
    session = st.session_state.user_session
    ouvrir_parametres = False

    if bouton_parametres:
        col_title, col_params, col_profil = st.columns([4.2, 1.2, 1.8], vertical_alignment="center")
    else:
        col_title, col_profil = st.columns([5.4, 1.8], vertical_alignment="center")
        col_params = None

    with col_title:
        st.markdown(
            html_bandeau_marque(titre_principal, sous_titre, session.get("club"), session.get("club_slug")),
            unsafe_allow_html=True,
        )

    if col_params is not None:
        with col_params:
            ouvrir_parametres = st.button("Paramètres", key="hs_btn_parametres", use_container_width=True)

    with col_profil:
        with st.popover(session["nom"], use_container_width=True):
            role_labels = {
                "super_admin": "Super Admin Plateforme",
                "manager": "Club Manager",
                "staff": "Staff / Entraîneur",
                "analyste": "Analyste",
            }
            st.markdown("### Mon profil")
            st.markdown(f"**Nom / Prénom :** {session['nom']}")
            st.markdown(f"**Rôle :** {role_labels.get(session['role'], session['role'])}")
            if session.get("club"):
                st.markdown(f"**Club :** `{session['club']}`")

            if session["role"] in ("staff", "analyste"):
                st.markdown(f"**Équipe active :** `{session.get('equipe_active', 'Aucune')}`")
                st.markdown(f"**Équipes gérées :** `{', '.join(session.get('equipes', []))}`")

                equipes_gerees = session.get("equipes", [])
                if len(equipes_gerees) > 1:
                    st.markdown("---")
                    st.markdown("#### Changer d'équipe active")
                    equipe_actuelle = session.get("equipe_active")
                    nouvelle_equipe = st.selectbox(
                        "Basculer vers :",
                        equipes_gerees,
                        index=equipes_gerees.index(equipe_actuelle) if equipe_actuelle in equipes_gerees else 0,
                        key="popover_switch_equipe",
                    )
                    if nouvelle_equipe != equipe_actuelle:
                        if st.button("Confirmer le changement", type="primary", use_container_width=True):
                            st.session_state.user_session["equipe_active"] = nouvelle_equipe
                            st.rerun()

            elif session["role"] == "manager":
                nb_eq = len(st.session_state.get("club_equipes", []))
                st.markdown(f"**Équipes enregistrées au club :** `{nb_eq}`")

            st.markdown("---")
            if st.button("Se déconnecter", type="primary", use_container_width=True):
                st.session_state.user_session = _session_vide()
                st.rerun()

    return ouvrir_parametres


def afficher_espace_super_admin():
    """Console d'administration globale : droits des clubs, accès et comptes."""
    reg = st.session_state.registre_app
    clubs = reg["clubs"]
    users = reg["users"]

    nav_sa_key = "page_super_admin"
    if nav_sa_key not in st.session_state:
        st.session_state[nav_sa_key] = "clubs"

    page_sa = barre_laterale(
        pages=[
            ("clubs", "Clubs & droits d'accès"),
            ("comptes", "Comptes & rôles"),
            ("parametres", "Paramètres"),
        ],
        page_active=st.session_state[nav_sa_key],
        equipe="Administration plateforme",
        club="HandStats Pro",
    )
    if page_sa and page_sa != st.session_state[nav_sa_key]:
        st.session_state[nav_sa_key] = page_sa
        st.rerun()

    page_active_sa = st.session_state[nav_sa_key]

    afficher_en_tete_avec_profil("Console plateforme", sous_titre="Clubs, accès et comptes")

    st.info("Gérez ici les clubs autorisés, l'activation/suspension de leurs accès et les comptes utilisateurs.")

    # --- VUE 1 : CLUBS ---
    if page_active_sa == "clubs":
        st.subheader("➕ Créer un nouveau club")
        with st.form("form_super_admin_create_club"):
            c1, c2 = st.columns(2)
            with c1:
                nom_nouveau_club = st.text_input("Nom officiel du club (ex: HBC Mérignac)")
                actif_initial = st.checkbox("Activer l'accès immédiatement", value=True)
            with c2:
                equipes_csv = st.text_input(
                    "Équipes initiales (séparées par des virgules)",
                    value="Séniors M, Séniors F, -18M, -15F",
                )
            if st.form_submit_button("Créer le club", type="primary"):
                nom_clean = nom_nouveau_club.strip()
                if not nom_clean:
                    st.error("Le nom du club est obligatoire.")
                elif nom_clean in clubs:
                    st.error("Ce club existe déjà.")
                else:
                    eq_list = [e.strip() for e in equipes_csv.split(",") if e.strip()]
                    clubs[nom_clean] = {
                        "slug": slugify_club(nom_clean),
                        "actif": actif_initial,
                        "equipes": eq_list,
                    }
                    sauvegarder_registre(reg)
                    st.success(f"Club '{nom_clean}' créé avec succès.")
                    st.rerun()

        st.markdown("---")
        st.subheader("📋 Clubs enregistrés & État des droits")
        for nom_c, info_c in list(clubs.items()):
            slug_c = info_c.get("slug", slugify_club(nom_c))
            with st.container(border=True):
                col_a, col_b, col_c = st.columns([2.5, 2, 1.5])
                statut_badge = "🟢 Actif" if info_c.get("actif", True) else "🔴 Suspendu"
                col_a.markdown(f"**{nom_c}** (`{slug_c}`)")
                col_a.caption(f"Statut : {statut_badge}")
                col_b.caption(f"Équipes : {', '.join(info_c.get('equipes', [])) or 'Aucune'}")

                with col_c:
                    est_actif = info_c.get("actif", True)
                    label_toggle = "⏸️ Suspendre l'accès" if est_actif else "▶️ Réactiver l'accès"
                    if st.button(label_toggle, key=f"toggle_club_{nom_c}", use_container_width=True):
                        info_c["actif"] = not est_actif
                        sauvegarder_registre(reg)
                        st.rerun()

                with st.expander(f"Modifier les équipes de {nom_c}"):
                    nouvelles_eq_str = st.text_input(
                        "Liste des équipes (séparées par des virgules)",
                        value=", ".join(info_c.get("equipes", [])),
                        key=f"eq_input_{nom_c}",
                    )
                    if st.button("Enregistrer les équipes", key=f"save_eq_{nom_c}"):
                        info_c["equipes"] = [e.strip() for e in nouvelles_eq_str.split(",") if e.strip()]
                        sauvegarder_registre(reg)
                        st.success("Équipes mises à jour.")
                        st.rerun()

                with st.expander(f"🗑️ Supprimer définitivement {nom_c}"):
                    comptes_lies = [
                        _uname for _uname, _udata in users.items()
                        if _udata.get("club") == nom_c
                        and _udata.get("role") != "super_admin"
                        and _uname != st.session_state.user_session.get("username")
                    ]
                    st.warning(
                        f"Cette action supprime définitivement **{nom_c}** du registre, "
                        f"efface son dossier de données (`{slug_c}` : effectifs, matchs, brouillons et file de synchro) "
                        f"et supprime les comptes rattachés ({', '.join(comptes_lies) if comptes_lies else 'aucun'})."
                    )
                    confirmer_suppr = st.checkbox(
                        f"Je confirme la suppression complète de '{nom_c}' et de ses comptes",
                        key=f"confirm_del_club_{nom_c}",
                    )
                    if st.button(
                        "🗑️ Supprimer définitivement le club",
                        type="primary",
                        disabled=not confirmer_suppr,
                        key=f"btn_del_club_{nom_c}",
                    ):
                        # 1. Supprimer les comptes rattachés au club (hors super_admin et session courante)
                        for _uname in comptes_lies:
                            del users[_uname]

                        # 2. Retirer le club du registre
                        del clubs[nom_c]

                        # 3. Supprimer les données disque du club
                        supprimer_dossier_club(slug_c)

                        # 4. Nettoyer la session si besoin
                        if st.session_state.get("club_equipes") and st.session_state.user_session.get("club") == nom_c:
                            st.session_state.club_equipes = []

                        sauvegarder_registre(reg)
                        st.success(
                            f"Le club '{nom_c}', ses données et {len(comptes_lies)} compte(s) rattaché(s) ont été supprimés."
                        )
                        st.rerun()

    # --- VUE 2 : COMPTES ---
    elif page_active_sa == "comptes":
        st.subheader("➕ Créer un compte utilisateur")
        liste_clubs = list(clubs.keys())

        with st.form("form_super_admin_create_user"):
            u1, u2, u3 = st.columns(3)
            with u1:
                u_login = st.text_input("Identifiant").strip().lower()
                u_pass = st.text_input("Mot de passe", type="password")
            with u2:
                u_nom = st.text_input("Nom complet")
                u_role = st.selectbox("Rôle", ["manager", "staff", "super_admin"])
            with u3:
                u_club = st.selectbox("Club rattaché", liste_clubs) if liste_clubs else None
                eq_du_club = clubs[u_club]["equipes"] if (u_club and u_club in clubs) else []
                u_equipes = st.multiselect("Équipes autorisées (si role = staff)", eq_du_club)

            if st.form_submit_button("Créer le compte", type="primary"):
                identifiants_existants = {k.strip().lower() for k in users.keys()}
                if not u_login or not u_pass or not u_nom.strip():
                    st.error("Identifiant, mot de passe et nom sont obligatoires.")
                elif " " in u_login:
                    st.error("L'identifiant ne peut pas contenir d'espaces.")
                elif u_login in identifiants_existants:
                    st.error("Désolé, cet identifiant est déjà attribué à un autre compte.")
                elif u_role != "super_admin" and not u_club:
                    st.error("Un compte manager ou staff doit être rattaché à un club.")
                else:
                    users[u_login] = {
                        "password": hasher_mot_de_passe(u_pass),
                        "role": u_role,
                        "nom": u_nom.strip(),
                        "club": None if u_role == "super_admin" else u_club,
                        "equipes": u_equipes if u_role == "staff" else [],
                    }
                    sauvegarder_registre(reg)
                    st.success(f"Compte '{u_login}' créé.")
                    st.rerun()

        st.markdown("---")
        st.subheader("📋 Comptes existants")
        for uname, udata in list(users.items()):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1.5, 2.5, 1])
                c1.markdown(f"**{udata.get('nom', uname)}** (`{uname}`)")
                c2.write(f"Rôle : `{udata.get('role')}`")
                c3.write(
                    f"Club : `{udata.get('club') or 'Plateforme'}` | "
                    f"Équipes : `{', '.join(udata.get('equipes', [])) or '-'}`"
                )
                with c4:
                    if uname != st.session_state.user_session.get("username"):
                        if st.button("🗑️", key=f"del_user_{uname}", help="Supprimer ce compte"):
                            del users[uname]
                            sauvegarder_registre(reg)
                            st.rerun()

    # --- VUE 3 : PARAMÈTRES ---
    elif page_active_sa == "parametres":
        st.subheader("⚙️ Paramètres du Compte & Sécurité")
        afficher_bloc_changement_mot_de_passe(key_suffix="super_admin")


def afficher_bloc_changement_mot_de_passe(key_suffix: str = ""):
    """Affiche le formulaire de changement de mot de passe dans les paramètres généraux."""
    session = st.session_state.get("user_session", {})
    uname = session.get("username")
    if not uname:
        return

    with st.container(border=True):
        st.subheader("🔐 Mot de passe et sécurité")
        st.caption(f"Compte connecté : **{session.get('nom', uname)}** (`{uname}`)")
        suffix = f"_{key_suffix}" if key_suffix else ""
        with st.form(f"form_change_password_{uname}{suffix}"):
            nouveau_mdp = st.text_input("Nouveau mot de passe", type="password")
            confirmer_mdp = st.text_input("Confirmer le mot de passe", type="password")
            if st.form_submit_button("Modifier mon mot de passe", type="primary"):
                if nouveau_mdp and nouveau_mdp == confirmer_mdp:
                    reg = st.session_state.registre_app
                    if uname in reg["users"]:
                        reg["users"][uname]["password"] = hasher_mot_de_passe(nouveau_mdp)
                        sauvegarder_registre(reg)
                        st.success("Mot de passe mis à jour avec succès !")
                else:
                    st.error("Les mots de passe ne correspondent pas ou sont vides.")