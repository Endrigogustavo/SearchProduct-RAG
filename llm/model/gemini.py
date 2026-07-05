import os
from google import genai
from typing import Any


def call_isstudio_via_genai(token: str, prompt: str, model: str | None = None) -> str:
	model = model or os.environ.get("GENAI_MODEL", "gemini-3.5-flash")
	client = genai.Client(api_key=token)
	resp = client.interactions.create(model=model, input=prompt)
	return extract_text_from_response(resp)


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
