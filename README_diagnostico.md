# Versão de diagnóstico - NBA Google Sheets

Esta versão foi feita para descobrir por que o script aparenta escrever, mas o resultado não aparece na planilha.

## O que ela faz
- Mostra o caminho real da credencial.
- Mostra o nome da planilha conectada.
- Lista as abas encontradas.
- Mostra o cabeçalho detectado em cada aba.
- Processa apenas a primeira linha elegível por padrão.
- Faz escrita célula a célula em modo seguro.
- Lê novamente a célula após escrever para conferir o valor.

## Configurações úteis no topo do script
- `ABA_TESTE = None` -> coloque o nome exato da aba para testar só uma.
- `PROCESSAR_APENAS_PRIMEIRA_LINHA = True` -> mantém o teste curto.
- `CELULA_TESTE = None` -> coloque algo como `"E2"` para testar escrita simples.

## Como usar
1. Coloque `service_account.json` na mesma pasta do script.
2. Se quiser, defina `ABA_TESTE` com o nome exato da aba.
3. Rode o script.
4. Me envie o log que aparecer no terminal.
