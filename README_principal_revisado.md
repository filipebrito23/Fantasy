# NBA Google Sheets - código principal revisado

Este pacote atualiza o código principal com as melhorias que validamos no diagnóstico.

## Melhorias aplicadas
- `update_acell()` para escrita segura.
- impressão da URL exata da planilha.
- `game_id = f"{game_date}0{team_abbr}"`.
- proteção para não gravar stats vazias.
- leitura pós-escrita em cada célula.
- teste inicial de `E2` com `999` para validar o pipeline.

## Observação
Se quiser usar em produção, você pode desativar o teste inicial ou ajustar `PROCESSAR_APENAS_PRIMEIRA_LINHA`.
