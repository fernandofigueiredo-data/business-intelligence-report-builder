"""
Renderizador: transforma o que `dashboard.montar()` calculou em HTML.

Gera dois arquivos em `saidas/bi/`:
- `dashboard.html`: documento completo, abre direto no navegador;
- `dashboard.artifact.html`: o mesmo conteúdo sem `<html>`/`<head>`/`<body>`,
  no formato que a ferramenta Artifact do Claude publica.

O HTML não faz conta: os números vêm prontos de `montar()`, e o JavaScript só
procura a linha da combinação de filtros escolhida, formata em pt-BR e desenha
(gráficos com ECharts, carregado do cdnjs). Sem internet, os gráficos não
aparecem, mas cada bloco tem a tabela "Ver os números" com os mesmos valores.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from .dashboard import montar

ECHARTS = "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.6.0/echarts.min.js"
SAIDA = Path("saidas") / "bi"
FONTES_DO_SISTEMA = {"segoe ui", "system-ui", "arial", "helvetica", "helvetica neue", "-apple-system",
                     "roboto", "sans-serif", "serif", "georgia", "times new roman", "menlo", "monospace"}
META_BYTES = 5 * 1024 * 1024
DOMINIOS = {"marketing": "Marketing", "vendas": "Vendas", "financeiro": "Financeiro", "operacoes": "Operações",
            "rh": "Pessoas", "outro": "Painel"}

CSS = r"""
body { margin: 0; background: var(--background); color: var(--foreground); font-family: var(--font-sans);
  font-size: 15px; line-height: 1.5; -webkit-font-smoothing: antialiased; }
.pagina { max-width: 1240px; margin: 0 auto; padding-block: 28px 56px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: flex; flex-direction: column; gap: 20px; }
.topo { display: flex; flex-direction: column; gap: 10px; }
.olho { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 12px; letter-spacing: .06em;
  text-transform: uppercase; color: var(--muted-foreground); }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: 999px;
  border: var(--border-width) solid var(--border); background: var(--muted); color: var(--muted-foreground);
  font-size: 12px; letter-spacing: 0; text-transform: none; }
.chip.alerta { color: var(--alerta); border-color: currentColor; background: transparent; }
.chip.positivo { color: var(--positivo); border-color: currentColor; background: transparent; }
h1 { font-family: var(--font-titulo); font-size: clamp(26px, 4vw, 38px); line-height: 1.12; margin: 0;
  text-wrap: balance; letter-spacing: -.01em; }
.subtitulo { margin: 0; color: var(--muted-foreground); max-width: 70ch; }
.pergunta { margin: 0; max-width: 70ch; font-size: 14px; }
.pergunta b { font-weight: 600; }
.filtros { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: end; padding: 12px 14px;
  background: var(--muted); border-radius: var(--radius); }
.filtros label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted-foreground);
  min-width: 0; }
.filtros select { font: inherit; font-size: 14px; color: var(--foreground); background: var(--card);
  border: var(--border-width) solid var(--border); border-radius: calc(var(--radius) * .7); padding: 6px 30px 6px 10px;
  max-width: 100%; }
.filtros select:focus-visible, button:focus-visible, summary:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.limpar { font: inherit; font-size: 13px; color: var(--primary); background: none; border: 0; padding: 6px 2px;
  cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.grade { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 16px; }
.bloco { grid-column: span var(--span, 6); min-width: 0; container-type: inline-size; background: var(--card); color: var(--card-foreground);
  border: var(--border-width) solid var(--border); border-radius: var(--radius); padding: 16px 18px;
  display: flex; flex-direction: column; gap: 10px; }
.bloco[data-largura="um_terco"] { --span: 4; } .bloco[data-largura="metade"] { --span: 6; }
.bloco[data-largura="dois_tercos"] { --span: 8; } .bloco[data-largura="inteira"] { --span: 12; }
.bloco h2 { font-family: var(--font-titulo); font-size: 16px; line-height: 1.3; margin: 0; text-wrap: balance; }
.bloco .sub { margin: -6px 0 0; font-size: 13px; color: var(--muted-foreground); }
.achado { margin: 0; font-size: 14px; }
.destaque { display: flex; flex-direction: column; gap: 8px; }
.valor-grande { font-family: var(--font-titulo); font-size: clamp(22px, 10cqi, 52px); line-height: 1.05; font-weight: 600;
  font-variant-numeric: tabular-nums; letter-spacing: -.02em; white-space: nowrap; }
.variacao { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: baseline; font-size: 13px; color: var(--muted-foreground); }
.delta { font-weight: 600; font-variant-numeric: tabular-nums; }
.delta.sobe { color: var(--positivo); } .delta.desce { color: var(--negativo); }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.kpi { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border-radius: calc(var(--radius) * .7);
  background: var(--muted); min-width: 0; container-type: inline-size; }
.kpi .rotulo { font-size: 12px; color: var(--muted-foreground); }
.kpi .valor { font-size: clamp(14px, 11cqi, 22px); font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.grafico { width: 100%; height: 280px; min-width: 0; }
.bloco[data-tipo="linha_tempo"] .grafico, .bloco[data-tipo="area_empilhada"] .grafico { height: 300px; }
.bloco[data-tipo="mapa_calor"] .grafico { height: 320px; }
.mapa { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }
.uf { aspect-ratio: 1.15; max-width: 100%; border-radius: 4px; display: flex; flex-direction: column; justify-content: center;
  align-items: center; font-size: 11px; line-height: 1.15; font-variant-numeric: tabular-nums; min-width: 0; overflow: hidden; }
.uf b { font-size: 12px; }
.uf.vazia { background: var(--muted); color: var(--muted-foreground); }
.legenda { display: flex; justify-content: space-between; font-size: 11px; color: var(--muted-foreground); gap: 8px; }
.tabela-rolagem { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); white-space: nowrap; }
th { font-weight: 600; color: var(--muted-foreground); font-size: 12px; }
td.num, th.num { text-align: right; }
tfoot td { font-weight: 600; border-bottom: 0; }
details { font-size: 13px; }
details summary { cursor: pointer; color: var(--muted-foreground); width: fit-content; }
details[open] summary { margin-bottom: 6px; }
.definicoes { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.definicoes b { font-weight: 600; }
.definicoes span { color: var(--muted-foreground); }
.sem-grafico { font-size: 13px; color: var(--muted-foreground); }
.rodape { display: flex; flex-direction: column; gap: 10px; padding-top: 14px; border-top: 1px solid var(--border);
  font-size: 13px; color: var(--muted-foreground); }
.rodape code { font-family: var(--font-mono); font-size: 12px; overflow-wrap: anywhere; }
.rodape h2 { font-size: 14px; color: var(--foreground); margin: 0; font-family: var(--font-titulo); }
@media (max-width: 960px) {
  .bloco[data-largura="um_terco"] { --span: 6; }
  .bloco[data-largura="metade"], .bloco[data-largura="dois_tercos"] { --span: 12; }
}
@media (max-width: 640px) {
  .bloco { --span: 12 !important; padding: 14px; }
  .grafico { height: 240px; }
  .mapa { gap: 3px; } .uf { font-size: 10px; } .uf b { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
"""

JS = r"""
(function () {
  const D = JSON.parse(document.getElementById('dados-bi').textContent);
  const TODOS = D.constantes.todos;
  const estado = {};
  D.filtros.forEach(f => { estado[f.dimensao] = TODOS; });
  const graficos = [];
  const temEcharts = typeof window.echarts !== 'undefined';

  const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
  const dec2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const ate2 = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
  const pct1 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 });
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

  function fmt(v, m) {
    if (v === null || v === undefined) return '—';
    const def = D.metricas[m] || {};
    const u = !def.unidade ? '' : (/^[%×x°]$/.test(def.unidade) ? '' : ' ') + def.unidade;
    switch (def.formato) {
      case 'moeda': return moeda.format(v);
      case 'inteiro': return inteiro.format(v) + u;
      case 'percentual': return pct1.format(v * 100) + '%';
      case 'decimal': return dec2.format(v) + u;
      default: return ate2.format(v) + u;
    }
  }
  function fmtEixo(v, m) {
    const def = D.metricas[m] || {};
    if (def.formato === 'percentual') return pct1.format(v * 100) + '%';
    const t = Math.abs(v) >= 10000 ? compacto.format(v) : ate2.format(v);
    return def.formato === 'moeda' ? 'R$ ' + t : t;
  }
  function rotuloDim(dim, valor) {
    if (valor === null || valor === undefined) return '—';
    const g = (D.dimensoes[dim] || {}).granularidade;
    const s = String(valor);
    if (g === 'mes' && /^\d{4}-\d{2}$/.test(s)) return MESES[+s.slice(5, 7) - 1] + '/' + s.slice(2, 4);
    if (g === 'trimestre') return s.replace(/^(\d{4})-T(\d)$/, (_, a, t) => t + 'º tri/' + a.slice(2));
    if ((g === 'dia' || g === 'semana') && /^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(8, 10) + '/' + s.slice(5, 7) + '/' + s.slice(2, 4);
    return s;
  }
  function cor(nome) { return getComputedStyle(document.documentElement).getPropertyValue('--' + nome).trim(); }
  function serieCores() { return [1, 2, 3, 4, 5].map(i => cor('chart-' + i)); }
  function el(tag, attrs, filhos) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === 'texto') e.textContent = v; else if (k === 'classe') e.className = v; else e.setAttribute(k, v);
    });
    (filhos || []).forEach(f => f && e.appendChild(f));
    return e;
  }
  function dadosDo(b) {
    const dims = b.dimensoes || [];
    const chave = D.filtros.map(f => dims.includes(f.dimensao) ? TODOS : estado[f.dimensao]).join('|');
    const base = b.dados[chave] || { linhas: [], total: null };
    const ativos = D.filtros.filter(f => dims.includes(f.dimensao) && estado[f.dimensao] !== TODOS);
    if (!ativos.length) return base;
    return { linhas: base.linhas.filter(l => ativos.every(f => l[f.dimensao] === estado[f.dimensao])), total: null };
  }
  function preencher(texto, b, dados) {
    const ref = dados.linhas[0] || dados.total || {};
    return texto.replace(/\{([a-z_]+)\}/g, (_, m) => fmt(ref[m], m));
  }
  function deltaEl(linha, m, b) {
    const p = linha[m + '__variacao_pct'];
    const box = el('div', { classe: 'variacao' });
    if (p === null || p === undefined) {
      if (b.comparacao_periodo) box.appendChild(el('span', { texto: 'Sem dados no período de comparação' }));
      return box;
    }
    const sobe = p >= 0;
    const bom = (D.metricas[m] || {}).melhor === 'menor' ? !sobe : sobe;
    box.appendChild(el('span', { classe: 'delta ' + (bom ? 'sobe' : 'desce'), texto: (sobe ? '▲ ' : '▼ ') + pct1.format(Math.abs(p) * 100) + '%' }));
    box.appendChild(el('span', { texto: 'vs. ' + fmt(linha[m + '__comparacao'], m) + ' em ' + b.comparacao_periodo.inicio + ' a ' + b.comparacao_periodo.fim }));
    return box;
  }
  function tabelaNumeros(b, dados) {
    const dims = b.dimensoes || [];
    const cab = el('tr', {}, dims.map(d => el('th', { texto: D.dimensoes[d].descricao, scope: 'col' }))
      .concat(b.metricas.map(m => el('th', { classe: 'num', texto: D.metricas[m].descricao, scope: 'col' }))));
    const corpo = dados.linhas.map(l => el('tr', {}, dims.map(d => el('td', { texto: rotuloDim(d, l[d]) }))
      .concat(b.metricas.map(m => el('td', { classe: 'num', texto: fmt(l[m], m) })))));
    const filhos = [el('thead', {}, [cab]), el('tbody', {}, corpo)];
    if (dados.total && dims.length) {
      filhos.push(el('tfoot', {}, [el('tr', {}, [el('td', { texto: 'Total', colspan: String(dims.length) })]
        .concat(b.metricas.map(m => el('td', { classe: 'num', texto: fmt(dados.total[m], m) }))))]));
    }
    return el('div', { classe: 'tabela-rolagem' }, [el('table', {}, filhos)]);
  }
  function eixoBase() {
    return {
      axisLine: { lineStyle: { color: cor('border') } }, axisTick: { show: false },
      axisLabel: { color: cor('muted-foreground'), fontFamily: getComputedStyle(document.body).fontFamily, hideOverlap: true },
      splitLine: { lineStyle: { color: cor('border'), type: 'dashed' } }
    };
  }
  function opcoesBase() {
    return {
      color: serieCores(), animation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
      textStyle: { fontFamily: getComputedStyle(document.body).fontFamily, color: cor('card-foreground') },
      grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
      tooltip: { trigger: 'axis', backgroundColor: cor('card'), borderColor: cor('border'), textStyle: { color: cor('card-foreground') } },
      legend: { show: false, textStyle: { color: cor('muted-foreground') }, top: 0 }
    };
  }
  function opcaoGrafico(b, dados) {
    const o = opcoesBase();
    const dims = b.dimensoes || [], ms = b.metricas, ls = dados.linhas;
    const m0 = ms[0];
    const tt = (params) => {
      const ps = Array.isArray(params) ? params : [params];
      return ps.map(p => (p.seriesName && ps.length > 1 ? p.marker + p.seriesName + ': ' : (p.name ? p.name + ': ' : '')) + (p.data && p.data.texto ? p.data.texto : '')).join('<br>');
    };
    o.tooltip.formatter = tt;
    if (b.tipo === 'linha_tempo') {
      o.xAxis = Object.assign(eixoBase(), { type: 'category', data: ls.map(l => rotuloDim(dims[0], l[dims[0]])), boundaryGap: false, splitLine: { show: false } });
      o.yAxis = Object.assign(eixoBase(), { type: 'value', axisLabel: Object.assign(eixoBase().axisLabel, { formatter: v => fmtEixo(v, m0) }) });
      o.series = ms.map((m, i) => ({ type: 'line', name: D.metricas[m].descricao, smooth: true, showSymbol: ls.length < 20, symbolSize: 6,
        areaStyle: i === 0 ? { opacity: .12 } : undefined, lineStyle: { width: 2.5 },
        data: ls.map(l => ({ value: l[m], texto: fmt(l[m], m) })) }));
      o.legend.show = ms.length > 1; if (ms.length > 1) o.grid.top = 36;
    } else if (b.tipo === 'barras_ranking') {
      const rev = ls.slice().reverse();
      o.tooltip.trigger = 'item';
      o.xAxis = Object.assign(eixoBase(), { type: 'value', axisLabel: Object.assign(eixoBase().axisLabel, { formatter: v => fmtEixo(v, m0) }) });
      o.yAxis = Object.assign(eixoBase(), { type: 'category', data: rev.map(l => rotuloDim(dims[0], l[dims[0]])), splitLine: { show: false } });
      o.series = [{ type: 'bar', barMaxWidth: 22, data: rev.map((l, i) => ({ value: l[m0], texto: fmt(l[m0], m0),
        itemStyle: { color: i === rev.length - 1 ? cor('primary') : cor('muted-foreground'), opacity: i === rev.length - 1 ? 1 : .45, borderRadius: [0, 4, 4, 0] } })),
        label: { show: true, position: 'right', color: cor('card-foreground'), opacity: 1, formatter: p => p.data.texto } }];
      o.grid.right = 88;
    } else if (b.tipo === 'barras_agrupadas') {
      o.tooltip.axisPointer = { type: 'shadow' };
      const cats = [...new Set(ls.map(l => l[dims[0]]))];
      o.xAxis = Object.assign(eixoBase(), { type: 'category', data: cats.map(c => rotuloDim(dims[0], c)), splitLine: { show: false } });
      o.yAxis = Object.assign(eixoBase(), { type: 'value', axisLabel: Object.assign(eixoBase().axisLabel, { formatter: v => fmtEixo(v, m0) }) });
      if (dims.length === 2) {
        const grupos = [...new Set(ls.map(l => l[dims[1]]))];
        o.series = grupos.map(g => ({ type: 'bar', name: rotuloDim(dims[1], g), barMaxWidth: 28,
          data: cats.map(c => { const l = ls.find(x => x[dims[0]] === c && x[dims[1]] === g); return { value: l ? l[m0] : null, texto: l ? fmt(l[m0], m0) : '—' }; }) }));
      } else {
        o.series = ms.map(m => ({ type: 'bar', name: D.metricas[m].descricao, barMaxWidth: 28,
          data: cats.map(c => { const l = ls.find(x => x[dims[0]] === c); return { value: l ? l[m] : null, texto: l ? fmt(l[m], m) : '—' }; }) }));
      }
      o.legend.show = o.series.length > 1; if (o.legend.show) o.grid.top = 36;
    } else if (b.tipo === 'area_empilhada') {
      const xs = [...new Set(ls.map(l => l[dims[0]]))], grupos = [...new Set(ls.map(l => l[dims[1]]))];
      o.xAxis = Object.assign(eixoBase(), { type: 'category', data: xs.map(x => rotuloDim(dims[0], x)), boundaryGap: false, splitLine: { show: false } });
      o.yAxis = Object.assign(eixoBase(), { type: 'value', axisLabel: Object.assign(eixoBase().axisLabel, { formatter: v => fmtEixo(v, m0) }) });
      o.series = grupos.map(g => ({ type: 'line', name: rotuloDim(dims[1], g), stack: 'total', areaStyle: { opacity: .55 }, showSymbol: false, smooth: true,
        data: xs.map(x => { const l = ls.find(y => y[dims[0]] === x && y[dims[1]] === g); return { value: l ? l[m0] : 0, texto: l ? fmt(l[m0], m0) : '—' }; }) }));
      o.legend.show = true; o.grid.top = 36;
    } else if (b.tipo === 'rosca') {
      o.tooltip = { trigger: 'item', backgroundColor: cor('card'), borderColor: cor('border'), textStyle: { color: cor('card-foreground') },
        formatter: p => p.name + ': ' + p.data.texto + ' (' + pct1.format(p.percent) + '%)' };
      o.legend = { show: true, bottom: 0, textStyle: { color: cor('muted-foreground') }, icon: 'circle' };
      o.series = [{ type: 'pie', radius: ['54%', '78%'], center: ['50%', '44%'], avoidLabelOverlap: true, label: { show: false },
        itemStyle: { borderColor: cor('card'), borderWidth: 2 },
        data: ls.map(l => ({ name: rotuloDim(dims[0], l[dims[0]]), value: l[m0], texto: fmt(l[m0], m0) })) }];
      if (dados.total) o.graphic = [{ type: 'text', left: 'center', top: '38%', style: { text: fmt(dados.total[m0], m0), fill: cor('card-foreground'), fontSize: 15, fontWeight: 600, align: 'center' } }];
    } else if (b.tipo === 'cascata') {
      let acumulado = 0; const base = [], valor = [], nomes = [];
      ls.forEach(l => { const v = l[m0] || 0; nomes.push(rotuloDim(dims[0], l[dims[0]]));
        base.push(v >= 0 ? acumulado : acumulado + v); valor.push({ value: Math.abs(v), texto: fmt(v, m0), itemStyle: { color: v >= 0 ? cor('positivo') : cor('negativo') } }); acumulado += v; });
      if (dados.total) { nomes.push('Resultado'); base.push(Math.min(0, dados.total[m0])); valor.push({ value: Math.abs(dados.total[m0]), texto: fmt(dados.total[m0], m0), itemStyle: { color: cor('primary') } }); }
      o.tooltip = { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: cor('card'), borderColor: cor('border'), textStyle: { color: cor('card-foreground') },
        formatter: ps => { const p = ps.find(x => x.seriesIndex === 1); return p.name + ': ' + p.data.texto; } };
      o.xAxis = Object.assign(eixoBase(), { type: 'category', data: nomes, splitLine: { show: false }, axisLabel: Object.assign(eixoBase().axisLabel, { interval: 0, rotate: nomes.length > 5 ? 30 : 0 }) });
      o.yAxis = Object.assign(eixoBase(), { type: 'value', axisLabel: Object.assign(eixoBase().axisLabel, { formatter: v => fmtEixo(v, m0) }) });
      o.series = [{ type: 'bar', stack: 'c', itemStyle: { color: 'transparent' }, emphasis: { disabled: true }, data: base },
                  { type: 'bar', stack: 'c', barMaxWidth: 40, data: valor }];
    } else if (b.tipo === 'funil') {
      const linha = ls[0] || {};
      o.tooltip = { trigger: 'item', backgroundColor: cor('card'), borderColor: cor('border'), textStyle: { color: cor('card-foreground') }, formatter: p => p.name + ': ' + p.data.texto };
      o.series = [{ type: 'funnel', left: '8%', right: '8%', top: 8, bottom: 8, sort: 'none', gap: 3, minSize: '18%',
        label: { position: 'inside', color: cor('primary-foreground'), formatter: p => p.name + '\n' + p.data.texto },
        data: ms.map((m, i) => ({ name: D.metricas[m].descricao, value: linha[m], texto: fmt(linha[m], m),
          itemStyle: { color: cor('primary'), opacity: 1 - i * (0.5 / ms.length) } })) }];
    } else if (b.tipo === 'mapa_calor') {
      const xs = [...new Set(ls.map(l => l[dims[0]]))], ys = [...new Set(ls.map(l => l[dims[1]]))];
      const vals = ls.map(l => l[m0]).filter(v => v !== null);
      o.tooltip = { trigger: 'item', backgroundColor: cor('card'), borderColor: cor('border'), textStyle: { color: cor('card-foreground') }, formatter: p => p.data.texto };
      o.grid.bottom = 48;
      o.xAxis = Object.assign(eixoBase(), { type: 'category', data: xs.map(x => rotuloDim(dims[0], x)), splitArea: { show: false } });
      o.yAxis = Object.assign(eixoBase(), { type: 'category', data: ys.map(y => rotuloDim(dims[1], y)) });
      o.visualMap = { min: Math.min(...vals), max: Math.max(...vals), calculable: false, orient: 'horizontal', left: 'center', bottom: 0,
        inRange: { color: [cor('muted'), cor('primary')] }, textStyle: { color: cor('muted-foreground') }, formatter: v => fmtEixo(v, m0) };
      o.series = [{ type: 'heatmap', data: ls.map(l => ({ value: [xs.indexOf(l[dims[0]]), ys.indexOf(l[dims[1]]), l[m0]], texto: rotuloDim(dims[0], l[dims[0]]) + ' · ' + rotuloDim(dims[1], l[dims[1]]) + ': ' + fmt(l[m0], m0) })) }];
    }
    return o;
  }
  const GRADE_UF = { RR: [0, 3], AP: [0, 5], AM: [1, 1], PA: [1, 3], MA: [1, 4], CE: [1, 5], RN: [1, 6], AC: [2, 0], RO: [2, 1],
    TO: [2, 3], PI: [2, 4], PE: [2, 5], PB: [2, 6], MT: [3, 2], GO: [3, 3], DF: [3, 4], BA: [3, 5], AL: [3, 6], MS: [4, 2],
    MG: [4, 4], ES: [4, 5], SE: [4, 6], SP: [5, 3], RJ: [5, 4], PR: [6, 3], SC: [7, 3], RS: [8, 3] };
  function mapaUF(b, dados) {
    const dim = b.dimensoes[0], m0 = b.metricas[0];
    const por = {}; dados.linhas.forEach(l => { por[l[dim]] = l; });
    const vals = dados.linhas.map(l => l[m0]).filter(v => v !== null);
    const max = Math.max(...vals, 0), min = Math.min(...vals, max);
    const grade = el('div', { classe: 'mapa', role: 'img', 'aria-label': 'Mapa do Brasil por UF: ' + b.titulo });
    for (let r = 0; r < 9; r++) for (let c = 0; c < 7; c++) {
      const uf = Object.keys(GRADE_UF).find(k => GRADE_UF[k][0] === r && GRADE_UF[k][1] === c);
      if (!uf) { grade.appendChild(el('div')); continue; }
      const l = por[uf];
      const cel = el('div', { classe: 'uf' + (l ? '' : ' vazia'), title: uf + (l ? ': ' + fmt(l[m0], m0) : ': sem dados') },
        [el('b', { texto: uf }), l ? el('span', { texto: fmtEixo(l[m0], m0) }) : null]);
      if (l) {
        const t = max > min ? (l[m0] - min) / (max - min) : 1;
        cel.style.background = 'color-mix(in srgb, var(--primary) ' + Math.round(18 + t * 82) + '%, var(--card))';
        cel.style.color = t > 0.45 ? 'var(--primary-foreground)' : 'var(--card-foreground)';
      }
      grade.appendChild(cel);
    }
    const leg = el('div', { classe: 'legenda' }, [el('span', { texto: 'menor: ' + fmt(min, m0) }), el('span', { texto: 'maior: ' + fmt(max, m0) })]);
    return el('div', {}, [grade, leg]);
  }
  function definicoes(b) {
    return el('details', {}, [el('summary', { texto: 'Como calculamos' }), el('ul', { classe: 'definicoes' },
      b.metricas.map(m => el('li', {}, [el('b', { texto: D.metricas[m].descricao + ': ' }), el('span', { texto: D.metricas[m].definicao })])))]);
  }
  const COMGRAFICO = ['linha_tempo', 'barras_ranking', 'barras_agrupadas', 'area_empilhada', 'rosca', 'cascata', 'funil', 'mapa_calor'];
  function desenharBloco(b) {
    const dados = dadosDo(b);
    const corpo = b._corpo; corpo.replaceChildren();
    if (!dados.linhas.length && !dados.total) {
      if (b._achado) b._achado.hidden = true;
      corpo.appendChild(el('p', { classe: 'sem-grafico', texto: 'Nenhum dado com estes filtros. Mude ou limpe os filtros acima.' }));
      return;
    }
    if (b._achado) { b._achado.hidden = false; b._achado.textContent = preencher(b.achado || '', b, dados); }
    if (b._titulo) b._titulo.textContent = preencher(b.titulo, b, dados);
    if (b.tipo === 'numero_destaque') {
      const l = dados.linhas[0] || {}, m = b.metricas[0];
      corpo.appendChild(el('div', { classe: 'destaque' }, [el('div', { classe: 'valor-grande', texto: fmt(l[m], m) }), b.comparacao_periodo ? deltaEl(l, m, b) : null]));
    } else if (b.tipo === 'faixa_kpis') {
      const l = dados.linhas[0] || {};
      corpo.appendChild(el('div', { classe: 'kpis' }, b.metricas.map(m => el('div', { classe: 'kpi' },
        [el('span', { classe: 'rotulo', texto: D.metricas[m].descricao }), el('span', { classe: 'valor', texto: fmt(l[m], m) }), b.comparacao_periodo ? deltaEl(l, m, b) : null]))));
    } else if (b.tipo === 'tabela') {
      corpo.appendChild(tabelaNumeros(b, dados));
    } else if (b.tipo === 'mapa_uf') {
      corpo.appendChild(mapaUF(b, dados));
      corpo.appendChild(el('details', {}, [el('summary', { texto: 'Ver os números' }), tabelaNumeros(b, dados)]));
    } else if (COMGRAFICO.includes(b.tipo)) {
      const alvo = el('div', { classe: 'grafico', role: 'img', 'aria-label': b.titulo });
      corpo.appendChild(alvo);
      const numeros = el('details', {}, [el('summary', { texto: 'Ver os números' }), tabelaNumeros(b, dados)]);
      corpo.appendChild(numeros);
      if (temEcharts) {
        const g = echarts.init(alvo, null, { renderer: 'svg' });
        g.setOption(opcaoGrafico(b, dados));
        graficos.push(g);
      } else {
        alvo.replaceWith(el('p', { classe: 'sem-grafico', texto: 'O gráfico precisa de internet para carregar. Os números estão na tabela abaixo.' }));
        numeros.open = true;
      }
    }
  }
  function desenharTudo() {
    graficos.splice(0).forEach(g => g.dispose());
    D.blocos.forEach(desenharBloco);
  }
  function montar() {
    const grade = document.getElementById('grade');
    D.blocos.forEach(b => {
      const sec = el('section', { classe: 'bloco', 'data-tipo': b.tipo, 'data-largura': b._largura, 'aria-labelledby': 'tit-' + b.id });
      b._titulo = el('h2', { id: 'tit-' + b.id });
      sec.appendChild(b._titulo);
      if (b.subtitulo) sec.appendChild(el('p', { classe: 'sub', texto: b.subtitulo }));
      if (b.achado) { b._achado = el('p', { classe: 'achado' }); sec.appendChild(b._achado); }
      b._corpo = el('div', { classe: 'corpo' });
      sec.appendChild(b._corpo);
      sec.appendChild(definicoes(b));
      grade.appendChild(sec);
    });
    const caixa = document.getElementById('filtros');
    if (!D.filtros.length) { caixa.hidden = true; } else {
      D.filtros.forEach(f => {
        const sel = el('select', { id: 'filtro-' + f.dimensao }, [el('option', { value: TODOS, texto: 'Todos' })]
          .concat(f.opcoes.map(v => el('option', { value: v, texto: rotuloDim(f.dimensao, v) }))));
        sel.addEventListener('change', () => { estado[f.dimensao] = sel.value; desenharTudo(); });
        caixa.appendChild(el('label', { for: 'filtro-' + f.dimensao }, [document.createTextNode(f.rotulo), sel]));
      });
      const limpar = el('button', { classe: 'limpar', type: 'button', texto: 'Limpar filtros' });
      limpar.addEventListener('click', () => { D.filtros.forEach(f => { estado[f.dimensao] = TODOS; document.getElementById('filtro-' + f.dimensao).value = TODOS; }); desenharTudo(); });
      caixa.appendChild(limpar);
    }
    desenharTudo();
    let espera;
    window.addEventListener('resize', () => { clearTimeout(espera); espera = setTimeout(() => graficos.forEach(g => g.resize()), 120); });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', desenharTudo);
    new MutationObserver(desenharTudo).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }
  montar();
})();
"""

LARGURA_PADRAO = {"duas_colunas": "metade", "tres_colunas": "um_terco", "faixas": "inteira", "denso": "um_terco"}


def _largura(layout: str, bloco: dict, indice: int) -> str:
    if bloco.get("largura"):
        return bloco["largura"]
    if bloco["tipo"] in ("tabela", "linha_tempo", "area_empilhada", "mapa_calor") and layout != "denso":
        return "inteira"
    if layout == "assimetrico":
        return "dois_tercos" if indice % 2 == 0 else "um_terco"
    if layout == "mapa_em_destaque":
        return "dois_tercos" if bloco["tipo"] == "mapa_uf" else "um_terco"
    return LARGURA_PADRAO.get(layout, "metade")


def _link_fontes(tipografia: dict) -> str:
    familias = []
    for f in dict.fromkeys([tipografia.get("sans"), tipografia.get("titulo"), tipografia.get("mono")]):
        if f and f.lower() not in FONTES_DO_SISTEMA:
            familias.append("family=" + f.replace(" ", "+") + ":wght@400;500;600;700")
    if not familias:
        return ""
    return (f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{"&amp;".join(familias)}&amp;display=swap">')


def _json_seguro(dados) -> str:
    return json.dumps(dados, ensure_ascii=False, separators=(",", ":"), default=str).replace("</", "<\\/")


def fragmento(montado: dict) -> str:
    """O conteúdo da página, sem <html>/<head>/<body>: é o que a ferramenta Artifact publica."""
    from .design import css as css_tokens

    spec, tokens = montado["spec"], montado["tokens"]
    for i, b in enumerate(montado["blocos"]):
        b["_largura"] = _largura(spec["layout"], b, i)
        b.pop("sql", None)
    dados = {k: v for k, v in montado.items() if k != "tokens"}
    e = html.escape
    dominio = DOMINIOS.get((spec.get("estilo") or {}).get("dominio") or "outro", "Painel")
    origem = montado["origem"]
    chip_origem = ('<span class="chip positivo">Análise revisada antes do painel</span>' if origem == "analise" else
                   '<span class="chip alerta">Sem análise prévia</span>' if origem == "planilha_direta" else
                   '<span class="chip">Convertido de Power BI</span>')
    pergunta = (f'<p class="pergunta"><b>Pergunta:</b> {e(spec["pergunta_negocio"])}'
                + (f' <span class="subtitulo">· para {e(spec["publico"])}</span>' if spec.get("publico") else "") + "</p>")
    avisos = "".join(f"<li>{e(a)}</li>" for a in montado["avisos"])
    fonte = montado["fonte"]
    sha = (fonte.get("sha256") or "")[:12]
    return f"""<title>{e(spec["titulo"])}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="{e(spec.get("subtitulo") or spec["pergunta_negocio"])}">
{_link_fontes(tokens["tipografia"])}
<style>
{css_tokens(tokens)}{CSS}
</style>
<div class="pagina">
  <header class="topo">
    <div class="olho"><span>{e(dominio)}</span><span class="chip">{e(montado["periodo"]["rotulo"])}</span>{chip_origem}</div>
    <h1>{e(spec["titulo"])}</h1>
    {f'<p class="subtitulo">{e(spec["subtitulo"])}</p>' if spec.get("subtitulo") else ""}
    {pergunta}
  </header>
  <div class="filtros" id="filtros" role="group" aria-label="Filtros"></div>
  <main class="grade" id="grade"></main>
  <footer class="rodape">
    <h2>Sobre os números</h2>
    <p>Todos os valores vêm da camada de métricas do bi-html, calculados a partir de <code>{e(fonte["arquivo"])}</code>{f' (sha256 <code>{e(sha)}</code>…)' if sha else ""}. Cada bloco mostra como a métrica é calculada em "Como calculamos".</p>
    {f'<p>{e(spec["notas"])}</p>' if spec.get("notas") else ""}
    {f'<ul>{avisos}</ul>' if avisos else ""}
    <p>Gerado em <span id="gerado-em">{e(montado["gerado_em"][:10])}</span> pelo bi-html.</p>
  </footer>
</div>
<script type="application/json" id="dados-bi">{_json_seguro(dados)}</script>
<script src="{ECHARTS}"></script>
<script>{JS}</script>
"""


def documento(frag: str) -> str:
    return ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + frag + '</body>\n</html>\n')


def bloqueio_de_publicacao(projeto: Path) -> list[str]:
    """Motivos para não publicar: dados pessoais apontados pelo perfil de alguma tabela usada."""
    from .ingestao import ler_manifesto

    motivos = []
    for nome, t in ler_manifesto(projeto)["tabelas"].items():
        caminho = projeto / t.get("qualidade", "")
        if t.get("qualidade") and caminho.is_file():
            rel = json.loads(caminho.read_text(encoding="utf-8"))
            if rel.get("dados_pessoais"):
                cols = ", ".join(d["coluna"] for d in rel["dados_pessoais"])
                motivos.append(f"a tabela {nome} tem dados pessoais ({cols})")
    pbix = ler_manifesto(projeto).get("pbix") or {}
    if pbix.get("dados_pessoais"):
        cols = ", ".join(d["coluna"] for d in pbix["dados_pessoais"])
        motivos.append(f"o .pbix convertido tem dados pessoais ({cols})")
    return motivos


def renderizar(projeto: Path, arquivo_spec: Path | None = None, destino: Path | None = None) -> dict:
    """Renderiza dashboard/spec.json em saidas/bi/dashboard.html (e a versão para Artifact).
    Com `arquivo_spec` e `destino` (sem extensão, relativo ao projeto), renderiza outra spec,
    como cada página de um .pbix convertido."""
    from .dashboard import ARQUIVO_SPEC

    projeto = Path(projeto)
    montado = montar(projeto, Path(arquivo_spec or ARQUIVO_SPEC))
    frag = fragmento(montado)
    base = Path(destino) if destino else SAIDA / "dashboard"
    pasta = projeto / base.parent
    pasta.mkdir(parents=True, exist_ok=True)
    artifact, html_ = base.with_name(base.name + ".artifact.html"), base.with_name(base.name + ".html")
    (projeto / artifact).write_text(frag, encoding="utf-8")
    completo = documento(frag)
    (projeto / html_).write_text(completo, encoding="utf-8")
    tamanho = len(completo.encode("utf-8"))
    return {"html": str(html_), "artifact": str(artifact),
            "titulo": montado["spec"]["titulo"], "bytes": tamanho, "dentro_da_meta": tamanho <= META_BYTES,
            "blocos": len(montado["blocos"]), "avisos": montado["avisos"],
            "publicacao_bloqueada": bloqueio_de_publicacao(projeto)}
