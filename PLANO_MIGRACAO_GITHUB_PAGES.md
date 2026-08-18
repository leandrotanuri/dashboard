# Plano — Migrar as dashboards Streamlit para o padrão GitHub Pages

> Status: **rascunho pra decisão** (03/08/2026). Nada foi migrado ainda.
> Referência de padrão: a dash da Michelle Ziade (já no modelo novo, agora com 3 abas).
> Playbook técnico: skill `dashboard-trafego` (instalada em `~/.claude/skills/`).

## Por que migrar
O padrão GitHub Pages (HTML/CSS/JS estático + `build.ps1` lendo as planilhas via gviz + GitHub Actions + cron-job.org a cada 3h) é **mais bonito, mais rápido, sem servidor pra manter e sem login Streamlit**. A dash da Michelle já provou o modelo — e agora ganhou os 3 botões (Visão Geral / Tráfego Pago / Relatório) que o dono da agência usa.

## O que existe hoje
Dois apps Streamlit (mesmo código-base, `CLIENTS` diferente):

| App | Pasta / repo | Clientes | Tipo de funil |
|---|---|---|---|
| Agência | `MetaAds Relatórios` · `leandrotanuri/dashboard` | Dr. Vinicius, Clínica PRC, Conta Casinha, Elisa Lobo | mensagens/lead (a confirmar por cliente) |
| My clients | `myclients-dash` · `leandrotanuri/myclients-dash` | CA - Instituto Master Beauty | mensagens_lead |
| **Já migrado** | `dash-michelle-ziade` · `agenciascale/dash-michelle-ziade` | Michelle Ziade | venda direta (Hotmart + pixel) |

## O ponto-chave: cada cliente tem uma fonte de dados diferente
A migração **não é copiar/colar** — o `build.ps1` e o funil mudam por cliente:

- **Venda direta (ex.: Michelle):** template pronto = a dash da Michelle. Precisa: planilha de gasto por dia×anúncio (Adveronix/Meta) + planilha de vendas (Hotmart/checkout). Atribuição por pixel.
- **Lead / mensagens (ex.: Master Beauty, provável Dr. Vinicius/PRC/Casinha):** funil diferente — o "resultado" é lead/agendamento/mensagem, não venda Hotmart. O modelo de 3 planilhas (leads por UTM + conversões) da skill se aplica melhor. Precisa mapear, por cliente: fonte de gasto, fonte de leads/agendamentos, e a régua de custo por resultado.

**Antes de migrar cada um, definir (checklist):**
1. Fonte de **gasto** (Adveronix? conexão Meta MCP? planilha manual?).
2. Fonte de **resultado** (Hotmart? planilha de agendamentos? Kommo/CRM? mensagens?).
3. **Atribuição** (pixel? UTM por lead? manual?).
4. **Régua** de bom/médio/ruim (usar `reference_benchmarks_metricas` + meta de custo por resultado do cliente).
5. Onde fica o **repo** (org `agenciascale`) e a **planilha** (compartilhada por link → Leitor).

## Passo a passo por dashboard (do skill `dashboard-trafego`)
1. Criar repo `agenciascale/dash-<cliente>` (público) e pasta local.
2. Escrever `build.ps1` que lê as planilhas do cliente (gviz CSV) e gera `data.js`/`data.json`.
3. Front: `index.html` + `styles.css` + `app.js` — partindo do template certo (Michelle p/ venda direta; variante lead p/ os demais).
4. `.github/workflows/build.yml` (deploy via `actions/deploy-pages@v4`).
5. cron-job.org a cada 3h disparando o `workflows/build.yml/dispatches` (mesmo PAT clássico, header Authorization Bearer).
6. Deixar as planilhas "Qualquer pessoa com link → Leitor".
7. Verificar no ar e ajustar filtro de campanha/imposto.

## Ordem recomendada
1. **Piloto:** escolher 1 cliente e migrar ponta a ponta (validar o template da variante lead, que ainda não existe pronto como o de venda direta).
   - Sugestão de piloto: **um cliente de lead/mensagens** (ex.: Master Beauty ou Dr. Vinicius), porque é o modelo que falta consolidar. Assim o 2º ao 5º viram quase cópia.
2. Validar com você (números batendo com o Streamlit).
3. Replicar para os demais, um a um, reusando o `build.ps1` e o front do piloto.
4. Aposentar o app Streamlit correspondente quando a versão GitHub Pages estiver estável.

## Esforço / riscos
- **Esforço:** ~1 dash de venda direta é rápido (template Michelle pronto). O 1º de lead exige montar o template da variante (maior). Depois, cada um ~rápido.
- **Risco:** divergência de números por diferença de fonte/atribuição — mitigado validando cada piloto contra o Streamlit antes de aposentar.
- **Dependências:** cada cliente precisa das planilhas compartilhadas por link e (se usar Adveronix Free) refresh manual do relatório, como na Michelle.

## Decisões pendentes (suas)
- [ ] Qual cliente vira **piloto**?
- [ ] Confirmar o **tipo de funil** de Dr. Vinicius, Clínica PRC e Conta Casinha (lead/mensagens/agendamento?).
- [ ] Manter os repos na org **agenciascale**?
- [ ] Aposentar os apps Streamlit após migrar, ou rodar em paralelo por um tempo?
