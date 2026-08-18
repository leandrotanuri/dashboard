# Workflow: Baixar Vídeo (yt-dlp)

Baixa vídeos do Instagram / YouTube via o script **`Baixar Video.bat`**
(fica em `C:\Users\leand\OneDrive\Desktop\Baixar Video.bat`).

## Objetivo
Baixar 1 ou mais vídeos colando os links (separados por espaço) e salvar em
`%USERPROFILE%\Videos`.

## Como usar (dia a dia)
1. Duplo clique em **Baixar Video.bat** na área de trabalho.
2. Colar os links separados por espaço.
3. Enter. Os arquivos caem em `C:\Users\leand\Videos`.

## Ferramenta
- Motor: **yt-dlp** rodando como módulo Python → `python -m yt_dlp`
- Runtime JS: **bun** (`--js-runtime bun`) — necessário pro YouTube resolver desafios.
- Instalar / atualizar o yt-dlp:
  ```
  python -m pip install --user -U yt-dlp
  ```

## Problemas já resolvidos (NÃO repetir os erros antigos)

### 1. Device Guard bloqueava o yt-dlp.exe
- **Sintoma:** `'C:\ProgramData\chocolatey\bin\yt-dlp.exe' foi bloqueado pela
  política do Device Guard da sua organização.`
- **Causa:** o `.exe` do yt-dlp instalado via Chocolatey está barrado pela
  política de segurança da máquina (não dá pra simplesmente desligar).
- **Correção:** NÃO usar o `.exe`. Rodar pelo Python (`python -m yt_dlp`), que
  é processo confiável e passa pelo Device Guard. Já configurado no .bat
  (`set "YTDLP=python -m yt_dlp"`).

### 2. YouTube fechava a janela ("& foi inesperado neste momento")
- **Causa:** links do YouTube têm `&` e `?` (ex: `watch?v=abc&t=10s`). Em
  `.bat`, `&` é separador de comandos → o antigo `for %%L in (%LINKS%)`
  quebrava o parser e fechava o programa. Instagram raramente tem `&`, por
  isso só o YouTube travava.
- **Correção:** usar `setlocal enabledelayedexpansion` e passar `!LINKS!`
  direto pro yt-dlp (que aceita várias URLs de uma vez). Com delayed expansion
  o `&`/`?` viram texto literal e não quebram o script. Nada de `for` loop.

### 3. YouTube "Signature solving failed" (formatos faltando / download falha)
- **Causa:** o YouTube exige resolver um desafio JS; sem isso o download pode
  dar 403 ou faltar formatos.
- **Correção:** flag `--remote-components ejs:github` (baixa o solver oficial
  do yt-dlp). Já incluída no .bat.

## Manutenção futura
- Se voltar a falhar YouTube, **primeiro** atualize o yt-dlp
  (`python -m pip install --user -U yt-dlp`) — o YouTube muda com frequência.
- O yt-dlp avisou que o suporte a **bun** está deprecado; se um dia parar,
  trocar `--js-runtime bun` por `--js-runtime deno` (instalar deno antes).
- Nunca voltar a usar o `yt-dlp.exe` do Chocolatey (Device Guard bloqueia).
