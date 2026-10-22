/* Optional browser checks. Requires Playwright and Chromium; no real report data. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.COMPARADOR_TEST_URL || 'http://127.0.0.1:5000';
const output = process.env.COMPARADOR_UI_OUTPUT || path.join(os.tmpdir(), 'comparador-ui');
fs.mkdirSync(output, {recursive: true});
const root = path.resolve(__dirname, '..');
const sourceFile = source => path.join(root, 'exemplos', source + '_simulado.pdf');

async function run() {
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {}),
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking']});
  const errors = [];
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}, reducedMotion: 'reduce', acceptDownloads: true});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    assert(await page.locator('#submit').isDisabled());
    assert(await page.locator('[data-inspect="sped"]').isDisabled());
    assert(await page.locator('[data-inspect="dominio"]').isDisabled());
    await page.screenshot({path: path.join(output, 'desktop-inicio.png'), fullPage: true});

    // Keyboard access to examples, then real extraction and comparison endpoints.
    await page.locator('#use-examples').focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => !document.querySelector('#submit').disabled);
    assert.match(await page.locator('[data-filename="sped"]').innerText(), /sped_simulado.pdf/);
    await page.locator('[data-inspect="sped"]').click();
    await page.waitForFunction(() => !document.querySelector('#inspection').hidden && document.querySelector('#loading').hidden);
    assert.match(await page.locator('#inspection-visible').innerText(), /100 de 100/);
    await page.locator('#inspection-search').fill('comercio');
    assert.match(await page.locator('#inspection-rows').innerText(), /Comércio/);
    const identity = await page.locator('#inspection-rows tr:first-child td:first-child').innerText();
    const formatted = `${identity.slice(0,2)}.${identity.slice(2,5)}.${identity.slice(5,8)}/${identity.slice(8,12)}-${identity.slice(12)}`;
    await page.locator('#inspection-search').fill(formatted);
    assert((await page.locator('#inspection-rows tr').count()) > 0);
    assert(!(await page.locator('#inspection-rows').innerText()).includes('Nenhuma nota'));

    await page.locator('#submit').click();
    await page.waitForFunction(() => !document.querySelector('#result').hidden && document.querySelector('#loading').hidden);
    assert.match(await page.locator('#result-visible').innerText(), /45 de 105/);
    assert.equal(await page.locator('#rows tr').count(), 45);
    await page.locator('#filter').selectOption('Divergente');
    assert.equal(await page.locator('#rows tr').count(), 20);
    await page.locator('#result-search').fill('10061');
    assert.equal(await page.locator('#rows tr').count(), 1);
    assert.match(await page.locator('#result-visible').innerText(), /1 de 105/);
    await page.locator('#result-search').fill('nao existe este fornecedor');
    assert.match(await page.locator('#rows').innerText(), /Nenhuma nota encontrada/);
    await page.locator('#result-search').fill('');
    await page.locator('[data-result-filter="Conferente"]').click();
    assert.equal(await page.locator('#rows tr').count(), 60);
    await page.locator('[data-result-filter="all"]').click();
    assert.equal(await page.locator('#rows tr').count(), 105);
    await page.locator('#filter').selectOption('Divergente');
    for (const format of ['xlsx', 'pdf']) {
      const downloadPromise = page.waitForEvent('download');
      await page.locator(`[data-export="${format}"]`).click();
      const download = await downloadPromise;
      assert.equal(download.suggestedFilename(), `comparativo.${format}`);
      await download.saveAs(path.join(output, `relatorio.${format}`));
      assert(fs.statSync(path.join(output, `relatorio.${format}`)).size > 1000);
      await page.waitForFunction(() => document.querySelector('#loading').hidden);
    }
    await page.screenshot({path: path.join(output, 'desktop-resultado.png'), fullPage: true});

    // API contract fixture: distinguish supplier names, values and internal codes.
    const note = (documento, fornecedor, valor, codigo) => ({cnpj:'12345678000190',documento,fornecedor,valor,pagina:1,...(codigo ? {codigo_fornecedor:codigo} : {})});
    const sampleRows = [
      {documento:'201',status:'Conferente',diferencas:'',sped:[note('201','Comércio Exemplo LTDA','100.00')],dominio:[note('201','Comércio Exemplo','100.00','0042')]},
      {documento:'202',status:'Divergente',diferencas:'Fornecedor',sped:[note('202','Empresa Um','200.00')],dominio:[note('202','Empresa Dois','200.00','0043')]},
      {documento:'203',status:'Divergente',diferencas:'Valor',sped:[note('203','Empresa Exemplo','300.00')],dominio:[note('203','Empresa Exemplo','301.00','0044')]},
    ].map(row => ({cnpj:'12345678000190',pendencias:[],...row}));
    await page.route('**/comparar', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({rows:sampleRows,counts:[3,3],warnings:[],sources:{}})}));
    await page.locator('#submit').click();
    await page.waitForFunction(() => document.querySelector('#loading').hidden && !document.querySelector('#result').hidden);
    assert.match(await page.locator('#rows tr:first-child td:last-child').innerText(),/Valor diferente/);
    assert(await page.locator('#rows tr:first-child td:nth-child(3) > div:first-child').evaluate(node => node.classList.contains('note-amount')));
    await page.locator('#result-search').fill('202');
    assert.equal(await page.locator('#rows td > div.field-different').count(),2);
    assert.equal(await page.locator('#rows span.field-different').count(),0);
    assert.match(await page.locator('#rows td:last-child').innerText(),/Nome do fornecedor diferente/);
    await page.locator('#result-search').fill('203');
    assert.equal(await page.locator('#rows td > div.field-different').count(),0);
    assert.equal(await page.locator('#rows span.field-different').count(),2);
    assert.match(await page.locator('#rows td:last-child').innerText(),/Valor diferente/);
    await page.locator('#filter').selectOption('all');
    await page.locator('#result-search').fill('201');
    assert.equal(await page.locator('#rows .field-different').count(),0);
    assert.match(await page.locator('#rows').innerText(),/Conferente/);
    assert.match(await page.locator('#rows td:nth-child(4) > small').filter({hasText:'Código interno'}).innerText(),/Código interno: 0042/);
    await page.locator('#result-search').fill('');
    await page.screenshot({path:path.join(output,'diferenca-de-campos.png'),fullPage:true});
    await page.unroute('**/comparar');

    // Long names, drag and drop, removal, and validation before upload.
    await page.goto(base);
    const longName = 'relatorio_de_entradas_sped_empresa_exemplo_periodo_setembro_2026.pdf';
    await page.locator('#file-sped').setInputFiles({name: longName, mimeType: 'application/pdf', buffer: fs.readFileSync(sourceFile('sped'))});
    assert.equal(await page.locator('[data-filename="sped"]').innerText(), longName);
    assert(await page.locator('#submit').isDisabled());
    assert.match(await page.locator('#next-action').innerText(), /Falta o PDF do Domínio/);
    const transfer = await page.evaluateHandle(bytes => {
      const dt = new DataTransfer();
      dt.items.add(new File([new Uint8Array(bytes)], 'dominio_arrastado.pdf', {type: 'application/pdf'}));
      return dt;
    }, [...fs.readFileSync(sourceFile('dominio'))]);
    await page.locator('[data-drop="dominio"]').dispatchEvent('drop', {dataTransfer: transfer});
    await transfer.dispose();
    assert(await page.locator('#submit').isEnabled());
    await page.locator('[data-remove="dominio"]').click();
    assert(await page.locator('#submit').isDisabled());
    assert(await page.locator('[data-inspect="dominio"]').isDisabled());
    await page.locator('#file-dominio').setInputFiles({name:'incorreto.txt', mimeType:'text/plain', buffer:Buffer.from('texto')});
    assert.match(await page.locator('#error-message').innerText(), /Escolha um arquivo PDF/);
    await page.locator('#dismiss-error').click();
    assert(await page.locator('#error').isHidden());
    assert(await page.locator('#file-dominio').evaluate(node => node === document.activeElement));
    const tooLarge = await page.evaluateHandle(() => {
      const dt = new DataTransfer();
      dt.items.add(new File([new Uint8Array(21 * 1024 * 1024)], 'grande.pdf', {type:'application/pdf'}));
      return dt;
    });
    await page.locator('[data-drop="dominio"]').dispatchEvent('drop', {dataTransfer:tooLarge});
    await tooLarge.dispose();
    assert.match(await page.locator('#error-message').innerText(), /20 MB/);
    assert(await page.locator('#submit').isDisabled());

    // Server-error presentation is exercised against the same payload contract as API tests.
    await page.goto(base);
    await page.locator('#use-examples').click();
    await page.waitForFunction(() => !document.querySelector('#submit').disabled);
    await page.locator('[data-inspect="sped"]').click();
    await page.waitForFunction(() => document.querySelector('#loading').hidden && !document.querySelector('#inspection').hidden);
    await page.route('**/conferir/dominio', route => route.fulfill({status:422, contentType:'application/json', body:JSON.stringify({source:'dominio',notes:[],error:'Layout Domínio precisa de ajuste.',summary:{quantidade:0,paginas:3,total:'0.00',cnpj:0,cpf:0,warnings:['Página 1: nenhuma nota reconhecida.'],error:'Layout Domínio precisa de ajuste.'}})}));
    await page.locator('[data-inspect="dominio"]').click();
    await page.waitForFunction(() => document.querySelector('#loading').hidden && !document.querySelector('#error').hidden);
    assert.match(await page.locator('#source-summary').innerText(), /100 notas lidas/);
    assert.match(await page.locator('#source-summary').innerText(), /Layout Domínio precisa de ajuste/);
    assert.match(await page.locator('#inspection-rows').innerText(), /Nenhuma nota reconhecida/);
    assert(await page.locator('[data-inspect="dominio"]').isEnabled());

    // Mobile viewport: document stays within screen width; tables scroll locally.
    const mobile = await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'reduce'});
    const phone = await mobile.newPage();
    phone.on('pageerror', error => errors.push(error.message));
    await phone.goto(base);
    assert(await phone.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await phone.screenshot({path:path.join(output,'celular-inicio.png'),fullPage:true});
    await phone.locator('#use-examples').click();
    await phone.waitForFunction(() => !document.querySelector('#submit').disabled);
    await phone.locator('#submit').click();
    await phone.waitForFunction(() => document.querySelector('#loading').hidden && !document.querySelector('#result').hidden);
    assert.match(await phone.locator('#result-visible').innerText(), /45 de 105/);
    assert(await phone.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await phone.screenshot({path:path.join(output,'celular-resultado.png'),fullPage:true});
    await phone.setViewportSize({width:320,height:740});
    assert(await phone.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []);
    console.log('Interface aprovada: seleção, arrastar/soltar, remoção, exemplos, leitura, busca, filtros, downloads, avisos e largura móvel.');
    console.log('Capturas e relatórios sintéticos em ' + output);
    await mobile.close();
    await context.close();
  } finally { await browser.close(); }
}
run().catch(error => {console.error(error);process.exitCode=1;});
