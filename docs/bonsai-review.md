# Bonsai review record

We used `prism-ml/Bonsai-4B-gguf` at snapshot
`78f2c2bacd0904ffaba24b4873ed975e5818354a` to review two early scripts. Both
runs used llama.cpp on the CPU. The videos were later retired because they used
a fixture based product scene. The measurements remain useful as a record of
the local review experiment.

## First review

The first run used a 2,048 token context and generated 240 tokens. The model
loaded in 1.97 seconds. Prompt processing ran at 103.23 tokens per second.
Generation ran at 22.26 tokens per second.

The review found that the narration described an address entry step that the
screen did not show. It also rejected a live data claim because that version of
the screen used a fixture. Those findings led to stricter checks between spoken
claims and visible evidence.

## Second review

The second run used a 4,096 token context and generated 320 tokens. Prompt
processing ran at 134.3 tokens per second. Generation ran at 32.1 tokens per
second.

The prompt asked whether the user problem was clear, whether an impact claim
lacked proof, and whether the proposed pilot had measures. The review suggested
preparation time, classification errors, address resolution, and source
accuracy as pilot measures. No pilot has yet tested those measures.

## What remains useful

This experiment shows that a small local model can review a bounded writing
artifact on the CPU. It does not prove product usability, model correctness, or
32K inference safety. The live browser run and dated public data evaluations
support the current product claims.
