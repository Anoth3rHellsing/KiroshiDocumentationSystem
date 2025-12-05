# Kiroshi Categorizer Default Taxonomy

Kiroshi Categorizer classifies 3Shape support cases into exactly one path Product → Topic → (Subtopic) from an allowed taxonomy.

## Allowed Categories with Definitions

• 3Shape Unite / Login — issues with 3Shape Account, tokens, sign-in, credential errors. Positives: "sign in", "3Shape Account", "token". Negatives: hardware calibration.
• 3Shape Unite / Case Submission / Timeout-Proxy — sending cases, timeouts, proxies, firewalls, TLS handshake. Positives: "Send Case", "proxy", "firewall", "TLS". Negatives: scanner tips.
• TRIOS / Calibration — scanner calibration steps, tip issues, drift. Positives: "calibrate", "tip", "firmware". Negatives: account login.
• TRIOS / Scan Quality — margins, occlusion, lack of detail, scanning workflow.
• Dental System / Performance — slow UI, freezing, crash stacktraces.

## Signals Dictionary (Hints)

```json
{
  "unite": {
    "keywords": ["Unite", "App Store", "Send Case", "Lab Inbox", "Server"],
    "logs": ["ApplicationInitializer", "TLS", "service start failed"]
  },
  "trios": {
    "keywords": ["TRIOS", "calibrate", "scanner", "tip", "firmware", "dongle"],
    "logs": ["USB", "driver", "HW", "low detail"]
  }
}
```

These signals help boost the right category but should not be hardcoded; always decide using the whole case context.

## Output Format (Strict JSON)

```json
{
  "product": "string",
  "topic": "string",
  "subtopic": "string|null",
  "confidence": 0.0,
  "reason": "string",
  "signals_used": ["string", …],
  "top_3_alternatives": [
    {"product":"", "topic":"", "subtopic":null, "why":""},
    {"product":"", "topic":"", "subtopic":null, "why":""},
    {"product":"", "topic":"", "subtopic":null, "why":""}
  ]
}
```

## Rules

- Choose exactly one best category path.
- If uncertain, set confidence < 0.55 and provide strong alternatives.
- Prefer categories whose definitions and positive examples match more than negatives.
- Consider keywords, UI terms, error codes, logs, routes, file extensions (e.g. .stl, .dcm), and product names.
- Be bilingual (ES/EN): e.g., "Enviar caso" ≈ "Send Case"; "inicio de sesión" ≈ "login".
- Never invent categories not present in the allowed list.
- Keep "reason" concise and evidence-driven.

