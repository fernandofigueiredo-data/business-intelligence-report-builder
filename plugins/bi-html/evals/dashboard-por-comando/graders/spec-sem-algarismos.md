---
type: regex
target: { source: file, path: dashboard/spec.json }
pattern: '"(titulo|subtitulo|pergunta_negocio|publico|achado)"\s*:\s*"[^"]*[0-9]'
match: not_contains
weight: 2
---

Nenhum texto da spec traz algarismo: valores entram só como marcador de métrica.
