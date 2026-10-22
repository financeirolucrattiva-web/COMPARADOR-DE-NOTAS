"""SPED PVA entry-book blocks: identification plus one or more C190 lines."""
import re
from decimal import Decimal


class SpedBlocks:
    def __init__(self):
        self.notes = []
        self.warnings = []
        self.current = None
        self.summary = False
        self.header_count = 0
        self.tax_count = 0
        self.summary_count = 0

    def finish(self):
        from comparator import parse_record
        if self.current is None:
            return
        current, self.current = self.current, None
        if current.get('invalid'):
            self.warnings.append(f"Página {current['page']}: documento {current['documento']} com detalhe fiscal inválido; total parcial não utilizado.")
            return
        if not current['values']:
            self.warnings.append(f"Página {current['page']}: documento {current['documento']} sem linhas de Valor Operação; registro não comparado.")
            return
        amount = sum(current['values'], Decimal('0.00'))
        cells = [current['cnpj'], current['documento'], current['fornecedor'], f'{amount:.2f}'.replace('.', ',')]
        note, issue = parse_record(cells, dict(cnpj=0, documento=1, fornecedor=2, valor=3), current['page'])
        if issue:
            self.warnings.append(f"Página {current['page']}: documento {current['documento']}: {issue}")
            return
        note.update(serie=current['serie'], modelo=current['modelo'], situacao=current['situacao'],
                    data_emissao=current['data_emissao'], data_entrada=current['data_entrada'],
                    cfops=sorted(current['cfops']), linhas_fiscais=len(current['values']),
                    paginas=sorted(current['pages']), valor_origem='Soma de Valor Operação (SPED)')
        self.notes.append(note)

    def consume(self, table, page_number):
        from comparator import MONEY, column_name, normalized
        document_columns, fiscal_columns = None, None
        first_data = None
        for index, row in enumerate(table):
            mapped = {column_name(cell): pos for pos, cell in enumerate(row) if column_name(cell)}
            raw = {re.sub(r'[^A-Z0-9]', '', normalized(cell or '')): pos for pos, cell in enumerate(row) if cell}
            if {'cnpj', 'documento', 'fornecedor', 'serie'} <= mapped.keys() and {'DATAENTRADA', 'DATAEMISSAO'} <= raw.keys():
                document_columns = {**mapped, 'entrada': raw['DATAENTRADA'], 'emissao': raw['DATAEMISSAO']}
                for name in ('modelo', 'situacao'):
                    if name.upper() in raw:
                        document_columns[name] = raw[name.upper()]
                if index + 1 < len(table):
                    next_row = table[index + 1]
                    fiscal_raw = {re.sub(r'[^A-Z0-9]', '', normalized(cell or '')): pos for pos, cell in enumerate(next_row) if cell}
                    if {'CSTICMS', 'CFOP', 'VALOROPERACAO'} <= fiscal_raw.keys():
                        fiscal_columns = fiscal_raw
                        first_data = index + 2
                        break
        if document_columns is None or fiscal_columns is None:
            return False
        def get(row, mapping, field):
            position = mapping.get(field)
            return ' '.join((row[position] or '').split()) if position is not None and position < len(row) else ''
        for index, row in enumerate(table[first_data:], first_data + 1):
            if any('RESUMO - TOTAIS' in normalized(cell) for cell in row if cell):
                self.finish()
                self.summary = True
                self.summary_count += 1
                continue
            if self.summary:
                continue
            entry = get(row, document_columns, 'entrada')
            issue_date = get(row, document_columns, 'emissao')
            if entry or issue_date:
                self.finish()
                if not all(re.fullmatch(r'\d{2}/\d{2}/\d{4}', date) for date in (entry, issue_date)):
                    self.warnings.append(f'Página {page_number}, linha {index}: datas de identificação inválidas; revise o bloco.')
                    continue
                self.header_count += 1
                self.current = dict(cnpj=get(row, document_columns, 'cnpj'),
                                    documento=get(row, document_columns, 'documento'),
                                    fornecedor=get(row, document_columns, 'fornecedor'),
                                    serie=get(row, document_columns, 'serie'),
                                    modelo=get(row, document_columns, 'modelo'),
                                    situacao=get(row, document_columns, 'situacao'),
                                    data_emissao=issue_date, data_entrada=entry,
                                    page=page_number, pages={page_number}, values=[], cfops=set())
                continue
            cst = get(row, fiscal_columns, 'CSTICMS')
            cfop = get(row, fiscal_columns, 'CFOP')
            amount = get(row, fiscal_columns, 'VALOROPERACAO')
            if cst or cfop or amount:
                if not (re.fullmatch(r'\d{3}', cst) and re.fullmatch(r'\d{4}', cfop) and re.fullmatch(MONEY, amount)):
                    self.warnings.append(f'Página {page_number}, linha {index}: detalhe fiscal inválido; bloco precisa de revisão.')
                    # Do not report a partial monetary sum as the note total.
                    if self.current is not None:
                        self.current['invalid'] = True
                    continue
                self.tax_count += 1
                if self.current is None:
                    self.warnings.append(f'Página {page_number}, linha {index}: Valor Operação sem identificação da nota anterior.')
                    continue
                self.current['values'].append(Decimal(amount.replace('.', '').replace(',', '.')))
                self.current['cfops'].add(cfop)
                self.current['pages'].add(page_number)
                continue
            continuation = get(row, document_columns, 'fornecedor')
            if continuation:
                if self.current is None:
                    self.warnings.append(f'Página {page_number}: continuação de fornecedor sem nota anterior.')
                else:
                    self.current['fornecedor'] = (self.current['fornecedor'] + ' ' + continuation).strip()
                    self.current['pages'].add(page_number)
            elif any(cell and cell.strip() for cell in row):
                self.warnings.append(f'Página {page_number}, linha {index}: linha do bloco SPED não reconhecida; revise a extração.')
        return True
