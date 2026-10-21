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

A extração é conservadora: não adivinha a ordem das colunas. PDFs sem texto precisam de OCR, ainda não implementado. Layouts reais do SPED e Domínio precisam ser homologados com amostras. Avisos de extração impedem considerar a conferência completa; confira as contagens e páginas. Registros em várias linhas, tabelas sem bordas e cabeçalhos diferentes ainda podem precisar de adaptadores. O sistema não valida dígitos verificadores: normaliza CNPJ de 14 dígitos ou CPF de 11 dígitos para comparação.

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

Se o navegador não abrir, use o endereço mostrado na janela em **Endereço desta cópia**, no computador em que o programa foi iniciado. A porta padrão é 5000; se estiver ocupada, o inicializador escolhe outra porta livre. Esse endereço não acessa o ambiente na nuvem. Ainda não existe um site público desta aplicação.

Na tela, selecione os arquivos `exemplos/sped_simulado.pdf` e
`exemplos/dominio_simulado.pdf`, ou use os links para baixar os exemplos. Confira
o gabarito em `exemplos/LEIA-ME.txt`. Depois selecione os PDFs reais do mesmo
período/escopo e confira a quantidade de notas lidas e os avisos de extração.

Para gerar novamente os exemplos: `.venv/bin/python scripts/gerar_exemplos.py`.
A simulação tem 100 registros SPED, 95 Domínio e 105 chaves esperadas. O teste
paginado compara cada chave com um gabarito independente e verifica Excel e PDF.
O inicializador Windows não foi executado neste ambiente Linux.


## Campos diferentes nos relatórios

Cada cabeçalho reconhecido é convertido para um campo comum; não é necessário
ter os mesmos nomes de colunas nos dois PDFs.

| Campo comum | Domínio | Outros cabeçalhos reconhecidos |
| --- | --- | --- |
| CNPJ | CNPJ/CPF/CEI/CAEPF, inclusive sufixo I | CNPJ, CNPJ/CPF |
| Documento | Nota Série (número e série separados por espaço, `/` ou `-`) | Nº Doc., NR. DOC., Documento |
| Nome do fornecedor | Fornecedor / Razão Social, quando presentes | Nome/Razão Social, Nome Empresarial |
| Código interno do fornecedor | Código Fornecedor | Não substitui o nome |
| Valor total da nota | Valor Contábil, ou Valor Contábil Tipo | Valor da Operação, Valor |

O leitor dá prioridade ao Valor Contábil/Valor da Operação e ignora a coluna
isolada Valor quando ela representa imposto. Cabeçalhos de tabela em até três
linhas são combinados por posição da coluna. O nome e código do fornecedor são
armazenados separadamente: nome ausente deixa o resultado como **Conferência
parcial**, ou mantém **Divergente** com pendência se também houver diferença de
valor. Essa pendência aparece na tela, no Excel e no PDF. CPF é aceito e identificado separadamente. CEI e CAEPF ainda não são suportados e geram avisos de registros não comparados.

Esta adaptação foi testada com PDFs sintéticos que reproduzem os cabeçalhos
informados. A lista de colunas e a imagem não substituem a homologação com os
PDFs originais do SPED e do Domínio. Não se presume que todo layout desses
sistemas seja reconhecido. O pareamento continua por CNPJ + número; a série
extraída é preservada para revisão, sem alterar a chave nesta versão.


## Como confirmar a versão que está aberta

A versão atual **0.4.0** aparece no topo e no rodapé da página. O endereço
`/versao` também informa a versão e um identificador da execução (sem credenciais).
O inicializador confere esse identificador antes de abrir o navegador, para não
abrir uma cópia antiga que já esteja usando a porta padrão. Não encerra programas
de terceiros; abre a nova cópia em outra porta disponível. A reserva da porta
é liberada antes de iniciar o servidor: se outro programa tomar essa porta nesse
intervalo, o inicializador não abrirá a instância errada e mostrará a falha.

A mensagem antiga “Não foi possível reconhecer notas nos dois arquivos. Use
tabelas...” identifica uma cópia anterior à adaptação dos cabeçalhos fiscais.
Baixe o ZIP atualizado, extraia em uma nova pasta e execute o inicializador dessa
pasta. Confira a versão 0.4.0 antes de enviar os PDFs. A atualização não garante a
leitura de um layout real ainda não homologado: para adaptar um relatório que
continue sem notas reconhecidas, são necessários os PDFs originais.


## Leitura do livro de entradas SPED — versão 0.3.0

O livro PVA pode apresentar cada documento em um bloco: Data Entrada, Data
emissão, Nr. Doc., Modelo, Série, Situação, CNPJ/CPF e Razão social na primeira
linha; CST/ICMS, CFOP e Valor Operação em uma ou mais linhas abaixo. O leitor
soma apenas Valor Operação dessas linhas e mantém o bloco entre páginas,
inclusive quando a razão social continua na página seguinte. A seção
**RESUMO - TOTAIS** é excluída das notas. Linhas fiscais inválidas impedem o uso
de um total parcial; os problemas são apresentados como avisos.

A orientação dominante dos caracteres é detectada por página e normalizada em
memória usando a biblioteca já instalada. O arquivo original não é alterado;
isso permite ler PDFs com texto girado, sem OCR. PDFs que são apenas imagens
ainda exigem uma etapa de OCR, não implementada.

A adaptação foi validada com um livro real enviado pelo usuário: 39 páginas,
589 documentos (570 com CNPJ e 19 com CPF), 599 linhas fiscais, 20 documentos
com continuidade entre páginas e 7 com mais de uma linha fiscal. Não houve
avisos de extração. Cada documento foi conferido contra uma leitura independente
do texto e a soma bateu com o resumo do próprio relatório. Esses números são
registrados apenas como evidência de validação; o PDF original, as identidades,
os fornecedores e os valores reais não fazem parte do repositório nem dos testes.

Os testes públicos usam dados fictícios e cobrem quatro orientações, múltiplas
linhas fiscais, CPF, continuação de nome/documento entre páginas e exclusão do
resumo. A leitura e a comparação com o relatório **real do Domínio** ainda
precisam ser validadas com esse segundo arquivo.


## Conferir um PDF separadamente — versão 0.4.0

Depois de selecionar o SPED, clique em **Conferir leitura SPED**. O Domínio não
precisa estar selecionado. O mesmo vale para **Conferir leitura Domínio**.
A conferência mostra as notas reconhecidas, CNPJ/CPF, documento, série,
fornecedor (ou código interno quando faltar o nome), valor e páginas de origem.
A busca aceita documentos, CNPJ/CPF com ou sem pontuação e nomes com ou sem acento.

O resumo mostra quantidade de notas, páginas, identificações CNPJ/CPF e soma
exata das notas reconhecidas. Essa soma não garante que todas as notas de um
layout desconhecido foram lidas: confira os avisos e o relatório original.
O tempo decorrido aparece durante a leitura; não é uma porcentagem de progresso.

Se um dos PDFs falhar durante a comparação, o resumo do outro permanece
visível. Dados não reconhecidos não são tratados como ausência de notas na
comparação, e o sistema não gera um comparativo completo com um arquivo vazio.
A exportação mantém os mesmos requisitos da comparação.

A operação `POST /conferir/sped` recebe um único arquivo multipart no campo
`sped`; `POST /conferir/dominio` usa o campo `dominio`. A resposta inclui `notes`
e `summary` (quantidade, páginas, total decimal em string, contagens CNPJ/CPF,
avisos e erro). PDFs válidos sem notas reconhecidas retornam 422 com os avisos
e o número de páginas; erros de comparação incluem um resumo separado de cada
origem em `sources`. Nenhum PDF ou resultado fica salvo permanentemente no servidor.

A leitura individual foi validada com o mesmo SPED real de 39 páginas e 589
documentos. O PDF real do Domínio continua necessário para homologar esse layout.
