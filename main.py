import os
import json
import llm.model.gemini as gemini
import llm.prompt.prompt as prompt_module

from repository.produtoRepository import (
	load_db,
	save_db,
	load_ncm_table,
	extract_gtin,
	search_db,
	find_ncm_candidates,
	find_ncm_by_code,
	build_rag_context,
)
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TOKEN = os.environ.get("ISSTUDIO_TOKEN")


def run():
	print("Sistema RAG de produtos — base em JSON")
	db = load_db()
	ncm_table = load_ncm_table()
	nome = input("Digite o nome do produto (consulta): ").strip()
	if not nome:
		print("Nome vazio — saindo.")
		return

	matches = search_db(db, nome)
	rag = build_rag_context(matches)
	gtin_from_input = extract_gtin(nome)
	candidate_ncm = find_ncm_candidates(nome, ncm_table, top_n=5)

	prompt = prompt_module.build_prompt(nome, rag)

	if candidate_ncm:
		prompt += "\nPossíveis NCMs locais para este produto:\n"
		for candidate in candidate_ncm:
			prompt += f"- {candidate.get('Codigo')}: {candidate.get('Descricao')}\n"

	try:
		print("Consultando a IA externa via genai client para obter/normalizar dados...")
		token = os.environ.get("ISSTUDIO_TOKEN", DEFAULT_TOKEN)
		resp_text = gemini.call_isstudio_via_genai(token, prompt, model=os.environ.get("GENAI_MODEL"))
	except Exception as e:
		print("Erro ao chamar o cliente genai:", e)
		return

	produto = None
	try:
		produto = json.loads(resp_text)
		if not isinstance(produto, dict):
			produto = None
	except Exception:
		start = resp_text.find("{")
		end = resp_text.rfind("}")
		if start != -1 and end != -1 and end > start:
			try:
				produto = json.loads(resp_text[start:end+1])
			except Exception:
				produto = None

	if not produto:
		print("Resposta da IA não pôde ser convertida para JSON. Exibindo texto bruto:")
		print(resp_text)
		if input("Deseja salvar manualmente os campos no JSON? (s/n): ").lower().startswith("s"):
			nomef = input(f"Nome [{nome}]: ").strip() or nome
			preco = input("Preço: ").strip() or None
			gtin = input("GTIN/EAN/UPC: ").strip() or None
			categoria = input("Categoria: ").strip() or None
			categoria_hierarquia = input("Hierarquia de categoria: ").strip() or None
			ncm = input("NCM: ").strip() or None
			confiabilidade = input("Confiabilidade (0-1): ").strip() or None
			imagem = input("URL da imagem: ").strip() or None
			produto = {
				"Nome": nomef,
				"preço": preco,
				"gtin": gtin,
				"categoria": categoria,
				"categoria_hierarquia": categoria_hierarquia,
				"ncm": ncm,
				"confiabilidade": confiabilidade,
				"imagem": imagem,
			}
		else:
			print("Nada salvo.")
			return

	entry = {
		"Nome": produto.get("Nome") or nome,
		"gtin": produto.get("gtin") or produto.get("GTIN") or gtin_from_input,
		"preço": produto.get("preço"),
		"categoria": produto.get("categoria"),
		"categoria_hierarquia": produto.get("categoria_hierarquia"),
		"ncm": produto.get("ncm"),
		"confiabilidade": produto.get("confiabilidade"),
		"imagem": produto.get("imagem") or produto.get("image") or produto.get("Image"),
	}

	# Validar e completar NCM - SEMPRE tenta buscar na base primeiro
	if not entry["ncm"] and candidate_ncm:
		entry["ncm"] = candidate_ncm[0].get("Codigo")
		entry["ncm_fonte"] = "local"
		print(f"✓ NCM encontrado na base local: {entry['ncm']}")
	elif entry["ncm"]:
		verified = find_ncm_by_code(str(entry["ncm"]), ncm_table)
		entry["ncm_fonte"] = "local" if verified else "ia"
		if verified:
			entry["ncm_descricao_local"] = verified.get("Descricao")
			print(f"✓ NCM validado na base local: {entry['ncm']}")
		else:
			print(f"⚠ NCM da IA não encontrado na base: {entry['ncm']}")

	if not entry["categoria_hierarquia"] and entry["categoria"]:
		entry["categoria_hierarquia"] = entry["categoria"]

	# Calcular confiabilidade baseada em completude dos dados
	campos_obrigatorios = ["Nome", "preço", "gtin", "categoria", "ncm"]
	campos_preenchidos = sum(1 for campo in campos_obrigatorios if entry.get(campo))
	percentual_completude = (campos_preenchidos / len(campos_obrigatorios)) * 100

	if percentual_completude == 100:
		confiabilidade_calculada = "Muito Alta" if entry.get("imagem") else "Alta"
	elif percentual_completude >= 80:
		confiabilidade_calculada = "Alta"
	elif percentual_completude >= 60:
		confiabilidade_calculada = "Média"
	elif percentual_completude >= 40:
		confiabilidade_calculada = "Baixa"
	else:
		confiabilidade_calculada = "Muito Baixa"

	# Usar confiabilidade calculada como padrão, mas permitir override se informado pela IA
	if not entry["confiabilidade"] or entry["confiabilidade"] == "Muito Baixa":
		entry["confiabilidade"] = confiabilidade_calculada
	
	print(f"\nCompletude dos dados: {percentual_completude:.0f}% ({campos_preenchidos}/{len(campos_obrigatorios)} campos obrigatórios)")
	print(f"Confiabilidade: {entry['confiabilidade']}")

	print("JSON do produto retornado:")
	print(json.dumps(entry, ensure_ascii=False, indent=2))

	db.append(entry)
	save_db(db)
	print("Produto salvo na base (product_db.json).")


if __name__ == "__main__":
	run()
