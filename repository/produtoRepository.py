import os
import difflib
import re
import json
from typing import Any, Dict, List

DB_PATH = os.path.join(os.path.dirname(__file__), "../rag/product_db.json")
NCM_PATH = os.path.join(os.path.dirname(__file__), "../rag/Tabela_NCM_Vigente_20260705.json")


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



def find_ncm_candidates(product_name: str, ncm_list: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
	"""Busca robus­ta por NCM usando keywords e similaridade"""
	if not product_name or not ncm_list:
		return []

	name_norm = normalize_text(product_name)
	
	# Dicionário de keywords para categorias de produtos
	category_keywords = {
		"smartphone": ["telefone inteligente", "smartphones", "smartfone", "celular inteligente"],
		"notebook": ["notebook", "laptop", "computador portátil"],
		"tablet": ["tablet"],
		"monitor": ["monitor", "tela de vídeo"],
		"câmera": ["câmera", "fotográfica"],
		"fone": ["fones de ouvido", "headphone", "auricular"],
		"cabo": ["cabos", "conector"],
		"fonte": ["fontes de alimentação", "carregador"],
	}
	
	candidates = []

	for entry in ncm_list:
		desc_raw = entry.get("Descricao", "")
		desc = normalize_text(desc_raw)
		if not desc:
			continue
		
		score = 0
		
		# 1. Busca por keywords de categoria (alta prioridade)
		for category, keywords in category_keywords.items():
			for kw in keywords:
				if kw in desc:
					score += 100
					break
			if score >= 100:
				break
		
		# 2. Se não encontrou por keyword, tentar similaridade com marca
		if score == 0:
			tokens = name_norm.split()
			for token in tokens:
				if len(token) >= 4 and token in desc:
					score += 20
		
		# 3. Adicionar score por similaridade geral
		similarity = difflib.SequenceMatcher(None, name_norm, desc).ratio()
		if similarity > 0.2:
			score += similarity * 10
		
		if score > 0:
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


def build_rag_context(matches: List[Dict[str, Any]]) -> str:
	if not matches:
		return ""
	parts = []
	for m in matches:
		parts.append(
			f"Nome: {m.get('Nome')} | Preço: {m.get('preço')} | Categoria: {m.get('categoria')} | NCM: {m.get('ncm')} | Confiabilidade: {m.get('confiabilidade')}"
		)
	return "\n".join(parts)
