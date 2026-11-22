from io import BytesIO
import os
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

from shot_grid import afficher_cage_recapitulative

ZONES_CAGE_9 = [
    "Haut-Gauche", "Haut-Centre", "Haut-Droite",
    "Milieu-Gauche", "Milieu-Centre", "Milieu-Droite",
    "Bas-Gauche", "Bas-Centre", "Bas-Droite",
]

ZONES_TERRAIN_6 = [
    "Aile Gauche",
    "Exter 9m Gauche",
    "6m Centre",
    "Exter 9m Centre",
    "Aile Droite",
    "Exter 9m Droite",
]


def _resoudre_logo_club(dossier_club=None):
    if dossier_club:
        candidat_club = os.path.join(dossier_club, "logo_club.png")
        if os.path.exists(candidat_club):
            return candidat_club
    base_dir = os.path.dirname(os.path.abspath(__file__))
    fallback_local = os.path.join(base_dir, "logo_club.png")
    if os.path.exists(fallback_local):
        return fallback_local
    return None


def extraire_nom_adversaire(nom_match: str) -> str:
    """Extrait un libellé d'adversaire propre depuis un nom de rencontre (ex: 'J1 - Mérignac' -> 'Mérignac')."""
    if not nom_match:
        return "Adversaire inconnu"
    texte = str(nom_match).strip()
    # Retire les préfixes classiques type 'J1 - ', 'J04 : ', 'Coupe - ', 'Amical / '
    texte_nettoye = re.sub(
        r"^(?:j(?:ournée)?\s*\d+|r\d+|match\s*\d+|amical|coupe|tournoi)\s*[-–—:/|]+\s*",
        "",
        texte,
        flags=re.IGNORECASE,
    ).strip()
    return texte_nettoye or texte


def collecter_matchs_archives(joueuses_par_equipe: dict) -> dict:
    """
    Agrège les matchs archivés depuis un mapping {nom_equipe: {nom_joueuse: obj_joueuse}}.
    Retourne {nom_match: dict_match_consolide}.
    """
    matchs = {}

    for nom_eq, joueurs_dict in (joueuses_par_equipe or {}).items():
        for j in (joueurs_dict or {}).values():
            for m in getattr(j, "historique_matchs", []) or []:
                nom_m = m.get("match")
                if not nom_m:
                    continue

                if nom_m not in matchs:
                    matchs[nom_m] = {
                        "match": nom_m,
                        "adversaire": extraire_nom_adversaire(nom_m),
                        "equipe_source": nom_eq,
                        "score_equipe": m.get("score_equipe", 0),
                        "score_adversaire": m.get("score_adversaire", 0),
                        "attaques_adversaires": dict(m.get("attaques_adversaires") or {}),
                        "journal_actions": list(m.get("journal_actions") or []),
                        "commentaires_staff": list(m.get("commentaires_staff") or []),
                        "bilan_post_match": m.get("bilan_post_match", ""),
                    }
                else:
                    # Complète les champs si absents ou plus complets dans une autre fiche
                    if not matchs[nom_m].get("journal_actions") and m.get("journal_actions"):
                        matchs[nom_m]["journal_actions"] = list(m.get("journal_actions") or [])
                    if not matchs[nom_m].get("attaques_adversaires") and m.get("attaques_adversaires"):
                        matchs[nom_m]["attaques_adversaires"] = dict(m.get("attaques_adversaires") or {})
                    if not matchs[nom_m].get("commentaires_staff") and m.get("commentaires_staff"):
                        matchs[nom_m]["commentaires_staff"] = list(m.get("commentaires_staff") or [])
                    if not matchs[nom_m].get("bilan_post_match") and m.get("bilan_post_match"):
                        matchs[nom_m]["bilan_post_match"] = m.get("bilan_post_match", "")
                    if m.get("score_equipe") is not None:
                        matchs[nom_m]["score_equipe"] = m.get("score_equipe")
                    if m.get("score_adversaire") is not None:
                        matchs[nom_m]["score_adversaire"] = m.get("score_adversaire")

    return matchs


def _extraire_zones_depuis_action(act: dict) -> tuple[str, str]:
    """Retourne (zone_terrain, zone_cage) depuis un événement du journal."""
    z_ter = str(act.get("zone_terrain") or "").strip()
    z_cage = str(act.get("zone_cage") or "").strip()
    det = str(act.get("details") or "")

    if not z_ter or not z_cage:
        if "Terrain: " in det and " | Cage: " in det:
            try:
                if not z_ter:
                    z_ter = det.split("Terrain: ", 1)[1].split(" | Cage: ", 1)[0].strip()
                if not z_cage:
                    z_cage = det.split(" | Cage: ", 1)[1].split("]", 1)[0].strip()
            except Exception:
                pass
        elif "[" in det and "]" in det and not z_cage:
            try:
                z_cage = det.rsplit("[", 1)[1].split("]", 1)[0].strip()
            except Exception:
                pass

    return (z_ter or "Non précisée"), (z_cage or "Non précisée")


def _identifier_gardien_adverse(act: dict) -> str:
    """
    Identifie le profil de gardien(ne) adverse sur un tir de notre équipe :
    1) champ explicite 'gardien_adv' si présent dans l'action,
    2) mention '(Gardien... : XXX)' dans details si présente,
    3) sinon découpage par période ('Gardienne Adverse (1ère MT)', etc.) pour distinguer les rotations.
    """
    gard_explicite = str(act.get("gardien_adv") or "").strip()
    if gard_explicite:
        return gard_explicite

    det = str(act.get("details") or "")
    match_g = re.search(r"Gardien(?:ne)?\s*adverse\s*:\s*([^\[\]]+)", det, flags=re.IGNORECASE)
    if match_g:
        val = match_g.group(1).strip(" )")
        if val:
            return val

    periode = str(act.get("periode") or "").strip()
    if periode:
        return f"Gardienne Adverse ({periode})"
    return "Gardienne Adverse"


def analyser_profil_adversaire(matchs_selectionnes: list[dict]) -> dict:
    """
    Calcule le profil collectif de l'adversaire et le profilage de ses gardien(ne)s
    sur une liste de dictionnaires de matchs archivés.
    """
    nb_matchs = len(matchs_selectionnes or [])
    victoires = 0
    nuls = 0
    defaites = 0
    buts_pour_cumul = 0
    buts_contre_cumul = 0

    systemes_cumul = {}
    temps_morts_adv = []
    cartons_rouges_journal = []

    # Attaque adverse (ce que l'adversaire marque / tire contre nous)
    tirs_adv_par_terrain = {z: {"buts": 0, "arrets_nos_gard": 0, "total": 0} for z in ZONES_TERRAIN_6}
    tirs_adv_par_terrain["Non précisée"] = {"buts": 0, "arrets_nos_gard": 0, "total": 0}
    cage_tirs_adv = {z: {"succes": 0, "echec": 0} for z in ZONES_CAGE_9}
    buts_adv_par_periode = {"1ère MT": 0, "2ème MT": 0, "Autre": 0}

    # Nos tirs face au(x) gardien(ne)s adverse(s)
    # Par profil de gardien adverse : {"buts_marques": int, "tirs_cadres_rates": int, "hors_cadre": int, "par_zone_cage": {...}, "par_zone_terrain": {...}}
    profils_gardiens_adv = {}

    def _get_profil_gard(nom_g: str) -> dict:
        if nom_g not in profils_gardiens_adv:
            profils_gardiens_adv[nom_g] = {
                "gardien": nom_g,
                "buts_marques": 0,
                "tirs_cadres_rates": 0,
                "hors_cadre": 0,
                "par_zone_cage": {z: {"succes": 0, "echec": 0} for z in ZONES_CAGE_9},
                "par_zone_terrain": {
                    z: {"buts": 0, "echec_cadre": 0, "hors_cadre": 0, "total": 0}
                    for z in ZONES_TERRAIN_6 + ["Non précisée"]
                },
            }
        return profils_gardiens_adv[nom_g]

    for m in (matchs_selectionnes or []):
        s_eq = int(m.get("score_equipe", 0) or 0)
        s_adv = int(m.get("score_adversaire", 0) or 0)
        buts_pour_cumul += s_eq
        buts_contre_cumul += s_adv

        if s_eq > s_adv:
            victoires += 1
        elif s_eq < s_adv:
            defaites += 1
        else:
            nuls += 1

        for sys_nom, cnt in (m.get("attaques_adversaires") or {}).items():
            systemes_cumul[sys_nom] = systemes_cumul.get(sys_nom, 0) + int(cnt or 0)

        for act in (m.get("journal_actions") or []):
            t_act = str(act.get("type_action") or "")
            t_low = t_act.lower()
            det = str(act.get("details") or "")
            periode = str(act.get("periode") or "").strip()
            cle_periode = periode if periode in ("1ère MT", "2ème MT") else "Autre"

            # Temps morts adverses
            if "temps mort" in t_low and ("advers" in t_low or "advers" in det.lower()):
                temps_morts_adv.append({
                    "match": m.get("match", ""),
                    "periode": periode or "-",
                    "temps": act.get("temps", "00:00"),
                    "details": det,
                })

            # Cartons rouges enregistrés dans le journal
            if "rouge" in t_low:
                cartons_rouges_journal.append({
                    "match": m.get("match", ""),
                    "periode": periode or "-",
                    "temps": act.get("temps", "00:00"),
                    "type_action": t_act,
                    "details": det,
                })

            z_ter, z_cage = _extraire_zones_depuis_action(act)

            # Tirs de l'adversaire (But encaissé ou Arrêt décisif de notre gardienne)
            if t_act == "But encaissé" or t_act == "Arrêt décisif":
                buts_adv_par_periode[cle_periode] += 1 if t_act == "But encaissé" else 0
                cible_ter = tirs_adv_par_terrain.get(z_ter)
                if cible_ter is None:
                    cible_ter = tirs_adv_par_terrain["Non précisée"]
                cible_ter["total"] += 1
                if t_act == "But encaissé":
                    cible_ter["buts"] += 1
                else:
                    cible_ter["arrets_nos_gard"] += 1

                if z_cage in cage_tirs_adv:
                    # Convention cage : 'succes' = but adverse (ou arrêt selon lecture), ici on suit la réussite adverse
                    if t_act == "But encaissé":
                        cage_tirs_adv[z_cage]["succes"] += 1
                    else:
                        cage_tirs_adv[z_cage]["echec"] += 1

            # Nos tirs face au/à la gardien(ne) adverse
            elif t_act == "But" or t_act.startswith("But (") or t_act == "Tir raté" or t_act.startswith("Tir raté ("):
                nom_g_adv = _identifier_gardien_adverse(act)
                prof_g = _get_profil_gard(nom_g_adv)

                est_but = t_act == "But" or t_act.startswith("But (")
                est_hors_cadre = (not est_but) and (z_cage.lower() == "hors cadre")

                cible_ter_g = prof_g["par_zone_terrain"].get(z_ter)
                if cible_ter_g is None:
                    cible_ter_g = prof_g["par_zone_terrain"]["Non précisée"]
                cible_ter_g["total"] += 1

                if est_but:
                    prof_g["buts_marques"] += 1
                    cible_ter_g["buts"] += 1
                    if z_cage in prof_g["par_zone_cage"]:
                        # 'succes' = but marqué contre ce gardien (point faible du gardien)
                        prof_g["par_zone_cage"][z_cage]["succes"] += 1
                elif est_hors_cadre:
                    prof_g["hors_cadre"] += 1
                    cible_ter_g["hors_cadre"] += 1
                else:
                    prof_g["tirs_cadres_rates"] += 1
                    cible_ter_g["echec_cadre"] += 1
                    if z_cage in prof_g["par_zone_cage"]:
                        # 'echec' = tir cadré non marqué (arrêt / échec face au gardien)
                        prof_g["par_zone_cage"][z_cage]["echec"] += 1

    # Classement des systèmes offensifs adverses
    total_sys = sum(systemes_cumul.values())
    systemes_tries = sorted(systemes_cumul.items(), key=lambda x: x[1], reverse=True)
    systeme_principal = systemes_tries[0][0] if systemes_tries and systemes_tries[0][1] > 0 else "Non renseigné"

    # Zone de départ la plus dangereuse pour l'adversaire
    zones_ter_tries = sorted(
        [(k, v) for k, v in tirs_adv_par_terrain.items() if v["total"] > 0],
        key=lambda item: item[1]["buts"],
        reverse=True,
    )
    zone_dangereuse_adv = zones_ter_tries[0][0] if zones_ter_tries else "Non précisée"

    return {
        "nb_matchs": nb_matchs,
        "bilan": f"{victoires}V / {nuls}N / {defaites}D",
        "victoires": victoires,
        "nuls": nuls,
        "defaites": defaites,
        "buts_pour_cumul": buts_pour_cumul,
        "buts_contre_cumul": buts_contre_cumul,
        "moy_buts_pour": round(buts_pour_cumul / nb_matchs, 1) if nb_matchs > 0 else 0.0,
        "moy_buts_contre": round(buts_contre_cumul / nb_matchs, 1) if nb_matchs > 0 else 0.0,
        "systemes_cumul": systemes_cumul,
        "systemes_tries": systemes_tries,
        "total_systemes": total_sys,
        "systeme_principal": systeme_principal,
        "zone_dangereuse_adv": zone_dangereuse_adv,
        "tirs_adv_par_terrain": tirs_adv_par_terrain,
        "cage_tirs_adv": cage_tirs_adv,
        "buts_adv_par_periode": buts_adv_par_periode,
        "profils_gardiens_adv": profils_gardiens_adv,
        "temps_morts_adv": temps_morts_adv,
        "cartons_rouges_journal": cartons_rouges_journal,
    }


def generer_pdf_scouting_adversaire(
    nom_adversaire: str,
    noms_matchs: list[str],
    analyse: dict,
    club_nom: str = "Mon Club",
    equipe_nom: str = "Équipe",
    notes_scouting: str = "",
    dossier_club=None,
) -> bytes:
    """Génère une fiche PDF synthétique de scouting adverse sur plusieurs matchs."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0F172A")
    slate_dark = colors.HexColor("#1E293B")
    slate_muted = colors.HexColor("#475569")
    accent_blue = colors.HexColor("#0284C7")
    bg_soft = colors.HexColor("#F8FAFC")
    border_grey = colors.HexColor("#CBD5E1")

    title_style = ParagraphStyle(
        "ScoutTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=15, leading=19, textColor=navy, alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "ScoutSub", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=10, leading=13, textColor=accent_blue, alignment=TA_CENTER,
    )
    sec_style = ParagraphStyle(
        "ScoutSec", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=13, textColor=navy, spaceBefore=10, spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "ScoutBody", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.8, leading=12.5, textColor=slate_dark,
    )
    hdr_style = ParagraphStyle(
        "ScoutHdr", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=11, textColor=colors.white, alignment=TA_CENTER,
    )
    cell_center = ParagraphStyle(
        "ScoutCenter", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11, textColor=slate_dark, alignment=TA_CENTER,
    )

    story = []

    # Bandeau en-tête
    logo_path = _resoudre_logo_club(dossier_club)
    left_banner = [
        Paragraph(str(club_nom).upper(), ParagraphStyle(
            "SCB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.white
        )),
        Paragraph(f"RAPPORT DE SCOUTING ADVERSE — Équipe : {equipe_nom}", ParagraphStyle(
            "SCT", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.8, leading=11, textColor=colors.HexColor("#38BDF8")
        )),
    ]
    right_banner = Paragraph("", styles["Normal"])
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=38, height=38)
            img.hAlign = "RIGHT"
            right_banner = img
        except Exception:
            right_banner = Paragraph(
                "<b>SCOUTING</b>",
                ParagraphStyle("SCR", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=8, textColor=colors.white),
            )

    bandeau = Table([[left_banner, right_banner]], colWidths=[425, 85])
    bandeau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(bandeau)
    story.append(Spacer(1, 10))

    story.append(Paragraph("FICHE DE SCOUTING & PROFILAGE ADVERSE", title_style))
    story.append(Paragraph(f"Adversaire : {str(nom_adversaire).upper()} ({analyse.get('nb_matchs', 0)} match(s) analysé(s))", sub_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Matchs pris en compte : {', '.join(noms_matchs) if noms_matchs else 'Aucun'}",
        ParagraphStyle("MatchsList", parent=body_style, fontSize=8, textColor=slate_muted, alignment=TA_CENTER),
    ))
    story.append(Spacer(1, 8))

    # KPIs globaux
    kpi_row = [[
        Paragraph(f"<font size='7.5' color='#64748B'><b>BILAN</b></font><br/><font size='11' color='#0F172A'><b>{analyse.get('bilan', '-')}</b></font>", cell_center),
        Paragraph(f"<font size='7.5' color='#64748B'><b>MOY. BUTS MARQUÉS</b></font><br/><font size='11' color='#15803D'><b>{analyse.get('moy_buts_pour', 0.0)}</b></font>", cell_center),
        Paragraph(f"<font size='7.5' color='#64748B'><b>MOY. BUTS ENCAISSÉS</b></font><br/><font size='11' color='#B91C1C'><b>{analyse.get('moy_buts_contre', 0.0)}</b></font>", cell_center),
        Paragraph(f"<font size='7.5' color='#64748B'><b>SYSTÈME N°1 ADV.</b></font><br/><font size='10.5' color='#0284C7'><b>{analyse.get('systeme_principal', '-')}</b></font>", cell_center),
    ]]
    t_kpi = Table(kpi_row, colWidths=[115, 130, 135, 130])
    t_kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_soft),
        ("BOX", (0, 0), (-1, -1), 0.8, border_grey),
        ("LINEBEFORE", (1, 0), (1, -1), 0.6, border_grey),
        ("LINEBEFORE", (2, 0), (2, -1), 0.6, border_grey),
        ("LINEBEFORE", (3, 0), (3, -1), 0.6, border_grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t_kpi)

    # 1. Systèmes d'attaque adverses
    story.append(Paragraph("1. TENDANCES OFFENSIVES — SYSTÈMES ADVERSES", sec_style))
    sys_tries = analyse.get("systemes_tries") or []
    tot_sys = analyse.get("total_systemes", 0)
    if tot_sys > 0:
        sys_rows = [[
            Paragraph("Système", hdr_style),
            Paragraph("Occurrences", hdr_style),
            Paragraph("Part (%)", hdr_style),
        ]]
        for s_nom, s_cnt in sys_tries:
            pct_s = round(s_cnt / tot_sys * 100, 1) if tot_sys > 0 else 0.0
            sys_rows.append([
                Paragraph(f"<b>{s_nom}</b>", cell_center),
                Paragraph(str(s_cnt), cell_center),
                Paragraph(f"{pct_s}%", cell_center),
            ])
        t_sys = Table(sys_rows, colWidths=[230, 140, 140], repeatRows=1)
        t_sys.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), slate_dark),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_soft]),
            ("GRID", (0, 0), (-1, -1), 0.4, border_grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_sys)
    else:
        story.append(Paragraph("Aucun système offensif adverse renseigné sur la sélection.", body_style))

    # 2. Zones de tir adverses
    story.append(Paragraph("2. ZONES DE DÉPART DES TIRS ADVERSES", sec_style))
    ter_rows = [[
        Paragraph("Zone Terrain", hdr_style),
        Paragraph("Buts Adv.", hdr_style),
        Paragraph("Arrêts Nos Gard.", hdr_style),
        Paragraph("Total Tirs", hdr_style),
    ]]
    for z_nom, z_vals in (analyse.get("tirs_adv_par_terrain") or {}).items():
        if z_vals.get("total", 0) > 0:
            ter_rows.append([
                Paragraph(z_nom, cell_center),
                Paragraph(f"<b>{z_vals.get('buts', 0)}</b>", cell_center),
                Paragraph(str(z_vals.get("arrets_nos_gard", 0)), cell_center),
                Paragraph(str(z_vals.get("total", 0)), cell_center),
            ])
    if len(ter_rows) > 1:
        t_ter = Table(ter_rows, colWidths=[195, 105, 115, 95], repeatRows=1)
        t_ter.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), slate_dark),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_soft]),
            ("GRID", (0, 0), (-1, -1), 0.4, border_grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_ter)
    else:
        story.append(Paragraph("Aucune localisation de tir adverse enregistrée.", body_style))

    # 3. Profilage des gardiens adverses
    story.append(Paragraph("3. PROFILAGE DES GARDIEN(NE)S ADVERSES (NOS TIRS)", sec_style))
    profils_g = analyse.get("profils_gardiens_adv") or {}
    if profils_g:
        g_rows = [[
            Paragraph("Gardien(ne) / Période", hdr_style),
            Paragraph("Buts Marqués", hdr_style),
            Paragraph("Tirs Cadrés Ratés", hdr_style),
            Paragraph("Hors Cadre", hdr_style),
            Paragraph("Réussite Cadrée", hdr_style),
        ]]
        for g_nom, g_inf in profils_g.items():
            b_m = g_inf.get("buts_marques", 0)
            r_c = g_inf.get("tirs_cadres_rates", 0)
            h_c = g_inf.get("hors_cadre", 0)
            denom = b_m + r_c
            pct_r = f"{round(b_m / denom * 100, 1)}%" if denom > 0 else "-"
            g_rows.append([
                Paragraph(f"<b>{g_nom}</b>", cell_center),
                Paragraph(str(b_m), cell_center),
                Paragraph(str(r_c), cell_center),
                Paragraph(str(h_c), cell_center),
                Paragraph(pct_r, cell_center),
            ])
        t_g = Table(g_rows, colWidths=[170, 85, 95, 75, 85], repeatRows=1)
        t_g.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_soft]),
            ("GRID", (0, 0), (-1, -1), 0.4, border_grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_g)
    else:
        story.append(Paragraph("Aucune donnée de tir face aux gardien(ne)s adverses.", body_style))

    # 4. Temps morts adverses & cartons rouges
    tm_adv = analyse.get("temps_morts_adv") or []
    cr_list = analyse.get("cartons_rouges_journal") or []
    if tm_adv or cr_list:
        story.append(Paragraph("4. TEMPS MORTS ADVERSES & CARTONS ROUGES RELEVÉS", sec_style))
        ev_rows = [[
            Paragraph("Match", hdr_style),
            Paragraph("Moment", hdr_style),
            Paragraph("Événement", hdr_style),
            Paragraph("Détail", hdr_style),
        ]]
        for tm in tm_adv:
            ev_rows.append([
                Paragraph(tm.get("match", ""), cell_center),
                Paragraph(f"{tm.get('periode', '')} • {tm.get('temps', '')}", cell_center),
                Paragraph("Temps mort adverse", cell_center),
                Paragraph(tm.get("details", ""), body_style),
            ])
        for cr in cr_list:
            ev_rows.append([
                Paragraph(cr.get("match", ""), cell_center),
                Paragraph(f"{cr.get('periode', '')} • {cr.get('temps', '')}", cell_center),
                Paragraph(cr.get("type_action", "Carton Rouge"), cell_center),
                Paragraph(cr.get("details", ""), body_style),
            ])
        t_ev = Table(ev_rows, colWidths=[120, 95, 115, 180], repeatRows=1)
        t_ev.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), slate_dark),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_soft]),
            ("GRID", (0, 0), (-1, -1), 0.4, border_grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_ev)

    # 5. Notes scouting coach
    if notes_scouting and notes_scouting.strip():
        story.append(Paragraph("5. CONSIGNES & OBSERVATIONS SCOUTING", sec_style))
        story.append(Paragraph(notes_scouting.strip().replace("\n", "<br/>"), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def afficher_onglet_scouting_adversaire(
    joueuses_par_equipe: dict,
    club_nom: str = "Mon Club",
    equipe_nom: str = "Équipe",
    ctx_prefix: str = "default",
    dossier_club=None,
    peut_exporter: bool = True,
):
    """Affiche l'onglet complet de scouting et profilage multi-matchs des adversaires et gardien(ne)s."""
    st.subheader("🔎 Scouting & Profilage Multi-Matchs (Équipes & Gardien(ne)s Adverses)")

    matchs_dict = collecter_matchs_archives(joueuses_par_equipe)
    if not matchs_dict:
        st.info("Aucun match archivé disponible pour effectuer du scouting adverse.")
        return

    noms_matchs_dispos = list(matchs_dict.keys())
    adversaires_detectes = sorted({matchs_dict[m]["adversaire"] for m in noms_matchs_dispos})

    col_adv, col_matchs = st.columns([1.6, 2.4])
    with col_adv:
        options_adv = ["Tous / Sélection manuelle"] + adversaires_detectes
        adv_choisi = st.selectbox(
            "🎯 Cibler un adversaire",
            options_adv,
            key=f"scout_sel_adv_{ctx_prefix}",
        )

    if adv_choisi == "Tous / Sélection manuelle":
        matchs_par_defaut = noms_matchs_dispos
        titre_cible = "Sélection multi-matchs"
    else:
        matchs_par_defaut = [m for m in noms_matchs_dispos if matchs_dict[m]["adversaire"] == adv_choisi]
        titre_cible = adv_choisi

    with col_matchs:
        matchs_retenus = st.multiselect(
            "🗂️ Matchs archivés inclus dans l'analyse",
            options=noms_matchs_dispos,
            default=matchs_par_defaut,
            key=f"scout_ms_matchs_{ctx_prefix}_{adv_choisi}",
        )

    if not matchs_retenus:
        st.warning("Sélectionnez au moins un match archivé pour afficher le profilage.")
        return

    selection_objs = [matchs_dict[m] for m in matchs_retenus if m in matchs_dict]
    analyse = analyser_profil_adversaire(selection_objs)

    # KPIs globaux
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Bilan sur la sélection", analyse["bilan"], f"{analyse['nb_matchs']} match(s)")
    k2.metric("Buts Marqués / Match", analyse["moy_buts_pour"], f"Cumul : {analyse['buts_pour_cumul']}")
    k3.metric("Buts Encaissés / Match", analyse["moy_buts_contre"], f"Cumul : {analyse['buts_contre_cumul']}")
    k4.metric("Système N°1 Adverse", analyse["systeme_principal"], f"Zone choc : {analyse['zone_dangereuse_adv']}")

    st.divider()

    sous_onglet_eq_adv, sous_onglet_gard_adv, sous_onglet_export_scout = st.tabs([
        "⚔️ Profilage Équipe Adverse",
        "🧤 Profilage Gardien(ne)s Adverses",
        "📄 Fiche Scouting & Export PDF",
    ])

    # --- SOUS-ONGLET 1 : ÉQUIPE ADVERSE ---
    with sous_onglet_eq_adv:
        st.markdown("#### 📊 Systèmes Offensifs Adverses")
        if analyse["total_systemes"] > 0:
            rows_sys = []
            for s_nom, s_cnt in analyse["systemes_tries"]:
                pct_s = round(s_cnt / analyse["total_systemes"] * 100, 1)
                rows_sys.append({
                    "Système": s_nom,
                    "Occurrences": s_cnt,
                    "Part (%)": f"{pct_s}%",
                })
            st.dataframe(rows_sys, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun système offensif adverse enregistré sur ces matchs.")

        st.markdown("#### 📍 Répartition des Tirs Adverses par Zone de Terrain")
        rows_ter = []
        for z_nom, z_inf in analyse["tirs_adv_par_terrain"].items():
            if z_inf["total"] > 0:
                eff_z = round(z_inf["buts"] / z_inf["total"] * 100, 1)
                rows_ter.append({
                    "Zone Terrain": z_nom,
                    "Buts Adverses": z_inf["buts"],
                    "Arrêts Nos Gardien(ne)s": z_inf["arrets_nos_gard"],
                    "Total Tirs": z_inf["total"],
                    "Réussite Adv.": f"{eff_z}%",
                })
        if rows_ter:
            st.dataframe(rows_ter, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée de zone de terrain enregistrée sur les tirs adverses.")

        st.markdown("#### 🎯 Cartographie des Frappes Adverses dans la Cage")
        afficher_cage_recapitulative(
            analyse["cage_tirs_adv"],
            titre="Frappes Adverses (Succès = But adverse | Échec = Arrêt de notre gardienne)",
            inclure_hors_cadre=False,
        )

        b_p = analyse["buts_adv_par_periode"]
        st.caption(
            f"Répartition des buts adverses par période : **1ère MT : {b_p.get('1ère MT', 0)}** • "
            f"**2ème MT : {b_p.get('2ème MT', 0)}** • **Autre : {b_p.get('Autre', 0)}**"
        )

        if analyse["temps_morts_adv"]:
            st.markdown("#### ⏱️ Moments des Temps Morts Adverses")
            st.dataframe(analyse["temps_morts_adv"], use_container_width=True, hide_index=True)

    # --- SOUS-ONGLET 2 : GARDIEN(NE)S ADVERSES ---
    with sous_onglet_gard_adv:
        profils_g = analyse["profils_gardiens_adv"]
        if not profils_g:
            st.info("Aucun tir de votre équipe n'est enregistré sur cette sélection.")
        else:
            noms_gardiens = list(profils_g.keys())
            g_selectionne = st.selectbox(
                "🧤 Sélectionner un profil de gardien(ne) adverse (rotations / mi-temps)",
                ["Toutes les gardiennes (cumul)"] + noms_gardiens,
                key=f"scout_sel_gard_{ctx_prefix}_{adv_choisi}",
            )

            if g_selectionne == "Toutes les gardiennes (cumul)":
                cage_cumul = {z: {"succes": 0, "echec": 0} for z in ZONES_CAGE_9}
                buts_tot = 0
                rates_cadres_tot = 0
                hc_tot = 0
                for g_inf in profils_g.values():
                    buts_tot += g_inf["buts_marques"]
                    rates_cadres_tot += g_inf["tirs_cadres_rates"]
                    hc_tot += g_inf["hors_cadre"]
                    for z, vals in g_inf["par_zone_cage"].items():
                        cage_cumul[z]["succes"] += vals.get("succes", 0)
                        cage_cumul[z]["echec"] += vals.get("echec", 0)

                c_g1, c_g2, c_g3 = st.columns(3)
                c_g1.metric("Buts Marqués", buts_tot)
                c_g2.metric("Tirs Cadrés Ratés", rates_cadres_tot)
                c_g3.metric("Tirs Hors Cadre", hc_tot)

                afficher_cage_recapitulative(
                    cage_cumul,
                    titre="Zones de Cage — Nos Tirs (Succès = Buts marqués | Échec = Tirs cadrés non marqués)",
                    inclure_hors_cadre=False,
                )

                resume_g_rows = []
                for nom_g, g_inf in profils_g.items():
                    bm = g_inf["buts_marques"]
                    rc = g_inf["tirs_cadres_rates"]
                    hc = g_inf["hors_cadre"]
                    denom = bm + rc
                    resume_g_rows.append({
                        "Gardien(ne) / Période": nom_g,
                        "Buts Marqués": bm,
                        "Tirs Cadrés Ratés": rc,
                        "Hors Cadre": hc,
                        "% Réussite Cadrée": f"{round(bm / denom * 100, 1)}%" if denom > 0 else "-",
                    })
                st.markdown("#### 📋 Comparatif par Gardien(ne) / Période")
                st.dataframe(resume_g_rows, use_container_width=True, hide_index=True)

            else:
                g_inf = profils_g[g_selectionne]
                bm = g_inf["buts_marques"]
                rc = g_inf["tirs_cadres_rates"]
                hc = g_inf["hors_cadre"]
                denom = bm + rc

                c_g1, c_g2, c_g3, c_g4 = st.columns(4)
                c_g1.metric("Buts Marqués", bm)
                c_g2.metric("Tirs Cadrés Ratés", rc)
                c_g3.metric("Hors Cadre", hc)
                c_g4.metric("% Réussite Cadrée", f"{round(bm / denom * 100, 1)}%" if denom > 0 else "-")

                afficher_cage_recapitulative(
                    g_inf["par_zone_cage"],
                    titre=f"Zones de Cage face à {g_selectionne} (Succès = Buts | Échec = Cadrés non marqués)",
                    inclure_hors_cadre=False,
                )

                rows_zt_g = []
                for z_ter, z_inf in g_inf["par_zone_terrain"].items():
                    if z_inf["total"] > 0:
                        rows_zt_g.append({
                            "Zone Terrain": z_ter,
                            "Buts": z_inf["buts"],
                            "Cadrés Ratés": z_inf["echec_cadre"],
                            "Hors Cadre": z_inf["hors_cadre"],
                            "Total Tirs": z_inf["total"],
                        })
                if rows_zt_g:
                    st.markdown("#### 📍 Efficacité par Zone de Terrain face à ce Profil")
                    st.dataframe(rows_zt_g, use_container_width=True, hide_index=True)

    # --- SOUS-ONGLET 3 : EXPORT PDF SCOUTING ---
    with sous_onglet_export_scout:
        notes_scout = st.text_area(
            "📝 Consignes / axes de travail avant match",
            placeholder="Ex : Fixer sur le secteur central puis jouer l'aile opposée ; viser le haut de cage sur les tirs extérieurs...",
            height=110,
            key=f"scout_notes_{ctx_prefix}_{adv_choisi}",
        )

        if not peut_exporter:
            st.info("🔒 L'export PDF n'est pas activé pour votre profil.")
        else:
            pdf_bytes = generer_pdf_scouting_adversaire(
                nom_adversaire=titre_cible,
                noms_matchs=matchs_retenus,
                analyse=analyse,
                club_nom=club_nom,
                equipe_nom=equipe_nom,
                notes_scouting=notes_scout,
                dossier_club=dossier_club,
            )
            nom_fichier_pdf = re.sub(r"[^a-zA-Z0-9_-]+", "_", titre_cible).strip("_") or "adversaire"
            st.download_button(
                "📥 Télécharger la Fiche Scouting (PDF)",
                data=pdf_bytes,
                file_name=f"scouting_{nom_fichier_pdf}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_scouting_{ctx_prefix}_{nom_fichier_pdf}",
            )