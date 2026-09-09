# Run the fleet on a local Ollama, for free

Sentarion's worker fleet (Algernon) can run on a local Ollama instead of a paid API. No key is needed.

## 1. Start Ollama and pull a model

```bash
ollama serve
ollama pull llama3.2:3b
```

Ollama listens on `http://127.0.0.1:11434` by default.

## 2. Leave the paid keys unset

Sentarion chooses the provider in this order (from `clients.py`, `fleet_env`):

1. `SENTARION_FLEET_PROVIDER=anthropic|openai|ollama` wins if set (`ALGERNON_PROVIDER` is honoured as an alias).
2. Otherwise a set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is used.
3. Otherwise, if a local Ollama answers, the fleet runs on it.

So for a free run either unset both keys, or force it:

```bash
export SENTARION_FLEET_PROVIDER=ollama
```

On Windows PowerShell: `$env:SENTARION_FLEET_PROVIDER = "ollama"`.

## 3. Pick the model and, if needed, the address

```bash
export OLLAMA_MODEL=llama3.2:3b          # any model you have pulled
export OLLAMA_BASE_URL=http://127.0.0.1:11434   # only if Ollama is not on the default port
```

## 4. Confirm with the doctor

Ask your client to run `sentarion_doctor`. You want:

- `ollama.ok: true` with `Ollama is answering at http://127.0.0.1:11434`
- `fleet_provider.detail` starting with `ollama`
- `api_key.ok: true` with `no API key set, but Ollama is up so the fleet runs locally`

If `ollama.ok` is false, the `next_steps` entry tells you to start Ollama or set `OLLAMA_BASE_URL`.

## Notes

- Small local models are slower and less careful than hosted ones; keep `k` small and prompts specific.
- A stale `OPENAI_API_KEY` left in your shell used to override an Ollama setup silently (0.2.1). Since 0.2.2 the order above is explicit; the doctor shows which provider will be used before you spend anything.
