"""Gera relatórios fictícios paginados e gabarito independente da extração."""
from collections import Counter
from decimal import Decimal
from pathlib import Path
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]

def money(value):
    return f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')

def generate(destination):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    sped, dominio, expected = [], [], []
    names = ['Comércio Aurora LTDA', 'Papelaria Horizonte', 'Distribuidora Sul', 'Alimentos Primavera', 'Indústria Modelo', 'Serviços União', 'Materiais Central', 'Oficina das Peças', 'Atacado Boa Vista', 'Tecnologia Futuro']
    for i in range(1, 101):
        cnpj = f'99000000{i % 10:04d}00'  # Identificadores fictícios; não usar fiscalmente.
        doc = str(10000+i)
        supplier = names[i % 10]
        amount = Decimal(i)*Decimal('137.29') + Decimal('0.01')
        a = [cnpj, doc.zfill(9), supplier, money(amount)]
        b = [cnpj, doc, supplier, money(amount)]
        status, diffs = 'Conferente', ''
        if 61 <= i <= 70:
            b[3] = money(amount + (Decimal('0.01') if i % 2 else Decimal('125.50')))
            status, diffs = 'Divergente', 'Valor'
        elif 71 <= i <= 75:
            b[2] = 'Fornecedor Diferente LTDA'
            status, diffs = 'Divergente', 'Fornecedor'
        elif 76 <= i <= 80:
            b[2] = 'Fornecedor Alternativo'
            b[3] = money(amount + Decimal('200.00'))
            status, diffs = 'Divergente', 'Valor, Fornecedor'
        elif 81 <= i <= 85:
            status = 'Somente SPED'
        elif 86 <= i <= 90:
            status = 'Somente Domínio'
        elif 91 <= i <= 95:
            status = 'Duplicidade / revisar'
        elif 96 <= i <= 100:
            if i <= 98: b[0] = f'88000000{i % 10:04d}00'
            else: b[1] = str(20000+i)
            expected.append(dict(cnpj=b[0], documento=str(int(b[1])), status='Somente Domínio', diferencas='', sped=0, dominio=1))
            status = 'Somente SPED'
        if not 86 <= i <= 90: sped.append(a)
        if not 81 <= i <= 85: dominio.append(b)
        if 91 <= i <= 95: sped.append(a.copy())
        expected.append(dict(cnpj=cnpj, documento=doc, status=status, diferencas=diffs, sped=(0 if 86 <= i <= 90 else 2 if 91 <= i <= 95 else 1), dominio=(0 if 81 <= i <= 85 or i >= 96 else 1)))
    styles = getSampleStyleSheet()
    for name, records in [('sped', sped), ('dominio', dominio)]:
        story = [Paragraph(f'{name.upper()} — NOTAS DE ENTRADA SIMULADAS', styles['Title']), Paragraph('DADOS FICTÍCIOS · Layout de teste, não representa exportação oficial. CNPJs sem validação fiscal.', styles['Normal']), Spacer(1, 15)]
        table = Table([['CNPJ','NR. DOC.','FORNECEDOR','VALOR']] + records, repeatRows=1, colWidths=[150,90,330,120], rowHeights=23)
        table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dceee4')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('ALIGN',(-1,1),(-1,-1),'RIGHT')]))
        story.append(table)
        def footer(canvas, doc):
            canvas.setFont('Helvetica',8);canvas.drawString(30,18,f'SIMULAÇÃO · Página {doc.page}')
        SimpleDocTemplate(str(destination/f'{name}_simulado.pdf'), pagesize=landscape(A4),leftMargin=30,rightMargin=30,topMargin=30,bottomMargin=35).build(story,onFirstPage=footer,onLaterPages=footer)
    manifest = dict(counts=[len(sped),len(dominio)], summary=dict(Counter(r['status'] for r in expected)), rows=sorted(expected,key=lambda r:(r['cnpj'],r['documento'])))
    (destination/'gabarito.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest

if __name__ == '__main__':
    result=generate(ROOT/'exemplos')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2))
