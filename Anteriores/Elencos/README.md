# Etapa 1 - Elencos Fantasy NBA

Arquivos:
- `elenco.py`: app principal Streamlit
- `data_loader.py`: leitura e limpeza inicial do Excel
- `transforms.py`: joins e montagem das visões
- `rules.py`: regras iniciais, incluindo a faixa de multa por dispensa

## Como rodar

Na pasta do projeto, mantenha o arquivo `roster.xlsx` ao lado dos scripts e execute:

```bash
streamlit run elenco.py
```

## Entregas desta etapa

- Leitura das abas principais
- Ignora a coluna `Jogador` da aba `roster`
- Seletor de time
- Prévia do elenco principal
- Prévia do elenco de desenvolvimento
