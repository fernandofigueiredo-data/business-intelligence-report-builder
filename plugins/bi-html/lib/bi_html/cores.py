"""
Cores: leitura de valores CSS, conversão para sRGB e contraste WCAG.

Aceita os formatos que aparecem em design systems e temas: hex (#RGB, #RRGGBB,
#RRGGBBAA), rgb()/rgba(), hsl()/hsla(), oklch() e alguns nomes. Tudo vira hex
sRGB para calcular contraste (WCAG 2.x) e gerar o CSS.

O ajuste de contraste mexe só na luminosidade (L do OKLCH) da cor da frente,
na direção que afasta do fundo, até atingir a razão pedida. Matiz e croma ficam
como estavam, para a cor continuar reconhecível.
"""
from __future__ import annotations

import math
import re

NOMES = {"white": "#ffffff", "black": "#000000", "transparent": "#ffffff", "red": "#ff0000",
         "green": "#008000", "blue": "#0000ff", "gray": "#808080", "grey": "#808080"}


class ErroDeCor(ValueError):
    pass


# ---------------------------------------------------------------- leitura

def _num(texto: str, escala: float = 1.0) -> float:
    texto = texto.strip()
    if texto.endswith("%"):
        return float(texto[:-1]) / 100 * escala
    if texto.endswith("deg"):
        return float(texto[:-3])
    return float(texto)


def _args(texto: str) -> list[str]:
    dentro = texto[texto.index("(") + 1: texto.rindex(")")]
    dentro = dentro.split("/")[0]
    return [p for p in re.split(r"[\s,]+", dentro.strip()) if p]


def para_rgb(valor: str) -> tuple[float, float, float]:
    """Cor CSS → (r, g, b) em 0–1, sRGB."""
    v = str(valor).strip().lower()
    v = NOMES.get(v, v)
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h[:3])
        elif len(h) in (6, 8):
            h = h[:6]
        else:
            raise ErroDeCor(f"hex inválido: {valor}")
        try:
            return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except ValueError:
            raise ErroDeCor(f"hex inválido: {valor}") from None
    if re.fullmatch(r"[0-9a-f]{6}", v):
        return para_rgb("#" + v)
    try:
        if v.startswith("rgb"):
            a = _args(v)
            return tuple(min(1.0, max(0.0, _num(x, 255) / 255)) for x in a[:3])
        if v.startswith("hsl"):
            a = _args(v)
            return _hsl_para_rgb(_num(a[0]) % 360, _num(a[1], 1.0), _num(a[2], 1.0))
        if v.startswith("oklch"):
            a = _args(v)
            l = _num(a[0], 1.0)
            return oklch_para_rgb(l, _num(a[1], 0.4), _num(a[2]) if a[2] != "none" else 0.0)
    except (ValueError, IndexError):
        raise ErroDeCor(f"cor inválida: {valor}") from None
    raise ErroDeCor(f"formato de cor não suportado: {valor}")


def _hsl_para_rgb(h, s, l):
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return (r + m, g + m, b + m)


def hex_de(rgb) -> str:
    return "#" + "".join(f"{round(min(1, max(0, c)) * 255):02x}" for c in rgb)


def normalizar(valor: str) -> str:
    return hex_de(para_rgb(valor))


# ---------------------------------------------------------------- OKLCH

def _linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c):
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def rgb_para_oklch(rgb):
    r, g, b = (_linear(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def oklch_para_rgb(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(_gamma(c) for c in (r, g, bl))


def com_luminosidade(cor: str, L: float, croma_max: float | None = None) -> str:
    _, C, H = rgb_para_oklch(para_rgb(cor))
    if croma_max is not None:
        C = min(C, croma_max)
    return hex_de(oklch_para_rgb(L, C, H))


def misturar(a: str, b: str, t: float) -> str:
    """Mistura em sRGB: t=0 devolve a, t=1 devolve b."""
    ra, rb = para_rgb(a), para_rgb(b)
    return hex_de(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


# ---------------------------------------------------------------- contraste

def luminancia(cor: str) -> float:
    r, g, b = (_linear(c) for c in para_rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(frente: str, fundo: str) -> float:
    a, b = luminancia(frente), luminancia(fundo)
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


def eh_escuro(cor: str) -> bool:
    return luminancia(cor) < 0.18


def ajustar_contraste(frente: str, fundo: str, minimo: float) -> str:
    """Escurece ou clareia `frente` (só o L do OKLCH) até o contraste com `fundo` chegar a `minimo`."""
    if contraste(frente, fundo) >= minimo:
        return frente
    L, C, H = rgb_para_oklch(para_rgb(frente))
    direcao = -1 if not eh_escuro(fundo) else 1
    for passo in range(1, 101):
        novo_L = min(1.0, max(0.0, L + direcao * passo * 0.01))
        candidato = hex_de(oklch_para_rgb(novo_L, C, H))
        if contraste(candidato, fundo) >= minimo:
            return candidato
    return "#000000" if direcao < 0 else "#ffffff"


def melhor_texto_sobre(fundo: str) -> str:
    return "#ffffff" if contraste("#ffffff", fundo) >= contraste("#0b0b0b", fundo) else "#0b0b0b"
