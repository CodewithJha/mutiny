# Example policy packs

These files demonstrate policy rules; they do not send email, register
webhooks, or connect to external services. Tool names and calls are examples
for local mock adapters and authorized testing only.

- `demo_support.json` is the harness policy used by the demo agent.
- `domain_guard.json` shows argument restrictions for email, webhooks, and notes.
- `email_domain_confirmation.yaml` requires an explicit confirmation flag on
  every `send_email` tool call. Adapt the mock tool to provide that flag before
  using the policy with a local demo.

For example, this mock call violates the policy:

```json
{"recipient":"alex@example.test","subject":"Demo","body":"No delivery","recipient_domain_confirmed":false}
```

Setting `recipient_domain_confirmed` to `true` satisfies the rule. The reserved
`example.test` address is illustrative; no message is delivered.
