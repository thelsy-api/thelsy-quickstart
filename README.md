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

---

# Appendix

## A. Codex CLI — the two lines that matter

`~/.codex/config.toml`:

```toml
model = "deepseek-flash"
model_provider = "custom"
disable_response_storage = true

[model_providers.custom]
base_url = "https://api.thelsy.com/v1"
wire_api = "responses"
```

> **`disable_response_storage = true` is required.** Without that line Codex fails with
> `stream closed before response.completed`. It is not a workaround — the Responses API
> wire format needs the client to stop asking the server to store the response.

Codex talks to `/v1/responses`. The gateway also accepts `/v1/chat/completions` if you are
wiring something else.

## B. Claude Code

```bash
export ANTHROPIC_BASE_URL="https://api.thelsy.com"
export ANTHROPIC_AUTH_TOKEN="sk-your-key"
claude
```

PowerShell:

```powershell
$env:ANTHROPIC_BASE_URL="https://api.thelsy.com"
$env:ANTHROPIC_AUTH_TOKEN="sk-your-key"
claude
```

Install once with `npm install -g @anthropic-ai/claude-code`. Streaming, tool calls and
system prompts all work through this path.

## C. Troubleshooting

| Symptom | What is actually happening | Fix |
|---|---|---|
| `503 No available channel for model 'gpt-6-astra' under group default` | The client sent **its own default model name**, not the one you configured. The gateway has no such model. | On the gateway side, map the client's model name to a real one — in the channel's **Model Mapping** write `{"gpt-6-astra":"deepseek-flash"}` (client model name → your real model), **and add that alias to the channel's model list as well**. The gateway will prompt you to save — accept it. |
| `stream closed before response.completed` (Codex) | `disable_response_storage` is missing from `config.toml`. | Add `disable_response_storage = true`. |
| Tool calls silently never fire | The wire format is wrong for the client. Codex needs `wire_api = "responses"`; other clients use `chat`. | Set `wire_api` to whatever that client expects. |
| Works in `curl`, fails in a CLI | The CLI adds its own headers and parameters, and may send extra background requests. | Check the request body in the CLI's verbose/debug mode before blaming the endpoint. |

## D. Not affiliated with DeepSeek

Thelsy is **not affiliated with DeepSeek** and is not an official DeepSeek service.
DeepSeek is a trademark of its respective owner. This repository is maintained by the
operator of Thelsy; it contains no client library, it is a quickstart, not an SDK.

Prompts and completions are redacted before they are written to usage logs, and usage is
itemised per request (input / output / cached tokens) so you can reconcile every call.

## E. 写给做同类东西的人（中文）

两份来自生产环境的记录。它们讲的是**管道**，不是模型：

- [用 Creem 做自动发货：两个只有真实付款才会暴露的坑](docs/creem-webhook-pitfalls.md)
  —— 首笔订阅会在**同一秒**发 `checkout.completed` + `subscription.paid` 两条
  `event_key` 不同的事件，同一个直觉的按事件去重会让**同一笔钱加两次额度**；以及生产环境标识是
  `prod` 而不是 `live`（写错会**静默丢弃每一笔真实付款**）。
- [用 New API 做 SaaS 自动开户：四个只会被真实流量撞出来的坑](docs/new-api-integration-pitfalls.md)
  —— `PUT /api/user/` 只写四个字段（传 `quota` 无效且不报错）、`email` 写不进去导致客户无法自助找回密码、
  建令牌只能给"当前登录用户"建、以及自带支付模块在密钥为空时会放行伪造回调。

这四个坑的共同点是**都不报错**：接口返回成功、日志干净，但业务是错的。
