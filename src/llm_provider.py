import time
import ollama

from config import get_ollama_base_url

_selected_model: str | None = None


def _client() -> ollama.Client:
    return ollama.Client(host=get_ollama_base_url())


def list_models() -> list[str]:
    """
    Lists all models available on the local Ollama server.

    Returns:
        models (list[str]): Sorted list of model names.
    """
    response = _client().list()
    return sorted(m.model for m in response.models)


def select_model(model: str) -> None:
    """
    Sets the model to use for all subsequent generate_text calls.

    Args:
        model (str): An Ollama model name (must be already pulled).
    """
    global _selected_model
    _selected_model = model


def get_active_model() -> str | None:
    """
    Returns the currently selected model, or None if none has been selected.
    """
    return _selected_model


def generate_text(prompt: str, model_name: str = None, retries: int = 3) -> str:
    """
    Generates text using the local Ollama server with automatic retry on failure.

    Args:
        prompt (str): User prompt
        model_name (str): Optional model name override
        retries (int): Number of retries on network/server errors

    Returns:
        response (str): Generated text
    """
    model = model_name or _selected_model
    if not model:
        raise RuntimeError(
            "No Ollama model selected. Call select_model() first or pass model_name."
        )

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = _client().chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response["message"]["content"].strip()
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)

    raise RuntimeError(f"Ollama request failed after {retries + 1} attempts: {last_error}")
