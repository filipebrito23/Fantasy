# Etapa 2 v3 - Elencos Fantasy NBA

Arquivos:
- `elenco.py`: app principal Streamlit
- `data_loader.py`: leitura e limpeza inicial do Excel
- `transforms.py`: joins, formatação e totalizadores do elenco principal
- `rules.py`: regras iniciais, incluindo a faixa de multa por dispensa

## Como rodar

Na pasta do projeto, mantenha o arquivo `roster.xlsx` ao lado dos scripts e execute:

```bash
streamlit run elenco.py
```

## Entregas desta etapa

- Seletor de time
- Seletor de temporada inicial
- Tabela do elenco principal com salários exibidos a partir da temporada escolhida
- Destaque em vermelho para team options
- Total de salários por temporada
- Total de multas por temporada
- Cap restante do elenco principal: 110.000.000 - salários - multas
