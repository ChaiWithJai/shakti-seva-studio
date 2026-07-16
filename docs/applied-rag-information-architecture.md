# Applied RAG information architecture

## Product story

Shakti begins with one useful public task. A person enters an address and reads
the City record for one building. The hosted lookup uses code, not AI.

The learning layer explains the reusable architecture behind that result. It
shows how a team can retrieve bounded evidence, treat it before model use, give
AI a narrow job, keep tool receipts, and return the work to a person for review.

## Navigation

- **Check a building** returns to the public lookup.
- **Where AI helps** opens the applied RAG guide.
- **Meet Jai** explains the author and guidance offer.
- **Dharmic Data** returns to the parent public work.
- **Newsletter** opens the existing Substack subscription page.

The same header and footer appear on every Shakti page. The housing lookup stays
the primary task. Dharmic Data does not need to share Shakti's visual system.

## Page roles

### Public lookup

Complete one housing record task. Explain the deterministic boundary. Offer the
applied RAG guide as a secondary path, not an interruption.

### Where AI helps

Teach the reference architecture, show meaningful use cases, explain tool use,
and help a technical reader run the local research edition.

### Meet Jai

Explain the author, method, evidence, and paid working session. Use the same
Shakti shell and visual language.

## Content model for a use case

Each applied use case must name:

1. the human problem;
2. the allowed evidence;
3. the bounded AI job;
4. the tool receipts a reviewer can inspect; and
5. the decision that remains with code or a person.

Do not publish a use case that only says a model can summarize documents.

## Reference flow

```text
person and task
  -> scoped retrieval
  -> normalization, privacy treatment, and limits
  -> case packet with source receipts
  -> optional AI explanation, comparison, or draft
  -> human review and deterministic action
```

## Proof policy

- Say what is implemented today.
- Label proposed extensions as patterns, not finished product features.
- Keep the public deployment's no-AI boundary visible.
- Do not claim that local processing alone makes a system safe.
- Do not claim enterprise readiness without deployment, security, load, and
  user evidence.
