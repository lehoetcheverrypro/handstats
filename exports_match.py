import csv
import io
import json
from datetime import datetime, timezone


def _temps_vers_secondes(temps_str):
    if not temps_str:
        return 0
    parties = str(temps_str).strip().split(":")
    try:
        if len(parties) == 2:
            minutes = int(parties[0])
            secondes = int(parties[1])
            return max(0, minutes * 60 + secondes)
        if len(parties) == 3:
            heures = int(parties[0])
            minutes = int(parties[1])
            secondes = int(parties[2])
            return max(0, heures * 3600 + minutes * 60 + secondes)
    except (ValueError, TypeError):
        return 0
    return 0


def _categoriser_action(type_action):
    t = str(type_action or "").strip()
    t_low = t.lower()
    if "repère mi-temps" in t_low:
        return "Repere_Periode"
    if "attaque adverse" in t_low:
        return "Tactique_Adversaire"
    if "gardien" in t_low or "arrêt" in t_low or "encaissé" in t_low:
        return "Gardien"
    if any(k in t_low for k in ["but", "tir", "duel off", "perte de balle", "passe décisive"]):
        return "Attaque"
    if any(k in t_low for k in ["duel déf", "interception", "neutralisation", "provoquée", "jaune", "2min", "exclusion"]):
        return "Defense_Discipline"
    return "Autre"


def construire_payload_match(
    nom_match,
    club_nom,
    equipe_nom,
    score_eq,
    score_adv,
    lignes_champ=None,
    lignes_gardiennes=None,
    historique_actions=None,
    attaques_adv=None,
    commentaires_staff=None,
    bilan_post_match="",
    statut_match="archive",
):
    actions_liste = list(historique_actions or [])
    notes_liste = list(commentaires_staff or [])
    champ_liste = list(lignes_champ or [])
    gard_liste = list(lignes_gardiennes or [])
    att_dict = dict(attaques_adv or {})

    b1, e1, b2, e2 = 0, 0, 0, 0
    evenements_enrichis = []

    for idx, act in enumerate(actions_liste, start=1):
        t_act = str(act.get("type_action", "")).strip()
        periode = str(act.get("periode", "")).strip()
        temps_str = str(act.get("temps", "00:00")).strip()
        secondes_chrono = _temps_vers_secondes(temps_str)
        horodatage_reel = str(act.get("horodatage_reel", "")).strip()
        details = str(act.get("details", "")).strip()

        est_2mt = periode == "2ème MT"
        if t_act == "But" or t_act.startswith("But ("):
            if est_2mt:
                b2 += 1
            else:
                b1 += 1
        elif t_act == "But encaissé":
            if est_2mt:
                e2 += 1
            else:
                e1 += 1

        evenements_enrichis.append({
            "sequence": idx,
            "periode": periode or None,
            "temps_chrono": temps_str,
            "secondes_chrono": secondes_chrono,
            "horodatage_reel": horodatage_reel or None,
            "categorie": _categoriser_action(t_act),
            "type_action": t_act,
            "membre": act.get("membre_nom"),
            "zone_terrain": act.get("zone_terrain"),
            "zone_cage": act.get("zone_cage"),
            "systeme_adv": act.get("systeme_adv"),
            "details": details,
        })

    notes_enrichies = []
    for idx, note in enumerate(notes_liste, start=1):
        temps_str = str(note.get("temps", "00:00")).strip()
        notes_enrichies.append({
            "index": idx,
            "periode": str(note.get("periode", "")).strip() or None,
            "temps_chrono": temps_str,
            "secondes_chrono": _temps_vers_secondes(temps_str),
            "horodatage_reel": str(note.get("horodatage_reel", "")).strip() or None,
            "texte": str(note.get("texte", "")).strip(),
        })

    if score_eq > score_adv:
        issue = "victoire"
    elif score_eq < score_adv:
        issue = "defaite"
    else:
        issue = "nul"

    return {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "statut_match": statut_match,
        "rencontre": {
            "nom_match": nom_match,
            "club": club_nom,
            "equipe": equipe_nom,
            "score_equipe": int(score_eq),
            "score_adversaire": int(score_adv),
            "issue": issue,
            "decoupage_horodate": {
                "mi_temps_1": {"buts_equipe": b1, "buts_adversaire": e1},
                "mi_temps_2": {"buts_equipe": b2, "buts_adversaire": e2},
            },
        },
        "statistiques_individuelles": {
            "joueurs_champ": champ_liste,
            "gardiens": gard_liste,
        },
        "tactique_et_notes": {
            "attaques_adversaires": att_dict,
            "bilan_post_match": str(bilan_post_match or "").strip(),
            "notes_staff": notes_enrichies,
        },
        "evenements_chronologiques": evenements_enrichis,
    }


def exporter_match_json(payload, indent=2):
    return json.dumps(payload, ensure_ascii=False, indent=indent)


def exporter_evenements_csv(payload):
    output = io.StringIO()
    colonnes = [
        "club",
        "equipe",
        "match",
        "statut_match",
        "sequence",
        "periode",
        "temps_chrono",
        "secondes_chrono",
        "horodatage_reel",
        "categorie",
        "type_action",
        "membre",
        "zone_terrain",
        "zone_cage",
        "systeme_adv",
        "details",
    ]
    writer = csv.DictWriter(output, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
    writer.writeheader()

    rencontre = payload.get("rencontre", {})
    club = rencontre.get("club", "")
    equipe = rencontre.get("equipe", "")
    nom_match = rencontre.get("nom_match", "")
    statut = payload.get("statut_match", "archive")

    for ev in payload.get("evenements_chronologiques", []):
        row = {
            "club": club,
            "equipe": equipe,
            "match": nom_match,
            "statut_match": statut,
            **ev,
        }
        writer.writerow(row)

    return output.getvalue()
