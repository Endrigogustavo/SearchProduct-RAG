def build_prompt(nome, rag):
	prompt = (
		"Você é um especialista em produtos e dados de mercado. "
		"TAREFA: Extrair informações PRECISAS e CONFIÁVEIS para o produto.\n\n"
		f"**Nome do produto a pesquisar: {nome}**\n\n"
		"**CONTEXTO - Base de produtos local (RAG):**\n"
		f"{rag if rag else '[Nenhum produto similar encontrado na base]'}\n\n"
		"**INSTRUÇÕES CRÍTICAS:**\n"
		"1. BUSQUE informações APENAS de fontes confiáveis (sites oficiais, marketplaces estabelecidos, Wikipedia).\n"
		"2. PREENCHA obrigatoriamente: Nome, preço (em reais, valor numérico), categoria, categoria_hierarquia, NCM, gtin.\n"
		"3. Se NÃO CONSEGUIR encontrar um campo obrigatório, MARQUE como null E AJUSTE 'confiabilidade' para 'Baixa' ou 'Muito Baixa'.\n"
		"4. NUNCA invente dados - retorne null ao invés de adivinhar.\n"
		"5. NCM: Deve ser código válido no formato XXXX.XX.XX (ex: 8517.13.00). Se não souber, deixe null.\n"
		"6. GTIN/EAN: Código de barras do produto (8-14 dígitos). Se não encontrar, deixe null.\n"
		"7. Imagem: URL https VÁLIDA de imagem de alta qualidade. Teste se a URL é acessível. Se não conseguir URL válida, deixe null.\n"
		"8. Confiabilidade: Calcule como 'Muito Alta' (todos campos preenchidos e verificados), 'Alta' (maioria dos campos), 'Média' (50% dos campos), 'Baixa' (poucas informações), 'Muito Baixa' (informações insuficientes).\n\n"
		"**FORMATO ESPERADO (JSON puro, sem markdown):**\n"
		"{ \"Nome\": \"...\", \"gtin\": \"...\", \"preço\": 0.00, \"categoria\": \"...\", \"categoria_hierarquia\": \"...\", \"ncm\": \"...\", \"confiabilidade\": \"...\", \"imagem\": \"https://...\" }"
	)
	return prompt