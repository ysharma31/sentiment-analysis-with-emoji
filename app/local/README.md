# Emoji Sentiment Lab (local, multi-model)

The same app as the online page, run on your own computer so it can call any provider
with your own API keys. Every analysis is added to `data/analyses.xlsx`, which has one
sheet per model plus a **Comparison** sheet.

## Set up (once)

```bash
cd app/local
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Open `.env` and paste in the keys you have. Providers without a key are greyed out in the app.

| Provider | Key in `.env` | Get a key |
|---|---|---|
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | console.anthropic.com |
| OpenAI (GPT) | `OPENAI_API_KEY` | platform.openai.com |
| Google (Gemini) | `GEMINI_API_KEY` | aistudio.google.com |
| xAI (Grok) | `XAI_API_KEY` | console.x.ai |
| DeepSeek | `DEEPSEEK_API_KEY` | platform.deepseek.com |
| Mistral | `MISTRAL_API_KEY` | console.mistral.ai |
| Meta Llama (via Groq) | `GROQ_API_KEY` | console.groq.com |

## Run

```bash
python server.py
```

Then open http://127.0.0.1:5000.

1. Press **Check models**. It asks each provider whether the model IDs in `models.json` exist for your key and suggests similar IDs when one doesn't.
2. Pick a model, type a message, and press **Analyze and add to sheet**, or press **Run test set with this model** to analyze the 25 starter sentences.
3. Open `data/analyses.xlsx`, or use **Download Excel**. If the file is open in Excel while you analyze, it updates the next time it's closed and something is saved.

## Changing the model list

Edit `models.json`. Each model needs the exact `id` the provider's API expects, a `label` (used as the sheet name), and a `provider`.
Model names change often, so run **Check models** after editing.

## Notes

- Every model gets the same system prompt, read from `prompts/sentiment_analysis_prompt.md`.
- The sheet starts with the 25 Claude Opus 5.5 analyses from `evaluation/results/responses.jsonl`.
- Your data stays in `data/` and your keys in `.env`. Both are git-ignored.
