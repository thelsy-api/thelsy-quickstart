# Thelsy Quickstart

A minimal, working starting point for calling **DeepSeek models through Thelsy** — an
OpenAI-compatible endpoint.

If your code already talks to an OpenAI-compatible API, switching is two values: the
base URL and the key. Nothing else changes — same request shape, same SDK, same
response objects.

- **Base URL:** `https://api.thelsy.com/v1`
- **Model ID:** `deepseek-flash`
- **Docs / pricing:** https://thelsy.com
- **Claude Code setup:** https://thelsy.com/claude-code.html
- **Codex CLI setup:** https://thelsy.com/codex.html

> This repository is maintained by the operator of Thelsy. It contains no client
> library — it is a quickstart, not an SDK.

---

## 1. 60-second check with curl

```bash
curl https://api.thelsy.com/v1/chat/completions \
  -H "Authorization: Bearer $THELSY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-flash",
    "messages": [
      {"role": "user", "content": "Reply with the single word: ok"}
    ]
  }'
```

A valid key returns a normal OpenAI-shaped response:

```json
{
  "choices": [
    { "message": { "role": "assistant", "content": "ok" } }
  ]
}
```

If you get `401`, the key is wrong or has been revoked. If you get
`insufficient_user_quota`, the allowance on that key is used up — see
[section 5](#5-what-happens-when-the-allowance-runs-out).

---

## 2. Python (official `openai` SDK)

```bash
pip install openai
```

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["THELSY_API_KEY"],
    base_url="https://api.thelsy.com/v1",
)

response = client.chat.completions.create(
    model="deepseek-flash",
    messages=[{"role": "user", "content": "Explain what an API gateway does in one sentence."}],
)

print(response.choices[0].message.content)
```

Streaming works the same way — pass `stream=True` and read SSE deltas:

```python
stream = client.chat.completions.create(
    model="deepseek-flash",
    messages=[{"role": "user", "content": "Count from 1 to 5."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta.content
    if delta:
        print(delta, end="", flush=True)
```

---

## 3. Node.js (official `openai` SDK)

```bash
npm install openai
```

```js
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.THELSY_API_KEY,
  baseURL: "https://api.thelsy.com/v1",
});

const response = await client.chat.completions.create({
  model: "deepseek-flash",
  messages: [{ role: "user", content: "Reply with the single word: ok" }],
});

console.log(response.choices[0].message.content);
```

---

## 4. Anthropic-compatible endpoint

The same host also serves an Anthropic-compatible endpoint, which is what Claude Code
uses. No extra configuration is needed on the gateway side.

```
POST https://api.thelsy.com/v1/messages
x-api-key: <your key>
anthropic-version: 2023-06-01
```

```bash
curl https://api.thelsy.com/v1/messages \
  -H "x-api-key: $THELSY_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-flash",
    "max_tokens": 512,
    "messages": [{"role": "user", "content": "Reply with the single word: ok"}]
  }'
```

Streaming, system prompts and `tool_use` all work over this endpoint.

> **Note on `max_tokens`:** thinking is enabled by default, and thinking tokens count
> toward `max_tokens`. If you set it very low (e.g. `64`) you can get a stop reason with
> an empty text block, because the output budget was spent on reasoning. Use a few
> hundred or more.

---

## 5. What happens when the allowance runs out

Calls stop. The API returns `insufficient_user_quota` and does not bill you anything
extra.

There is **no automatic overage billing** — you will never receive a surprise invoice
for usage you did not plan for. When you want more, you top up deliberately or move to a
larger plan. That is a design choice, not a limitation: an unexpected invoice is a
worse failure than a clear error message.

---

## 6. Models and capabilities

| | |
| --- | --- |
| Model ID | `deepseek-flash` |
| Streaming | Yes (SSE) |
| Tool / function calling | Yes (`tools` → `tool_calls`) |
| Structured output | Yes (`response_format: {"type": "json_object"}`) |
| Reasoning output | Yes (`reasoning_content`; thinking is on by default) |
| Image input | Yes |
| Context | 1M tokens |
| Max output | 384K tokens |

---

## 7. Gotchas worth knowing

- **Use `deepseek-flash` exactly.** Model IDs are case-sensitive; an unknown ID returns
  an error rather than silently falling back.
- **Keys are per-user.** A key issued for one account is charged against that account's
  allowance. Do not share one key across unrelated projects if you want per-project
  usage numbers.
- **Set a timeout.** Long generations over a 1M-token context can exceed a default
  client timeout. Give streaming calls a generous read timeout.
- **Retry on 429, not on 4xx.** Rate limits and transient 5xx are worth a bounded retry
  with backoff; a 400 means the request body is wrong and retrying will not help.

---

## 8. Getting a key

Keys are issued after checkout — payment is by card subscription (monthly) or a one-off
top-up, and the invoice is handled by the merchant of record, so the tax side is not
something you have to work out yourself.

Start here: **https://thelsy.com**

---

## License

The code samples in this repository are released under the MIT License. Use them
however you like.
