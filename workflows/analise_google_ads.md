# Workflow: Análise e Otimização de Conta Google Ads

## Objetivo
Analisar uma conta Google Ads de **geração de lead** (lead / cadastro / mensagem —
não e-commerce) e entregar um diagnóstico com **otimizações acionáveis**: onde cortar
desperdício, onde escalar, e o que ajustar.

## Inputs necessários
- `customer_id` da conta a analisar (formato `123-456-7890` ou só dígitos).
- Período (default: últimos 30 dias). Para comparação, rodar 2 janelas.
- Contexto do cliente: qual é a conversão que importa (lead/cadastro/mensagem),
  qual o CPA-alvo/aceitável, e se há sazonalidade.

## Pré-requisitos (setup, uma vez)
1. `pip install google-ads`
2. Developer Token aprovado (Basic Access) na MCC — `.env: GOOGLE_ADS_DEVELOPER_TOKEN`.
3. `python autenticar_google_ads.py` — logar com o e-mail que tem acesso à conta.
4. `.env: GOOGLE_ADS_LOGIN_CUSTOMER_ID` = ID da MCC (só dígitos).

## Passos

### 1. Extrair os dados
```bash
# Conta DENTRO da MCC (ex.: Dra. Roberta) — usa o login_customer_id do .env:
python tools/fetch_google_ads.py --customer_id <ID> --last_days 30

# Conta de acesso DIRETO, fora da MCC (ex.: Dr. Vinicius 510-526-9237):
python tools/fetch_google_ads.py --customer_id 510-526-9237 --last_days 30 --direct
```
**Regra da MCC:** o Developer Token da MCC funciona para qualquer conta que o
`letanuri@gmail.com` acessa, linkada ou não. A diferença é só o header
`login_customer_id`: contas dentro da MCC usam ele (padrão do `.env`); contas de
acesso direto precisam de `--direct` (omite o header, senão dá erro de permissão).
Para uma conta sob OUTRA MCC, use `--login_customer_id <id_daquela_mcc>`.
Gera CSVs em `output/google_ads/<id>/<periodo>/`:
`campanhas`, `grupos`, `palavras_chave`, `termos_de_busca`, `conversoes`, `dispositivos`.
O script já imprime um resumo (investimento, CPA médio, termos que queimam verba).

### 2. Ler os CSVs e diagnosticar
Analisar nesta ordem de prioridade (maior impacto primeiro):

1. **Termos de busca (`termos_de_busca.csv`)** — o maior vazamento. Listar termos com
   **custo > 0 e conversões = 0**; são candidatos a **palavra-chave negativa**. Somar o
   gasto desperdiçado. Procurar também termos irrelevantes ao negócio.
2. **CPA por campanha/grupo** — comparar com o CPA-alvo do cliente. Campanhas acima do
   alvo com volume: candidatas a corte/ajuste de lance. Abaixo do alvo com IS perdida:
   candidatas a escalar orçamento.
3. **Parcela de impressões (IS)** — `is_perdida_orcamento_%` alto = orçamento travando
   quem converte bem (subir budget). `is_perdida_rank_%` alto = problema de lance/QS.
4. **Quality Score (`palavras_chave.csv`)** — QS ≤ 4 encarece o clique; sinalizar para
   revisar anúncio/LP/relevância. Pausar palavras com muito custo e zero conversão.
5. **Dispositivos** — se um device tem CPA muito pior, sugerir ajuste de lance por device.
6. **Ações de conversão (`conversoes.csv`)** — confirmar que está otimizando pela
   conversão certa (lead real, não pageview/clique em telefone sem qualificação).

### 3. Entregar o diagnóstico
Formato: lista priorizada de **otimizações acionáveis**, cada uma com o dado que a
justifica e o impacto estimado. Exemplo:
- "Adicionar 12 palavras-chave negativas (queimaram R$ X sem conversão em 30 dias)."
- "Subir orçamento da campanha Y em Z% — está perdendo N% de IS por orçamento e o CPA
  está abaixo do alvo."
- "Pausar as 5 palavras com QS ≤ 3 e custo > R$ X sem conversão."

Sempre separar em: **cortar desperdício** / **escalar o que funciona** / **testar**.

### 4. (Opcional) Salvar o report
Se o cliente acompanha por planilha/dash, subir o resumo pro destino de sempre
(Google Sheets), seguindo o padrão dos outros clientes.

## Regras e cuidados
- **NÃO alterar a conta pela API** (pausar, mudar lance, criar negativas) sem o Leandro
  aprovar explicitamente. Este workflow é **só leitura + recomendação**. Alterações são
  decisão dele.
- Developer Token com acesso **Test** só lê contas de teste. Contas reais exigem
  **Basic Access** aprovado.
- O e-mail autenticado precisa ter acesso à conta. Sem MCC linkada, roda direto pelo
  `customer_id` da conta (o token da MCC continua valendo).
- Benchmarks: usar a régua em `memory/reference_benchmarks_metricas.md` para classificar
  CTR/CPC/CPM/conversão.

## Casos excepcionais / aprendizados
- `search_term_view` vem vazio em contas só de PMax/Display (não há termos de busca
  clássicos). Nesses casos o foco muda para grupos de recursos e públicos.
- Métricas de IS de busca (`search_impression_share`) vêm nulas para campanhas que não
  são de Rede de Pesquisa — normal.
- Se a extração falhar por token: reautenticar com `python autenticar_google_ads.py`.
