# Workflow: Criar Anúncio no Meta Ads

## Objetivo
Criar uma campanha completa (Campanha → Conjunto de Anúncios → Criativo → Anúncio) no Meta Ads via Marketing API, **sempre em status PAUSED**. A ativação final é sempre manual, feita pelo usuário no Ads Manager — este workflow nunca ativa um anúncio.

## Pré-requisito: permissão do token
O `META_ACCESS_TOKEN` usado hoje em `.env` serve para leitura de insights. Criar objetos de anúncio exige que esse token tenha o escopo `ads_management` (não apenas `ads_read`). Verificar isso antes de tentar criar:
- No [Graph API Explorer](https://developers.facebook.com/tools/explorer/) ou via `debug_token`, confirmar que `ads_management` está entre as permissões concedidas.
- Se faltar, gerar um novo token com esse escopo (idealmente um System User Token de longa duração) e atualizar `.env`.

## Inputs Necessários
Um arquivo JSON de configuração com 4 blocos — ver modelo em `tools/ad_config_example.json`:

| Bloco | Campos principais |
|---|---|
| `campaign` | `name`, `objective` (ex: `OUTCOME_LEADS`, `OUTCOME_TRAFFIC`, `OUTCOME_ENGAGEMENT`), `special_ad_categories` |
| `adset` | `name`, `daily_budget` ou `lifetime_budget` (em centavos), `billing_event`, `optimization_goal`, `targeting` (geo, idade, gênero, interesses), `start_time` (opcional) |
| `creative` | `name`, `page_id` (Página do Facebook do cliente), `message`, `link`, `picture` (URL) ou `image_path` (arquivo local), `call_to_action_type` |
| `ad` | `name` |

Detalhes de segmentação (`targeting`) seguem o formato da [Targeting Spec do Meta](https://developers.facebook.com/docs/marketing-api/audiences/reference/basic-targeting) — cidades usam `key` (ID numérico do Meta, não o nome), raio e unidade de distância.

## Ferramenta
`tools/create_ad.py`

## Como Executar

### 1. Montar o JSON de configuração
Copiar `tools/ad_config_example.json` para `output/ad_config_<cliente>.json` e preencher com os dados reais da campanha (nunca editar o exemplo original).

### 2. Rodar em modo simulação primeiro (obrigatório)
```bash
python tools/create_ad.py --config output/ad_config_<cliente>.json
```
Sem a flag `--confirm`, o script **não faz nenhuma chamada de escrita à API** — só imprime um resumo (orçamento, segmentação, texto, link, página) para revisão. Sempre mostrar esse resumo ao usuário e aguardar aprovação explícita antes do próximo passo.

### 3. Criar de fato (após aprovação do usuário)
```bash
python tools/create_ad.py --config output/ad_config_<cliente>.json --confirm
```
Cria campanha, conjunto, criativo e anúncio nessa ordem, todos com `status=PAUSED`. Os IDs criados são salvos em `output/ad_created_<campaign_id>.json`.

### 4. Ativação
A ativação (mudar status para `ACTIVE`) é sempre feita manualmente pelo usuário no Ads Manager, nunca por este script.

## Output Esperado
- Campanha, conjunto de anúncios, criativo e anúncio criados na conta `META_AD_ACCOUNT_ID`, todos pausados.
- Arquivo `output/ad_created_<campaign_id>.json` com os IDs de cada objeto criado, para referência futura (edição, ativação, exclusão).

## Casos Excepcionais
- **Erro de permissão (`OAuthException` / código 200)**: o token não tem escopo `ads_management`. Gerar novo token com esse escopo.
- **`special_ad_categories` obrigatório**: campanhas de crédito, emprego, habitação ou temas sociais/eleitorais exigem categoria especial declarada — caso contrário a Meta pode rejeitar ou restringir a segmentação (ex: geolocalização e idade ficam limitadas).
- **`page_id` inválido ou sem permissão**: o token precisa ter permissão de admin/editor sobre a Página do Facebook usada no criativo.
- **Upload de imagem falha**: verificar se `image_path` aponta para um arquivo local válido (jpg/png). Para imagens já hospedadas, usar `picture` (URL) em vez de `image_path`.
- **`targeting` com cidade/região errada**: os IDs de `geo_locations` (cidades, regiões) vêm da Targeting Search API do Meta, não são o nome livre — buscar o ID correto antes de montar o JSON.
- **Orçamento em unidade errada**: `daily_budget`/`lifetime_budget` são em **centavos** da moeda da conta (ex: R$ 50,00 = `5000`).
- **Rate limit (erro 80004)**: mesmo comportamento documentado em `workflows/fetch_meta_ads_data.md` — aguardar e tentar novamente.

## Notas
- Este workflow nunca ativa um anúncio automaticamente. Toda ativação é uma ação manual e deliberada do usuário.
- O modo simulação (sem `--confirm`) é o padrão e deve ser sempre executado e revisado antes de `--confirm`.
- Tokens de acesso ficam em `.env` — nunca commitar esse arquivo.
