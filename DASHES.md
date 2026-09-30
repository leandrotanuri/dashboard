# Dashes de clientes (GitHub Pages)

Registro de todas as dashes. **Atualize ao criar/aposentar uma.** Endereço: `https://<org>.github.io/<repo>/`.
Todas leem a Meta Graph API com o secret `META_ACCESS_TOKEN` e rodam o build pelo GitHub Actions.

## Org `dashonline` (atual — dashes novas vão aqui)

| Cliente | Repo | Conta Meta | Tipo | Filtro de campanha | Obs. |
|---|---|---|---|---|---|
| Clínica Master Beauty | `masterbeautyclinica` | `act_1007230201772374` | mensagem + lead + agendamentos | `CMB \|` | **Modelo padrão** do `tools/nova_dash.ps1` |
| Instituto Master Beauty | `institutomasterbeauty` | `act_400205609739120` | mensagem + lead (formulários, lista de leads) | padrão `IMB` | |
| Dra Roberta Esteves | `drarobertaesteves` | `act_1388498128427677` | quiz (lead do pixel) + Google Ads | campanhas com `quiz` | Google Ads: `821-841-2725` (dentro da MCC, sem `--direct`) |
| Conta Casinha | `casinha` | `act_2315650968737562` | lead + mensagem | — | |
| Dra Bacarin | `draisabellabacarin` | `act_876078115252891` | mensagem (click to WhatsApp) | `IB \|` | Criada 28/09/2026. Agendamentos: falta planilha |
| — | `clinicamasterbeauty` | — | — | — | Repo vazio, não usado |

## Org `agenciascale` (primeira leva, ago/2026)

| Cliente | Repo | Conta Meta | Tipo | Obs. |
|---|---|---|---|---|
| Dr. Vinícius | `dash-drvinicius` | `act_1189400572310429` | conversas (CTWA) + planilha de faturamento | |
| Clínica PRC | `dash-clinica-prc` | `act_546529263459917` | mensagem + seguidores (planilha) | filtro `PRC \|` |
| Elisa Lobo | `dash-elisa-lobo` | `act_995746376256993` | quiz + mensagem + seguidores | |
| Lilian Mesquita (Rubra) | `dash-lilian-rubra` | `act_1490434912872704` | seguidores / visitas ao perfil | |
| Michelle Ziade | `dash-michelle-ziade` | pixel `2070377586792193` | venda direta (Adveronix + Hotmart) | |
| Família Aprovada | `dash-familia-aprovada` | — | venda direta (Adveronix + Tutory) | |
| Conta Casinha | `dash-casinha` | `act_2315650968737562` | lead + mensagem | Versão antiga; a atual é `dashonline/casinha` |

## Qual modelo usar

| O cliente roda... | Modelo | Como criar |
|---|---|---|
| Só mensagem (click to WhatsApp), ou mensagem + formulário, com ou sem planilha de agendamentos | `dashonline/masterbeautyclinica` | `tools/nova_dash.ps1` (automático) |
| Mensagem + seguidores lançados em planilha | `agenciascale/dash-clinica-prc` | Manual (copiar e adaptar) |
| Só seguidores / visitas ao perfil | `agenciascale/dash-lilian-rubra` | Manual |
| Quiz | `agenciascale/dash-elisa-lobo` ou `dashonline/drarobertaesteves` | Manual |
| Venda direta (Hotmart/checkout) | `agenciascale/dash-michelle-ziade` | Manual |

Passo a passo: [`workflows/nova_dash_cliente.md`](workflows/nova_dash_cliente.md).
