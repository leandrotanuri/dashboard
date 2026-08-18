import json, time, requests

with open('token.json') as f:
    token = json.load(f)

if time.time() >= token.get('expires_at', 0) - 300:
    r = requests.post(token['token_uri'], data={
        'client_id': token['client_id'],
        'client_secret': token['client_secret'],
        'refresh_token': token['refresh_token'],
        'grant_type': 'refresh_token',
    })
    r.raise_for_status()
    new = r.json()
    token['access_token'] = new['access_token']
    token['expires_at'] = time.time() + new.get('expires_in', 3600)
    with open('token.json', 'w') as f:
        json.dump(token, f, indent=2)

access_token = token['access_token']
headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

# Criar documento
r = requests.post(
    'https://docs.googleapis.com/v1/documents',
    headers=headers,
    json={'title': 'Analise de Performance - LC 2'}
)
r.raise_for_status()
doc_id = r.json()['documentId']

# Montar conteudo como texto unico para inserir
content = """Analise de Performance - LC 2
Ultimos 90 dias | Maio 2026

RESUMO GERAL
Total investido: R$ 4.699,95
Conversas WhatsApp iniciadas: 441
Leads via formulario: 9
Custo medio por conversa WPP: R$ 10,65

OS CRIATIVOS QUE MAIS CONVERTERAM
Os videos do lote "novos 06/04" foram os grandes destaques do periodo:

VID11 (WPP_0604_novos_VID11)
- 107 conversas geradas
- Custo por conversa: R$ 7,33
- Total investido: R$ 784,06
- CTR: 4,29%

VID08 (WPP_0604_novos_VID08)
- 115 conversas geradas (maior volume da conta)
- Custo por conversa: R$ 8,56
- Total investido: R$ 984,91
- CTR: 2,54%

VID09 (WPP_0604_novos_VID09)
- 50 conversas geradas
- Custo por conversa: R$ 7,30 (melhor custo entre os de alto volume)
- Total investido: R$ 364,88
- CTR: 2,96%

Destaque adicional: o VID11 foi testado em campanha de formulario (iniciada em 27/04) e apresentou o menor CPL do periodo: R$ 6,73 por lead.

CRIATIVOS COM BAIXA PERFORMANCE
Posts do Instagram impulsionados - Desperdicio identificado
Aproximadamente R$ 700 foram investidos em posts impulsionados de conteudo educativo (sobre dividas rurais). Resultado: zero conversas para WhatsApp. Os posts geraram cliques e engajamento, mas nao converteram para o objetivo da conta.

Outros criativos abaixo da media:

IMG01 (WPP_0104L1_IMG01)
- Apenas 2 conversas | Custo: R$ 35,45/conv

VID05 (WPP_0604_novos_VID05)
- Apenas 2 conversas | Custo: R$ 29,91/conv

VID12 (WPP_0604_novos_VID12)
- Apenas 2 conversas | Custo: R$ 19,86/conv

IMG02 (WPP_0104L1_IMG02)
- 52 conversas, porem custo elevado: R$ 10,57/conv
- Volume razoavel, mas custa o dobro dos melhores videos

CONCLUSOES E PROXIMOS PASSOS
1. Os videos do lote "novos 06/04" vencem claramente os criativos anteriores. A troca de criativos em abril foi a decisao certa.

2. VID08, VID09 e VID11 sao os pilares da conta. A verba deve ser concentrada neles.

3. Posts impulsionados de Instagram devem ser pausados para este objetivo. Funcionam para alcance e branding, mas nao convertem para WhatsApp.

4. Imagens (IMG01, IMG02) performam consistentemente abaixo dos videos.

5. A campanha de formulario (iniciada em 27/04) e promissora. O VID11 demonstrou R$ 6,73 por lead, o que e um bom indicador. Vale acompanhar por mais 2 semanas antes de escalar.

Proximos passos sugeridos:
- Manter VID08, VID09 e VID11 como criativos principais
- Pausar posts impulsionados e criativos com custo por conversa acima de R$ 15
- Acompanhar campanha de formulario e avaliar escala em meados de maio
"""

# Inserir texto
batch_requests = [
    {
        'insertText': {
            'location': {'index': 1},
            'text': content
        }
    }
]

r = requests.post(
    f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
    headers=headers,
    json={'requests': batch_requests}
)
r.raise_for_status()

# Buscar documento para formatar
r = requests.get(f'https://docs.googleapis.com/v1/documents/{doc_id}', headers=headers)
r.raise_for_status()
doc_body = r.json()

format_requests = []

headings_h1 = ['Analise de Performance - LC 2']
headings_h2 = ['RESUMO GERAL', 'OS CRIATIVOS QUE MAIS CONVERTERAM', 'CRIATIVOS COM BAIXA PERFORMANCE', 'CONCLUSOES E PROXIMOS PASSOS']

for element in doc_body.get('body', {}).get('content', []):
    paragraph = element.get('paragraph', {})
    elements_list = paragraph.get('elements', [])
    for el in elements_list:
        text_run = el.get('textRun', {})
        content_text = text_run.get('content', '').strip()
        start = el.get('startIndex', 0)
        end = el.get('endIndex', 0)

        if content_text in headings_h1:
            format_requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'paragraphStyle': {'namedStyleType': 'HEADING_1'},
                    'fields': 'namedStyleType'
                }
            })
        elif content_text in headings_h2:
            format_requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'paragraphStyle': {'namedStyleType': 'HEADING_2'},
                    'fields': 'namedStyleType'
                }
            })

if format_requests:
    r = requests.post(
        f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
        headers=headers,
        json={'requests': format_requests}
    )
    r.raise_for_status()

print(f'Documento criado com sucesso!')
print(f'https://docs.google.com/document/d/{doc_id}/edit')
