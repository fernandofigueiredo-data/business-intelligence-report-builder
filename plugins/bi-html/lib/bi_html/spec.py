"""
Validação da spec de dashboard.

A spec é o que o Claude escreve. Ela descreve o dashboard (estilo, layout,
blocos, métricas ligadas) e nunca carrega valores: todo número vem da camada de
métricas. Este módulo confere isso em duas etapas:

1. o JSON Schema (`schemas/dashboard-spec.schema.json`), que não tem campo para
   valores e recusa algarismos nos textos;
2. regras que o schema não expressa: ids de bloco únicos, marcadores
   `{id_da_metrica}` que apontam para métricas do próprio bloco e, quando a
   lista é conhecida, métricas que existem no modelo.

Uso pela linha de comando: `scripts/validar_spec.py`. Uso pelo MCP: ferramenta
`validar_spec` do servidor `bi-dados`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

PLUGIN = Path(__file__).resolve().parents[2]
SCHEMA = PLUGIN / "schemas" / "dashboard-spec.schema.json"
MARCADOR = re.compile(r"\{([a-z][a-z_]*)\}")


def carregar_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _caminho(erro) -> str:
    partes = []
    for p in erro.absolute_path:
        partes.append(f"[{p}]" if isinstance(p, int) else (f".{p}" if partes else str(p)))
    return "".join(partes) or "(raiz)"


def _mensagem(erro) -> str:
    """Traduz os erros mais comuns do jsonschema para uma frase que o autor entende."""
    v = erro.validator
    if v == "pattern" and erro.validator_value == "^[^0-9]*$":
        trecho = re.findall(r"\S*\d\S*", str(erro.instance))[:3]
        return (f"texto com número literal ({', '.join(trecho)}); valores vêm da camada de "
                "métricas: use um marcador {id_da_metrica}")
    if v == "pattern":
        return f"formato inválido: {erro.instance!r}"
    if v == "additionalProperties":
        extras = sorted(set(erro.instance) - set(erro.schema.get("properties", {})))
        return f"campo não previsto: {', '.join(extras)}"
    if v == "required":
        faltando = [c for c in erro.validator_value if c not in erro.instance]
        return f"campo obrigatório ausente: {', '.join(faltando)}"
    if v == "enum":
        return f"valor {erro.instance!r} fora das opções: {', '.join(map(str, erro.validator_value))}"
    if v == "const":
        return f"valor deve ser {erro.validator_value!r}"
    if v == "type":
        return f"tipo errado: esperado {erro.validator_value}, veio {type(erro.instance).__name__}"
    if v in ("minItems", "maxItems", "minLength", "maxLength"):
        return f"tamanho fora do limite ({v} = {erro.validator_value})"
    if v == "uniqueItems":
        return "itens repetidos"
    return erro.message


def _textos(no, caminho=""):
    """Todos os textos livres da spec, com o caminho de cada um."""
    if isinstance(no, dict):
        for chave, valor in no.items():
            yield from _textos(valor, f"{caminho}.{chave}" if caminho else chave)
    elif isinstance(no, list):
        for i, valor in enumerate(no):
            yield from _textos(valor, f"{caminho}[{i}]")
    elif isinstance(no, str):
        yield caminho, no


def _regras_extras(spec: dict, metricas_conhecidas: set[str] | None) -> list[str]:
    problemas = []
    blocos = spec.get("blocos") or []
    vistos = set()
    todas = set()
    for i, bloco in enumerate(blocos):
        if not isinstance(bloco, dict):
            continue
        bid = bloco.get("id")
        if bid in vistos:
            problemas.append(f"blocos[{i}].id: id repetido ({bid})")
        vistos.add(bid)
        metricas = set(bloco.get("metricas") or [])
        todas |= metricas
        for campo in ("titulo", "subtitulo", "achado"):
            for nome in MARCADOR.findall(str(bloco.get(campo, ""))):
                if nome not in metricas:
                    problemas.append(f"blocos[{i}].{campo}: marcador {{{nome}}} não é métrica deste bloco")
    for campo in ("titulo", "subtitulo", "pergunta_negocio", "notas"):
        for nome in MARCADOR.findall(str(spec.get(campo, ""))):
            if nome not in todas:
                problemas.append(f"{campo}: marcador {{{nome}}} não aparece em nenhum bloco")
    if metricas_conhecidas is not None:
        for nome in sorted(todas - metricas_conhecidas):
            problemas.append(f"métrica {nome!r} não existe no modelo de métricas")
    return problemas


def validar(spec: dict, metricas_conhecidas: set[str] | None = None) -> list[str]:
    """Lista de problemas da spec; vazia quando ela é válida."""
    validador = Draft202012Validator(carregar_schema())
    erros = sorted(validador.iter_errors(spec), key=lambda e: list(e.absolute_path))
    problemas = [f"{_caminho(e)}: {_mensagem(e)}" for e in erros]
    if isinstance(spec, dict):
        problemas += _regras_extras(spec, metricas_conhecidas)
    return problemas


def validar_arquivo(caminho: str | Path, metricas_conhecidas: set[str] | None = None) -> list[str]:
    caminho = Path(caminho)
    try:
        spec = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"arquivo não encontrado: {caminho}"]
    except json.JSONDecodeError as e:
        return [f"JSON inválido em {caminho.name}, linha {e.lineno}: {e.msg}"]
    return validar(spec, metricas_conhecidas)
