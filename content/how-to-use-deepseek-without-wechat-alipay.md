# How to Use the DeepSeek API Without WeChat or Alipay

*Written September 2026. Payment options and prices on the official platform change often — check DeepSeek's own pages before you rely on anything here.*

DeepSeek Flash is one of the cheapest capable models you can call right now: **$0.15 per million input tokens and $0.60 per million output tokens in off-peak hours**, a 1M context window, tool calls, vision, and a plain OpenAI-compatible endpoint at `https://api.deepseek.com`.

The model is the easy part. If you are outside mainland China, everything *around* the model is where people get stuck — and then quietly give up and pay OpenAI prices instead.

This post maps the walls that actually exist, which routes get through them, and the configuration details that break *after* you've paid.

---

## The wall, precisely

There are four separate frictions, and people tend to conflate them into one vague "DeepSeek is hard to sign up for". Separating them matters, because each has a different escape route.

| Friction | Status (September 2026) |
| --- | --- |
| **Console language** | `platform.deepseek.com` is Chinese-first with no English toggle. Browser translation handles 90% of it. |
| **Phone number** | The phone-login path accepts **+86 only**. Email signup is the way around it. |
| **Real-name verification** | The fast path is tied to WeChat scan-login, which inherits your WeChat identity. Signing up by email and submitting a **passport** instead is possible — reported to take 1–3 business days. |
| **Payment** | Online top-up runs on **Alipay or WeChat Pay**. A separate **对公汇款 (corporate wire transfer)** tab exists for business accounts. Some third-party guides claim international cards and PayPal work in certain regions; the official FAQ and the console we tested still list only the two Chinese wallets. The list is rendered per account, so it may depend on where you registered. |

On that last row: check it yourself rather than trusting a guide — including this one. Payment options are drawn per account, so what a developer in Germany sees may not match what an account registered in mainland China sees. Open your own top-up page and read the list; that is the only answer that counts.

*(For what it's worth: on a mainland-registered account we could not reproduce card or PayPal availability. It offered Alipay, WeChat Pay, and a corporate wire-transfer tab.)*

### The failure mode nobody warns you about

If you go the WeChat/Alipay route with a foreign card, the single most common outcome is this: the payment page loads, you scan, and it says **payment failed**. No error code, no reason.

The usual cause is that the foreign card attached to your WeChat account does not have **RMB transactions** enabled. It's a per-card toggle buried in the app:

> WeChat → **Me** → **Services** → **Wallet** → **Bank Cards** → open the card → enable **RMB payments**

If your card isn't offered as a payment option at all, that toggle is almost always why.

---

## Route 1 — The official platform

**Best for:** the lowest possible price, and you don't mind an afternoon of setup.

1. Sign up at `platform.deepseek.com` **with email**, not the phone option.
2. Complete real-name verification by submitting your **passport** — English name and passport number. Expect 1–3 business days.
3. Top up from the **充值 (Top up)** page and see which methods your account offers.
4. Go to **API keys** and create one. It is shown **once** — copy it immediately, because only a hash is stored afterwards.
5. Point your code at `https://api.deepseek.com`.

New accounts also receive a chunk of **free tokens valid for 30 days**, which is usually enough to decide whether the model is good enough for your workload before you pay anything.

**Where it breaks down:** verification latency, a Chinese-only console, a payment step that can fail for reasons the platform doesn't explain, and — for a company billing in USD — no card charge to reconcile against. (The platform does issue invoices, but against a CNY wallet top-up, not a card statement.)

**If you have a registered business**, the corporate wire transfer path sidesteps the entire wallet problem. Ask your finance team; it's the quietest route through the wall.

---

## Route 2 — Something that already takes your card

**Best for:** getting a working key in minutes, and paying the way you normally pay for SaaS.

There are two shapes of this:

**Aggregators** — OpenRouter and similar. They accept international cards, speak the OpenAI format, and carry many models, including DeepSeek's. If you want to shop across models and you already have a card, this is a perfectly good answer and you should just use it. The trade-off is that you are choosing from a large catalogue with per-model pricing you have to reason about yourself.

**Single-model endpoints** — a service that carries one model, bills a flat per-token rate, and hands you a key. This is what we do at [Thelsy](https://thelsy.com): `deepseek-flash`, one endpoint, card billing, no pre-registration before checkout.

### How to check any endpoint in 60 seconds

Before you pay anyone — us included — run this. A real endpoint answers immediately; a fake or overloaded one doesn't:

```bash
curl https://api.thelsy.com/v1/chat/completions \
  -H "Authorization: Bearer $YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-flash","messages":[{"role":"user","content":"Reply with the single word: ok"}]}'
```

If you get a normal OpenAI-shaped response, you're done. If you get `401`, the key is wrong. If you get `insufficient_user_quota`, the allowance is spent — which, on a well-built endpoint, is the *worst* thing that happens when you run out. There is no surprise invoice, because there is no automatic overage billing.

---

## Whichever route you pick: the CLI config that actually trips people up

This is the part that took us longest to get right, and it is the same regardless of whether you point your tools at DeepSeek directly or at a gateway.

### Codex CLI

In `~/.codex/config.toml`:

```toml
model = "deepseek-flash"
model_provider = "custom"
disable_response_storage = true

[model_providers.custom]
base_url = "https://api.thelsy.com/v1"
wire_api = "responses"
```

> **`disable_response_storage = true` is not optional.** Leave it out and Codex fails with `stream closed before response.completed`. It is not a workaround — the Responses API wire format needs the client to stop asking the server to store the response. This one line accounts for a large share of "DeepSeek doesn't work with Codex" reports.

Swap `base_url` for `https://api.deepseek.com` if you're going direct — the DeepSeek platform serves the Responses API too.

### Claude Code

```bash
export ANTHROPIC_BASE_URL="https://api.thelsy.com"
export ANTHROPIC_AUTH_TOKEN="sk-your-key"
claude
```

Worth knowing: DeepSeek publishes an **Anthropic-format endpoint at `https://api.deepseek.com/anthropic`**, so Claude Code can talk to the official platform directly as well. The `ANTHROPIC_BASE_URL` trick is not gateway-specific.

### The error that looks like the model is broken

```
503 No available channel for model 'gpt-6-astra' under group default
```

Your client sent **its own default model name**, not the one you configured. Codex sends `gpt-6-astra` unless told otherwise. If you're self-hosting a gateway, the fix is a model mapping — `{"gpt-6-astra": "deepseek-flash"}` — **and you must also add that alias to the channel's model list**. Filling in the mapping without adding the alias does nothing, which is the single most-missed step.

---

## The cost trick almost nobody uses

DeepSeek charges **half price during off-peak hours**, and the peak window is defined in UTC:

> **Peak: 01:00–04:00 and 06:00–10:00 UTC, Monday to Friday.** Everything else is off-peak.

The console states the same rule in its own notice, in CNY: off-peak cache-miss input is ¥1 and output ¥4 per million tokens, with peak at double that. The dollar figures above are the same rates converted.

That is a strange window if you live in Asia and a *very* convenient one if you live in North America:

| Where you are | Peak hours, in your local time | What it means for you |
| --- | --- | --- |
| **US Eastern** | 21:00–00:00 and 02:00–06:00 | Your entire working day is off-peak. You always pay half. |
| **US Pacific** | 18:00–21:00 and 23:00–03:00 | Same — business hours are off-peak. |
| **Europe (CEST)** | 03:00–06:00 and 08:00–12:00 | Your mornings are the expensive ones. |
| **Asia (CST)** | 09:00–12:00 and 14:00–18:00 | Working hours *are* peak. |

For a US-based developer, this means the headline numbers you see quoted for DeepSeek are the full price, and you pay **half of that** for anything you run during the day. Batch jobs, nightly agent runs, and CI workloads sit comfortably in the cheap window. If you're in Europe, shifting heavy runs to the afternoon is a straight 50% saving on the same work.

If you self-host a gateway, this is also the single biggest lever on your own margin: your costs are halved whenever your customers are awake in the Americas.

---

## FAQ

**Can I pay for the DeepSeek API with a credit card?**
Officially, online top-up is Alipay / WeChat Pay, with corporate wire transfer for business accounts. International card and PayPal support has been reported in some regions — check your own top-up page, since availability varies by account.

**Does DeepSeek accept PayPal?**
Reported as available for some regions/accounts, and not listed as the official online top-up method. Don't plan around it without checking your account.

**Do I need a Chinese phone number?**
Not if you sign up with email. The *phone login* option is +86 only.

**Is there an English version of the console?**
No official English toggle. Browser auto-translation covers it in practice.

**Do I need a VPN?**
The API itself (`api.deepseek.com`) is reachable from most places. Whether the *console* loads for you is a separate question from whether the API works.

**Does it work with Codex CLI, Claude Code and Cursor?**
Yes. DeepSeek serves both OpenAI-format and Anthropic-format endpoints, so all of the above work. The one required extra for Codex is `disable_response_storage = true`.

**What happens when my balance runs out?**
Calls stop and return `insufficient_user_quota`. There is no automatic overage charge.

**Is going through a third party allowed?**
DeepSeek's service terms permit downstream resale. Note the flip side, though — you are trusting an intermediary with your prompts. Ask any provider what they log. Ours redacts request bodies before logging, keeps records for six months for reconciliation, and never sells or trains on your data.

---

## The honest bottom line

If you have a working payment path on the official platform and you don't mind the setup, **go direct — it is cheaper.** A gateway is not a cheaper way to buy tokens. The per-token price you pay a reseller sits above what DeepSeek charges them; that gap *is* the business.

It is not a small gap if your workload repeats itself, either. DeepSeek's **cache-hit input price is $0.003 per million tokens — fifty times below the cache-miss price.** An agent or RAG loop that resends the same long system prompt on every turn pays almost nothing for that prefix on the official platform.

Which gives you one question to ask *any* intermediary, us included: **how do you price cache hits?** A provider charging a single flat blended rate is charging you ordinary rates for traffic that costs them nearly nothing. Ours are itemised separately, per request, in the console — but ask everyone, not just us.

What you are actually buying is the parts that are not the model: card billing in USD, a key in minutes instead of days, no real-name step, no wallet to fix, an invoice your accountant accepts, and someone to email when it breaks.

That's worth $19 to some people and worth nothing to others. Both answers are correct. Now you know which one you are.

---

## If you'd rather skip the setup

Full disclosure: I built one of these, so weigh the recommendation accordingly.

[Thelsy](https://thelsy.com) serves `deepseek-flash` on an OpenAI-compatible endpoint, with an Anthropic-compatible path on the same host for Claude Code and a Responses-compatible path for Codex CLI. Card subscription in USD, per-request token usage in the console, and no automatic overage charge — when a plan's included tokens run out, calls stop.

- **[The full write-up, with the FAQ, on thelsy.com](https://thelsy.com/deepseek-without-wechat.html)**
- [Plans and allowances](https://thelsy.com/#pricing)
- Questions first? support@thelsy.com

---

*Thelsy is not affiliated with DeepSeek and is not an official DeepSeek service. DeepSeek is a trademark of its respective owner. Prices quoted for the official platform are from DeepSeek's published pricing page and are subject to change.*
