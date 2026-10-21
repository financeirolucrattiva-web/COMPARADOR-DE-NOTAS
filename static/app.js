const form = document.querySelector('#upload');
const error = document.querySelector('#error');
let result = null;
let files = null;
let inspection = null;
let busy = false;
const sourceNames = {sped: 'SPED', dominio: 'Domínio'};
const money = value => Number(value).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  node.textContent = text;
  if (cls) node.className = cls;
  return node;
};
const supplier = note => (note.fornecedor || 'Nome do fornecedor ausente') +
  (note.codigo_fornecedor ? ' (cód. ' + note.codigo_fornecedor + ')' : '');
const pages = note => (note.paginas || [note.pagina]).join(', ');
const searchText = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleUpperCase('pt-BR');

function showError(message) {
  error.textContent = message;
  error.hidden = false;
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch (_) {
    throw Error('Não foi possível receber a resposta. Confira se a janela do programa continua aberta.');
  }
}

async function working(message, action) {
  if (busy) return;
  busy = true;
  error.hidden = true;
  const controls = [...document.querySelectorAll('button, input[type=file]')];
  controls.forEach(control => { control.disabled = true; });
  const loading = document.querySelector('#loading');
  const started = Date.now();
  const update = () => {
    const elapsed = Math.floor((Date.now() - started) / 1000);
    loading.textContent = `${message} · ${elapsed}s. PDFs longos podem levar mais tempo.`;
  };
  update();
  loading.hidden = false;
  const timer = setInterval(update, 1000);
  try {
    await action();
  } catch (exc) {
    showError(exc.message || 'Falha ao acessar o programa. Confira se ele continua aberto.');
  } finally {
    clearInterval(timer);
    loading.hidden = true;
    controls.forEach(control => { control.disabled = false; });
    busy = false;
  }
}

function showWarnings(container, warnings) {
  container.replaceChildren();
  for (const warning of warnings || []) container.append(el('p', warning));
}

function sourceSummary(sources) {
  const container = document.querySelector('#source-summary');
  container.replaceChildren();
  for (const [source, summary] of Object.entries(sources || {})) {
    const card = el('div', '', 'source-card');
    card.append(el('strong', sourceNames[source] || source));
    if (summary.error) {
      card.append(el('p', summary.error));
    } else {
      card.append(el('p', `${summary.quantidade} notas lidas · ${summary.paginas} páginas · ${money(summary.total)}`));
    }
    if (summary.warnings?.length) card.append(el('p', `${summary.warnings.length} aviso(s). Confira a leitura desse arquivo.`));
    container.append(card);
  }
  container.hidden = !container.childElementCount;
}

function renderInspection() {
  const query = searchText(document.querySelector('#inspection-search').value.trim());
  const digits = /^[\d.\-\/\s]+$/.test(query) ? query.replace(/\D/g, '') : '';
  const matching = inspection.notes.filter(note =>
    searchText(`${note.cnpj} ${note.documento} ${supplier(note)}`).includes(query) ||
    Boolean(digits && (note.cnpj.includes(digits) || note.documento.includes(digits))));
  const rows = document.querySelector('#inspection-rows');
  rows.replaceChildren();
  for (const note of matching) {
    const row = el('tr', '');
    row.append(el('td', note.cnpj), el('td', note.documento + (note.serie ? ' / ' + note.serie : '')),
      el('td', supplier(note)), el('td', money(note.valor)), el('td', pages(note)));
    rows.append(row);
  }
  document.querySelector('#inspection-visible').textContent = `${matching.length} de ${inspection.notes.length} notas`;
}

function showInspection(data) {
  inspection = data;
  const summary = data.summary;
  document.querySelector('#inspection-title').textContent = `Leitura do ${sourceNames[data.source]}`;
  document.querySelector('#inspection-counts').textContent =
    `${summary.quantidade} notas · ${summary.paginas} páginas · ${summary.cnpj} CNPJ · ${summary.cpf} CPF · Total lido: ${money(summary.total)}`;
  document.querySelector('#inspection-search').value = '';
  showWarnings(document.querySelector('#inspection-warnings'), summary.warnings);
  renderInspection();
  document.querySelector('#inspection').hidden = false;
}

function render() {
  const body = document.querySelector('#rows');
  body.replaceChildren();
  const filter = document.querySelector('#filter').value;
  for (const row of result.rows) {
    if (filter === 'issues' && row.status === 'Conferente' || filter === 'Conferente' && row.status !== 'Conferente') continue;
    const tr = el('tr', '');
    const status = el('td', '');
    status.append(el('span', row.status, 'badge' + (row.status === 'Conferente' ? ' ok' : '')));
    tr.append(status);
    const key = el('td', row.cnpj);
    key.append(el('small', 'Documento ' + row.documento));
    tr.append(key);
    for (const source of ['sped', 'dominio']) {
      const cell = el('td', '');
      if (!row[source].length) cell.textContent = '—';
      for (const note of row[source]) {
        cell.append(el('div', supplier(note)), el('small', money(note.valor) + ' · páginas ' + pages(note) + (note.serie ? ' · série ' + note.serie : '')));
      }
      tr.append(cell);
    }
    tr.append(el('td', [row.diferencas, ...(row.pendencias || [])].filter(Boolean).join(' · ') || '—'));
    body.append(tr);
  }
}

form.addEventListener('change', () => {
  result = null;
  files = null;
  inspection = null;
  for (const id of ['result', 'inspection', 'source-summary', 'error']) document.querySelector('#' + id).hidden = true;
});

for (const button of document.querySelectorAll('[data-inspect]')) {
  button.addEventListener('click', () => {
    const source = button.dataset.inspect;
    const file = form.elements.namedItem(source).files[0];
    if (!file) { showError(`Selecione o PDF do ${sourceNames[source]} primeiro.`); return; }
    const payload = new FormData();
    payload.append(source, file);
    document.querySelector('#inspection').hidden = true;
    working(`Lendo o PDF do ${sourceNames[source]}`, async () => {
      const response = await fetch('/conferir/' + source, {method: 'POST', body: payload});
      const data = await readResponse(response);
      if (data.summary) {
        sourceSummary({[source]: data.summary});
        showInspection(data);
      }
      if (!response.ok) throw Error(data.error || 'Falha na leitura.');
    });
  });
}

form.addEventListener('submit', event => {
  event.preventDefault();
  if (busy) return;
  document.querySelector('#result').hidden = true;
  result = null;
  files = new FormData(form);
  working('Lendo os arquivos e comparando as notas', async () => {
    const response = await fetch('/comparar', {method: 'POST', body: files});
    const data = await readResponse(response);
    sourceSummary(data.sources);
    if (!response.ok) throw Error(data.error || 'Falha na comparação.');
    result = data;
    document.querySelector('#counts').textContent = `${data.counts[0]} notas SPED · ${data.counts[1]} notas Domínio`;
    showWarnings(document.querySelector('#warnings'), data.warnings);
    const stats = document.querySelector('#stats');
    stats.replaceChildren();
    for (const [name, count] of [['Notas comparadas', data.rows.length], ['Conferentes', data.rows.filter(row => row.status === 'Conferente').length], ['Pendências', data.rows.filter(row => row.status !== 'Conferente').length]]) {
      const card = el('span', '');
      card.append(el('b', count), document.createTextNode(name));
      stats.append(card);
    }
    render();
    document.querySelector('#result').hidden = false;
  });
});

document.querySelector('#filter').addEventListener('change', () => { if (result) render(); });
document.querySelector('#inspection-search').addEventListener('input', () => { if (inspection) renderInspection(); });

for (const button of document.querySelectorAll('[data-export]')) {
  button.addEventListener('click', () => {
    if (!files || !result) return;
    working('Gerando o relatório', async () => {
      const response = await fetch('/exportar/' + button.dataset.export, {method: 'POST', body: files});
      if (!response.ok) {
        const data = await readResponse(response);
        sourceSummary(data.sources);
        throw Error(data.error || 'Falha ao exportar.');
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'comparativo.' + button.dataset.export;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  });
}
