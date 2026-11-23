"""
Connexion mémorisée (cookie) : l'utilisateur reste connecté après un redémarrage
ou une mise à jour de l'application, sans ressaisir son mot de passe.

Fonctionnement
- À la connexion (case « Rester connecté » cochée), on génère un jeton aléatoire.
  Seule son empreinte (SHA-256) est stockée dans Supabase ; le jeton lui-même vit dans un cookie du navigateur.
- Au démarrage d'une nouvelle session, si le cookie est valide, la session est restaurée.
- À la déconnexion, le jeton est supprimé de la base et le cookie effacé.
- Un jeton expire après 30 jours, et devient invalide si le mot de passe change,
  si le compte est supprimé ou si le club est suspendu.
"""
from __future__ import annotations

import hashlib
import secrets
import time

import streamlit as st
import streamlit.components.v1 as components

from supabase_store import SCOPE_SESSIONS, delete_json, dump_scope, get_json, set_json

NOM_COOKIE = "hs_session"
DUREE_JOURS = 30


def _empreinte(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _lire_cookie() -> str | None:
    try:
        valeur = st.context.cookies.get(NOM_COOKIE)
        return valeur or None
    except Exception:
        return None  # version de Streamlit trop ancienne : la fonction reste simplement inactive


def _ecrire_cookie(valeur: str, duree_secondes: int) -> None:
    """Pose (ou efface, avec une durée de 0) le cookie dans le navigateur."""
    components.html(
        f"""<script>
        try {{
          var p = window.parent;
          var secure = (p.location.protocol === 'https:') ? '; Secure' : '';
          p.document.cookie = "{NOM_COOKIE}={valeur}; Max-Age={int(duree_secondes)}; Path=/; SameSite=Lax" + secure;
        }} catch (e) {{}}
        </script>""",
        height=0,
    )


def _creer_token(username: str, empreinte_mdp: str) -> str:
    token = secrets.token_urlsafe(32)
    set_json(
        SCOPE_SESSIONS,
        _empreinte(token),
        {"username": username, "pwd": empreinte_mdp, "expire": time.time() + DUREE_JOURS * 86400},
    )
    try:  # ménage opportuniste des jetons expirés
        maintenant = time.time()
        for cle, val in dump_scope(SCOPE_SESSIONS).items():
            if isinstance(val, dict) and val.get("expire", 0) < maintenant:
                delete_json(SCOPE_SESSIONS, cle)
    except Exception:
        pass
    return token


def _lire_token(token: str):
    val = get_json(SCOPE_SESSIONS, _empreinte(token), None)
    if not isinstance(val, dict):
        return None
    if val.get("expire", 0) < time.time():
        delete_json(SCOPE_SESSIONS, _empreinte(token))
        return None
    return val


def _revoquer_token(token: str) -> None:
    try:
        delete_json(SCOPE_SESSIONS, _empreinte(token))
    except Exception:
        pass


def gerer_session_persistante() -> None:
    """À appeler dans app.py, juste après init_users_db() et avant de lire la session."""
    from auth_manager import empreinte_mot_de_passe, session_depuis_compte

    session = st.session_state.user_session
    token_actif = st.session_state.get("_token_connexion")

    # 1) Déconnexion détectée : on révoque le jeton et on efface le cookie.
    if not session["logged_in"] and token_actif:
        _revoquer_token(token_actif)
        st.session_state.pop("_token_connexion", None)
        st.session_state.pop("_cookie_pose_restant", None)
        _ecrire_cookie("", 0)
        return

    # 2) Pas connecté : tentative de restauration depuis le cookie.
    if not session["logged_in"]:
        token = _lire_cookie()
        if not token:
            return
        try:
            info = _lire_token(token)
        except Exception:
            return
        if not info:
            return
        username = info.get("username")
        if info.get("pwd") != empreinte_mot_de_passe(username):
            _revoquer_token(token)  # mot de passe changé depuis : session invalide
            return
        restauree = session_depuis_compte(username)
        if not restauree:
            _revoquer_token(token)  # compte supprimé ou club suspendu
            return
        st.session_state.user_session = restauree
        st.session_state["_token_connexion"] = token
        return

    # 3) Connecté sans jeton : création (si l'utilisateur a laissé la case cochée).
    if not token_actif and st.session_state.get("_rester_connecte", False):
        try:
            token = _creer_token(session["username"], empreinte_mot_de_passe(session["username"]))
        except Exception:
            return
        st.session_state["_token_connexion"] = token
        st.session_state["_cookie_pose_restant"] = 3   # on repose le cookie sur quelques exécutions,
                                                       # au cas où un clic rapide interromprait la première

    # 4) Pose du cookie (invisible).
    restant = st.session_state.get("_cookie_pose_restant", 0)
    token_actif = st.session_state.get("_token_connexion")
    if restant > 0 and token_actif:
        _ecrire_cookie(token_actif, DUREE_JOURS * 86400)
        st.session_state["_cookie_pose_restant"] = restant - 1
