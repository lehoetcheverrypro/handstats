from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

def generer_pdf_chronologique(nom_match, score_eq, score_adv, historique_actions, attaques_adv, commentaires_staff):
    """
    Génère un rapport PDF chronologique et qualitatif du match sous forme de flux d'octets.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22,
        textColor=colors.HexColor("#1A365D"), spaceAfter=10, alignment=1
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle', parent=styles['Normal'], fontSize=12, leading=16,
        textColor=colors.HexColor("#4A5568"), spaceAfter=20, alignment=1
    )
    section_style = ParagraphStyle(
        'SectionStyle', parent=styles['Heading2'], fontSize=14, leading=18,
        textColor=colors.HexColor("#2B6CB0"), spaceBefore=15, spaceAfter=8
    )
    normal_style = ParagraphStyle(
        'NormalStyle', parent=styles['Normal'], fontSize=10, leading=14,
        textColor=colors.HexColor("#2D3748")
    )
    table_header_style = ParagraphStyle(
        'TableHeader', parent=styles['Normal'], fontSize=10, leading=12,
        textColor=colors.white, fontName="Helvetica-Bold", alignment=1
    )

    # --- ENTÊTE ---
    story.append(Paragraph("RAPPORT CHRONOLOGIQUE ET TACTIQUE", title_style))
    story.append(Paragraph(f"Rencontre : <b>{nom_match}</b> | Score Final : <b>{score_eq} - {score_adv}</b>", subtitle_style))
    story.append(Spacer(1, 10))

    # --- SECTION 1 : ATTAQUES ADVERSES ---
    story.append(Paragraph("1. Bilan des Attaques Adverses", section_style))
    if attaques_adv:
        att_data = [
            [Paragraph(k, table_header_style) for k in attaques_adv.keys()],
            [Paragraph(str(v), normal_style) for v in attaques_adv.values()]
        ]
        t_att = Table(att_data, colWidths=[3*cm]*len(attaques_adv))
        t_att.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_att)
    else:
        story.append(Paragraph("Aucune donnée d'attaque adverse enregistrée.", normal_style))
    
    story.append(Spacer(1, 15))

    # --- SECTION 2 : COMMENTAIRES DU STAFF ---
    story.append(Paragraph("2. Notes et Commentaires du Staff", section_style))
    if commentaires_staff:
        com_data = [[Paragraph("Temps", table_header_style), Paragraph("Commentaire / Fait de match", table_header_style)]]
        for c in commentaires_staff:
            com_data.append([
                Paragraph(c.get("temps", "00:00"), normal_style),
                Paragraph(c.get("texte", ""), normal_style)
            ])
        t_com = Table(com_data, colWidths=[3*cm, 14*cm])
        t_com.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4A5568")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_com)
    else:
        story.append(Paragraph("Aucun commentaire ou note de staff enregistré pour ce match.", normal_style))

    story.append(Spacer(1, 15))

    # --- SECTION 3 : JOURNAL CHRONOLOGIQUE DES ACTIONS ---
    story.append(Paragraph("3. Journal Chronologique des Actions (Play-by-Play)", section_style))
    if historique_actions:
        act_data = [[
            Paragraph("Chrono", table_header_style), 
            Paragraph("Action", table_header_style), 
            Paragraph("Joueuse / Détail", table_header_style)
        ]]
        for act in historique_actions:
            act_data.append([
                Paragraph(act.get("temps", "00:00"), normal_style),
                Paragraph(act.get("type_action", ""), normal_style),
                Paragraph(act.get("details", ""), normal_style)
            ])
        t_act = Table(act_data, colWidths=[3*cm, 5*cm, 9*cm])
        t_act.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_act)
    else:
        story.append(Paragraph("Aucune action enregistrée dans le journal chronologique.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()