import re
import unicodedata
from collections import defaultdict
from decimal import Decimal

FIELDS = ['cnpj', 'documento', 'fornecedor', 'valor']

def normalized(value):
    return ' '.join(unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().upper().split())

def parse_text(text, page):
    """Conservative fallback: explicit pipe/semicolon separated four-column rows."""
    notes, warnings = [], []
    for number, line in enumerate(text.splitlines(), 1):
        cells = [x.strip() for x in re.split(r'\s*[|;]\s*', line)]
        if len(cells) != 4:
            if re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', line):
                warnings.append(f'Página {page}, linha {number}: formato não reconhecido. Revise a extração.')
            continue
        cnpj, doc, supplier, amount = cells
        if normalized(cnpj) == 'CNPJ':
            continue
        digits = re.sub(r'\D', '', cnpj)
        if len(digits) != 14 or not re.fullmatch(r'\d+', doc) or not supplier or not re.fullmatch(r'(?:R\$\s*)?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}', amount):
            warnings.append(f'Página {page}, linha {number}: campos inválidos; registro não comparado.')
            continue
        value = Decimal(re.sub(r'R\$\s*', '', amount).replace('.', '').replace(',', '.'))
        notes.append(dict(cnpj=digits, documento=str(int(doc)), fornecedor=supplier, valor=str(value), pagina=page))
    return notes, warnings

def extract_pdf(stream):
    import pdfplumber
    notes, warnings = [], []
    with pdfplumber.open(stream) as pdf:
        if len(pdf.pages) > 200:
            raise ValueError('Limite de 200 páginas por arquivo.')
        for number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ''
            if not text.strip():
                warnings.append(f'Página {number}: sem texto extraível. PDF digitalizado exige OCR.')
                continue
            # Prefer tables with explicitly identified columns; never guess column order.
            table_found = False
            aliases = {'CNPJ': 'cnpj', 'NUMERO DO DOCUMENTO': 'documento', 'NR. DOC.': 'documento', 'DOCUMENTO': 'documento', 'FORNECEDOR': 'fornecedor', 'VALOR': 'valor'}
            for table in page.extract_tables():
                for index, row in enumerate(table):
                    mapped = [aliases.get(normalized(c or '')) for c in row]
                    if all(f in mapped for f in FIELDS):
                        table_found = True
                        for data in table[index+1:]:
                            line = ' | '.join((data[mapped.index(f)] or '').replace('\n', ' ') for f in FIELDS)
                            found, issues = parse_text(line, number)
                            notes.extend(found); warnings.extend(issues)
                        break
            if not table_found:
                found, issues = parse_text(text, number)
                notes.extend(found); warnings.extend(issues)
            if not table_found and not any(n['pagina'] == number for n in notes):
                warnings.append(f'Página {number}: nenhuma nota reconhecida. Layout precisa de ajuste.')
    return notes, warnings

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
        status, differences = 'Conferente', []
        if len(a) > 1 or len(b) > 1:
            status = 'Duplicidade / revisar'
        elif not a:
            status = 'Somente Domínio'
        elif not b:
            status = 'Somente SPED'
        else:
            if normalized(a[0]['fornecedor']) != normalized(b[0]['fornecedor']): differences.append('Fornecedor')
            if Decimal(a[0]['valor']) != Decimal(b[0]['valor']): differences.append('Valor')
            if differences: status = 'Divergente'
        result.append(dict(cnpj=key[0], documento=key[1], status=status, diferencas=', '.join(differences), sped=a, dominio=b))
    return result
