import re
import unicodedata
from collections import defaultdict
from decimal import Decimal
from difflib import SequenceMatcher

MONEY = r'(?:R\$\s*)?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}'
HEADER_ALIASES = {
    'CNPJ': 'cnpj', 'CNPJCPF': 'cnpj', 'CNPJCPFCEICAEPF': 'cnpj',
    'CNPJCPFCEICAEPFI': 'cnpj',
    'NUMERODODOCUMENTO': 'documento', 'NRDOC': 'documento',
    'NDOC': 'documento', 'NRODOC': 'documento', 'NUMDOC': 'documento',
    'NODOC': 'documento', 'NODODOCUMENTO': 'documento',
    'DOCUMENTO': 'documento', 'NOTA': 'documento',
    'NOTASERIE': 'documento_serie', 'SERIE': 'serie',
    'FORNECEDOR': 'fornecedor', 'RAZAOSOCIAL': 'fornecedor',
    'NOMEEMPRESARIAL': 'fornecedor', 'NOMERAZAOSOCIAL': 'fornecedor',
    'CODIGOFORNECEDOR': 'codigo_fornecedor', 'CODFORNECEDOR': 'codigo_fornecedor',
    'VALOR': 'valor', 'VALORCONTABIL': 'valor_contabil',
    'VALORCONTABILTIPO': 'valor_contabil_tipo',
    'VALORDAOPERACAO': 'valor_operacao',
    'VALOROPERACAO': 'valor_operacao',
}


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().upper().split())


def column_name(value):
    return HEADER_ALIASES.get(re.sub(r'[^A-Z0-9]', '', normalized(value or '')))


def map_header(cells):
    columns = {}
    duplicates = set()
    for index, cell in enumerate(cells):
        field = column_name(cell)
        if field:
            if field in columns:
                duplicates.add(field)
            columns[field] = index
    if 'cnpj' not in columns or not ({'documento', 'documento_serie'} & columns.keys()):
        return None
    domain = bool({'valor_contabil', 'valor_contabil_tipo'} & columns.keys())
    if domain or 'valor_operacao' in columns:
        # A report also has ICMS/IPI "Valor" columns. Never use them as note totals.
        columns.pop('valor', None)
    if duplicates & columns.keys():
        return None
    if not ({'valor', 'valor_contabil', 'valor_contabil_tipo', 'valor_operacao'} & columns.keys()):
        return None
    if 'fornecedor' not in columns and not (domain and 'codigo_fornecedor' in columns):
        return None
    return columns


def parse_record(cells, columns, page):
    def get(field):
        index = columns.get(field)
        return ' '.join((cells[index] or '').split()) if index is not None and index < len(cells) else ''
    identity = get('cnpj')
    digits = re.sub(r'\D', '', identity)
    if not (re.fullmatch(r'(?:\d{14}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', identity)
            or re.fullmatch(r'(?:\d{11}|\d{3}\.\d{3}\.\d{3}-\d{2})', identity)):
        return None, 'CNPJ/CPF ausente ou inválido; CEI/CAEPF ainda não suportados.'
    doc = get('documento')
    series = get('serie')
    if 'documento_serie' in columns:
        match = re.fullmatch(r'(\d+)(?:[ /\-]+([A-Za-z0-9]+))?', get('documento_serie'))
        if not match:
            return None, 'Nota/Série em formato não reconhecido; registro não comparado.'
        doc, series = match.group(1), match.group(2) or ''
    if not re.fullmatch(r'\d+', doc):
        return None, 'Número da nota ausente ou inválido; registro não comparado.'
    field = next((f for f in ('valor_contabil_tipo', 'valor_contabil', 'valor_operacao', 'valor') if f in columns), None)
    amount = get(field)
    pattern = f'({MONEY})' + (r'(?:\s+[A-Za-z0-9]+)?' if field == 'valor_contabil_tipo' else '')
    match = re.fullmatch(pattern, amount)
    if not match:
        return None, 'Valor contábil ausente ou fora do padrão brasileiro; registro não comparado.'
    supplier, code = get('fornecedor'), get('codigo_fornecedor')
    if not supplier and not code:
        return None, 'Nome e código do fornecedor ausentes; registro não comparado.'
    value = Decimal(re.sub(r'R\$\s*', '', match.group(1)).replace('.', '').replace(',', '.'))
    note = dict(cnpj=digits, documento=str(int(doc)), fornecedor=supplier, valor=str(value), pagina=page,
                tipo_identificacao='CPF' if len(digits) == 11 else 'CNPJ')
    if code:
        note['codigo_fornecedor'] = code
    if series:
        note['serie'] = series
    return note, None


def parse_text(text, page):
    """Read explicit pipe/semicolon-separated columns, optionally with headers."""
    notes, warnings, columns = [], [], None
    for number, line in enumerate(text.splitlines(), 1):
        cells = [x.strip() for x in re.split(r'\s*[|;]\s*', line)]
        header = map_header(cells)
        if header:
            columns = header
            continue
        if columns is None and len(cells) != 4:
            if re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', line):
                warnings.append(f'Página {page}, linha {number}: formato não reconhecido. Revise a extração.')
            continue
        if len(cells) == 1:
            continue
        mapping = columns or dict(cnpj=0, documento=1, fornecedor=2, valor=3)
        note, issue = parse_record(cells, mapping, page)
        if note:
            notes.append(note)
        else:
            warnings.append(f'Página {page}, linha {number}: {issue}')
    return notes, warnings


def find_table_header(table, start):
    """Join up to three physical header rows, preserving each column's position."""
    for height in range(1, min(3, len(table) - start) + 1):
        rows = table[start:start+height]
        width = max(len(row) for row in rows)
        joined = [' '.join((row[i] or '') for row in rows if i < len(row)) for i in range(width)]
        columns = map_header(joined)
        if columns:
            return columns, height
    return None, 0


def parse_table(table, page):
    notes, warnings, columns, index, recognized = [], [], None, 0, False
    while index < len(table):
        header, height = find_table_header(table, index)
        if header:
            recognized, columns = True, header
            index += height
            continue
        row = table[index]
        index += 1
        if columns is None or not any(cell for cell in row):
            continue
        first = next((normalized(c) for c in row if c), '')
        if re.fullmatch(r'TOTAL(?:\s.*)?', first):
            continue
        note, issue = parse_record(row, columns, page)
        if note:
            notes.append(note)
        else:
            warnings.append(f'Página {page}, linha de tabela {index}: {issue}')
    return notes, warnings, recognized


def extract_pdf(stream, metadata=None):
    from dominio_reader import extract_dominio
    domain = extract_dominio(stream, metadata)
    if domain is not None:
        return domain
    from pdf_orientation import readable_pdf
    from sped_reader import SpedBlocks
    notes, warnings = [], []
    sped = SpedBlocks()
    with readable_pdf(stream) as pdf:
        if metadata is not None:
            metadata['paginas'] = len(pdf.pages)
        for number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ''
            if not text.strip():
                warnings.append(f'Página {number}: sem texto extraível. PDF digitalizado exige OCR.')
                continue
            table_found = False
            sped_found = False
            page_notes = []
            for table in page.extract_tables():
                if sped.consume(table, number):
                    table_found = sped_found = True
                    continue
                found, issues, recognized = parse_table(table, number)
                if recognized:
                    table_found = True
                    page_notes.extend(found)
                    warnings.extend(issues)
            if not table_found:
                found, issues = parse_text(text, number)
                page_notes.extend(found)
                warnings.extend(issues)
            if not page_notes and not sped_found:
                warnings.append(f'Página {number}: nenhuma nota reconhecida. Layout precisa de ajuste.')
            missing_names = sum(not n['fornecedor'] for n in page_notes)
            if missing_names:
                warnings.append(f'Página {number}: {missing_names} registro(s) com código de fornecedor, sem razão social. Conferência do nome do fornecedor pendente.')
            notes.extend(page_notes)
            page.close()
    sped.finish()
    notes.extend(sped.notes)
    warnings.extend(sped.warnings)
    return notes, warnings


def supplier_label(note):
    name = note.get('fornecedor') or 'Nome do fornecedor ausente'
    if note.get('codigo_fornecedor'):
        name += f"\nCódigo interno: {note['codigo_fornecedor']}"
    return name


def supplier_matches(left, right):
    def canonical(value):
        # With the same identity/document, trailing trade names are secondary.
        value = re.sub(r'\s*(?:\([^()]*\)\s*)+$', '', value).strip()
        # Dotted abbreviations (S.A.) and terminal punctuation are formatting.
        value = normalized(value).replace('.', '').replace("'", '')
        value = re.sub(r'[^A-Z0-9]+', ' ', value).strip()
        # MEI registered names may start with the eight-digit company root.
        value = re.sub(r'^\d{8}\s+(?=[A-Z])', '', value)
        # Reports may abbreviate the registered name by omitting this suffix.
        # Restrict this to whole terminal words; never trim arbitrary prefixes.
        return re.sub(r'(?:\s+(?:LTDA|LIMITADA))+$', '', value)

    a, b = canonical(left), canonical(right)
    if not a or not b:
        return False
    if a == b:
        return True
    connectors = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E'}
    generic = {'EMPRESA', 'COMERCIO', 'COMERCIAL', 'INDUSTRIA', 'DISTRIBUIDORA', 'PRODUTOS',
               'SERVICOS', 'TRANSPORTES', 'LTDA', 'LIMITADA', 'SA', 'ME', 'EPP', 'EIRELI'}
    words_a = [word for word in a.split() if word not in connectors]
    words_b = [word for word in b.split() if word not in connectors]
    common = []
    for x, y in zip(words_a, words_b):
        if x != y:
            break
        common.append(x)
    meaningful = any(word not in generic for word in common)
    if meaningful and ((len(common) >= 2 and len(''.join(common)) >= 8)
                       or (common and len(common[0]) >= 6)):
        return True
    # A report can cut even the last word of a long name.
    short, long = sorted((a, b), key=len)
    if (len(short.replace(' ', '')) >= 6 and long.startswith(short)
            and any(word not in generic | connectors for word in short.split())):
        return True
    # Small spelling changes are not absolutely different names. Require a
    # substantial shared word as well as high similarity in both directions.
    shared = (set(words_a) & set(words_b)) - generic
    informative_a = {word for word in words_a if len(word) >= 3 and word not in generic}
    informative_b = {word for word in words_b if len(word) >= 3 and word not in generic}
    overlap = informative_a & informative_b
    if (len(overlap) >= 2 and sum(map(len, overlap)) >= 8
            and len(overlap) / min(len(informative_a), len(informative_b)) >= .75):
        return True
    significant_a = ' '.join(word for word in words_a if len(word) >= 3 and word not in generic)
    significant_b = ' '.join(word for word in words_b if len(word) >= 3 and word not in generic)
    close_single_name = (min(len(significant_a), len(significant_b)) >= 6
                         and significant_a[:4] == significant_b[:4])
    if min(len(a), len(b)) >= 8 and (any(len(word) >= 4 for word in shared) or close_single_name):
        similarity = min(SequenceMatcher(None, a, b, autojunk=False).ratio(),
                         SequenceMatcher(None, b, a, autojunk=False).ratio())
        return similarity >= .9
    return False


def issue_date(note):
    from datetime import datetime
    try:
        return datetime.strptime(note.get('data_emissao', ''), '%d/%m/%Y').date()
    except (ValueError, TypeError):
        return None


def document_label(row):
    a = ', '.join(n['documento'] for n in row['sped'])
    b = ', '.join(n['documento'] for n in row['dominio'])
    return f'SPED: {a}\nDomínio: {b}' if a and b and a != b else a or b


def service_sequence(note):
    """Domínio municipal NFS-e: YY + 11-digit padded sequence, dated that year."""
    date = issue_date(note)
    number = note['documento']
    if (date and note.get('especie') == '66' and re.fullmatch(r'\d{13}', number)
            and number.startswith(date.strftime('%y') + '0')):
        sequence = str(int(number[2:]))
        if sequence != '0':
            return sequence
    return None


def compare(left, right):
    groups = [defaultdict(list), defaultdict(list)]
    for source, grouped in zip((left, right), groups):
        for note in source:
            grouped[(note['cnpj'], note['documento'])].append(note)
    result, used = [], [set(), set()]

    def add(a, b, method='exata', review=False):
        primary = (a or b)[0]
        status, differences, pending = 'Conferente', [], []
        if review:
            status = 'Correspondência a revisar'
            pending.append('Mais de uma nota com o mesmo CNPJ/CPF, valor e data de emissão. Não houve pareamento automático; confira os números originais.')
        elif len(a) > 1 or len(b) > 1:
            status = 'Duplicidade / revisar'
        elif not a:
            status = 'Somente Domínio'
            pending.append('Não localizada no PDF SPED enviado. Confira o documento original e o período dos arquivos.')
        elif not b:
            status = 'Somente SPED'
            pending.append('Não localizada no PDF Domínio enviado. Confira o documento original e o período dos arquivos.')
        else:
            # Identity/document define the pair; money takes priority over name.
            if Decimal(a[0]['valor']) != Decimal(b[0]['valor']):
                differences.append('Valor')
            if method == 'cnpj_valor_data':
                differences.append('Documento')
                pending.append('Mesmo CNPJ/CPF, valor e data de emissão; números diferentes nos PDFs. Confirme o documento original.')
            if not a[0]['fornecedor'] or not b[0]['fornecedor']:
                pending.append('Nome do fornecedor ausente; código interno não valida razão social.')
            elif not supplier_matches(a[0]['fornecedor'], b[0]['fornecedor']):
                differences.append('Fornecedor')
            if differences:
                status = 'Divergente'
            elif pending:
                status = 'Conferência parcial'
        result.append(dict(cnpj=primary['cnpj'], documento=primary['documento'], status=status,
                           diferencas=', '.join(differences), pendencias=pending,
                           correspondencia=method, sped=a, dominio=b))

    # Reserve exact keys and duplicates first. A note may never be reused.
    for key in sorted(groups[0].keys() | groups[1].keys()):
        a, b = groups[0].get(key, []), groups[1].get(key, [])
        if (a and b) or len(a) > 1 or len(b) > 1:
            add(a, b)
            used[0].add(key); used[1].add(key)

    # Reconcile recognized annual service numbering without changing raw notes.
    aliases = defaultdict(list)
    for key, b in groups[1].items():
        if key in used[1]:
            continue
        sequence = service_sequence(b[0])
        target = (key[0], sequence)
        a = groups[0].get(target, [])
        if (sequence and target not in used[0] and len(a) == 1
                and a[0].get('modelo') == '01' and issue_date(a[0]) == issue_date(b[0])):
            aliases[target].append(key)
    for target, candidates in aliases.items():
        if len(candidates) == 1:
            key = candidates[0]
            add(groups[0][target], groups[1][key], 'sequencial_nfse')
            used[0].add(target); used[1].add(key)

    # An exact CNPJ/value/date is evidence to review a different document number,
    # never evidence to declare it conferente. Ambiguous groups stay together.
    candidates = [defaultdict(list), defaultdict(list)]
    for index, grouped in enumerate(groups):
        for key, notes in grouped.items():
            if key not in used[index] and issue_date(notes[0]):
                signature = (key[0], Decimal(notes[0]['valor']), issue_date(notes[0]))
                candidates[index][signature].append(key)
    for signature in sorted(candidates[0].keys() & candidates[1].keys()):
        keys_a, keys_b = candidates[0][signature], candidates[1][signature]
        a = [n for key in keys_a for n in groups[0][key]]
        b = [n for key in keys_b for n in groups[1][key]]
        add(a, b, 'cnpj_valor_data', review=len(a) != 1 or len(b) != 1)
        used[0].update(keys_a); used[1].update(keys_b)
    for index, grouped in enumerate(groups):
        for key, notes in grouped.items():
            if key not in used[index]:
                add(notes if index == 0 else [], notes if index == 1 else [])
    result.sort(key=lambda row: (row['cnpj'], row['documento']))
    return result
