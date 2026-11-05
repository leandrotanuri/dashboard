// Recebe os leads da LP do Divine Motel e grava na aba "Leads"
// da planilha "DIVINE MOTEL - Leads e UTMs".
// Instalação: na planilha, Extensões > Apps Script > cole este código > Salvar.
// Depois: Implantar > Nova implantação > App da Web
//   Executar como: Eu | Quem pode acessar: Qualquer pessoa
// Copie a URL gerada e cole em LEADS_ENDPOINT no arquivo lead.js.

const ABA = 'Leads';
const HORAS_SEM_DUPLICAR = 24; // mesmo telefone dentro desse prazo não vira linha nova

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const d = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA);
    if (!sheet) return ContentService.createTextOutput('aba Leads não encontrada');

    if (jaRegistrado(sheet, d.telefone)) return ContentService.createTextOutput('duplicado');

    const origem = (d.utm_source || '').toLowerCase();
    let plataforma = 'Orgânico';
    if (d.gclid || origem === 'google') plataforma = 'Google';
    else if (d.fbclid || ['facebook', 'instagram', 'meta', 'fb', 'ig'].includes(origem)) plataforma = 'Meta';
    else if (origem) plataforma = 'Outro';

    const obs = [d.interesse, d.pagina ? 'Página: ' + d.pagina : ''].filter(Boolean).join(' | ');

    sheet.appendRow([
      new Date(),            // A Data e hora
      d.nome || '',          // B Nome
      d.telefone || '',      // C Telefone
      plataforma,            // D Plataforma
      'Site / LP',           // E Captura
      '', '', '',            // F Quando precisa, G Pessoas, H Motivo (a recepção preenche)
      d.utm_source || '',    // I
      d.utm_medium || '',    // J
      d.utm_campaign || '',  // K
      d.utm_content || '',   // L
      d.utm_term || '',      // M
      d.gclid || d.fbclid || '', // N Click ID
      'Novo',                // O Status
      '', '', '',            // P Data do pernoite, Q Valor, R Responsável
      obs                    // S Observações
    ]);
    sheet.getRange(sheet.getLastRow(), 1).setNumberFormat('dd/MM/yyyy HH:mm');
    return ContentService.createTextOutput('ok');
  } finally {
    lock.releaseLock();
  }
}

function jaRegistrado(sheet, telefone) {
  const ultima = sheet.getLastRow();
  if (!telefone || ultima < 2) return false;
  const inicio = Math.max(2, ultima - 300);
  const linhas = sheet.getRange(inicio, 1, ultima - inicio + 1, 3).getValues();
  const limite = Date.now() - HORAS_SEM_DUPLICAR * 3600 * 1000;
  const alvo = String(telefone).replace(/\D/g, '');
  return linhas.some(r => r[0] instanceof Date && r[0].getTime() > limite &&
    String(r[2]).replace(/\D/g, '') === alvo);
}
