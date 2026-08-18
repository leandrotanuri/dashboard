# Casinha Le Julie — Conectar Leads dos Formulários à Planilha

**Objetivo:** cada lead novo dos formulários cai automático numa Google Sheet, em tempo real.
Método = **conexão nativa do Meta → Google Sheets** (grátis, sem token, com backfill do histórico).

---

## ✅ Já feito (Claude)
- Planilha criada: **Casinha Le Julie — Leads Formularios**
  - URL: https://docs.google.com/spreadsheets/d/1kVliNsOeAhXMisENdzn8yhxfxrhNjy3K2kkKTeslh5M/edit
  - Abas prontas: **Corporativo** e **Casamento**
  - Conta dona: **letanuri@gmail.com** (a da agência)

---

## 👉 Sua parte (5 min, precisa do seu login — só você faz)

Onde: **Meta Business Suite → Todas as ferramentas → Formulários instantâneos → aba "CRM setup"**

### 1. Limpar o teste antigo
- Na tabela "Integrações com Planilha Google", **apague** a linha antiga
  (Formulário Corporativo → planilha "teste leandro") no ícone de **lixeira**.

### 2. Conectar o Formulário CORPORATIVO
- Clique **"Nova integração"**
- Escolha **Google Sheets** → **"Entrar com Google"**
- ⚠️ **ESCOLHA A CONTA `letanuri@gmail.com`** (NÃO outra conta! foi o erro da "teste leandro")
- Planilha: **Casinha Le Julie — Leads Formularios**
- Aba: **Corporativo**
- Formulário instantâneo: **Formulário Corporativo**
- ✅ Marque **"Sincronizar leads existentes"** (traz os ~28 antigos)
- Salvar / validar

### 3. Conectar o Formulário CASAMENTO
- **"Nova integração"** de novo
- Google Sheets → **Entrar com Google → `letanuri@gmail.com`** (mesma conta!)
- Planilha: **Casinha Le Julie — Leads Formularios** (a mesma)
- Aba: **Casamento**
- Formulário instantâneo: **Formulário Casamento**
- ✅ Marque **"Sincronizar leads existentes"** (traz os ~164 antigos)
- Salvar / validar

### 4. Conferir
- A tabela do CRM setup deve mostrar **2 linhas 🟢 Conectado**, ambas apontando pra `letanuri@gmail.com`.
- Abra a planilha e veja se as abas encheram com os leads antigos.
- (Opcional) mande um **lead de teste** preenchendo o form pra ver caindo na hora.

---

## 🔜 Depois (Claude assume)
Quando as 2 integrações estiverem 🟢 e os leads tiverem caído na planilha:
- Claude confere as colunas reais que o Meta escreveu
- Monta a leitura **autenticada** (a planilha tem PII — nome/telefone — então **NÃO** vai ser pública)
- Pluga os leads na **dash da Casinha** (https://agenciascale.github.io/dash-casinha/)

**É só avisar o Claude: "Casinha conectada".**
