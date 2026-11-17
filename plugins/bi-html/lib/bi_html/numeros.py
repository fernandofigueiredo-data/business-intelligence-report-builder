"""
Leitura de números escritos em português do Brasil.

Usada em dois lugares: para tirar da conclusão do notebook os números que a
análise afirmou (e reproduzi-los), e para conferir que todo número do
documento de decisão saiu de um achado.

Reconhece: valores em reais (R$ 1.234,56; R$ 4,1 mi; R$ 380 mil), percentuais
(39%; 12,5 %), pontos percentuais (3,2 p.p.), multiplicadores (12,1×), datas
(31/12/2025), anos (2025) e números soltos (16.254; 3,5). Referências a
achados como [A12] não contam como número.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def arredondar(v: float, casas: int) -> Decimal:
    """Arredondamento comercial (meio para cima), como se escreve em português: 17,5 → 18."""
    return Decimal(repr(v)).quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)

ESCALAS = {"mil": 1e3, "mi": 1e6, "milhão": 1e6, "milhao": 1e6, "milhões": 1e6, "milhoes": 1e6,
           "bi": 1e9, "bilhão": 1e9, "bilhao": 1e9, "bilhões": 1e9, "bilhoes": 1e9}
NUM = r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?"
ESC = r"(?:\s?(?:mil|mi|milh(?:ão|ao|ões|oes)|bi|bilh(?:ão|ao|ões|oes))\b)?"
PADRAO = re.compile(
    r"(?P<data>\b\d{2}/\d{2}/\d{4}\b)"
    rf"|(?P<moeda>-?R\$\s?(?:{NUM}){ESC})"
    rf"|(?P<pp>(?:{NUM})\s?(?:p\.\s?p\.|pp\b|pontos? percentua(?:l|is)))"
    rf"|(?P<pct>(?:{NUM})\s?%)"
    rf"|(?P<mult>(?:{NUM})\s?[×x](?![a-zA-Z]))"
    rf"|(?P<num>(?<![\w/])(?:{NUM}){ESC}(?![\w/]))",
    re.IGNORECASE)
REF = re.compile(r"\[A\d+\]|\bA\d+\b")


@dataclass
class Numero:
    texto: str
    tipo: str          # moeda, pct, pp, mult, num, ano, data
    valor: float       # percentuais e pontos percentuais em fração (39% → 0,39)
    casas: int         # casas decimais escritas (na escala escrita)
    escala: float      # 1, mil, milhão...
    inicio: int

    def bate_com(self, valor: float, tipo: str) -> bool:
        """O valor calculado, arredondado como este número foi escrito, dá este número?"""
        if self.tipo in ("data",):
            return False
        if tipo != self.tipo:
            return False
        if self.tipo in ("pct", "pp"):
            return arredondar(abs(valor) * 100, self.casas) == arredondar(abs(self.valor) * 100, self.casas)
        return arredondar(abs(valor) / self.escala, self.casas) == arredondar(abs(self.valor) / self.escala, self.casas)


def _valor(trecho: str) -> tuple[float, int, float]:
    m = re.search(NUM, trecho)
    bruto = m.group(0)
    casas = len(bruto.split(",")[1]) if "," in bruto else 0
    v = float(bruto.replace(".", "").replace(",", "."))
    escala = 1.0
    resto = trecho[m.end():].strip().lower()
    for nome, fator in sorted(ESCALAS.items(), key=lambda x: -len(x[0])):  # "milhões" antes de "mil"
        if re.match(rf"{nome}\b", resto):
            escala = fator
            break
    return v * escala, casas, escala


def extrair(texto: str) -> list[Numero]:
    limpo = REF.sub(lambda m: " " * len(m.group(0)), texto)
    achados = []
    for m in PADRAO.finditer(limpo):
        tipo = m.lastgroup
        trecho = m.group(0).strip()
        if tipo == "data":
            achados.append(Numero(trecho, "data", 0.0, 0, 1.0, m.start()))
            continue
        valor, casas, escala = _valor(trecho)
        if trecho.lstrip().startswith("-") or trecho.startswith("-R$"):
            valor = -abs(valor)
        if tipo in ("pct", "pp"):
            valor = valor / 100
        if tipo == "num" and escala == 1 and casas == 0 and 1900 <= abs(valor) <= 2100 and "." not in trecho:
            tipo = "ano"
        achados.append(Numero(trecho, tipo, valor, casas, escala, m.start()))
    return achados
