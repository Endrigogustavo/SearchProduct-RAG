import os
import re
import json
import difflib
from typing import List, Dict, Any
from google import genai

DB_PATH = os.path.join(os.path.dirname(__file__), "rag/product_db.json")
NCM_PATH = os.path.join(os.path.dirname(__file__), "rag/Tabela_NCM_Vigente_20260705.json")
DEFAULT_TOKEN = ""


def load_db() -> List[Dict[str, Any]]:
	if not os.path.exists(DB_PATH):
		return []
	with open(DB_PATH, "r", encoding="utf-8") as f:
		return json.load(f)


def save_db(db: List[Dict[str, Any]]):
	with open(DB_PATH, "w", encoding="utf-8") as f:
		json.dump(db, f, ensure_ascii=False, indent=2)


def load_ncm_table() -> List[Dict[str, Any]]:
	if not os.path.exists(NCM_PATH):
		return []
	with open(NCM_PATH, "r", encoding="utf-8") as f:
		data = json.load(f)
	return data.get("Nomenclaturas", []) if isinstance(data, dict) else []


def normalize_text(text: str) -> str:
	return re.sub(r"[^0-9a-zA-Z]+", " ", (text or "").lower()).strip()


def extract_gtin(text: str) -> str | None:
	if not text:
		return None
	candidates = re.findall(r"\b(?:\d[\s-]*){8,14}\b", text)
	for candidate in candidates:
		cleaned = re.sub(r"[\s-]", "", candidate)
		if 8 <= len(cleaned) <= 14:
			return cleaned
	return None


def search_db(db: List[Dict[str, Any]], query: str, n=3) -> List[Dict[str, Any]]:
	names = [p.get("Nome", "") for p in db]
	matches = difflib.get_close_matches(query, names, n=n, cutoff=0.4)
	return [p for p in db if p.get("Nome") in matches]


def build_rag_context(matches: List[Dict[str, Any]]) -> str:
	if not matches:
		return ""
	parts = []
	for m in matches:
		parts.append(
			f"Nome: {m.get('Nome')} | Preço: {m.get('preço')} | Categoria: {m.get('categoria')} | NCM: {m.get('ncm')} | Confiabilidade: {m.get('confiabilidade')}"
		)
	return "\n".join(parts)


def find_ncm_candidates(product_name: str, ncm_list: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
	if not product_name or not ncm_list:
		return []

	name_norm = normalize_text(product_name)
	tokens = [t for t in name_norm.split() if len(t) >= 3 and t not in {"pro", "max", "plus", "mini", "ultra", "novo", "novo", "kit", "com"}]
	candidates = []

	for entry in ncm_list:
		desc = normalize_text(entry.get("Descricao", ""))
		if not desc:
			continue
		match_tokens = 0
		score = 0
		for token in tokens:
			if re.search(rf"\b{re.escape(token)}\b", desc):
				score += 20
				match_tokens += 1
			elif token in desc:
				score += 4
				match_tokens += 1
		if match_tokens == 0:
			continue
		ratio = difflib.SequenceMatcher(None, name_norm, desc).ratio()
		score += ratio * 20
		if desc.startswith("-"):
			score += 1
		candidates.append({"entry": entry, "score": score})

	candidates.sort(key=lambda item: item["score"], reverse=True)
	return [item["entry"] for item in candidates[:top_n]]


def find_ncm_by_code(code: str, ncm_list: List[Dict[str, Any]]) -> Dict[str, Any] | None:
	if not code:
		return None
	code_norm = re.sub(r"[\.\s-]", "", code)
	for entry in ncm_list:
		if re.sub(r"[\.\s-]", "", entry.get("Codigo", "")) == code_norm:
			return entry
	return None


def normalize_response_text(text: str) -> str:
	"""Remove markdown e espaços, mantendo o texto limpo para extração de JSON."""
	text = text.strip()
	if text.startswith("```") and text.endswith("```"):
		parts = text.split("\n")
		if len(parts) >= 3:
			return "\n".join(parts[1:-1]).strip()
	return text


def extract_text_from_response(resp: Any) -> str:
	if hasattr(resp, "output_text") and isinstance(resp.output_text, str) and resp.output_text.strip():
		return normalize_response_text(resp.output_text)

	if hasattr(resp, "text") and isinstance(resp.text, str) and resp.text.strip():
		return normalize_response_text(resp.text)

	if hasattr(resp, "output") and resp.output:
		for out in resp.output:
			if hasattr(out, "content") and out.content:
				for c in out.content:
					if hasattr(c, "text") and c.text:
						return normalize_response_text(c.text)

	if isinstance(resp, dict):
		def find_text(d):
			if isinstance(d, str):
				return d
			if isinstance(d, dict):
				for v in d.values():
					t = find_text(v)
					if t:
						return t
			if isinstance(d, list):
				for item in d:
					t = find_text(item)
					if t:
						return t
			return None

		t = find_text(resp)
		if t:
			return normalize_response_text(t)

	return str(resp)


def call_isstudio_via_genai(token: str, prompt: str, model: str | None = None) -> str:
	model = model or os.environ.get("GENAI_MODEL", "gemini-3.5-flash")
	client = genai.Client(api_key=token)
	resp = client.interactions.create(model=model, input=prompt)
	return extract_text_from_response(resp)


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

	prompt = (
		"Você é um assistente que busca informações públicas sobre um produto. "
		f"Nome do produto: '{nome}'. "
		"Use como referência a base local a seguir, mas priorize dados externos atualizados da web sempre que possível. "
		f"Referências locais (RAG):\n{rag}\n"
		"Procure também identificar o GTIN/EAN/UPC do produto. "
		"Use o arquivo local de NCM quando possível para validar ou sugerir o código correto. "
		"Forneça a hierarquia de categoria no estilo Amazon, por exemplo: Eletrônicos > Informática > Placas de Vídeo. "
		"Retorne somente um JSON válido, sem explicações extras. "
		"As chaves obrigatórias são: Nome, gtin, preço, categoria, categoria_hierarquia, ncm, confiabilidade. "
		"O campo preço deve vir do custo de mercado atual do produto ou da melhor estimativa oficial disponível. "
		"O campo ncm deve ser o código NCM correto para o produto. "
		"Se não houver dados externos claros, use null para os campos desconhecidos e inclua apenas o valor mais provável ou melhor estimativa encontrada. "
		"Não inclua markdown; apenas retorne um JSON puro ou um JSON dentro de blocos de código."
	)

	if candidate_ncm:
		prompt += "\nPossíveis NCMs locais para este produto:\n"
		for candidate in candidate_ncm:
			prompt += f"- {candidate.get('Codigo')}: {candidate.get('Descricao')}\n"

	try:
		print("Consultando a IA externa via genai client para obter/normalizar dados...")
		token = os.environ.get("ISSTUDIO_TOKEN", DEFAULT_TOKEN)
		resp_text = call_isstudio_via_genai(token, prompt, model=os.environ.get("GENAI_MODEL"))
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
			produto = {
				"Nome": nomef,
				"preço": preco,
				"gtin": gtin,
				"categoria": categoria,
				"categoria_hierarquia": categoria_hierarquia,
				"ncm": ncm,
				"confiabilidade": confiabilidade,
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
	}

	if not entry["ncm"] and candidate_ncm:
		entry["ncm"] = candidate_ncm[0].get("Codigo")
		entry["ncm_fonte"] = "local"
	elif entry["ncm"]:
		verified = find_ncm_by_code(str(entry["ncm"]), ncm_table)
		entry["ncm_fonte"] = "local" if verified else "ia"
		if verified:
			entry["ncm_descricao_local"] = verified.get("Descricao")

	if not entry["categoria_hierarquia"] and entry["categoria"]:
		entry["categoria_hierarquia"] = entry["categoria"]

	print("JSON do produto retornado:")
	print(json.dumps(entry, ensure_ascii=False, indent=2))

	db.append(entry)
	save_db(db)
	print("Produto salvo na base (product_db.json).")


if __name__ == "__main__":
	run()
