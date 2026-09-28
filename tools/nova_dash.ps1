#requires -Version 5
<#
  nova_dash.ps1 - Cria a dash (GitHub Pages) de um cliente novo a partir de um modelo.

  Modelo padrao: dashonline/masterbeautyclinica (captacao por MENSAGEM + LEAD, le a Meta Graph API).
  Leads e agendamentos aparecem sozinhos quando existir dado, entao serve tanto pra cliente so de
  mensagem (click to WhatsApp) quanto pra mensagem + formulario.

  O que faz:
    1. Clona o modelo e troca conta, nome, prefixo das campanhas, data de inicio e planilha de agendamentos
    2. Cria o repo <Org>/<Slug> (publico) - ou usa um vazio que ja exista
    3. Cadastra o secret META_ACCESS_TOKEN (do ambiente ou do .env da raiz do projeto)
    4. Liga o GitHub Pages (source = GitHub Actions)
    5. Sobe os arquivos -> o push dispara o primeiro build/deploy

  Pre-requisitos: git, GitHub CLI (`gh auth login` com acesso a org) e META_ACCESS_TOKEN no .env.

  Exemplo:
    .\tools\nova_dash.ps1 -Slug draisabellabacarin -Nome "Dra Bacarin" `
      -Conta 876078115252891 -Prefixo "IB |" -Inicio 2026-09-01

  -SoGerar: so gera a pasta (sem gh/push) pra conferir antes.
  Ver workflows/nova_dash_cliente.md.
#>
param(
  [Parameter(Mandatory = $true)][string]$Slug,       # nome do repo, ex: draisabellabacarin
  [Parameter(Mandatory = $true)][string]$Nome,       # nome que aparece na dash, ex: "Dra Bacarin"
  [Parameter(Mandatory = $true)][string]$Conta,      # conta de anuncios, com ou sem "act_"
  [Parameter(Mandatory = $true)][string]$Prefixo,    # inicio do nome das campanhas do cliente, ex: "IB |"
  [Parameter(Mandatory = $true)][string]$Inicio,     # busca dados desde (yyyy-MM-dd)
  [string]$AgendamentosId = "",                      # ID da planilha de agendamentos (opcional)
  [string]$Org = "dashonline",
  [string]$Modelo = "dashonline/masterbeautyclinica",
  [string]$ModeloDir = "",                           # usa uma pasta local do modelo em vez de clonar
  [string]$Saida = "",                               # onde gerar a pasta (padrao: %TEMP%\nova_dash\<Slug>)
  [switch]$SoGerar
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function ReadText($p) { return [IO.File]::ReadAllText($p, [Text.Encoding]::UTF8) }
function WriteText($p, $s) { [IO.File]::WriteAllText($p, $s, $utf8NoBom) }
function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }

# Troca obrigatoria: se o padrao nao existir, o modelo mudou -> para tudo em vez de gerar dash errada.
function MustReplace([string]$text, [string]$pattern, [string]$replacement, [string]$what) {
  if (-not [regex]::IsMatch($text, $pattern)) { throw "Nao achei '$what' no modelo (padrao: $pattern). O modelo mudou; ajuste o nova_dash.ps1." }
  return [regex]::Replace($text, $pattern, { param($m) $replacement })
}

# ---------------- validacao ----------------
if ($Slug -notmatch '^[a-z0-9][a-z0-9-]*$') { throw "Slug invalido: use so letras minusculas, numeros e hifen." }
$acct = $Conta.Trim(); if ($acct -notmatch '^act_') { $acct = "act_$acct" }
if ($acct -notmatch '^act_\d+$') { throw "Conta invalida: $Conta" }
[void][DateTime]::ParseExact($Inicio, "yyyy-MM-dd", $null)
$Prefixo = $Prefixo.Trim(); if (-not $Prefixo) { throw "Prefixo vazio." }
if ($Prefixo -match "['""]") { throw "Prefixo nao pode ter aspas." }
$repo = "$Org/$Slug"
$root = Split-Path -Parent $PSScriptRoot

# ---------------- token (so quando vai publicar) ----------------
$token = $null
if (-not $SoGerar) {
  Step "Conferindo gh e token"
  gh auth status 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "GitHub CLI nao logado. Rode: gh auth login" }
  $token = $env:META_ACCESS_TOKEN
  if ([string]::IsNullOrWhiteSpace($token)) {
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
      foreach ($ln in [IO.File]::ReadAllLines($envFile)) {
        if ($ln -match '^\s*META_ACCESS_TOKEN\s*=\s*(.+?)\s*$') { $token = $matches[1].Trim('"').Trim("'") }
      }
    }
  }
  if ([string]::IsNullOrWhiteSpace($token)) { throw "META_ACCESS_TOKEN nao encontrado (nem no ambiente nem em $root\.env)." }
  $token = $token.Trim()

  gh repo view $repo --json name 2>&1 | Out-Null
  $repoExists = ($LASTEXITCODE -eq 0)
  if ($repoExists) {
    gh api "repos/$repo/commits?per_page=1" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { throw "O repo $repo ja existe e tem commits. Escolha outro -Slug ou apague o repo." }
    Write-Host "  repo $repo ja existe e esta vazio -> vou usar ele"
  }
}

# ---------------- gerar a pasta ----------------
Step "Gerando arquivos a partir de $Modelo"
if (-not $Saida) { $Saida = Join-Path ([IO.Path]::GetTempPath()) "nova_dash\$Slug" }
if (Test-Path $Saida) { Remove-Item -Recurse -Force $Saida }
if ($ModeloDir) {
  New-Item -ItemType Directory -Force $Saida | Out-Null
  Get-ChildItem -Force $ModeloDir | Where-Object { $_.Name -ne ".git" } | Copy-Item -Destination $Saida -Recurse -Force
} else {
  gh repo clone $Modelo $Saida -- --depth 1 -q
  if ($LASTEXITCODE -ne 0) { throw "Falhou ao clonar $Modelo" }
  Remove-Item -Recurse -Force (Join-Path $Saida ".git")
}
foreach ($f in @("build.ps1", "app.js", "index.html", ".github\workflows\build.yml")) {
  if (-not (Test-Path (Join-Path $Saida $f))) { throw "Modelo sem $f - nao e o tipo de dash que este script sabe copiar." }
}

$pBuild = Join-Path $Saida "build.ps1"
$pApp   = Join-Path $Saida "app.js"
$pIndex = Join-Path $Saida "index.html"
$pLeads = Join-Path $Saida "leads\index.html"
$build = ReadText $pBuild; $app = ReadText $pApp; $index = ReadText $pIndex

# nomes do cliente-modelo (com e sem acento) pra trocar pelo novo
$mTitle = [regex]::Match($index, '<title>(.+?) — ')
if (-not $mTitle.Success) { throw "Nao achei o nome do cliente no <title> do modelo." }
$oldNome = $mTitle.Groups[1].Value
$mClient = [regex]::Match($build, 'client="([^"]+)"')
if (-not $mClient.Success) { throw "Nao achei client=""..."" no build.ps1 do modelo." }
$oldNomeAscii = $mClient.Groups[1].Value
$mPrefix = [regex]::Match($build, '"field":"campaign\.name","operator":"CONTAIN","value":"([^"]+)"')
if (-not $mPrefix.Success) { throw "Nao achei o filtro de campanha no build.ps1 do modelo." }
$oldPrefix = $mPrefix.Groups[1].Value

# build.ps1
$build = MustReplace $build '\$ACCOUNT\s*=\s*"act_\d+"[^\r\n]*' ('$ACCOUNT   = "' + $acct + '"   # ' + $Nome) 'ACCOUNT'
$build = MustReplace $build '\$START\s*=\s*"\d{4}-\d{2}-\d{2}"[^\r\n]*' ('$START     = "' + $Inicio + '"   # busca desde aqui ate hoje (BRT)') 'START'
$build = MustReplace $build ([regex]::Escape('"value":"' + $oldPrefix + '"')) ('"value":"' + $Prefixo + '"') 'filtro campaign.name'
$build = MustReplace $build ([regex]::Escape(".StartsWith('" + $oldPrefix.ToLower() + "')")) (".StartsWith('" + $Prefixo.ToLower() + "')") 'StartsWith do prefixo'
$build = $build.Replace($oldNomeAscii, $Nome).Replace($oldNome, $Nome)

# app.js
$agVal = $AgendamentosId.Trim()
$app = MustReplace $app "var AG_ID = '[^']*';" ("var AG_ID = '" + $agVal + "';") 'AG_ID'
$app = $app.Replace($oldNome, $Nome).Replace($oldNomeAscii, $Nome)

# html
$index = $index.Replace($oldNome, $Nome)
WriteText $pBuild $build; WriteText $pApp $app; WriteText $pIndex $index
if (Test-Path $pLeads) { WriteText $pLeads ((ReadText $pLeads).Replace($oldNome, $Nome)) }

$agTxt = if ($agVal) { "planilha ``$agVal``, aba ``Planilha agendamento`` (A = dd/mm, D = agendamentos, F = valor total)." } else { "preencher ``AG_ID`` no ``app.js`` com o ID da planilha (aba ``Planilha agendamento``: A = dd/mm, D = agendamentos, F = valor total). Enquanto vazio, o card nao aparece." }
$readme = @"
# Dashboard de Tráfego — $Nome

Dashboard estática (GitHub Pages) do funil de captação de $Nome. Gerada por
``tools/nova_dash.ps1`` (repo leandrotanuri/dashboard) a partir de ``$Modelo``.

## Como funciona
- ``build.ps1`` chama a **Meta Graph API** (insights nível anúncio, por dia) e gera ``data.js``.
  Imposto ×1,1385 sobre todo gasto. Só entram campanhas cujo nome começa com ``$Prefixo``.
- Mensagens são o resultado principal; leads de formulário aparecem sozinhos quando existir campanha ``| LEAD |``.
- **Agendamentos**: $agTxt
- ``.github/workflows/build.yml`` roda o build de hora em hora e publica no Pages.
  O token da Meta vem do secret **``META_ACCESS_TOKEN``**.

## Manutenção
- Conta: ``$acct`` ($Nome).
"@
WriteText (Join-Path $Saida "README.md") $readme
Write-Host "  modelo '$oldNome' -> '$Nome' | $acct | prefixo '$oldPrefix' -> '$Prefixo' | inicio $Inicio"
Write-Host "  pasta: $Saida"

if ($SoGerar) { Write-Host "`n-SoGerar: parei aqui (nada foi publicado)." -ForegroundColor Yellow; return }

# ---------------- publicar ----------------
Step "Criando repo $repo"
if (-not $repoExists) {
  gh repo create $repo --public --description "Dashboard de tráfego — $Nome"
  if ($LASTEXITCODE -ne 0) { throw "Falhou ao criar $repo (sua conta tem permissao de criar repo na org $Org?)" }
}

Step "Cadastrando secret META_ACCESS_TOKEN"
$token | gh secret set META_ACCESS_TOKEN --repo $repo
if ($LASTEXITCODE -ne 0) { throw "Falhou ao cadastrar o secret." }

Step "Ligando GitHub Pages (source = GitHub Actions)"
gh api -X POST "repos/$repo/pages" -f build_type=workflow 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
  gh api -X PUT "repos/$repo/pages" -f build_type=workflow 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { Write-Warning "Nao consegui ligar o Pages. Faca na mao: Settings -> Pages -> Source: GitHub Actions" }
}

Step "Subindo arquivos (dispara o primeiro build)"
Push-Location $Saida
try {
  git init -q -b main
  git add -A
  git commit -q -m "feat: dash $Nome (gerada por nova_dash.ps1 a partir de $Modelo)"
  git remote add origin "https://github.com/$repo.git"
  git push -u origin main
  if ($LASTEXITCODE -ne 0) { throw "Falhou o push." }
} finally { Pop-Location }

$pagesUrl = "https://$Org.github.io/$Slug/"
Write-Host "`nPronto! Acompanhe o build: https://github.com/$repo/actions" -ForegroundColor Green
Write-Host "Dash (quando o build ficar verde): $pagesUrl" -ForegroundColor Green
Write-Host "Lembrete: adicionar o cliente em DASHES.md." -ForegroundColor Yellow
