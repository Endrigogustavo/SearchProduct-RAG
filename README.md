# SearchProduct-RAG

Engenharia de IA — sistema de estudo de LLMs com RAG básico para catalogação de produtos (GTIN, preço, categoria, NCM) usando o Gemini com Google Search.

## Configuração

1. Instale as dependências:

   ```sh
   pip install -r requirements.txt
   ```

2. Copie `.env.example` para `.env` e preencha a chave do Gemini (`GEMINI_API_KEY` ou `ISSTUDIO_TOKEN`), gerada em https://aistudio.google.com/apikey.

## Uso

```sh
python main.py
```

Digite o nome do produto; o sistema busca similares na base local (`rag/product_db.json`), consulta o Gemini com busca na web habilitada, valida o NCM contra a tabela oficial (`rag/Tabela_NCM_Vigente_*.json`) e salva/atualiza o produto na base sem duplicar.

## Anti-alucinação

O prompt segue uma hierarquia de evidência (RAG local > busca na web > `null`), proíbe explicitamente inventar GTIN, preço e URL de imagem, restringe o NCM à lista de candidatos da base oficial e exige autoavaliação de confiabilidade. NCMs não confirmados na tabela oficial são descartados pelo código.
