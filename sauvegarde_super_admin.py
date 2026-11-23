import datetime
import io
import json
import os
import zipfile
import streamlit as st

from supabase_store import dump_scope, get_bytes, set_bytes, set_json

try:
    from auth_manager import sauvegarder_registre
except Exception:
    sauvegarder_registre = None


SCHEMA_VERSION = "1.1"


def _est_json_serialisable(valeur) -> bool:
    try:
        json.dumps(valeur)
        return True
    except (TypeError, OverflowError):
        return False


def _extraire_etat_session_propre() -> dict:
    """Récupère uniquement les clés de session_state sérialisables en JSON."""
    etat_propre = {}
    for cle, val in st.session_state.items():
        if cle.startswith("_") or cle == "user_session":
            continue
        if _est_json_serialisable(val):
            etat_propre[cle] = val
    return etat_propre


def _collecter_fichiers_clubs(registre_app: dict) -> dict[str, str]:
    """
    Lit les données d'équipes de chaque club connu dans Supabase
    et retourne un mapping { 'slug_club/nom_fichier.json': contenu_json_str }.
    """
    fichiers_clubs: dict[str, str] = {}
    if not isinstance(registre_app, dict):
        return fichiers_clubs

    clubs_dict = registre_app.get("clubs", {})
    if not isinstance(clubs_dict, dict):
        return fichiers_clubs

    for club_nom, club_info in clubs_dict.items():
        if not isinstance(club_info, dict):
            continue
        slug = club_info.get("slug") or club_nom.lower().replace(" ", "_")
        try:
            lignes = dump_scope(slug)
        except Exception:
            continue
        for cle, valeur in lignes.items():
            if cle.lower().endswith(".json") and not cle.startswith(("draft_", "offline_queue_")):
                fichiers_clubs[f"{slug}/{cle}"] = json.dumps(valeur, ensure_ascii=False)

    return fichiers_clubs


def construire_payload_sauvegarde(manager=None, inclure_session: bool = True) -> dict:
    """Construit la sauvegarde globale multi-clubs (registre + données d'équipes + session)."""
    registre_actuel = st.session_state.get("registre_app", {})
    donnees_manager = {}

    if manager is not None:
        if hasattr(manager, "exporter_donnees_dict") and callable(manager.exporter_donnees_dict):
            donnees_manager = manager.exporter_donnees_dict()
        elif hasattr(manager, "to_dict") and callable(manager.to_dict):
            donnees_manager = manager.to_dict()
        else:
            for attr in ("clubs", "equipes", "joueuses", "joueurs", "matchs", "historique", "parametres", "donnees"):
                if hasattr(manager, attr):
                    val = getattr(manager, attr)
                    if _est_json_serialisable(val):
                        donnees_manager[attr] = val

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "registre_app": registre_actuel if _est_json_serialisable(registre_actuel) else {},
        "fichiers_equipes_clubs": _collecter_fichiers_clubs(registre_actuel),
        "manager_data": donnees_manager,
        "session_data": _extraire_etat_session_propre() if inclure_session else {},
    }


def generer_octets_sauvegarde_json(manager=None, inclure_session: bool = True) -> bytes:
    payload = construire_payload_sauvegarde(manager=manager, inclure_session=inclure_session)
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def generer_octets_sauvegarde_zip(manager=None, dossier_logos: str | None = None, inclure_session: bool = True) -> bytes:
    """Génère une archive ZIP contenant sauvegarde.json + logos des clubs si disponibles."""
    json_bytes = generer_octets_sauvegarde_json(manager=manager, inclure_session=inclure_session)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sauvegarde.json", json_bytes)

        registre_actuel = st.session_state.get("registre_app", {})
        if isinstance(registre_actuel, dict):
            for club_nom, club_info in registre_actuel.get("clubs", {}).items():
                if not isinstance(club_info, dict):
                    continue
                slug = club_info.get("slug") or club_nom.lower().replace(" ", "_")
                try:
                    logo = get_bytes(slug, "logo_club.png")
                except Exception:
                    logo = None
                if logo:
                    zf.writestr(f"logos/{slug}/logo_club.png", logo)

    buf.seek(0)
    return buf.getvalue()


def charger_et_valider_sauvegarde(fichier_uploade) -> tuple[bool, str, dict | None]:
    """Lit un fichier .json ou .zip uploadé et vérifie sa structure."""
    if fichier_uploade is None:
        return False, "Aucun fichier sélectionné.", None

    nom = (fichier_uploade.name or "").lower()
    contenu = fichier_uploade.getvalue()

    try:
        if nom.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(contenu), "r") as zf:
                if "sauvegarde.json" not in zf.namelist():
                    return False, "Archive invalide : 'sauvegarde.json' introuvable.", None
                data = json.loads(zf.read("sauvegarde.json").decode("utf-8"))
        else:
            data = json.loads(contenu.decode("utf-8"))
    except Exception as exc:
        return False, f"Fichier corrompu ou illisible : {exc}", None

    if not isinstance(data, dict) or ("manager_data" not in data and "registre_app" not in data):
        return False, "Format de sauvegarde non reconnu.", None

    version = data.get("version_schema") or data.get("schema_version") or "inconnue"
    date_exp = data.get("exported_at") or "date inconnue"
    return True, f"Sauvegarde valide (schéma v{version}, export du {date_exp}).", data


def appliquer_restauration_sauvegarde(payload: dict, manager=None, restaurer_session: bool = True) -> tuple[bool, str]:
    """Restaure le registre, les fichiers d'équipes par club, le manager et la session."""
    try:
        reg_restore = payload.get("registre_app")
        if isinstance(reg_restore, dict) and reg_restore:
            st.session_state["registre_app"] = reg_restore
            if isinstance(reg_restore.get("users"), dict):
                st.session_state["users_db"] = reg_restore["users"]
            if sauvegarder_registre and callable(sauvegarder_registre):
                sauvegarder_registre(reg_restore, remplacer=True)

        fichiers_clubs = payload.get("fichiers_equipes_clubs") or {}
        if isinstance(fichiers_clubs, dict):
            for rel_cle, contenu_json in fichiers_clubs.items():
                if "/" not in rel_cle:
                    continue
                slug, nom_f = rel_cle.split("/", 1)
                set_json(slug, os.path.basename(nom_f), json.loads(contenu_json))

        manager_data = payload.get("manager_data") or {}
        if manager is not None and manager_data:
            if hasattr(manager, "importer_donnees_dict") and callable(manager.importer_donnees_dict):
                manager.importer_donnees_dict(manager_data)
            elif hasattr(manager, "from_dict") and callable(manager.from_dict):
                manager.from_dict(manager_data)
            else:
                for cle, val in manager_data.items():
                    if hasattr(manager, cle):
                        setattr(manager, cle, val)

            if hasattr(manager, "charger_donnees") and callable(manager.charger_donnees):
                manager.charger_donnees()

        if restaurer_session and isinstance(payload.get("session_data"), dict):
            for cle, val in payload["session_data"].items():
                if cle != "user_session":
                    st.session_state[cle] = val

        return True, "Restauration complète effectuée avec succès."
    except Exception as exc:
        return False, f"Erreur lors de la restauration : {exc}"


def afficher_bloc_super_admin(manager=None, dossier_logos: str | None = None):
    """Bloc UI à placer dans l'espace Super Admin."""
    st.subheader("🛡️ Sauvegarde & Restauration Globale (Super Admin)")
    st.caption(
        "Exporte le registre (clubs, équipes, comptes), les données d'équipes et la session "
        "avant une mise à jour ou migration, et restaure l'ensemble proprement."
    )

    col_exp, col_imp = st.columns(2)

    with col_exp:
        st.markdown("### 1. Télécharger une sauvegarde")
        inclure_sess = st.checkbox("Inclure l'état courant de session", value=True, key="sa_inclure_session")
        format_zip = st.checkbox("Inclure les logos dans une archive .ZIP", value=False, key="sa_format_zip")

        horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if format_zip:
            data_bytes = generer_octets_sauvegarde_zip(
                manager=manager,
                dossier_logos=dossier_logos,
                inclure_session=inclure_sess,
            )
            st.download_button(
                label="📦 Télécharger la sauvegarde (.ZIP)",
                data=data_bytes,
                file_name=f"sauvegarde_super_admin_{horodatage}.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary",
            )
        else:
            data_bytes = generer_octets_sauvegarde_json(
                manager=manager,
                inclure_session=inclure_sess,
            )
            st.download_button(
                label="💾 Télécharger la sauvegarde (.JSON)",
                data=data_bytes,
                file_name=f"sauvegarde_super_admin_{horodatage}.json",
                mime="application/json",
                use_container_width=True,
                type="primary",
            )

    with col_imp:
        st.markdown("### 2. Restaurer une sauvegarde")
        uploaded = st.file_uploader(
            "Importer un fichier de sauvegarde (.json ou .zip)",
            type=["json", "zip"],
            key="sa_upload_file",
        )
        restaurer_sess = st.checkbox("Restaurer aussi l'état de session", value=True, key="sa_restaurer_session")

        if uploaded is not None:
            ok, msg, parsed = charger_et_valider_sauvegarde(uploaded)
            if not ok:
                st.error(msg)
            else:
                st.success(msg)
                nb_clubs = len((parsed.get("registre_app") or {}).get("clubs", {}))
                nb_fichiers = len(parsed.get("fichiers_equipes_clubs") or {})
                st.caption(f"Contenu détecté : {nb_clubs} club(s) au registre, {nb_fichiers} fichier(s) d'équipe.")

                confirmer = st.checkbox(
                    "Je confirme vouloir remplacer les données actuelles par cette sauvegarde",
                    key="sa_confirmer_restore",
                )
                if st.button(
                    "♻️ Appliquer la restauration",
                    disabled=not confirmer,
                    use_container_width=True,
                ):
                    ok_res, msg_res = appliquer_restauration_sauvegarde(
                        parsed,
                        manager=manager,
                        restaurer_session=restaurer_sess,
                    )
                    if ok_res:
                        st.success(msg_res)
                        st.rerun()
                    else:
                        st.error(msg_res)