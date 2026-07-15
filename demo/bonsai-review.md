# Bonsai review record

The demo plan was reviewed with the local `prism-ml/Bonsai-4B-gguf` model at
snapshot `78f2c2bacd0904ffaba24b4873ed975e5818354a`. The run used llama.cpp on the
CPU with a 2,048 token context and 180 generated tokens.

The prompt asked for five short scenes about the public HPD record problem, the
data treatment path, Hermes, the web app, and the Day 0 suite. It also told the
model not to claim that Bonsai built the original code.

Bonsai suggested a clear order that began with public records and moved through
the data path, Hermes, and privacy. It also made unsupported claims that the app
routes work to HPD, encrypts all data, and lets the TUI manage record entry. We
rejected those claims. The final script says what the code and tests prove.

The measured local run loaded Bonsai in 1.90 seconds. Prompt processing ran at
74.51 tokens per second, and generation ran at 48.12 tokens per second.
