import os
from google import genai
from typing import Any


from google.genai import types # Importação necessária para as ferramentas

def call_isstudio_via_genai(token: str, prompt: str, model: str | None = None) -> str:
    # Define o modelo (Gemini 2.0 Flash ou 3.5 Flash são ótimos para busca)
    model_name = model or os.environ.get("GENAI_MODEL", "gemini-2.0-flash")
    
    client = genai.Client(api_key=token)

    # 1. Configura a ferramenta de busca do Google
    google_search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # 2. Faz a chamada incluindo a ferramenta no config
    # Usamos generate_content para garantir suporte total a tools e retorno de texto
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[google_search_tool]
        )
    )

    # O SDK novo já limpa a resposta em .text, mas mantemos sua lógica se preferir
    return response.text

# Caso você precise manter o extract_text_from_response por algum motivo específico:
# return extract_text_from_response(response)


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


def normalize_response_text(text: str) -> str:
	"""Remove markdown e espaços, mantendo o texto limpo para extração de JSON."""
	text = text.strip()
	if text.startswith("```") and text.endswith("```"):
		parts = text.split("\n")
		if len(parts) >= 3:
			return "\n".join(parts[1:-1]).strip()
	return text
