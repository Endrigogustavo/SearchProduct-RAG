import os
import json

import llm.model.gemini as gemini
import llm.model.claude as claude
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
	normalize_text,
)
from dotenv import load_dotenv

load_dotenv()


def get_gemini_token() -> str | None:
	return os.environ.get("GEMINI_API_KEY") or os.environ.get("ISSTUDIO_TOKEN")


def get_claude_token() -> str | None:
	return os.environ.get("CLAUDE_API_KEY")


def call_llm(prompt: str) -> str:
	"""Consulta o provedor de IA configurado (LLM_PROVIDER=gemini|claude) e retorna o texto da resposta."""
	provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
	if provider == "claude":
		print("Consultando Claude (com busca na web)...")
		return claude.call_claude(get_claude_token(), prompt)
	print("Consultando Gemini (com Google Search)...")
	return gemini.call_gemini(get_gemini_token(), prompt)


def parse_product_json(resp_text: str) -> dict | None:
	"""Converte a resposta do LLM em dict, tolerando texto ao redor do JSON."""
	try:
		produto = json.loads(resp_text)
		return produto if isinstance(produto, dict) else None
	except (json.JSONDecodeError, TypeError):
		pass
	start = resp_text.find("{")
	end = resp_text.rfind("}")
	if start != -1 and end > start:
		try:
			produto = json.loads(resp_text[start:end + 1])
			return produto if isinstance(produto, dict) else None
		except json.JSONDecodeError:
			return None
	return None


def upsert_product(db: list, entry: dict) -> str:
	"""Atualiza um produto existente (mesmo GTIN ou mesmo nome) ou insere um novo."""
	for i, existing in enumerate(db):
		same_gtin = entry.get("gtin") and existing.get("gtin") == entry.get("gtin")
		same_name = normalize_text(existing.get("Nome", "")) == normalize_text(entry.get("Nome", ""))
		if same_gtin or same_name:
			# Preserva campos antigos que a nova consulta não preencheu.
			merged = {**existing, **{k: v for k, v in entry.items() if v is not None}}
			db[i] = merged
			return "atualizado"
	db.append(entry)
	return "inserido"


def collect_manual_entry(nome: str) -> dict | None:
	if not input("Deseja salvar manualmente os campos no JSON? (s/n): ").lower().startswith("s"):
		return None
	return {
		"Nome": input(f"Nome [{nome}]: ").strip() or nome,
		"preço": input("Preço: ").strip() or None,
		"gtin": input("GTIN/EAN/UPC: ").strip() or None,
		"categoria": input("Categoria: ").strip() or None,
		"categoria_hierarquia": input("Hierarquia de categoria: ").strip() or None,
		"ncm": input("NCM: ").strip() or None,
		"confiabilidade": input("Confiabilidade: ").strip() or None,
		"imagem": input("URL da imagem: ").strip() or None,
	}


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

	prompt = prompt_module.build_prompt(nome, rag, candidatos_ncm=candidate_ncm)

	try:
		resp_text = call_llm(prompt)
	except Exception as e:
		print(f"Erro ao consultar a IA: {e}")
		return

	produto = parse_product_json(resp_text)
	if not produto:
		print("Resposta da IA não pôde ser convertida para JSON. Exibindo texto bruto:")
		print(resp_text)
		produto = collect_manual_entry(nome)
		if not produto:
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

	# Validar e completar NCM — sempre confere na base oficial local
	if not entry["ncm"] and candidate_ncm:
		entry["ncm"] = candidate_ncm[0].get("Codigo")
		entry["ncm_fonte"] = "local"
		print(f"[OK] NCM encontrado na base local: {entry['ncm']}")
	elif entry["ncm"]:
		verified = find_ncm_by_code(str(entry["ncm"]), ncm_table)
		entry["ncm_fonte"] = "local" if verified else "ia"
		if verified:
			entry["ncm_descricao_local"] = verified.get("Descricao")
			print(f"[OK] NCM validado na base local: {entry['ncm']}")
		else:
			print(f"[!] NCM da IA nao encontrado na base oficial - descartando: {entry['ncm']}")
			entry["ncm"] = None
			entry["ncm_fonte"] = None

	if not entry["categoria_hierarquia"] and entry["categoria"]:
		entry["categoria_hierarquia"] = entry["categoria"]

	# Confiabilidade baseada em completude dos dados
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

	if not entry["confiabilidade"] or entry["confiabilidade"] == "Muito Baixa":
		entry["confiabilidade"] = confiabilidade_calculada

	print(f"\nCompletude dos dados: {percentual_completude:.0f}% ({campos_preenchidos}/{len(campos_obrigatorios)} campos obrigatórios)")
	print(f"Confiabilidade: {entry['confiabilidade']}")

	print("JSON do produto retornado:")
	print(json.dumps(entry, ensure_ascii=False, indent=2))

	resultado = upsert_product(db, entry)
	save_db(db)
	print(f"Produto {resultado} na base (product_db.json).")


if __name__ == "__main__":
	run()
