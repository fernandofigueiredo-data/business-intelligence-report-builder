"""
exportacao.py — fase F11: o dashboard num HTML autocontido, para enviar (WhatsApp, e-mail, pendrive).

O dashboard normal busca o ECharts no cdnjs e as fontes no Google Fonts. A cópia de envio embute o
ECharts no próprio arquivo e troca as fontes da web pelas do sistema (a pilha de fontes dos tokens
já tem as alternativas), então abre sem internet. Os dados que ela leva são os mesmos do dashboard:
o cubo agregado, nunca as linhas da tabela.

Diferenças em relação ao Artifact (seção 6 do plano): o arquivo pode ser reencaminhado sem
controle e não há como revogá-lo depois do envio. Por isso:
- a exportação é recusada quando há dados pessoais (mesma regra da publicação, regra 5);
- o rodapé diz que é uma cópia congelada, com a data e o hash da fonte.

O ECharts vem do cdnjs uma única vez, na versão fixa do dashboard, conferido pelo hash SRI do
próprio cdnjs, e fica no cache do usuário (~/.cache/bi-html). A variável BI_HTML_ECHARTS aponta
para um arquivo local, para máquinas sem internet.
"""
from __future__ import annotations

import base64
import hashlib
import html
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .ingestao import ErroDeLeitura
from .render import ECHARTS, SAIDA, bloqueio_de_publicacao, documento, fragmento

VERSAO_ECHARTS = "5.6.0"
SRI_ECHARTS = "sha512-XSmbX3mhrD2ix5fXPTRQb2FwK22sRMVQTpBP2ac8hX7Dh/605hA2QDegVWiAvZPiXIxOV0CbkmUjGionDpbCmw=="
EXTERNO = re.compile(r"""<(?:script|link|img|iframe)\b[^>]*\b(?:src|href)\s*=\s*["']https?://""", re.I)


class ErroDeExportacao(ErroDeLeitura):
    pass


def _cache() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "bi-html" / f"echarts-{VERSAO_ECHARTS}.min.js"


def _confere(conteudo: bytes) -> bool:
    algoritmo, esperado = SRI_ECHARTS.split("-", 1)
    return base64.b64encode(hashlib.new(algoritmo, conteudo).digest()).decode() == esperado


def echarts() -> str:
    """Código do ECharts conferido pelo SRI: BI_HTML_ECHARTS, o cache ou o cdnjs (e grava no cache)."""
    local = os.environ.get("BI_HTML_ECHARTS")
    if local:
        conteudo = Path(local).read_bytes()
        if not _confere(conteudo):
            raise ErroDeExportacao("o ECharts de BI_HTML_ECHARTS não confere com o hash esperado",
                                   [f"use o echarts.min.js da versão {VERSAO_ECHARTS}"])
        return conteudo.decode("utf-8")
    cache = _cache()
    if cache.is_file() and _confere(cache.read_bytes()):
        return cache.read_text(encoding="utf-8")
    try:
        req = urllib.request.Request(ECHARTS, headers={"User-Agent": "bi-html"})
        with urllib.request.urlopen(req, timeout=60) as r:
            conteudo = r.read()
    except OSError as e:
        raise ErroDeExportacao("não deu para baixar o ECharts para embutir",
                               [str(e), "sem internet, aponte BI_HTML_ECHARTS para um echarts.min.js "
                                        f"da versão {VERSAO_ECHARTS}"]) from None
    if not _confere(conteudo):
        raise ErroDeExportacao("o ECharts baixado não confere com o hash esperado; nada foi gravado")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(conteudo)
    return conteudo.decode("utf-8")


def autocontido(frag: str, codigo_echarts: str, aviso: str) -> str:
    """Troca o ECharts do CDN pelo código embutido, tira as fontes da web e põe o aviso de cópia."""
    script_cdn = f'<script src="{ECHARTS}"></script>'
    if script_cdn not in frag:
        raise ErroDeExportacao("o dashboard não tem o ECharts no formato esperado")
    # "</script" dentro do código encerraria a tag: a sequência é escapada (vale em JavaScript).
    seguro = codigo_echarts.replace("</script", "<\\/script")
    frag = frag.replace(script_cdn, f"<script>{seguro}</script>")
    frag = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">\n?', "", frag)
    frag = frag.replace("<footer class=\"rodape\">", f"<footer class=\"rodape\">\n    <p><strong>{html.escape(aviso)}</strong></p>", 1)
    externos = EXTERNO.findall(frag)
    if externos:
        raise ErroDeExportacao("a cópia ainda depende da internet", externos[:3])
    return frag


def exportar(projeto: Path, arquivo_spec: Path | None = None, destino: Path | None = None) -> dict:
    """Grava o dashboard (ou outra spec do projeto) num HTML que abre sem internet."""
    from .dashboard import ARQUIVO_SPEC, montar

    projeto = Path(projeto)
    motivos = bloqueio_de_publicacao(projeto)
    if motivos:
        raise ErroDeExportacao("a cópia para envio não pode sair com dados pessoais",
                               motivos + ["remova ou agregue essas colunas e exporte de novo"])
    montado = montar(projeto, Path(arquivo_spec or ARQUIVO_SPEC))
    data = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y")
    aviso = (f"Cópia para envio, gerada em {data}: não se atualiza e não pode ser revogada depois de enviada. "
             "Leva só os números agregados do dashboard.")
    frag = autocontido(fragmento(montado), echarts(), aviso)
    rel = Path(destino) if destino else SAIDA / "dashboard.offline.html"
    caminho = projeto / rel
    caminho.parent.mkdir(parents=True, exist_ok=True)
    completo = documento(frag)
    caminho.write_text(completo, encoding="utf-8")
    return {"html": rel.as_posix(), "bytes": len(completo.encode("utf-8")), "titulo": montado["spec"]["titulo"],
            "echarts": VERSAO_ECHARTS, "aviso": aviso}
