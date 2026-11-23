import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def detecter_genre(nom_equipe):
    nom_l = str(nom_equipe).lower()
    if re.search(r'(^|[\s(\[_-])(f|fem|feminine|féminine|fille|filles)([\s)\]_.-]|$)', nom_l):
        return "F"
    if re.search(r'(^|[\s(\[_-])(m|masc|masculin|garcon|garçon|garcons|garçons|h)([\s)\]_.-]|$)', nom_l):
        return "M"
    return "F"


def _resoudre_logo_club(dossier_club=None):
    if dossier_club:
        candidat_club = os.path.join(dossier_club, "logo_club.png")
        if os.path.exists(candidat_club):
            return candidat_club
    if os.path.exists("logo_club.png"):
        return "logo_club.png"
    return None


def creer_bandeau_en_tete(club_nom, equipe_nom, styles, dossier_club=None):
    """Crée un bandeau exécutif ultra-pro avec le nom du club, l'équipe et le logo à droite."""
    logo_path = _resoudre_logo_club(dossier_club)

    style_club = ParagraphStyle(
        'BandeauClub', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=colors.HexColor("#FFFFFF")
    )
    style_team = ParagraphStyle(
        'BandeauTeam', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor("#38BDF8")
    )

    text_content = [
        Paragraph(club_nom.upper(), style_club),
        Spacer(1, 2),
        Paragraph(f"Équipe : {equipe_nom} — Rapport Officiel & Analytique Pro", style_team)
    ]

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=44, height=44)
            img.hAlign = 'RIGHT'
            cell_right = img
        except Exception:
            cell_right = Paragraph("<b>CLUB</b>", ParagraphStyle('BandeauRight', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=8, textColor=colors.white))
    else:
        cell_right = Paragraph("", styles['Normal'])

    bandeau_table = Table([[text_content, cell_right]], colWidths=[435, 110])
    bandeau_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0A192F")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor("#38BDF8")),
    ]))
    return bandeau_table


def _extraire_compte_zone(zone_val):
    """Supporte les formats dict {'buts': b, 'tirs': t} ou {'succes': s, 'echec': e}."""
    if not isinstance(zone_val, dict):
        return 0, 0
    if "buts" in zone_val or "tirs" in zone_val:
        return int(zone_val.get("buts", 0) or 0), int(zone_val.get("tirs", 0) or 0)
    succes = int(zone_val.get("succes", 0) or 0)
    echec = int(zone_val.get("echec", 0) or 0)
    return succes, succes + echec


_ALIAS_ZONES_CAGE = {
    "H_G": ["H_G", "Haut-Gauche"],
    "H_C": ["H_C", "Haut-Centre"],
    "H_D": ["H_D", "Haut-Droite"],
    "M_G": ["M_G", "Milieu-Gauche"],
    "M_C": ["M_C", "Milieu-Centre"],
    "M_D": ["M_D", "Milieu-Droite"],
    "B_G": ["B_G", "Bas-Gauche"],
    "B_C": ["B_C", "Bas-Centre"],
    "B_D": ["B_D", "Bas-Droite"],
    "HC": ["HC", "Hors cadre"],
}


def _sommer_cles_zone(zones_data, cles_possibles):
    total_reussis = 0
    total_tirs = 0
    for cle in cles_possibles:
        val = zones_data.get(cle)
        if val is not None:
            b, t = _extraire_compte_zone(val)
            total_reussis += b
            total_tirs += t
    return total_reussis, total_tirs


def generer_grille_3x3_avec_hc(zones_data, styles, est_gardien=False):
    """Génère la grille 3x3 de la cage et intègre proprement la case 'Hors-Cadre' (HC)."""
    if not zones_data:
        zones_data = {}

    def get_zone_cell(zone_key, label_nom):
        b, t = _sommer_cles_zone(zones_data, _ALIAS_ZONES_CAGE.get(zone_key, [zone_key]))
        pct = round((b / t * 100), 1) if t > 0 else 0.0

        if t == 0:
            text_col = "#64748B"
        elif pct >= 60:
            text_col = "#065F46"
        elif pct >= 40:
            text_col = "#B45309"
        else:
            text_col = "#991B1B"

        cell_text = (
            f"<b>{label_nom}</b><br/>"
            f"<font size=10 color='{text_col}'><b>{b}/{t}</b></font><br/>"
            f"<font size=7 color='{text_col}'>({pct}%)</font>"
        )
        return Paragraph(
            cell_text,
            ParagraphStyle("ZoneGrid", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8, leading=10),
        )

    grid_data = [
        [get_zone_cell("H_G", "Haut Gauche"), get_zone_cell("H_C", "Haut Centre"), get_zone_cell("H_D", "Haut Droite")],
        [get_zone_cell("M_G", "Milieu Gauche"), get_zone_cell("M_C", "Centre"), get_zone_cell("M_D", "Milieu Droite")],
        [get_zone_cell("B_G", "Bas Gauche"), get_zone_cell("B_C", "Bas Centre"), get_zone_cell("B_D", "Bas Droite")],
    ]

    t_grid = Table(grid_data, colWidths=[130, 130, 130])
    t_grid.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1.5, colors.HexColor("#0A192F")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements_carto = [t_grid]

    if not est_gardien:
        _, hc_tirs = _sommer_cles_zone(zones_data, _ALIAS_ZONES_CAGE["HC"])

        hc_text = f"<b>Tirs Hors-Cadre (Ratés) :</b> <font color='#DC2626'><b>{hc_tirs} tirs</b></font>"
        t_hc = Table(
            [[Paragraph(hc_text, ParagraphStyle("HCText", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9, leading=12, textColor=colors.HexColor("#1E293B")))]],
            colWidths=[390],
        )
        t_hc.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEE2E2")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#EF4444")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements_carto.append(Spacer(1, 8))
        elements_carto.append(t_hc)

    return elements_carto

def _extraire_pertes(row):
    p_passe = row.get("Perte (Passe)", row.get("pertes_passe", row.get("pertes_de_balles_passe", 0)))
    p_faute = row.get("Perte (Faute)", row.get("pertes_faute", row.get("pertes_de_balles_faute", 0)))
    return p_passe, p_faute

def _formater_nom_avec_capitaine(nom, capitaine=None):
    nom_str = str(nom or "")
    if capitaine and nom_str.strip() == str(capitaine).strip():
        if not nom_str.endswith("(C)"):
            return f"{nom_str} (C)"
    return nom_str

def generer_pdf_match(
    nom_match, score_eq, score_adv, lignes_champ, lignes_gardiennes,
    zones_tirs=None, zones_gardiennes=None, attaques_adversaires=None,
    club_nom="Mon Club", equipe_nom="Équipe", dossier_club=None, capitaine=None
):
    genre = detecter_genre(equipe_nom)
    if genre == "M":
        titre_champ = "COMPOSITION DE L'ÉQUIPE — JOUEURS DE CHAMP"
        col_nom_j = "Nom du Joueur"
        titre_gard = "COMPOSITION DE L'ÉQUIPE — GARDIENS"
        col_nom_g = "Nom du Gardien"
        label_champ_col = "Joueur"
    else:
        titre_champ = "COMPOSITION DE L'ÉQUIPE — JOUEUSES DE CHAMP"
        col_nom_j = "Nom de la Joueuse"
        titre_gard = "COMPOSITION DE L'ÉQUIPE — GARDIENNES"
        col_nom_g = "Nom de la Gardienne"
        label_champ_col = "Joueuse"

    def tri_num(x):
        try:
            return int(x.get("N°", 999))
        except (TypeError, ValueError):
            return 999

    lignes_champ_triees = sorted(lignes_champ or [], key=tri_num)
    lignes_gardiennes_triees = sorted(lignes_gardiennes or [], key=tri_num)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25, leftMargin=25,
        topMargin=25, bottomMargin=25
    )

    styles = getSampleStyleSheet()

    primary_color = colors.HexColor("#0A192F")
    accent_red = colors.HexColor("#E63946")
    bg_light = colors.HexColor("#F8FAFC")
    border_color = colors.HexColor("#CBD5E1")
    text_dark = colors.HexColor("#1E293B")

    header_org = ParagraphStyle('HeaderOrg', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor("#64748B"), alignment=TA_CENTER)
    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=primary_color, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=accent_red, alignment=TA_CENTER)
    h1_style = ParagraphStyle('SectionH1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=primary_color, spaceAfter=4, spaceBefore=6)
    cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=text_dark, alignment=TA_CENTER)
    cell_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)

    story = []

    # =========================================================================
    # PAGE 1 : FEUILLE DE MATCH OFFICIELLE (Modèle FFHB Expert)
    # =========================================================================
    story.append(creer_bandeau_en_tete(club_nom, equipe_nom, styles, dossier_club=dossier_club))
    story.append(Spacer(1, 10))

    story.append(Paragraph("FÉDÉRATION FRANÇAISE DE HANDBALL — RAPPORT OFFICIEL", header_org))
    story.append(Spacer(1, 2))
    story.append(Paragraph("FEUILLE DE MATCH OFFICIELLE", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(nom_match, subtitle_style))
    story.append(Spacer(1, 8))

    res_text = "VICTOIRE" if score_eq > score_adv else ("DÉFAITE" if score_eq < score_adv else "MATCH NUL")
    res_color = "#059669" if score_eq > score_adv else ("#DC2626" if score_eq < score_adv else "#D97706")

    score_data = [
        [Paragraph(f"<font color='{res_color}'><b>{res_text}</b></font>", ParagraphStyle('Res', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER))],
        [Paragraph(f"<b>{score_eq} — {score_adv}</b>", ParagraphStyle('Sc', parent=styles['Normal'], fontSize=22, leading=26, fontName='Helvetica-Bold', textColor=primary_color, alignment=TA_CENTER))]
    ]
    t_score = Table(score_data, colWidths=[545])
    t_score.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#94A3B8")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_score)
    story.append(Spacer(1, 10))

    story.append(Paragraph(titre_champ, h1_style))
    headers_ffh_c = ["N°", col_nom_j, "Poste", "Buts", "Tirs", "% Réussite", "Avert.", "2min"]
    table_data_ffh_c = [[Paragraph(h, cell_header_style) for h in headers_ffh_c]]

    for row in lignes_champ_triees:
        b = row.get("Buts", 0)
        t = row.get("Tirs", 0)
        pct = f"{round((b / t * 100), 1)}%" if t > 0 else "0.0%"
        nom_j_val = str(row.get("Joueuse", row.get("Joueur", "")))
        nom_j_aff = _formater_nom_avec_capitaine(nom_j_val, capitaine)
        table_data_ffh_c.append([
            Paragraph(str(row.get("N°", "")), cell_style),
            Paragraph(nom_j_aff, ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
            Paragraph(str(row.get("Poste", "")), cell_style),
            Paragraph(str(b), cell_style),
            Paragraph(str(t), cell_style),
            Paragraph(pct, cell_style),
            Paragraph(str(row.get("🟨", 0)), cell_style),
            Paragraph(str(row.get("⏱️ 2min", 0)), cell_style),
        ])

    t_ffh_champ = Table(table_data_ffh_c, colWidths=[25, 190, 115, 35, 35, 50, 45, 50])
    t_ffh_champ.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_ffh_champ)
    story.append(Spacer(1, 8))

    if lignes_gardiennes_triees:
        story.append(Paragraph(titre_gard, h1_style))
        headers_ffh_g = ["N°", col_nom_g, "Arrêts", "Tirs Subis", "% Arrêts", "Buts Encaissés", "Avert.", "2min"]
        table_data_ffh_g = [[Paragraph(h, cell_header_style) for h in headers_ffh_g]]
        for row in lignes_gardiennes_triees:
            nom_g_val = str(row.get("Gardienne", row.get("Gardien", "")))
            nom_g_aff = _formater_nom_avec_capitaine(nom_g_val, capitaine)
            table_data_ffh_g.append([
                Paragraph(str(row.get("N°", "")), cell_style),
                Paragraph(nom_g_aff, ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
                Paragraph(str(row.get("Arrêts", 0)), cell_style),
                Paragraph(str(row.get("Tirs Subis", 0)), cell_style),
                Paragraph(str(row.get("% Arrêts", "0%")), cell_style),
                Paragraph(str(row.get("Buts Encaissés", 0)), cell_style),
                Paragraph(str(row.get("🟨", 0)), cell_style),
                Paragraph(str(row.get("⏱️ 2min", 0)), cell_style),
            ])
        t_ffh_gard = Table(table_data_ffh_g, colWidths=[25, 205, 55, 65, 60, 75, 30, 30])
        t_ffh_gard.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_ffh_gard)

    # =========================================================================
    # PAGE 2 : RAPPORT GLOBAL OFFENSIF + CARTOGRAPHIE COLLECTIVE DES TIRS
    # =========================================================================
    story.append(PageBreak())
    story.append(creer_bandeau_en_tete(club_nom, equipe_nom, styles, dossier_club=dossier_club))
    story.append(Spacer(1, 10))

    story.append(Paragraph("RAPPORT STATISTIQUE GLOBAL — OFFENSIVE", header_org))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Synthèse Offensive & Cartographie Collective des Tirs", title_style))
    story.append(Spacer(1, 10))

    headers_off = ["N°", label_champ_col, "Poste", "Buts", "Tirs", "% Réussite", "Passes D.", "Pertes (P/F)"]
    table_data_off = [[Paragraph(h, cell_header_style) for h in headers_off]]

    for row in lignes_champ_triees:
        b = row.get("Buts", 0)
        t = row.get("Tirs", 0)
        pct = f"{round((b / t * 100), 1)}%" if t > 0 else "0.0%"
        pd = row.get("Passes D.", 0)
        p_passe, p_faute = _extraire_pertes(row)
        nom_j_val = str(row.get("Joueuse", row.get("Joueur", "")))

        table_data_off.append([
            Paragraph(str(row.get("N°", "")), cell_style),
            Paragraph(_formater_nom_avec_capitaine(nom_j_val, capitaine), ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
            Paragraph(str(row.get("Poste", "")), cell_style),
            Paragraph(str(b), cell_style),
            Paragraph(str(t), cell_style),
            Paragraph(pct, cell_style),
            Paragraph(str(pd), cell_style),
            Paragraph(f"{p_passe} / {p_faute}", cell_style),
        ])

    t_off = Table(table_data_off, colWidths=[25, 170, 110, 40, 40, 60, 45, 55])
    t_off.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_off)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Cartographie Collective des Tirs (Cage 3x3)</b>", h1_style))
    story.append(Spacer(1, 4))
    for el in generer_grille_3x3_avec_hc(zones_tirs, styles, est_gardien=False):
        story.append(el)

    # =========================================================================
    # PAGE 3 : RAPPORT GLOBAL DÉFENSIF + GARDIENNES + CARTO COLLECTIVE GARDIENNES
    # =========================================================================
    story.append(PageBreak())
    story.append(creer_bandeau_en_tete(club_nom, equipe_nom, styles, dossier_club=dossier_club))
    story.append(Spacer(1, 10))

    story.append(Paragraph("RAPPORT STATISTIQUE GLOBAL — DÉFENSE & GARDIENS", header_org))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Impact Défensif, Synthèse & Cartographie des Gardiens", title_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>1. Activité Défensive & Duels</b>", h1_style))
    headers_def = ["N°", label_champ_col, "Duels Off.", "Duels Déf.", "Interceptions", "Neutralisations", "Ballons Prov."]
    table_data_def = [[Paragraph(h, cell_header_style) for h in headers_def]]

    for row in lignes_champ_triees:
        nom_j_val = str(row.get("Joueuse", row.get("Joueur", "")))
        nom_j_aff = _formater_nom_avec_capitaine(nom_j_val, capitaine)
        table_data_def.append([
            Paragraph(str(row.get("N°", "")), cell_style),
            Paragraph(nom_j_aff, ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
            Paragraph(str(row.get("Duels Off", "0/0")), cell_style),
            Paragraph(str(row.get("Duels Déf", "0/0")), cell_style),
            Paragraph(str(row.get("Interceptions", 0)), cell_style),
            Paragraph(str(row.get("Neutralisations", 0)), cell_style),
            Paragraph(str(row.get("Provoquées", 0)), cell_style),
        ])

    t_def = Table(table_data_def, colWidths=[30, 195, 75, 75, 55, 60, 55])
    t_def.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_def)
    story.append(Spacer(1, 8))

    if lignes_gardiennes_triees:
        story.append(Paragraph("<b>2. Synthèse & Performance des Gardiennes / Gardiens</b>", h1_style))
        headers_g_exp = ["N°", col_nom_g, "Arrêts", "Tirs Subis", "% Arrêts", "Buts Encaissés"]
        table_data_g_exp = [[Paragraph(h, cell_header_style) for h in headers_g_exp]]
        for row in lignes_gardiennes_triees:
            nom_g_val = str(row.get("Gardienne", row.get("Gardien", "")))
            nom_g_aff = _formater_nom_avec_capitaine(nom_g_val, capitaine)
            table_data_g_exp.append([
                Paragraph(str(row.get("N°", "")), cell_style),
                Paragraph(nom_g_aff, ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
                Paragraph(str(row.get("Arrêts", 0)), cell_style),
                Paragraph(str(row.get("Tirs Subis", 0)), cell_style),
                Paragraph(str(row.get("% Arrêts", "0%")), cell_style),
                Paragraph(str(row.get("Buts Encaissés", 0)), cell_style),
            ])
        t_g_exp = Table(table_data_g_exp, colWidths=[30, 215, 70, 75, 75, 80])
        t_g_exp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_g_exp)
        story.append(Spacer(1, 8))

        story.append(Paragraph("<b>3. Cartographie Collective des Arrêts (Cage 3x3)</b>", h1_style))
        story.append(Spacer(1, 2))
        carto_g_data = zones_gardiennes if zones_gardiennes is not None else {}
        for el in generer_grille_3x3_avec_hc(carto_g_data, styles, est_gardien=True):
            story.append(el)

    # =========================================================================
    # PAGES 4 À X : RAPPORT INDIVIDUEL PAR JOUEUSE (1 page par joueuse)
    # =========================================================================
    tous_les_membres = []
    for r in lignes_champ_triees:
        r_copy = r.copy()
        r_copy["_type"] = "champ"
        tous_les_membres.append(r_copy)
    for r in lignes_gardiennes_triees:
        r_copy = r.copy()
        r_copy["_type"] = "gardienne"
        tous_les_membres.append(r_copy)

    tous_les_membres = sorted(tous_les_membres, key=tri_num)

    for membre in tous_les_membres:
        story.append(PageBreak())
        story.append(creer_bandeau_en_tete(club_nom, equipe_nom, styles, dossier_club=dossier_club))
        story.append(Spacer(1, 10))

        num = membre.get("N°", "")
        nom = membre.get("Joueuse", membre.get("Joueur", membre.get("Gardienne", membre.get("Gardien", "Inconnu"))))
        est_gardienne = (membre["_type"] == "gardienne")

        if est_gardienne:
            poste = membre.get("Poste", "Gardienne" if genre == "F" else "Gardien")
        else:
            poste = membre.get("Poste", "Joueuse de champ" if genre == "F" else "Joueur de champ")

        story.append(Paragraph(f"RAPPORT INDIVIDUEL — {poste}", header_org))
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"{num} — {_formater_nom_avec_capitaine(nom, capitaine).upper()}", title_style))
        story.append(Spacer(1, 10))

        if not est_gardienne:
            b = membre.get("Buts", 0)
            t = membre.get("Tirs", 0)
            pct = f"{round((b / t * 100), 1)}%" if t > 0 else "0.0%"
            pd = membre.get("Passes D.", 0)
            p_passe, p_faute = _extraire_pertes(membre)
            duels_off = membre.get("Duels Off", "0/0")
            duels_def = membre.get("Duels Déf", "0/0")
            inter = membre.get("Interceptions", 0)
            neut = membre.get("Neutralisations", 0)
            prov = membre.get("Provoquées", 0)
            jaune = membre.get("🟨", 0)
            e2min = membre.get("⏱️ 2min", 0)

            stats_data = [
                [Paragraph("<b>Indicateur</b>", cell_header_style), Paragraph("<b>Valeur</b>", cell_header_style)],
                [Paragraph("Buts / Tirs", cell_style), Paragraph(f"<b>{b} / {t} ({pct})</b>", cell_style)],
                [Paragraph("Passes Décisives", cell_style), Paragraph(str(pd), cell_style)],
                [Paragraph("Pertes de Balle (Passe / Faute)", cell_style), Paragraph(f"{p_passe} / {p_faute}", cell_style)],
                [Paragraph("Duels Offensifs", cell_style), Paragraph(str(duels_off), cell_style)],
                [Paragraph("Duels Défensifs", cell_style), Paragraph(str(duels_def), cell_style)],
                [Paragraph("Interceptions", cell_style), Paragraph(str(inter), cell_style)],
                [Paragraph("Neutralisations", cell_style), Paragraph(str(neut), cell_style)],
                [Paragraph("Ballons Provoqués", cell_style), Paragraph(str(prov), cell_style)],
                [Paragraph("Discipline (Jaune / 2min)", cell_style), Paragraph(f"{jaune} / {e2min}", cell_style)],
            ]
        else:
            arr = membre.get("Arrêts", 0)
            subis = membre.get("Tirs Subis", 0)
            pct_arr = membre.get("% Arrêts", "0%")
            encaisses = membre.get("Buts Encaissés", 0)
            jaune = membre.get("🟨", 0)
            e2min = membre.get("⏱️ 2min", 0)

            stats_data = [
                [Paragraph("<b>Indicateur</b>", cell_header_style), Paragraph("<b>Valeur</b>", cell_header_style)],
                [Paragraph("Arrêts / Tirs Subis", cell_style), Paragraph(f"<b>{arr} / {subis} ({pct_arr})</b>", cell_style)],
                [Paragraph("Buts Encaissés", cell_style), Paragraph(str(encaisses), cell_style)],
                [Paragraph("Discipline (Jaune / 2min)", cell_style), Paragraph(f"{jaune} / {e2min}", cell_style)],
            ]

        t_indiv = Table(stats_data, colWidths=[240, 305])
        t_indiv.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_indiv)
        story.append(Spacer(1, 10))

        titre_carto = "Cartographie Individuelle des Arrêts (Cage 3x3)" if est_gardienne else "Cartographie Individuelle des Tirs (Cage 3x3)"
        story.append(Paragraph(f"<b>{titre_carto}</b>", h1_style))
        story.append(Spacer(1, 4))

        zones_indiv = membre.get("zones_tirs", {})
        for el in generer_grille_3x3_avec_hc(zones_indiv, styles, est_gardien=est_gardienne):
            story.append(el)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
