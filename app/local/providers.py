"""Calls each AI provider with the same system prompt and returns the reply text.

Claude goes through the official Anthropic SDK. Every other provider in models.json
offers an OpenAI-compatible endpoint, so they share the OpenAI SDK with a different base_url.
"""
import os

import anthropic
import openai


class ProviderError(Exception):
    def __init__(self, message, code="provider_error"):
        super().__init__(message)
        self.code = code


def _key(provider):
    key = os.environ.get(provider["key_env"], "").strip()
    if not key:
        raise ProviderError(
            f"No API key for {provider['label']}. Add {provider['key_env']} to app/local/.env and restart the app.",
            "no_key",
        )
    return key


def has_key(provider):
    return bool(os.environ.get(provider["key_env"], "").strip())


def complete(provider, model_id, system, user):
    """Send one analysis request; return the model's reply text."""
    if provider["type"] == "anthropic":
        return _anthropic(provider, model_id, system, user)
    return _openai_compatible(provider, model_id, system, user)


def _anthropic(provider, model_id, system, user):
    client = anthropic.Anthropic(api_key=_key(provider))
    try:
        msg = client.messages.create(
            model=model_id,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise ProviderError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY in .env.", "auth")
    except anthropic.NotFoundError:
        raise ProviderError(f"Anthropic doesn't recognize the model '{model_id}'. Fix its id in models.json.", "model_not_found")
    except anthropic.RateLimitError:
        raise ProviderError("Anthropic rate limit reached. Wait a minute and try again.", "rate_limited")
    except anthropic.APIStatusError as e:
        raise ProviderError(f"Anthropic error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise ProviderError("Couldn't reach Anthropic. Check your internet connection.")
    if msg.stop_reason == "refusal":
        raise ProviderError("The model declined to analyze this message.", "refusal")
    return "".join(b.text for b in msg.content if b.type == "text")


def _openai_compatible(provider, model_id, system, user):
    client = openai.OpenAI(api_key=_key(provider), base_url=provider["base_url"])
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    label = provider["label"]
    try:
        try:
            # Ask for a JSON object where the provider supports it...
            resp = client.chat.completions.create(model=model_id, messages=messages, response_format={"type": "json_object"})
        except openai.BadRequestError:
            # ...and retry without it for providers or models that don't.
            resp = client.chat.completions.create(model=model_id, messages=messages)
    except openai.AuthenticationError:
        raise ProviderError(f"{label} rejected the API key. Check {provider['key_env']} in .env.", "auth")
    except openai.NotFoundError:
        raise ProviderError(f"{label} doesn't recognize the model '{model_id}'. Fix its id in models.json.", "model_not_found")
    except openai.RateLimitError:
        raise ProviderError(f"{label} rate limit or quota reached. Wait, or check your billing.", "rate_limited")
    except openai.APIStatusError as e:
        raise ProviderError(f"{label} error {e.status_code}: {e.message}")
    except openai.APIConnectionError:
        raise ProviderError(f"Couldn't reach {label}. Check your internet connection.")
    text = resp.choices[0].message.content if resp.choices else None
    if not text:
        raise ProviderError(f"{label} returned an empty reply.")
    return text


def list_model_ids(provider):
    """Model IDs the provider says this key can use (for the 'Check models' button)."""
    if provider["type"] == "anthropic":
        client = anthropic.Anthropic(api_key=_key(provider))
        return {m.id for m in client.models.list()}
    client = openai.OpenAI(api_key=_key(provider), base_url=provider["base_url"])
    # Gemini lists ids as "models/<id>".
    return {m.id.removeprefix("models/") for m in client.models.list()}
