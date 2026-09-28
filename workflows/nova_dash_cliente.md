# Workflow: Criar Dash de Cliente Novo (GitHub Pages)

## Objetivo
Publicar a dash de tráfego de um cliente novo "no mesmo padrão do cliente X", em minutos.

## Inputs Necessários
- **Nome** que aparece na dash (ex: `Dra Bacarin`)
- **Conta de anúncios** (ex: `876078115252891` ou `act_876078115252891`)
- **Slug** do repo: minúsculo, sem espaço (ex: `draisabellabacarin`)
- **Prefixo das campanhas** do cliente (ex: `IB |`). Só campanhas cujo nome começa com ele entram na dash.
  Conferir o nome das campanhas na conta (MCP do Meta Ads ou Gerenciador) antes de escolher.
- **Data de início** da busca (`yyyy-MM-dd`): um pouco antes da 1ª campanha no padrão
- **Tipo de funil**, que define o modelo (ver tabela em [`DASHES.md`](../DASHES.md))
- Opcional: **ID da planilha de agendamentos**, na aba `Planilha agendamento` (A = dd/mm, D = agendamentos, F = valor total)

## Pré-requisitos (uma vez por PC)
1. Esta pasta clonada (`git clone https://github.com/leandrotanuri/dashboard.git`)
2. `.env` na raiz com `META_ACCESS_TOKEN=...`. Usar token de **usuário do sistema que nunca expira**
   (Meta Business → Usuários do sistema), com acesso às contas dos clientes.
3. GitHub CLI instalado e logado: `winget install GitHub.cli` e depois `gh auth login`.
   A conta precisa poder criar repo na org `dashonline`.
4. Rodar o Claude Code **no PC, dentro desta pasta**. Numa sessão na nuvem não tem o `.env`, e o app do
   GitHub não consegue criar repo na org (erro 403).

## Ferramenta
`tools/nova_dash.ps1`: só para o modelo padrão (`dashonline/masterbeautyclinica`: mensagem + lead + agendamentos).

## Como Executar
```powershell
# 1. Conferir antes (gera a pasta, não publica nada)
.\tools\nova_dash.ps1 -Slug draisabellabacarin -Nome "Dra Bacarin" -Conta 876078115252891 `
  -Prefixo "IB |" -Inicio 2026-09-01 -SoGerar

# 2. Publicar (cria o repo, cadastra o secret, liga o Pages, sobe e dispara o 1º build)
.\tools\nova_dash.ps1 -Slug draisabellabacarin -Nome "Dra Bacarin" -Conta 876078115252891 `
  -Prefixo "IB |" -Inicio 2026-09-01
# + -AgendamentosId <id> se tiver planilha de agendamentos
```
Depois:
1. Acompanhar em `https://github.com/dashonline/<slug>/actions` até ficar verde
2. Abrir `https://dashonline.github.io/<slug>/` e conferir gasto e mensagens contra o Gerenciador
3. Adicionar o cliente em [`DASHES.md`](../DASHES.md)

## Outros modelos (seguidores, quiz, venda direta)
Não têm script. Copiar o repo modelo (tabela em `DASHES.md`) e trocar no `build.ps1` o `$ACCOUNT`, o `$START`,
o filtro de campanha (`$INCLUDE_RX` / `$EXCLUDE_RX`) e os IDs de planilha. Trocar também o nome do cliente no
`index.html`/`app.js`. Criar o repo com `gh repo create`, cadastrar o secret, ligar o Pages e subir: mesma
sequência do final do `nova_dash.ps1`.

## Casos Excepcionais
- **O script diz "Nao achei ... no modelo"**: o modelo mudou. Ajustar o padrão no `nova_dash.ps1` em vez de editar na mão.
- **1º build falha com token**: conferir o secret `META_ACCESS_TOKEN` no repo. O valor de um secret não pode
  ser lido depois de salvo; a fonte é sempre o `.env`.
- **Build falha com "0 linhas"**: o prefixo não bate com nenhuma campanha ou a data de início é depois da 1ª campanha.
  O build aborta de propósito para não publicar dash vazia.
- **Upload manual pelo site do GitHub** (último recurso): subir os arquivos **descompactados**, não o `.zip`.
  O Windows esconde `.github` e `.gitignore`; criar `.github/workflows/build.yml` via *Add file → Create new file*.

## Histórico
- 28/09/2026: script criado ao montar a dash da Dra Bacarin. Antes, o passo a passo só existia na memória do
  Claude no PC antigo, e a troca de PC fez tudo virar "do zero".
