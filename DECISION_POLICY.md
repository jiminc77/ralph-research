# Decision Policy

Unattended execution uses the lowest-risk valid default. Security refusals are recorded and skipped. Ambiguous experimental choices preserve the frozen configuration, use the declared primary metric, and stop rather than expand budget or permissions. Failures are recorded with their evidence and retried only when the configured retry policy permits it.
