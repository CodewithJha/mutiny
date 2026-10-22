# Example policy packs

These files demonstrate policy rules; they do not send email, register
webhooks, or connect to external services. Tool names and calls are examples
for local mock adapters and authorized testing only.

- `demo_support.json` is the harness policy used by the demo agent.
- `domain_guard.json` shows argument restrictions for email, webhooks, and notes.
- `email_domain_confirmation.yaml` binds every `send_email` recipient to the
  customer's address in trusted adapter context. It works with the support
  sample's existing `CUSTOMER_CONTEXT` without changing its mock tool.

For example, this mock call violates the policy because the recipient differs
from the address on file:

```json
{"recipient":"exfil@attacker.invalid","subject":"Demo","body":"No delivery"}
```

The comparison is exact, so lookalike addresses such as
`alice@example.com.evil.invalid` also fail. These examples use mock tools only;
no message is delivered.
