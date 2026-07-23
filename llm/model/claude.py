import os

from anthropic import Anthropic


def call_claude(api_key: str | None, prompt: str, model: str | None = None) -> str:
    """Consulta a Claude API (com busca na web habilitada) e retorna o texto da resposta."""
    if not api_key:
        raise RuntimeError(
            "Token da Claude ausente. Defina CLAUDE_API_KEY no .env."
        )
    model_name = model or os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")

    client = Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model_name,
        max_tokens=2048,
        # Busca na web habilitada para paridade com o grounding do Gemini —
        # o prompt exige preço/imagem verificados em busca atual, nunca em
        # memória do modelo.
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": prompt}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("A Claude recusou a solicitação (stop_reason=refusal).")

    text = "".join(block.text for block in response.content if block.type == "text")
    text = normalize_response_text(text)
    if not text:
        raise RuntimeError("Resposta da Claude vazia.")
    return text


def normalize_response_text(text: str) -> str:
    """Remove cercas de markdown (```json ... ```) e espaços das bordas."""
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        parts = text.split("\n")
        if len(parts) >= 3:
            return "\n".join(parts[1:-1]).strip()
    return text
