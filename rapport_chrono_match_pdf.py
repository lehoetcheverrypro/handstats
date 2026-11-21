import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import cm


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
    """Crée un bandeau professionnel moderne avec le club, l'équipe et le logo."""
    logo_path = _resoudre_logo_club(dossier_club)

    style_club = ParagraphStyle(
        'BandeauClub', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=13, leading=15, textColor=colors.white
    )
    style_team = ParagraphStyle(
        'BandeauTeam', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor("#38BDF8")
    )
    style_tag = ParagraphStyle(
        'BandeauTag', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#CBD5E1")
    )

    text_content = [
        Paragraph(club_nom.upper(), style_club),
        Spacer(1, 2),
        Paragraph(f"CELLULE PERFORMANCE & ANALYSE VIDEO — Équipe : {equipe_nom}", style_team),
        Paragraph("Document interne réservé au Staff Technique", style_tag)
    ]

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=42, height=42)
            img.hAlign = 'RIGHT'
            cell_right = img
        except Exception:
            cell_right = Paragraph("<b>STAFF PRO</b>", ParagraphStyle('BandeauRight', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=8, textColor=colors.white))
    else:
        cell_right = Paragraph("", styles['Normal'])

    bandeau_table = Table([[text_content, cell_right]], colWidths=[415, 95])
    bandeau_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
    ]))
    return bandeau_table


def _style_ligne_action(type_action):
    """Retourne (couleur_fond, couleur_texte_action) selon le type d'action."""
    act_low = str(type_action).lower()
    if "but encaissé" in act_low or "tir raté" in act_low or "perte" in act_low or ("duel" in act_low and "perdu" in act_low):
        return colors.HexColor("#FEF2F2"), "#B91C1C"
    elif "but" in act_low or "arrêt" in act_low or "gagné" in act_low or "interception" in act_low or "provoquée" in act_low or "passe décisive" in act_low or "neutralisation" in act_low:
        return colors.HexColor("#F0FDF4"), "#15803D"
    elif "rouge" in act_low:
        return colors.HexColor("#FEE2E2"), "#991B1B"
    elif "jaune" in act_low or "2min" in act_low or "exclusion" in act_low:
        return colors.HexColor("#FFFBEB"), "#B45309"
    elif "temps mort" in act_low:
        return colors.HexColor("#F3E8FF"), "#6B21A8"
    elif "attaque adverse" in act_low:
        return colors.HexColor("#EFF6FF"), "#1D4ED8"
    elif "repère mi-temps" in act_low:
        return colors.HexColor("#E0F2FE"), "#0369A1"
    return colors.white, "#1E293B"

def _formater_horodatage(item):
    temps_str = str(item.get("temps", "00:00"))
    periode_str = str(item.get("periode", "")).strip()
    horodatage_reel = str(item.get("horodatage_reel", "")).strip()

    repere_match = f"{periode_str} • {temps_str}" if periode_str else temps_str
    if horodatage_reel:
        return f"<b>{repere_match}</b><br/><font color='#64748B' size='7.5'>Réel : {horodatage_reel}</font>"
    return f"<b>{repere_match}</b>"

def generer_pdf_chronologique(
    nom_match, score_eq, score_adv, historique_actions,
    attaques_adv, commentaires_staff, club_nom="Mon Club",
    equipe_nom="Équipe", bilan_post_match="", dossier_club=None
):
    genre = detecter_genre(equipe_nom)
    col_detail_libelle = "Joueur / Détail de la séquence" if genre == "M" else "Joueuse / Détail de la séquence"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm
    )

    story = []
    styles = getSampleStyleSheet()

    navy = colors.HexColor("#0F172A")
    slate_dark = colors.HexColor("#1E293B")
    slate_muted = colors.HexColor("#475569")
    accent_blue = colors.HexColor("#0284C7")
    bg_soft = colors.HexColor("#F8FAFC")
    border_grey = colors.HexColor("#CBD5E1")

    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=16, leading=20, textColor=navy, alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=10, leading=14, textColor=accent_blue, alignment=TA_CENTER
    )
    section_header_style = ParagraphStyle(
        'SecHeader', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=11, leading=14, textColor=navy, spaceBefore=12, spaceAfter=6
    )
    normal_style = ParagraphStyle(
        'BodyText', parent=styles['Normal'], fontName='Helvetica',
        fontSize=9, leading=13, textColor=slate_dark
    )
    bold_center_style = ParagraphStyle(
        'BoldCenter', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=9, leading=12, textColor=slate_dark, alignment=TA_CENTER
    )
    table_header_style = ParagraphStyle(
        'TblHeader', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=9, leading=11, textColor=colors.white, alignment=TA_CENTER
    )

    # 1. EN-TÊTE ET CARTOUCHE SCORE
    story.append(creer_bandeau_en_tete(club_nom, equipe_nom, styles, dossier_club=dossier_club))
    story.append(Spacer(1, 12))

    story.append(Paragraph("RAPPORT D'ANALYSE TACTIQUE & CHRONOLOGIQUE", title_style))
    story.append(Paragraph(f"Rencontre : {nom_match.upper()}", subtitle_style))
    story.append(Spacer(1, 8))

    if score_eq > score_adv:
        statut_txt, statut_hex = "VICTOIRE", "#15803D"
    elif score_eq < score_adv:
        statut_txt, statut_hex = "DÉFAITE", "#B91C1C"
    else:
        statut_txt, statut_hex = "MATCH NUL", "#B45309"

    score_box_data = [[
        Paragraph(f"<font color='#64748B' size='8'><b>RÉSULTAT</b></font><br/><font color='{statut_hex}' size='11'><b>{statut_txt}</b></font>", ParagraphStyle('S1', parent=styles['Normal'], alignment=TA_CENTER, leading=14)),
        Paragraph(f"<font color='#64748B' size='8'><b>SCORE FINAL</b></font><br/><font color='#0F172A' size='18'><b>{score_eq}  —  {score_adv}</b></font>", ParagraphStyle('S2', parent=styles['Normal'], alignment=TA_CENTER, leading=20)),
        Paragraph(f"<font color='#64748B' size='8'><b>ACTIONS ANALYSÉES</b></font><br/><font color='#0284C7' size='12'><b>{len(historique_actions) if historique_actions else 0}</b></font>", ParagraphStyle('S3', parent=styles['Normal'], alignment=TA_CENTER, leading=14)),
    ]]
    t_score = Table(score_box_data, colWidths=[160, 190, 160])
    t_score.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_soft),
        ('BOX', (0, 0), (-1, -1), 1, border_grey),
        ('LINEBEFORE', (1, 0), (1, -1), 0.8, border_grey),
        ('LINEBEFORE', (2, 0), (2, -1), 0.8, border_grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(t_score)
    b1_pdf, e1_pdf, b2_pdf, e2_pdf = 0, 0, 0, 0
    for act in (historique_actions or []):
        est_2mt = act.get("periode") == "2ème MT"
        t_a = str(act.get("type_action", ""))
        if t_a == "But" or t_a.startswith("But ("):
            if est_2mt:
                b2_pdf += 1
            else:
                b1_pdf += 1
        elif t_a == "But encaissé":
            if est_2mt:
                e2_pdf += 1
            else:
                e1_pdf += 1

    if (b1_pdf + e1_pdf + b2_pdf + e2_pdf) > 0:
        mi_temps_style = ParagraphStyle(
            'MiTempsScore', parent=styles['Normal'], fontName='Helvetica-Bold',
            fontSize=8.5, leading=11, textColor=slate_muted, alignment=TA_CENTER
        )
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Découpage horodaté : 1ère MT : {b1_pdf} - {e1_pdf}  •  2ème MT : {b2_pdf} - {e2_pdf}",
            mi_temps_style
        ))
    story.append(Spacer(1, 10))

    # 2. SYNTHÈSE EXÉCUTIVE : BILAN POST-MATCH DU STAFF
    bilan_elements = [
        Paragraph("1. SYNTHÈSE EXÉCUTIVE — ANALYSE POST-MATCH DU STAFF", section_header_style)
    ]

    if bilan_post_match and bilan_post_match.strip():
        texte_formate = bilan_post_match.strip().replace('\n', '<br/>')
        contenu_bilan = Paragraph(texte_formate, ParagraphStyle(
            'BilanBody', parent=normal_style, fontSize=9.5, leading=14, textColor=navy
        ))
    else:
        contenu_bilan = Paragraph(
            "<i>Aucun compte-rendu post-match n'a encore été rédigé pour cette rencontre dans l'espace analyse.</i>",
            ParagraphStyle('BilanEmpty', parent=normal_style, textColor=slate_muted)
        )

    t_bilan = Table([[contenu_bilan]], colWidths=[510])
    t_bilan.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor("#BAE6FD")),
        ('LINEBEFORE', (0, 0), (0, -1), 3.5, accent_blue),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    bilan_elements.append(t_bilan)
    story.append(KeepTogether(bilan_elements))
    story.append(Spacer(1, 8))

    # 3. ANALYSE TACTIQUE : SYSTÈMES D'ATTAQUE ADVERSES
    tactique_elements = [
        Paragraph("2. ANALYSE TACTIQUE — SYSTÈMES D'ATTAQUE ADVERSES", section_header_style)
    ]

    if attaques_adv and any(v > 0 for v in attaques_adv.values()):
        total_att = sum(attaques_adv.values())
        headers_att = list(attaques_adv.keys()) + ["Total Séquences"]
        vals_att = [f"<b>{v}</b> ({round(v / total_att * 100)}%)" if total_att > 0 else "0" for v in attaques_adv.values()] + [f"<b>{total_att}</b>"]

        att_data = [
            [Paragraph(h, table_header_style) for h in headers_att],
            [Paragraph(val, bold_center_style) for val in vals_att]
        ]
        col_w = 510 / len(headers_att)
        t_att = Table(att_data, colWidths=[col_w] * len(headers_att))
        t_att.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), slate_dark),
            ('BACKGROUND', (-1, 1), (-1, 1), bg_soft),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        tactique_elements.append(t_att)
    else:
        tactique_elements.append(Paragraph("Aucune séquence tactique adverse relevée durant la rencontre.", normal_style))

    story.append(KeepTogether(tactique_elements))
    story.append(Spacer(1, 8))

    # 4. TEMPS MORTS & CARTONS ROUGES (MOMENTS CLÉS)
    evenements_cles = [
        act for act in (historique_actions or [])
        if "temps mort" in str(act.get("type_action", "")).lower()
        or "rouge" in str(act.get("type_action", "")).lower()
    ]

    if evenements_cles:
        cles_elements = [
            Paragraph("TEMPS MORTS & CARTONS ROUGES (MOMENTS CLÉS)", section_header_style)
        ]
        cles_data = [[
            Paragraph("Moment", table_header_style),
            Paragraph("Événement", table_header_style),
            Paragraph(col_detail_libelle, table_header_style),
        ]]
        for ev in evenements_cles:
            t_ev = str(ev.get("type_action", ""))
            bg_ev, hex_ev = _style_ligne_action(t_ev)
            cles_data.append([
                Paragraph(_formater_horodatage(ev), ParagraphStyle('CleHorodatage', parent=bold_center_style, leading=10.5)),
                Paragraph(f"<font color='{hex_ev}'><b>{t_ev}</b></font>", normal_style),
                Paragraph(ev.get("details", ""), normal_style),
            ])
        t_cles = Table(cles_data, colWidths=[75, 165, 270], repeatRows=1)
        cles_style = [
            ('BACKGROUND', (0, 0), (-1, 0), slate_dark),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]
        for idx_ev, ev in enumerate(evenements_cles, start=1):
            bg_ev, _ = _style_ligne_action(str(ev.get("type_action", "")))
            cles_style.append(('BACKGROUND', (0, idx_ev), (-1, idx_ev), bg_ev))
        t_cles.setStyle(TableStyle(cles_style))
        cles_elements.append(t_cles)
        story.append(KeepTogether(cles_elements))
        story.append(Spacer(1, 8))

    # 5. OBSERVATIONS & FAITS MARQUANTS EN DIRECT (NOTES DU BANC)
    notes_elements = [
        Paragraph("3. OBSERVATIONS & FAITS MARQUANTS EN DIRECT (NOTES DU BANC)", section_header_style)
    ]

    if commentaires_staff:
        com_data = [[
            Paragraph("Chrono", table_header_style),
            Paragraph("Observation / Fait de match relevé", table_header_style)
        ]]
        for c in commentaires_staff:
            com_data.append([
                Paragraph(_formater_horodatage(c), ParagraphStyle('ComHorodatage', parent=bold_center_style, leading=10.5)),
                Paragraph(c.get("texte", ""), normal_style)
            ])
        t_com = Table(com_data, colWidths=[75, 435], repeatRows=1)
        t_com.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), slate_muted),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_soft]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        notes_elements.append(t_com)
    else:
        notes_elements.append(Paragraph("Aucune note rapide saisie sur le banc pendant le match.", normal_style))

    story.append(KeepTogether(notes_elements))
    story.append(Spacer(1, 8))

    # 5. JOURNAL CHRONOLOGIQUE DES ACTIONS (PLAY-BY-PLAY)
    story.append(Paragraph("4. DÉROULÉ CHRONOLOGIQUE DES ACTIONS (PLAY-BY-PLAY)", section_header_style))

    if historique_actions:
        act_data = [[
            Paragraph("Chrono", table_header_style),
            Paragraph("Type d'Action", table_header_style),
            Paragraph(col_detail_libelle, table_header_style)
        ]]

        table_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]

        for idx, act in enumerate(historique_actions, start=1):
            t_act_str = act.get("type_action", "")
            bg_row, txt_hex = _style_ligne_action(t_act_str)

            act_data.append([
                Paragraph(_formater_horodatage(act), ParagraphStyle('ActHorodatage', parent=bold_center_style, leading=10.5)),
                Paragraph(f"<font color='{txt_hex}'><b>{t_act_str}</b></font>", normal_style),
                Paragraph(act.get("details", ""), normal_style)
            ])
            table_styles.append(('BACKGROUND', (0, idx), (-1, idx), bg_row))

        t_act = Table(act_data, colWidths=[75, 165, 270], repeatRows=1)
        t_act.setStyle(TableStyle(table_styles))
        story.append(t_act)
    else:
        story.append(Paragraph("Aucune action enregistrée dans le journal chronologique.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
