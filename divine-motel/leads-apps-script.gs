// Recebe os leads da LP do Divine Motel e grava na aba "Leads" da planilha.
// Como usar:
// 1. Crie uma planilha no Google Sheets > Extensões > Apps Script > cole este código.
// 2. Implantar > Nova implantação > App da Web > Executar como: Eu > Acesso: Qualquer pessoa.
// 3. Copie a URL gerada e cole em LEADS_ENDPOINT no arquivo lead.js.

const COLUNAS = ['data', 'nome', 'telefone', 'interesse', 'pagina', 'repetido',
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid', 'gclid'];

function doPost(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Leads') || ss.insertSheet('Leads');
  if (sheet.getLastRow() === 0) sheet.appendRow(COLUNAS);

  const d = JSON.parse(e.postData.contents);
  d.data = new Date();
  sheet.appendRow(COLUNAS.map(c => d[c] === undefined ? '' : d[c]));
  return ContentService.createTextOutput('ok');
}
