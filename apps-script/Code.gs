/**
 * Backend leve para:
 *   1) guardar a lista de nicks (Lichess / Chess.com) que devem ser
 *      importados; e
 *   2) disparar a importação sob demanda (botao "Atualizar agora" no
 *      site), chamando a API do GitHub pra rodar o workflow na hora
 *      em vez de esperar a segunda-feira.
 *
 * Mesma ideia do backend da Marcolino Champions League: Google Sheets
 * como "banco de dados", Apps Script como API HTTP na frente — e, no
 * caso do disparo do workflow, tambem como o unico lugar que guarda o
 * token do GitHub (o site nunca ve esse token).
 *
 * Como implantar:
 *   1. Crie uma planilha no Google Sheets com uma aba chamada "Nicks",
 *      com as colunas (linha 1, cabecalho): Plataforma | Nick
 *      (ex.: linha 2 = "lichess" | "meuNickPrincipal")
 *   2. Extensoes > Apps Script, cole este arquivo no lugar do Code.gs.
 *   3. Troque SHEET_ID, GITHUB_OWNER e GITHUB_REPO abaixo pelos seus
 *      valores.
 *   4. Configure o token do GitHub como Propriedade do Script (nao no
 *      codigo!): Configuracoes do projeto (icone de engrenagem) >
 *      Propriedades do script > Adicionar propriedade do script:
 *        nome: GITHUB_TOKEN
 *        valor: (veja como gerar no README, secao do botao "Atualizar agora")
 *   5. Implantar > Nova implantacao > tipo "App da Web".
 *        - Executar como: Eu (voce)
 *        - Quem pode acessar: Qualquer pessoa
 *   6. Copie a URL gerada e cole em APPS_SCRIPT_URL no index.html do site,
 *      e tambem use essa mesma URL no workflow do GitHub Actions
 *      (secret APPS_SCRIPT_URL, se for usar o fetch_config.py).
 */

const SHEET_ID = "COLE_AQUI_O_ID_DA_SUA_PLANILHA";
const SHEET_NAME = "Nicks";

// repositorio e arquivo do workflow que o botao "Atualizar agora" dispara
const GITHUB_OWNER = "SEU_USUARIO_GITHUB";
const GITHUB_REPO = "chess-opening-tree";
const GITHUB_WORKFLOW_FILE = "update-tree.yml";
const GITHUB_BRANCH = "main";

// intervalo minimo entre disparos manuais, pra evitar spam/abuso do botao
const MIN_MINUTES_BETWEEN_TRIGGERS = 5;

function doGet(e) {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  const rows = sheet.getDataRange().getValues();
  const nicks = rows
    .slice(1) // pula o cabecalho
    .filter(function (r) { return r[0] && r[1]; })
    .map(function (r) {
      return { platform: String(r[0]).trim().toLowerCase(), nick: String(r[1]).trim() };
    });
  return jsonResponse({ nicks: nicks });
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents);

  if (body.action === "add" || body.action === "remove") {
    return handleNickChange(body);
  }
  if (body.action === "trigger_import") {
    return handleTriggerImport();
  }
  return jsonResponse({ ok: false, error: "acao desconhecida: " + body.action });
}

function handleNickChange(body) {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  const platform = String(body.platform || "").trim().toLowerCase();
  const nick = String(body.nick || "").trim();

  if (!platform || !nick) {
    return jsonResponse({ ok: false, error: "platform e nick sao obrigatorios" });
  }

  if (body.action === "add") {
    const rows = sheet.getDataRange().getValues();
    const exists = rows.slice(1).some(function (r) {
      return String(r[0]).trim().toLowerCase() === platform && String(r[1]).trim() === nick;
    });
    if (!exists) {
      sheet.appendRow([platform, nick]);
    }
    return jsonResponse({ ok: true });
  }

  // action === "remove"
  const rows = sheet.getDataRange().getValues();
  for (let i = rows.length - 1; i >= 1; i--) {
    if (String(rows[i][0]).trim().toLowerCase() === platform && String(rows[i][1]).trim() === nick) {
      sheet.deleteRow(i + 1);
      break;
    }
  }
  return jsonResponse({ ok: true });
}

function handleTriggerImport() {
  const props = PropertiesService.getScriptProperties();

  const lastTrigger = Number(props.getProperty("last_trigger_ms") || 0);
  const now = Date.now();
  const elapsedMs = now - lastTrigger;
  const minMs = MIN_MINUTES_BETWEEN_TRIGGERS * 60 * 1000;
  if (lastTrigger && elapsedMs < minMs) {
    const waitSec = Math.ceil((minMs - elapsedMs) / 1000);
    return jsonResponse({ ok: false, error: "Aguarde " + waitSec + "s antes de importar de novo." });
  }

  const githubToken = props.getProperty("GITHUB_TOKEN");
  if (!githubToken) {
    return jsonResponse({ ok: false, error: "GITHUB_TOKEN nao configurado nas Propriedades do script." });
  }

  const url = "https://api.github.com/repos/" + GITHUB_OWNER + "/" + GITHUB_REPO +
    "/actions/workflows/" + GITHUB_WORKFLOW_FILE + "/dispatches";

  const response = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + githubToken,
      Accept: "application/vnd.github+json",
    },
    payload: JSON.stringify({ ref: GITHUB_BRANCH }),
    muteHttpExceptions: true,
  });

  const code = response.getResponseCode();
  if (code >= 200 && code < 300) {
    props.setProperty("last_trigger_ms", String(now));
    return jsonResponse({ ok: true });
  }

  return jsonResponse({
    ok: false,
    error: "GitHub respondeu " + code + ": " + response.getContentText(),
  });
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
