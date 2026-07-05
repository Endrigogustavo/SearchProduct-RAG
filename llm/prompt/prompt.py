def build_prompt(nome, rag):
    prompt = (
        "Você é um motor de busca e normalização de produtos de alta precisão.\n"
        f"OBJETIVO: Identificar e catalogar o produto: '{nome}'\n\n"
        
        "--- CONTEXTO DE PRODUTOS SIMILARES (RAG) ---\n"
        f"{rag if rag else 'Nenhum dado local encontrado. Use seu conhecimento global.'}\n\n"
        
        "--- DIRETRIZES DE EXTRAÇÃO ---\n"
        "1. GTIN (EAN/UPC): Tente extrair do contexto RAG ou identifique o GTIN padrão para este modelo/marca. "
        "Se o nome contiver 8, 12 ou 13 dígitos, trate como o GTIN.\n"
        "2. PREÇO: Busque o valor médio de mercado atual no Brasil (BRL). Use o valor numérico (ex: 1599.90). "
        "Priorize preços de grandes varejistas (Amazon, Mercado Livre, Magalu).\n"
        "3. CATEGORIA: Use uma taxonomia de e-commerce padrão. Em 'categoria_hierarquia', use o formato: 'Eletrônicos > Celulares > Smartphones'.\n"
        "4. NCM: Identifique o NCM (Nomenclatura Comum do Mercosul) correto com base na descrição técnica. Formato: 0000.00.00.\n"
        "5. IMAGEM: Retorne uma URL direta (.jpg, .png) de uma imagem representativa do produto.\n\n"

        "--- REGRAS DE OURO ---\n"
        "- Se o preço for incerto, forneça uma estimativa média baseada em dados recentes.\n"
        "- Se o GTIN for absolutamente desconhecido, retorne null.\n"
        "- O JSON deve ser válido e sem formatação Markdown (sem ```json).\n\n"
        
        "--- FORMATO DE SAÍDA ---\n"
        "{"
        " \"Nome\": \"Nome Comercial Completo\", "
        " \"gtin\": \"Somente números ou null\", "
        " \"preço\": 0.00, "
        " \"categoria\": \"Nome Simples\", "
        " \"categoria_hierarquia\": \"Pai > Filho > Neto\", "
        " \"ncm\": \"0000.00.00\", "
        " \"confiabilidade\": \"Muito Alta/Alta/Média/Baixa\", "
        " \"imagem\": \"https://...\" "
        "}"
    )
    return prompt