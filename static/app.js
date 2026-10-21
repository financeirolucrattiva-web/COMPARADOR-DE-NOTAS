const form = document.querySelector('#upload');
const error = document.querySelector('#error');
const sources = ['sped', 'dominio'];
const sourceNames = {sped: 'SPED', dominio: 'Domínio'};
const MAX_BYTES = 20 * 1024 * 1024;
let result = null;
let files = null;
let inspection = null;
let busy = false;
let summaries = {};
let errorReturnFocus = null;
const money = value => Number(value).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  node.textContent = text;
  if (cls) node.className = cls;
  return node;
};
const inputFor = source => form.elements.namedItem(source);
const fileFor = source => inputFor(source).files[0];
const supplier = note => (note.fornecedor || 'Nome do fornecedor ausente') +
  (note.codigo_fornecedor ? ' (cód. ' + note.codigo_fornecedor + ')' : '');
const pages = note => (note.paginas || [note.pagina]).join(', ');
const searchText = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleUpperCase('pt-BR');
const fileSize = size => size < 1024 * 1024 ? `${(size / 1024).toFixed(1)} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`;

function reveal(node) {
  node.hidden = false;
  node.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
}

function showError(message) {
  const active = document.activeElement;
  if (active && active !== document.body && !error.contains(active)) errorReturnFocus = active;
  document.querySelector('#error-message').textContent = message;
  reveal(error);
  error.focus({preventScroll: true});
}

function syncControls() {
  document.querySelectorAll('button').forEach(button => { button.disabled = busy; });
  sources.forEach(source => {
    const file = fileFor(source);
    const summary = summaries[source];
    inputFor(source).disabled = busy;
    document.querySelector(`[data-inspect="${source}"]`).disabled = busy || !file;
    const remove = document.querySelector(`[data-remove="${source}"]`);
    remove.hidden = !file;
    remove.disabled = busy || !file;
    document.querySelector(`[data-filename="${source}"]`).textContent = file ? file.name : 'Nenhum arquivo selecionado';
    document.querySelector(`[data-filesize="${source}"]`).textContent = file ? `${fileSize(file.size)} · Clique acima para trocar o arquivo.` : 'Você pode conferir este PDF separadamente.';
    document.querySelector(`[data-prompt="${source}"]`).textContent = file ? 'Trocar arquivo PDF' : 'Arraste o PDF aqui';
    const state = document.querySelector(`[data-state="${source}"]`);
    state.dataset.kind = !file ? 'empty' : summary?.error ? 'error' : summary?.warnings?.length ? 'warning' : summary ? 'read' : 'selected';
    state.textContent = !file ? 'Aguardando PDF' : summary?.error ? 'Revisar leitura' : summary?.warnings?.length ? 'Leitura com avisos' : summary ? `${summary.quantidade} notas lidas` : 'PDF selecionado';
  });
  const selected = sources.filter(source => fileFor(source));
  document.querySelector('#submit').disabled = busy || selected.length !== 2;
  const next = document.querySelector('#next-action');
  next.textContent = selected.length === 0 ? 'Adicione os dois PDFs para liberar a comparação.' : selected.length === 1 ? `Falta o PDF do ${sourceNames[sources.find(source => !fileFor(source))]}. Você já pode conferir o arquivo selecionado.` : 'Tudo pronto para comparar. Se quiser, confira a leitura de cada PDF primeiro.';
  document.querySelectorAll('[data-export]').forEach(button => { button.disabled = busy || !result; });
}

function sourceSummary(updated) {
  summaries = {...summaries, ...(updated || {})};
  const container = document.querySelector('#source-summary');
  container.replaceChildren();
  for (const source of sources) {
    const summary = summaries[source];
    if (!summary) continue;
    const card = el('div', '', 'source-card');
    card.dataset.kind = summary.error ? 'error' : 'read';
    card.append(el('strong', sourceNames[source] || source));
    card.append(el('p', summary.error || `${summary.quantidade} notas lidas · ${summary.paginas} páginas · ${money(summary.total)}`));
    if (summary.warnings?.length) card.append(el('p', `${summary.warnings.length} aviso(s). Use “Conferir leitura” para revisar.`));
    container.append(card);
  }
  container.hidden = !container.childElementCount;
  syncControls();
}

function invalidate(source) {
  result = null;
  files = null;
  delete summaries[source];
  document.querySelector('#result').hidden = true;
  if (inspection?.source === source) {
    inspection = null;
    document.querySelector('#inspection').hidden = true;
  }
  error.hidden = true;
  sourceSummary({});
}

function validateFile(source, file) {
  if (!/\.pdf$/i.test(file.name)) throw Error(`Escolha um arquivo PDF para o ${sourceNames[source]}.`);
  const total = file.size + sources.filter(other => other !== source).reduce((sum, other) => sum + (fileFor(other)?.size || 0), 0);
  if (total > MAX_BYTES) throw Error('Os dois arquivos juntos devem ter no máximo 20 MB. Escolha PDFs menores para continuar.');
}

function setFile(source, file) {
  validateFile(source, file);
  const transfer = new DataTransfer();
  transfer.items.add(file);
  inputFor(source).files = transfer.files;
  invalidate(source);
}

async function readResponse(response) {
  try { return await response.json(); }
  catch (_) { throw Error('Não foi possível receber a resposta. Confira se a janela do programa continua aberta e tente novamente.'); }
}

async function working(message, action, activeSources = []) {
  if (busy) return;
  errorReturnFocus = document.activeElement;
  busy = true;
  error.hidden = true;
  syncControls();
  activeSources.forEach(source => document.querySelector(`[data-card="${source}"]`).setAttribute('aria-busy', 'true'));
  const loading = document.querySelector('#loading');
  document.querySelector('#loading-title').textContent = message;
  const started = Date.now();
  const update = () => {
    const elapsed = Math.floor((Date.now() - started) / 1000);
    document.querySelector('#loading-time').textContent = `${elapsed}s decorridos. Relatórios longos podem levar mais tempo; mantenha a janela do programa aberta.`;
  };
  update();
  reveal(loading);
  const timer = setInterval(update, 1000);
  try { await action(); }
  catch (exc) { showError(exc.message || 'Falha ao acessar o programa. Confira se ele continua aberto.'); }
  finally {
    clearInterval(timer);
    loading.hidden = true;
    activeSources.forEach(source => document.querySelector(`[data-card="${source}"]`).setAttribute('aria-busy', 'false'));
    busy = false;
    syncControls();
  }
}

function showWarnings(container, warnings) {
  container.replaceChildren();
  for (const warning of warnings || []) container.append(el('p', warning));
}

function matchesSearch(query, notes, identity = '') {
  if (!query) return true;
  const text = searchText(identity + ' ' + notes.map(note => `${note.cnpj} ${note.documento} ${supplier(note)}`).join(' '));
  const digits = /^[\d.\-\/\s]+$/.test(query) ? query.replace(/\D/g, '') : '';
  return text.includes(query) || Boolean(digits && notes.some(note => note.cnpj.includes(digits) || note.documento.includes(digits)));
}

function emptyRow(body, message) {
  const row = el('tr', '');
  const cell = el('td', message, 'empty-state');
  cell.colSpan = 5;
  row.append(cell);
  body.append(row);
}

function renderInspection() {
  const query = searchText(document.querySelector('#inspection-search').value.trim());
  const matching = inspection.notes.filter(note => matchesSearch(query, [note]));
  const rows = document.querySelector('#inspection-rows');
  rows.replaceChildren();
  for (const note of matching) {
    const row = el('tr', '');
    row.append(el('td', note.cnpj), el('td', note.documento + (note.serie ? ' / ' + note.serie : '')),
      el('td', supplier(note)), el('td', money(note.valor)), el('td', pages(note)));
    rows.append(row);
  }
  if (!matching.length) emptyRow(rows, inspection.notes.length ? 'Nenhuma nota encontrada para essa busca.' : 'Nenhuma nota reconhecida. Confira os avisos de leitura acima.');
  document.querySelector('#inspection-visible').textContent = `${matching.length} de ${inspection.notes.length} notas`;
}

function showInspection(data) {
  inspection = data;
  const summary = data.summary;
  document.querySelector('#inspection-title').textContent = `Leitura do ${sourceNames[data.source]}`;
  document.querySelector('#inspection-counts').textContent = `${summary.quantidade} notas · ${summary.paginas} páginas · ${summary.cnpj} CNPJ · ${summary.cpf} CPF · Total lido: ${money(summary.total)}`;
  document.querySelector('#inspection-search').value = '';
  showWarnings(document.querySelector('#inspection-warnings'), summary.warnings);
  renderInspection();
  reveal(document.querySelector('#inspection'));
}

function render() {
  const body = document.querySelector('#rows');
  body.replaceChildren();
  const filter = document.querySelector('#filter').value;
  const query = searchText(document.querySelector('#result-search').value.trim());
  const matching = result.rows.filter(row => (filter === 'all' || (filter === 'issues' ? row.status !== 'Conferente' : row.status === filter)) && matchesSearch(query, [...row.sped, ...row.dominio], `${row.cnpj} ${row.documento}`));
  for (const row of matching) {
    const tr = el('tr', '');
    const status = el('td', '');
    const cls = row.status === 'Conferente' ? 'ok' : row.status === 'Divergente' ? 'different' : row.status.startsWith('Somente') ? 'missing' : '';
    status.append(el('span', row.status, 'badge ' + cls));
    tr.append(status);
    const key = el('td', row.cnpj);
    key.append(el('small', 'Documento ' + row.documento));
    tr.append(key);
    for (const source of sources) {
      const cell = el('td', '');
      if (!row[source].length) cell.textContent = '—';
      for (const note of row[source]) cell.append(el('div', supplier(note)), el('small', money(note.valor) + ' · páginas ' + pages(note) + (note.serie ? ' · série ' + note.serie : '')));
      tr.append(cell);
    }
    tr.append(el('td', [row.diferencas, ...(row.pendencias || [])].filter(Boolean).join(' · ') || '—'));
    body.append(tr);
  }
  if (!matching.length) emptyRow(body, query ? 'Nenhuma nota encontrada para essa busca e situação.' : filter === 'issues' ? 'Nenhuma pendência encontrada. Selecione “Todas as notas” para conferir os documentos.' : 'Nenhuma nota encontrada nessa situação.');
  document.querySelector('#result-visible').textContent = `${matching.length} de ${result.rows.length} documentos`;
  document.querySelectorAll('[data-result-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.resultFilter === filter)));
}

for (const source of sources) {
  inputFor(source).addEventListener('change', () => {
    try {
      const file = fileFor(source);
      if (file) validateFile(source, file);
      invalidate(source);
    } catch (exc) {
      inputFor(source).value = '';
      invalidate(source);
      showError(exc.message);
    }
  });
  document.querySelector(`[data-remove="${source}"]`).addEventListener('click', () => {
    inputFor(source).value = '';
    invalidate(source);
    inputFor(source).focus();
  });
  const drop = document.querySelector(`[data-drop="${source}"]`);
  drop.addEventListener('dragover', event => { event.preventDefault(); if (!busy) drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('dragover'));
  drop.addEventListener('drop', event => {
    event.preventDefault();
    drop.classList.remove('dragover');
    if (busy) return;
    if (event.dataTransfer.files.length !== 1) { showError('Arraste apenas um PDF para cada espaço.'); return; }
    try { setFile(source, event.dataTransfer.files[0]); }
    catch (exc) { showError(exc.message); }
  });
}

document.querySelector('#use-examples').addEventListener('click', () => working('Preparando os exemplos fictícios', async () => {
  const exampleFiles = await Promise.all(sources.map(async source => {
    const response = await fetch(`/exemplos/${source}_simulado.pdf`);
    if (!response.ok) throw Error('Não foi possível carregar os exemplos. Tente novamente.');
    return new File([await response.blob()], `${source}_simulado.pdf`, {type: 'application/pdf'});
  }));
  if (exampleFiles.reduce((sum, file) => sum + file.size, 0) > MAX_BYTES) throw Error('Os arquivos de exemplo ultrapassam o limite de 20 MB.');
  sources.forEach(source => { inputFor(source).value = ''; });
  summaries = {};
  inspection = null;
  document.querySelector('#inspection').hidden = true;
  sources.forEach((source, index) => setFile(source, exampleFiles[index]));
}));

for (const button of document.querySelectorAll('[data-inspect]')) button.addEventListener('click', () => {
  const source = button.dataset.inspect;
  const file = fileFor(source);
  if (!file) { showError(`Selecione o PDF do ${sourceNames[source]} primeiro.`); return; }
  const payload = new FormData();
  payload.append(source, file);
  document.querySelector('#inspection').hidden = true;
  working(`Lendo o PDF do ${sourceNames[source]}`, async () => {
    const response = await fetch('/conferir/' + source, {method: 'POST', body: payload});
    const data = await readResponse(response);
    if (data.summary) { sourceSummary({[source]: data.summary}); showInspection(data); }
    if (!response.ok) throw Error(data.error || 'Falha na leitura.');
  }, [source]);
});

form.addEventListener('submit', event => {
  event.preventDefault();
  if (busy) return;
  if (!sources.every(source => fileFor(source))) { showError('Selecione os dois PDFs para comparar.'); return; }
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
    document.querySelector('#result-search').value = '';
    document.querySelector('#filter').value = 'issues';
    showWarnings(document.querySelector('#warnings'), data.warnings);
    const stats = document.querySelector('#stats');
    stats.replaceChildren();
    for (const [name, count, filter] of [['Documentos no resultado', data.rows.length, 'all'], ['Conferentes', data.rows.filter(row => row.status === 'Conferente').length, 'Conferente'], ['Com pendências', data.rows.filter(row => row.status !== 'Conferente').length, 'issues']]) {
      const card = el('button', '', 'stat-card');
      card.type = 'button';
      card.dataset.resultFilter = filter;
      card.append(el('b', count), el('span', name));
      card.addEventListener('click', () => { document.querySelector('#filter').value = filter; render(); });
      stats.append(card);
    }
    render();
    reveal(document.querySelector('#result'));
  }, sources);
});

document.querySelector('#dismiss-error').addEventListener('click', () => {
  error.hidden = true;
  const target = errorReturnFocus?.isConnected && !errorReturnFocus.disabled && errorReturnFocus.getClientRects().length ? errorReturnFocus : document.querySelector('#use-examples');
  target.focus();
});
document.querySelector('#filter').addEventListener('change', () => { if (result) render(); });
document.querySelector('#result-search').addEventListener('input', () => { if (result) render(); });
document.querySelector('#inspection-search').addEventListener('input', () => { if (inspection) renderInspection(); });
for (const button of document.querySelectorAll('[data-export]')) button.addEventListener('click', () => {
  if (!files || !result) return;
  working('Gerando seu relatório completo', async () => {
    const response = await fetch('/exportar/' + button.dataset.export, {method: 'POST', body: files});
    if (!response.ok) { const data = await readResponse(response); sourceSummary(data.sources); throw Error(data.error || 'Falha ao exportar.'); }
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'comparativo.' + button.dataset.export;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
});
syncControls();
