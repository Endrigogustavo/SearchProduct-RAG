import os

from google import genai
from google.genai import types


def call_gemini(token: str | None, prompt: str, model: str | None = None) -> str:
    """Consulta o Gemini com Google Search habilitado e retorna o texto da resposta."""
    if not token:
        raise RuntimeError(
            "Token do Gemini ausente. Defina GEMINI_API_KEY (ou ISSTUDIO_TOKEN) no .env."
        )
    model_name = model or os.environ.get("GENAI_MODEL", "gemini-2.5-flash")

    client = genai.Client(api_key=token)

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            # Reduz variação criativa: para extração de dados queremos o
            # comportamento mais determinístico possível.
            temperature=0.1,
        ),
    )

    text = normalize_response_text(response.text or "")
    if not text:
        raise RuntimeError("Resposta do Gemini vazia.")
    return text


# Alias mantido para compatibilidade com código antigo.
call_isstudio_via_genai = call_gemini


def normalize_response_text(text: str) -> str:
    """Remove cercas de markdown (```json ... ```) e espaços das bordas."""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        parts = text.split("\n")
        if len(parts) >= 3:
            return "\n".join(parts[1:-1]).strip()
    return text
