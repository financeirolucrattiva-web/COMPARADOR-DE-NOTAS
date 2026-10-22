import re
import unicodedata
from collections import defaultdict
from decimal import Decimal

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
        # Dotted abbreviations (S.A.) and terminal punctuation are formatting.
        value = normalized(value).replace('.', '').replace("'", '')
        return re.sub(r'[^A-Z0-9]+', ' ', value).strip()

    a, b = canonical(left), canonical(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # Accept an extra trailing trade name only when the complete other name
    # matches the main name. Do not match arbitrary prefixes or two aliases.
    suffix = r'\s*(?:\([^()]*\)\s*)+$'
    base_left = re.sub(suffix, '', left).strip()
    base_right = re.sub(suffix, '', right).strip()
    left_has_alias, right_has_alias = base_left != left.strip(), base_right != right.strip()
    if left_has_alias == right_has_alias:
        return False
    return bool(canonical(base_left)) and canonical(base_left) == canonical(base_right)


def compare(left, right):
    groups = []
    for source in (left, right):
        grouped = defaultdict(list)
        for note in source:
            grouped[(note['cnpj'], note['documento'])].append(note)
        groups.append(grouped)
    result = []
    for key in sorted(groups[0].keys() | groups[1].keys()):
        a, b = groups[0].get(key, []), groups[1].get(key, [])
        status, differences, pending = 'Conferente', [], []
        if len(a) > 1 or len(b) > 1:
            status = 'Duplicidade / revisar'
        elif not a:
            status = 'Somente Domínio'
        elif not b:
            status = 'Somente SPED'
        else:
            if not a[0]['fornecedor'] or not b[0]['fornecedor']:
                pending.append('Nome do fornecedor ausente; código interno não valida razão social.')
            elif not supplier_matches(a[0]['fornecedor'], b[0]['fornecedor']):
                differences.append('Fornecedor')
            if Decimal(a[0]['valor']) != Decimal(b[0]['valor']):
                differences.append('Valor')
            if differences:
                status = 'Divergente'
            elif pending:
                status = 'Conferência parcial'
        result.append(dict(cnpj=key[0], documento=key[1], status=status, diferencas=', '.join(differences), pendencias=pending, sped=a, dominio=b))
    return result
