# -*- coding: utf-8 -*-
"""Gera o one-pager PDF do relatorio de anuncios da Clinica PRC - Junho 2026."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = os.path.join("output", "PRC_Relatorio_Anuncios_Junho_2026.pdf")
os.makedirs("output", exist_ok=True)

# Paleta
NAVY = colors.HexColor("#1f3a5f")
TEAL = colors.HexColor("#2a9d8f")
GOLD = colors.HexColor("#e9a23b")
RED = colors.HexColor("#c0504d")
LIGHT = colors.HexColor("#f2f5f8")
GREY = colors.HexColor("#6b7280")
GREENBG = colors.HexColor("#e7f4f1")
REDBG = colors.HexColor("#fbeae9")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], textColor=NAVY, fontSize=20,
                    leading=24, spaceAfter=2, alignment=TA_LEFT)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], textColor=GREY, fontSize=10,
                     leading=13)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=NAVY, fontSize=12.5,
                    leading=15, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9.2, leading=12.5)
SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=8, leading=10,
                       textColor=GREY)
CELL = ParagraphStyle("CELL", parent=styles["Normal"], fontSize=8.6, leading=10.5)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")
CELLW = ParagraphStyle("CELLW", parent=CELL, textColor=colors.white,
                       fontName="Helvetica-Bold")
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=8.8, leading=12, textColor=GREY)

story = []

# ---------- Cabecalho ----------
story.append(Paragraph("Clinica PRC &mdash; Relatorio de Anuncios", H1))
story.append(Paragraph("Meta Ads (Facebook / Instagram) &nbsp;|&nbsp; Periodo: 01 a 24 de junho de 2026 "
                       "&nbsp;|&nbsp; Gestor: Leandro Tanuri", SUB))
story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", thickness=1.2, color=NAVY))
story.append(Spacer(1, 8))

# ---------- KPIs ----------
def kpi(v, l, color):
    return Table([[Paragraph(f'<font color="{color.hexval()}"><b>{v}</b></font>',
                             ParagraphStyle("k", fontSize=15, alignment=TA_CENTER, leading=17))],
                  [Paragraph(l, ParagraphStyle("kl", fontSize=7.8, alignment=TA_CENTER,
                                               textColor=GREY, leading=9.5))]],
                 colWidths=[42*mm])

kpis = Table([[
    kpi("R$ 2.730,80", "INVESTIDO NO MES", NAVY),
    kpi("320", "CONVERSAS WHATSAPP", TEAL),
    kpi("R$ 7,09", "CUSTO/CONVERSA (medio)", GOLD),
    kpi("2.029", "VISITAS AO PERFIL IG", NAVY),
]], colWidths=[44*mm]*4)
kpis.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,-1), LIGHT),
    ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#dbe2ea")),
    ("INNERGRID", (0,0), (-1,-1), 0.5, colors.white),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7),
]))
story.append(kpis)
story.append(Spacer(1, 4))
story.append(Paragraph("WhatsApp: R$ 2.268 investidos &rarr; 320 conversas iniciadas. "
                       "Trafego de perfil: R$ 462 &rarr; 2.029 visitas (R$ 0,23 cada).", SMALL))

# ---------- Campanhas ----------
story.append(Paragraph("Desempenho por campanha", H2))
camp_head = [Paragraph(t, CELLW) for t in
             ["Campanha", "Objetivo", "Investido", "Resultado", "Custo/result."]]
camp_rows = [
    ["E2-CAP | QUENTE | 19/03 (Dr Joao)", "WhatsApp", "R$ 1.794,82", "212 conversas", "R$ 8,47"],
    ["E2-CAP | QUENTE | 02/04", "WhatsApp", "R$ 473,50", "108 conversas", "R$ 4,38"],
    ["E1-DIST | FRIO | Trafego Perfil", "Visitas IG", "R$ 462,48", "2.029 visitas", "R$ 0,23"],
]
data = [camp_head] + [[Paragraph(c, CELL) for c in r] for r in camp_rows]
t = Table(data, colWidths=[58*mm, 22*mm, 28*mm, 32*mm, 28*mm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("BACKGROUND", (0,2), (-1,2), GREENBG),   # campanha mais eficiente
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#dbe2ea")),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
]))
story.append(t)
story.append(Paragraph("Destaque (verde): a campanha de 02/04 converte a <b>R$ 4,38</b> &mdash; "
                       "quase metade do custo da de 19/03, que leva 4x mais verba.", SMALL))

# ---------- Criativos: campeoes x fracos ----------
story.append(Paragraph("Criativos &mdash; campeoes e os que pesam no custo", H2))

cre_head = [Paragraph(t, CELLW) for t in
            ["Criativo", "Campanha", "Investido", "Conversas", "Custo/conv.", "CTR"]]
# (linha, status) status: 'win', 'bad', None
cre = [
    ("Video - Seu cabelo esta assim", "02/04", "R$ 473,57", "108", "R$ 4,38", "3,65%", "win"),
    ("AD16", "Dr Joao 19/03", "R$ 447,54", "64", "R$ 6,99", "1,96%", None),
    ("AD14", "Dr Joao 19/03", "R$ 440,88", "63", "R$ 7,00", "2,72%", None),
    ("Video - Alopecia Areata", "Dr Joao 19/03", "R$ 483,12", "43", "R$ 11,24", "3,24%", "bad"),
    ("Video Angustiada", "Dr Joao 19/03", "R$ 312,11", "31", "R$ 10,07", "2,30%", "bad"),
    ("Video - Transicao Capilar (pausado)", "Dr Joao 19/03", "R$ 62,54", "3", "R$ 20,85", "1,20%", "bad"),
]
data = [cre_head]
stys = [TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#dbe2ea")),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
])]
for i, row in enumerate(cre, start=1):
    name, camp, inv, conv, cpr, ctr, status = row
    data.append([Paragraph(name, CELLB), Paragraph(camp, CELL), Paragraph(inv, CELL),
                 Paragraph(conv, CELL), Paragraph(cpr, CELLB), Paragraph(ctr, CELL)])
    if status == "win":
        stys[0].add("BACKGROUND", (0,i), (-1,i), GREENBG)
        stys[0].add("LINEBEFORE", (0,i), (0,i), 3, TEAL)
    elif status == "bad":
        stys[0].add("BACKGROUND", (0,i), (-1,i), REDBG)
        stys[0].add("LINEBEFORE", (0,i), (0,i), 3, RED)
    else:
        stys[0].add("BACKGROUND", (0,i), (-1,i), colors.white)

t = Table(data, colWidths=[55*mm, 28*mm, 25*mm, 22*mm, 25*mm, 17*mm])
t.setStyle(stys[0])
story.append(t)
story.append(Paragraph(
    '<font color="#2a9d8f"><b>Verde = campeao</b></font> &nbsp;&nbsp; '
    '<font color="#c0504d"><b>Vermelho = gasta mais e converte menos</b></font> '
    '&nbsp; (ordenado por volume de conversas)', SMALL))

# ---------- Validacao com a cliente ----------
story.append(Paragraph("Para validar na reuniao &mdash; conversao real no WhatsApp", H2))
story.append(Paragraph(
    "Os numeros acima medem <b>conversas iniciadas</b>, nao agendamentos/fechamentos. "
    "Como ainda nao temos rastreio das mensagens, precisamos da percepcao da clinica: "
    "<b>de quais videos chegam os pacientes que mais agendam/fecham?</b> Marque abaixo:", NOTE))
story.append(Spacer(1, 3))

val_head = [Paragraph(t, CELLW) for t in
            ["Criativo", "Mais agendam?", "Qualidade do lead (1 a 5)", "Observacoes da clinica"]]
val_rows = ["Video - Seu cabelo esta assim", "AD16", "AD14",
            "Video - Alopecia Areata", "Video Angustiada", "Outro: ____________"]
data = [val_head] + [[Paragraph(r, CELLB), "", "", ""] for r in val_rows]
t = Table(data, colWidths=[55*mm, 28*mm, 38*mm, 47*mm], rowHeights=[None]+[12*mm]*len(val_rows))
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), TEAL),
    ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#c7d2cf")),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
]))
story.append(t)

# ---------- Recomendacoes ----------
story.append(Paragraph("Recomendacoes", H2))
recs = [
    "<b>Realocar verba:</b> a campanha de 19/03 leva 4x mais orcamento mas converte a R$ 8,47; "
    "a de 02/04 converte a R$ 4,38. Migrar parte da verba para a estrutura mais eficiente tende a "
    "derrubar o custo por conversa do conjunto.",
    "<b>Escalar:</b> \"Seu cabelo esta assim\" (1/3 de todas as conversas, mais barato) e, no perfil, "
    "\"Alopecia Universal\" (R$ 0,18/visita, CTR 8,44%).",
    "<b>Pausar/substituir:</b> \"Alopecia Areata\" e \"Angustiada\" &mdash; juntos ~R$ 800 com o maior "
    "custo por conversa entre os ativos.",
    "<b>Proximo passo:</b> validar com a clinica a conversao real (tabela acima) para confirmar se o "
    "criativo mais barato e tambem o que traz o melhor paciente.",
]
for r in recs:
    story.append(Paragraph("&bull;&nbsp; " + r, BODY))
    story.append(Spacer(1, 2))

story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#dbe2ea")))
story.append(Paragraph("Dados extraidos via API do Meta Ads em 24/06/2026. "
                       "Custo/conversa = conversas iniciadas no WhatsApp (atribuicao 7 dias).", SMALL))

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=14*mm, rightMargin=14*mm,
                        topMargin=12*mm, bottomMargin=10*mm,
                        title="PRC - Relatorio de Anuncios - Junho 2026")
doc.build(story)
print("OK ->", OUT)
