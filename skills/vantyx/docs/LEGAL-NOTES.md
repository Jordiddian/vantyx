# Why the hard rules in SKILL.md exist

Not legal advice — a condensed summary of research done before writing this skill, kept here so the reasoning behind the rules doesn't get lost or "optimized away" later. Get a real lawyer before using this beyond personal, single-user, single-account use.

- **Own account only, local execution.** The Ninth Circuit's 2026 ruling in *Amazon v. Perplexity* found that when a user's own agent acts through the user's own browser/session, the *user* is the one "accessing" the site, not the tool vendor — a materially better position under the Computer Fraud and Abuse Act than third-party scraping. That reasoning only holds if execution actually stays on the user's own device with the user's own credentials. Centralizing execution or credentials breaks the exact fact pattern the ruling favored.

- **Never solve or bypass a CAPTCHA.** *Ticketmaster v. RMG Technologies* treated CAPTCHA as a DMCA §1201 "technological protection measure" — a real judgment (with default-judgment caveats) against a company whose product got past one. Whatever the merits, this is not a fight to pick by accident inside an automation helper.

- **Never automate a payment or money-movement step.** Initiating transfers or payments on someone's behalf can trigger state money-transmitter licensing, FinCEN money-services-business registration, and NACHA third-party-sender obligations — a licensing question for a lawyer, not something to route around in code.

- **Stop on a ban / cease-and-desist, don't get cleverer.** *Facebook v. Power Ventures* held that continued access after a platform's cease-and-desist was "without authorization" under the CFAA even though the underlying users had consented. A site telling you (or the account) to stop is a hard stop.

- **Rate limits are load-bearing, not a suggestion.** Documented real-world account bans in this exact category (AI assistants booking restaurant reservations) started around ~200 requests/hour against one site. The default rate limits in this skill's recipes should sit far below anything like that, and jitter/backoff should be the default, not an afterthought.

- **Recipes never carry credentials.** A shared or even just saved-and-forgotten recipe file that contains a live session token or cookie is a live credential leak waiting to be read by whoever finds the file. Credentials are resolved locally, at run time, from the user's own environment/session — never written to disk alongside the recipe's declarative shape.

- **No code fields in the recipe schema, ever.** Community-submitted or agent-generated "skills"/recipes with executable or free-text-instruction fields are exactly what got exploited in the OpenClaw ClawHub incident (hundreds of malicious skills, credential-stealing payloads) and in the Adblock Plus `$rewrite` filter-injection incident years earlier. Keeping the schema strictly declarative (see `schema/recipe.schema.json`) is the actual security boundary, not a formality.
