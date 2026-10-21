# Comparador de notas · Lucrattiva

Aplicação web em português para comparar relatórios PDF de notas de entrada SPED × Domínio. Chave: CNPJ + número do documento. Confere fornecedor e valor, identifica ausências e duplicidades, exporta Excel e PDF. Nenhuma nota é armazenada permanentemente: arquivos são processados durante a requisição, sem serviços externos de leitura.

## Executar

Python 3.12:

```bash
cd /workspace/COMPARADOR-DE-NOTAS
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Servidor de desenvolvimento na porta 5000, sem debug. Não publicar dados reais numa instância pública sem autenticação, HTTPS e servidor de produção. Esta versão não implementa contas de usuário ou histórico.

## Formato inicial

PDFs com texto selecionável, até 200 páginas por arquivo e 20 MB por requisição. Reconhece tabelas com cabeçalhos explícitos CNPJ, NR. DOC. (ou DOCUMENTO / NUMERO DO DOCUMENTO), FORNECEDOR e VALOR. Alternativamente, uma nota por linha com quatro campos separados por `|` ou `;`:

```
12.345.678/0001-90 | 000123 | Empresa Exemplo LTDA | 1.250,00
```

A extração é conservadora: não adivinha a ordem das colunas. PDFs sem texto precisam de OCR, ainda não implementado. Layouts reais do SPED e Domínio precisam ser homologados com amostras. Avisos de extração impedem considerar a conferência completa; confira as contagens e páginas. Colunas adicionais, registros em várias linhas e cabeçalhos diferentes podem precisar de adaptadores. O sistema não valida dígitos verificadores do CNPJ: normaliza os 14 dígitos para comparação.

Números de documento perdem zeros à esquerda. Fornecedor ignora acentos, maiúsculas e espaços repetidos. Valores usam Decimal, sem tolerância de centavos. CNPJ ou número diferente gera ausências, sem associação aproximada. Duplicatas não são pareadas automaticamente e todos os registros são preservados. Série, filial e período não fazem parte da chave inicial; compare relatórios do mesmo escopo. Planilhas exportam campos como texto para evitar fórmulas provenientes de PDFs.

## Verificação

```bash
.venv/bin/python -m pytest -q
```

Testes geram PDFs sintéticos e exercitam upload, extração, comparação, ausência, duplicidades, erros e os dois formatos de exportação. Não representam homologação com relatórios reais.

## Testar no seu computador

Baixe e extraia o pacote completo. Instale Python 3.12 ou superior. No Windows,
abra `INICIAR_WINDOWS.bat`. No macOS/Linux, execute `python3 iniciar.py` na pasta
extraída. O inicializador instala as dependências (precisa de Internet na primeira
execução), inicia o servidor e abre o navegador automaticamente. Deixe o terminal
aberto durante o uso; Ctrl+C encerra. Nenhum comando deve usar o caminho
`/workspace` no computador do usuário: esse caminho pertence ao ambiente na nuvem.

Se o navegador não abrir, digite `127.0.0.1:5000` na barra de endereços **do
computador em que o programa foi iniciado**. Esse endereço não acessa o ambiente
na nuvem. Ainda não existe um site público desta aplicação.

Na tela, selecione os arquivos `exemplos/sped_simulado.pdf` e
`exemplos/dominio_simulado.pdf`, ou use os links para baixar os exemplos. Confira
o gabarito em `exemplos/LEIA-ME.txt`. Depois selecione os PDFs reais do mesmo
período/escopo e confira a quantidade de notas lidas e os avisos de extração.

Para gerar novamente os exemplos: `.venv/bin/python scripts/gerar_exemplos.py`.
A simulação tem 100 registros SPED, 95 Domínio e 105 chaves esperadas. O teste
paginado compara cada chave com um gabarito independente e verifica Excel e PDF.
O inicializador Windows não foi executado neste ambiente Linux.
