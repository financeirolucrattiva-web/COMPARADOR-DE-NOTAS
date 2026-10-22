"""Domínio Acompanhamento de Entradas: read text objects before overlaps merge."""
import re
from decimal import Decimal

import pypdfium2 as pdfium


def _key(value):
    from comparator import normalized
    return re.sub(r'[^A-Z0-9]', '', normalized(value))


def _items(page, textpage):
    items = []
    for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_TEXT], textpage=textpage):
        text = obj.extract().strip()
        if not text:
            continue
        left, bottom, right, top = obj.get_bounds()
        items.append(dict(text=text, key=_key(text), left=left, right=right,
                          y=obj.get_matrix().f, center=(left+right)/2))
    return items


def _rows(items):
    rows = []
    for item in sorted(items, key=lambda obj: -obj['y']):
        if not rows or abs(rows[-1][0]['y'] - item['y']) > .65:
            rows.append([item])
        else:
            rows[-1].append(item)
    return rows


def _anchors(row):
    labels = {item['key']: item for item in row}
    required = {'DATAEMISSAO','DATAENTRADA','NOTA','SERIE','ESPECIE','FORNECEDOR','CNPJCPFCEICAEPF','VALORCONTABIL'}
    if not required <= labels.keys():
        return None
    codes = sorted((item for item in row if item['key'] == 'CODIGO'), key=lambda item: item['left'])
    if len(codes) != 2:
        return None
    return dict(emissao=labels['DATAEMISSAO'], entrada=labels['DATAENTRADA'],
                documento=labels['NOTA'], serie=labels['SERIE'], especie=labels['ESPECIE'],
                fornecedor=labels['FORNECEDOR'], cnpj=labels['CNPJCPFCEICAEPF'],
                valor=labels['VALORCONTABIL'], codigo=codes[0], codigo_fornecedor=codes[1])


def _field(row, anchor, alignment, field):
    from comparator import MONEY
    # Alignment comes from the report's headers, never a hard-coded x coordinate.
    # Match each object's origin/edge so long supplier names remain intact even
    # when their visible text extends over the next columns.
    candidates = [item for item in row if abs(item[alignment] - anchor[alignment]) <= 2]
    if field in ('codigo', 'codigo_fornecedor', 'documento', 'especie'):
        candidates = [item for item in candidates if re.fullmatch(r'\d+', item['text'])]
    elif field == 'valor':
        # Keep malformed numeric objects too: an overlapping second amount may
        # lose punctuation in PDFium text extraction and must still be flagged.
        candidates = [item for item in candidates if re.fullmatch(MONEY, item['text'])
                      or re.fullmatch(r'[\d.,R$+\s-]+', item['text'])]
    elif field in ('emissao', 'entrada'):
        candidates = [item for item in candidates if re.fullmatch(r'\d{2}/\d{2}/\d{4}', item['text'])]
    if len(candidates) > 1:
        raise ValueError(f'coluna {field} ambígua')
    return candidates[0]['text'] if candidates else ''


class DominioEntries:
    def __init__(self):
        self.notes = []
        self.warnings = []
        self.declared_total = None
        self.awaiting_total = False
        self.identified = 0

    def consume(self, page, textpage, number):
        from comparator import MONEY, parse_record
        groups = _rows(_items(page, textpage))
        anchors = None
        for row in groups:
            found = _anchors(row)
            if found:
                anchors = found
                continue
            if anchors is None:
                continue
            if any(item['key'] == 'TOTALGERAL' for item in row):
                self.awaiting_total = True
            # Tax totals and continuations do not identify new notes.
            dates = [item for item in row if re.fullmatch(r'\d{2}/\d{2}/\d{4}', item['text'])]
            if self.awaiting_total and not dates:
                try:
                    amount = _field(row, anchors['valor'], 'right', 'Valor Contábil')
                    if re.fullmatch(MONEY, amount):
                        value = Decimal(amount.replace('.', '').replace(',', '.'))
                        if self.declared_total is not None:
                            self.warnings.append(f'Página {number}: mais de um Total Geral; confira o escopo dos arquivos.')
                        self.declared_total = value
                        self.awaiting_total = False
                except ValueError as exc:
                    self.warnings.append(f'Página {number}: {exc}; Total Geral não utilizado.')
                continue
            if not dates:
                continue
            self.identified += 1
            try:
                fields = {}
                for field, alignment in [('emissao','center'),('entrada','center'),('documento','right'),('serie','left'),('especie','right'),('fornecedor','left'),('cnpj','left'),('valor','right'),('codigo','right'),('codigo_fornecedor','right')]:
                    fields[field] = _field(row, anchors[field], alignment, field)
                if not all(re.fullmatch(r'\d{2}/\d{2}/\d{4}', fields[field]) for field in ('emissao','entrada')):
                    raise ValueError('datas de identificação inválidas')
                if not all(re.fullmatch(r'\d+', fields[field]) for field in ('codigo','codigo_fornecedor','especie')):
                    raise ValueError('código do registro, fornecedor ou espécie inválido')
                note, issue = parse_record([fields['cnpj'],fields['documento'],fields['fornecedor'],fields['valor']],dict(cnpj=0,documento=1,fornecedor=2,valor=3),number)
                if issue:
                    raise ValueError(issue)
                note.update(codigo_fornecedor=fields['codigo_fornecedor'], codigo_registro=fields['codigo'],
                            serie=fields['serie'], especie=fields['especie'],
                            data_emissao=fields['emissao'], data_entrada=fields['entrada'],
                            valor_origem='Valor Contábil (Domínio)')
                self.notes.append(note)
            except ValueError as exc:
                self.warnings.append(f'Página {number}, registro {self.identified}: {exc}; nota não comparada.')
        if anchors is None:
            self.warnings.append(f'Página {number}: cabeçalhos do acompanhamento Domínio não identificados; revise a página.')

    def finish(self, metadata):
        total = sum((Decimal(note['valor']) for note in self.notes), Decimal('0.00'))
        if self.declared_total is None:
            self.warnings.append('Total Geral do Domínio não identificado; confira a cobertura das notas lidas.')
        elif total != self.declared_total:
            self.warnings.append(f'Total das notas reconhecidas ({total:.2f}) difere do Total Geral do Domínio ({self.declared_total:.2f}); confira as notas e os avisos.')
        if metadata is not None:
            metadata['leitor'] = 'dominio_acompanhamento'
            metadata['documentos_identificados'] = self.identified
            if self.declared_total is not None:
                metadata['total_declarado'] = str(self.declared_total)
        return self.notes, self.warnings


def extract_dominio(stream, metadata=None):
    """Return None for other layouts so existing generic/SPED readers still run."""
    stream.seek(0)
    content = stream.read()
    stream.seek(0)
    try:
        document = pdfium.PdfDocument(content)
    except pdfium.PdfiumError:
        return None  # Existing reader provides the usual damaged/encrypted error.
    try:
        if len(document) > 200:
            raise ValueError('Limite de 200 páginas por arquivo.')
        if not len(document):
            return None
        first = document[0]
        textpage = first.get_textpage()
        try:
            title = _key(textpage.get_text_range())
        finally:
            textpage.close(); first.close()
        if not all(marker in title for marker in ('ACOMPANHAMENTODEENTRADAS','VALORCONTABIL','CNPJCPFCEICAEPF','FORNECEDOR')):
            return None
        reader = DominioEntries()
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            try:
                reader.consume(page,textpage,index+1)
            finally:
                textpage.close(); page.close()
        if metadata is not None:
            metadata['paginas'] = len(document)
        return reader.finish(metadata)
    finally:
        document.close()
        stream.seek(0)
