"""
Ferramenta: gen_pdf_dr_vinicius_diagnostico.py
Gera o PDF de diagnóstico Maio-Julho 2026 para reunião com Dr. Vinicius.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT

OUT_PATH = r"C:\Users\leand\Downloads\MetaAds Relatórios\output\dr_vinicius\Diagnostico_Dr_Vinicius_Maio_Julho_2026.pdf"

NAVY = colors.HexColor("#152238")
BLUE = colors.HexColor("#2E5AAC")
RED = colors.HexColor("#B23A3A")
GREY = colors.HexColor("#5B6472")
LIGHT_GREY = colors.HexColor("#F2F4F7")
GREEN = colors.HexColor("#2E7D4F")

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=24, textColor=NAVY, spaceAfter=2, leading=28,
)
subtitle_style = ParagraphStyle(
    "SubtitleCustom", parent=styles["Normal"], fontName="Helvetica",
    fontSize=13, textColor=BLUE, spaceAfter=14,
)
h1_style = ParagraphStyle(
    "H1Custom", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=14, textColor=NAVY, spaceBefore=16, spaceAfter=8,
)
body_style = ParagraphStyle(
    "BodyCustom", parent=styles["Normal"], fontName="Helvetica",
    fontSize=10, textColor=colors.HexColor("#222222"), leading=14,
    alignment=TA_LEFT, spaceAfter=6,
)
bullet_style = ParagraphStyle(
    "BulletCustom", parent=body_style, leftIndent=12, bulletIndent=0, spaceAfter=6,
)
callout_style = ParagraphStyle(
    "CalloutCustom", parent=body_style, fontName="Helvetica-Bold",
    textColor=RED, backColor=colors.HexColor("#FBEAEA"),
    borderPadding=(8, 8, 8, 8), leading=14,
)
note_style = ParagraphStyle(
    "NoteCustom", parent=body_style, fontName="Helvetica-Oblique",
    textColor=GREY, fontSize=9,
)
footer_style = ParagraphStyle(
    "FooterCustom", parent=styles["Normal"], fontName="Helvetica",
    fontSize=8, textColor=GREY,
)

def table_std(data, col_widths, header_bg=NAVY, highlight_rows=None):
    highlight_rows = highlight_rows or {}
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DCE3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    for row, bg in highlight_rows.items():
        style.append(("BACKGROUND", (0, row), (-1, row), bg))
    t.setStyle(TableStyle(style))
    return t

def section_title(num, text):
    return Paragraph(f'<font color="#2E5AAC">{num}.</font> {text}', h1_style)

def build():
    doc = SimpleDocTemplate(
        OUT_PATH, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=16 * mm,
        title="Diagnóstico de Performance — Dr. Vinicius",
    )
    story = []

    # Header
    story.append(Paragraph("Diagnóstico de Performance", title_style))
    story.append(Paragraph("Dr. Vinicius — Meta Ads · Maio a Julho de 2026", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=10))

    # 1. Resumo Executivo
    story.append(section_title(1, "Resumo Executivo"))
    story.append(Paragraph(
        "Investimento subiu <b>14,8%</b> de maio para junho (R$ 4.889,69 → R$ 5.612,69), mas as "
        "conversas iniciadas no WhatsApp caíram <b>26,5%</b> (460 → 338) e o custo por conversa "
        "subiu <b>56,2%</b> (R$ 10,63 → R$ 16,61).", bullet_style))
    story.append(Paragraph(
        "Em julho a tendência piorou ainda mais: <b>R$ 26,97 por conversa</b> nos primeiros 6 dias, "
        "média de apenas <b>7 conversas/dia</b> (vs 15,3/dia em maio).", bullet_style))
    story.append(Paragraph(
        "<b>Causa raiz identificada:</b> não foi fadiga de audiência — a frequência ficou baixa "
        "(1,0 a 1,25) o mês inteiro. Foi uma sequência de reprovações de anúncios na revisão da Meta, "
        "incluindo o anúncio nº1 da conta (Cirurgia Tripla), combinada com expansão de orçamento para "
        "públicos de pior desempenho.", bullet_style))

    # 2. Evolução mês a mês
    story.append(section_title(2, "Evolução mês a mês"))
    data2 = [
        ["Métrica", "Maio", "Junho", "Julho (1–6)"],
        ["Investimento", "R$ 4.889,69", "R$ 5.612,69", "R$ 1.132,89 (6 dias)"],
        ["Conversas WhatsApp", "460", "338", "42"],
        ["Conversas/dia (média)", "15,3", "11,3", "7,0"],
        ["Custo por conversa", "R$ 10,63", "R$ 16,61", "R$ 26,97"],
        ["CPM médio", "R$ 19,04", "R$ 24,75", "—"],
    ]
    story.append(table_std(data2, [55 * mm, 38 * mm, 38 * mm, 39 * mm]))
    story.append(Spacer(1, 4))

    # 3. Timeline
    story.append(section_title(3, "Linha do tempo de reprovações de anúncios"))
    data3 = [
        ["Data", "Anúncio", "Motivo"],
        ["20/05/2026", "Reels – 80 kg", "Reprovado na revisão"],
        ["03/06/2026", "Reels – Resultado vai além do volume", "Reprovado na revisão"],
        ["04/06/2026", "Reels – 52kg a menos", "Reprovado na revisão"],
        ["16/06/2026", "AD04 – Mommy Makeover (uma das cópias)", "Reprovado na revisão"],
        ["30/06/2026", "Reels – queixas claras", "Reprovado na revisão"],
        ["02/07/2026", "AD02 – Cirurgia Tripla (melhor anúncio da conta)", "Nudez adulta e atividades sexuais"],
        ["03–04/07/2026", "AD10 e AD11 – tentativas de recriar o Cirurgia Tripla", "Nudez adulta e atividades sexuais (de novo)"],
    ]
    story.append(table_std(
        data3, [28 * mm, 78 * mm, 64 * mm],
        highlight_rows={6: colors.HexColor("#FBEAEA"), 7: colors.HexColor("#FBEAEA")}
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Destaque:</b> o AD02 (Cirurgia Tripla) está com <b>zero impressões desde 1º de julho</b> — "
        "parou de entregar completamente. Esse anúncio sozinho gerava 166 conversas/mês no custo mais "
        "baixo da conta (R$ 8,56/conversa em junho, quase metade da média da conta).",
        callout_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Nota: pelo histórico da conta, reprovações por nudez/conteúdo explícito são recorrentes desde "
        "2021 — não é um evento isolado, é um padrão estrutural ligado ao tipo de imagem usada "
        "(resultados de cirurgia com pouca roupa).", note_style))

    # 4. Melhores e piores criativos
    story.append(section_title(4, "Melhores e piores criativos"))
    data4 = [
        ["Ranking", "Criativo", "Custo/conversa Maio", "Custo/conversa Junho"],
        ["1º", "AD02 – Cirurgia Tripla (bloqueado)", "R$ 5,84", "R$ 8,56"],
        ["2º", "AD04 – Mommy Makeover", "R$ 6,97", "R$ 10,23"],
        ["3º", "AD01 – Pós Bariátrica", "R$ 9,91", "R$ 15,84"],
        ["Pior", "Reels – Preço da Cirurgia (pausar)", "R$ 241,05", "R$ 508,49"],
    ]
    story.append(table_std(
        data4, [20 * mm, 76 * mm, 37 * mm, 37 * mm],
        highlight_rows={4: colors.HexColor("#FBEAEA")}
    ))

    # 5. Conjuntos e interesses
    story.append(section_title(5, "Conjuntos e interesses: o que gerou melhor"))
    data5 = [
        ["Cluster de público", "Maio", "Junho", "Avaliação"],
        ["Gucci, Chanel, Louis Vuitton, Pandora + Beleza\n+ Fitness/Academia + Bens de luxo\n+ Viajante internacional frequente",
         "R$ 5,84–\n9,91", "R$ 7,61–\n16,67", "Melhor cluster\nnos dois meses"],
        ["Engajamento 60D + Lookalike 1%\n(remarketing)",
         "R$ 11,30", "R$ 14,63–\n20,49", "Intermediário,\npiorou"],
        ["Pilates, Spas, Resorts de luxo, Tênis\n(rotulado \"Iphone\" no conjunto)",
         "R$ 27,58", "R$ 41–\n111", "Sempre o pior — recebeu\nMAIS verba em junho"],
    ]
    story.append(table_std(
        data5, [62 * mm, 26 * mm, 26 * mm, 56 * mm],
        highlight_rows={1: colors.HexColor("#E9F3EC"), 3: colors.HexColor("#FBEAEA")}
    ))

    # 6. Conta backup
    story.append(section_title(6, "A conta de anúncios backup ajuda?"))
    story.append(Paragraph(
        "<b>Resposta: só parcialmente — não deve ser tratada como a solução principal.</b>", bullet_style))
    story.append(Paragraph(
        "A reprovação por nudez é feita por análise do <b>conteúdo</b> do criativo, não da conta — o "
        "mesmo vídeo tende a ser reprovado de novo em outra conta (já aconteceu 2 vezes com variações "
        "do mesmo anúncio).", bullet_style))
    story.append(Paragraph(
        "Conta nova pode ter revisão mais rápida no início (menos histórico de violações), mas também "
        "começa do zero na fase de aprendizado, o que tende a encarecer a entrega logo de cara.", bullet_style))
    story.append(Paragraph(
        "<b>Recomendação:</b> não migrar tudo. Usar a conta backup só para testar criativos com "
        "enquadramento mais conservador (sem pele exposta em destaque), mantendo a conta principal com "
        "os públicos que já provaram eficiência.", bullet_style))

    # 7. Recomendações
    story.append(section_title(7, "Recomendações"))
    recs = [
        "Resolver a reprovação por nudez: recriar o Cirurgia Tripla com corte mais conservador (evitar "
        "decote/pele exposta em foco) antes de tentar reenviar de novo — duas tentativas parecidas já "
        "foram reprovadas.",
        "Cortar/pausar o cluster de público Pilates/Spas/Resorts/Tênis — nunca performou bem e recebeu "
        "mais verba justamente quando piorou.",
        "Realocar orçamento para o cluster vencedor (luxo + beleza + fitness + viajante internacional).",
        "Pausar por enquanto a abertura de novos conjuntos — cada um entra em fase de aprendizado e "
        "encarece a entrega geral.",
        "Manter sempre um anúncio reserva pronto para os campeões de performance, dado o histórico "
        "recorrente de reprovações nesta conta.",
        "Testar criativos mais conservadores na conta backup, em paralelo, sem migrar a operação principal.",
    ]
    for i, r in enumerate(recs, 1):
        story.append(Paragraph(f"<b>{i}.</b> {r}", bullet_style))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.6, color=GREY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Relatório gerado a partir de dados da API do Meta Ads — Dr. Vinicius (act_10205578707965893) "
        "— Período de análise: 01/05/2026 a 06/07/2026.", footer_style))

    doc.build(story)
    print(f"PDF gerado: {OUT_PATH}")

if __name__ == "__main__":
    build()
