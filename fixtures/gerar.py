#!/usr/bin/env python3
"""
gerar.py — gera os conjuntos de dados fictícios do bi-html (determinístico, semente fixa).

    uv run --no-project --python 3.12 --with openpyxl fixtures/gerar.py

Todos os dados são inventados: empresas, lojas, pessoas, CPFs, e-mails e
telefones não correspondem a ninguém. Rodar de novo produz os mesmos arquivos.

Cada arquivo exercita um caso que a ingestão precisa tratar:
- vendas.csv        separador ';', vírgula decimal, datas dd/mm/aaaa, região ausente em ~1%
- marketing.xlsx    planilha Excel com datas nativas e uma aba de dicionário
- financeiro.csv    separador ',', ponto decimal, competência aaaa-mm, realizado vs. orçado
- clientes_ficticios.csv   CPF, e-mail e telefone fictícios: o perfil deve sinalizar dados pessoais
- malformado.csv    linhas com número de colunas diferente e um byte inválido em UTF-8
"""
import csv, random
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SEMENTE = 20261117


def br(valor, casas=2):
    """1234.5 → '1234,50' (vírgula decimal, sem separador de milhar, como sai de muitos ERPs)."""
    return f"{valor:.{casas}f}".replace(".", ",")


def dias(inicio, fim):
    d = inicio
    while d <= fim:
        yield d
        d += timedelta(days=1)


def sazonalidade(d):
    """Peso do dia: fim de semana mais fraco, novembro e dezembro mais fortes."""
    peso = 0.8 if d.weekday() >= 5 else 1.0
    return peso * {11: 1.45, 12: 1.7}.get(d.month, 1.0)


# ---------------------------------------------------------------- vendas

LOJAS = [
    ("SP", "Sudeste", "Loja Paulista"), ("SP", "Sudeste", "Loja Campinas"),
    ("RJ", "Sudeste", "Loja Botafogo"), ("MG", "Sudeste", "Loja Savassi"),
    ("PR", "Sul", "Loja Batel"), ("RS", "Sul", "Loja Moinhos"),
    ("SC", "Sul", "Loja Trindade"), ("BA", "Nordeste", "Loja Pituba"),
    ("PE", "Nordeste", "Loja Boa Viagem"), ("CE", "Nordeste", "Loja Aldeota"),
    ("DF", "Centro-Oeste", "Loja Asa Sul"), ("GO", "Centro-Oeste", "Loja Setor Bueno"),
    ("PA", "Norte", "Loja Umarizal"), ("AM", "Norte", "Loja Adrianópolis"),
]
PESO_LOJA = [16, 8, 10, 7, 6, 6, 4, 6, 5, 4, 6, 4, 3, 3]
CATEGORIAS = {
    "Vestuário": [("Camiseta básica", 59.9), ("Calça jeans", 189.9), ("Jaqueta leve", 249.9), ("Vestido midi", 219.9)],
    "Calçados": [("Tênis de corrida", 349.9), ("Sandália", 129.9), ("Bota cano curto", 299.9)],
    "Acessórios": [("Boné", 69.9), ("Mochila", 179.9), ("Cinto de couro", 99.9)],
    "Casa": [("Jogo de toalhas", 139.9), ("Manta", 159.9)],
}
CANAIS_VENDA = [("Loja física", 55), ("Site", 30), ("App", 15)]


def gerar_vendas(rng):
    linhas, n = [], 0
    for d in dias(date(2025, 1, 1), date(2025, 12, 31)):
        for _ in range(int(rng.gauss(44, 6) * sazonalidade(d))):
            n += 1
            uf, regiao, loja = rng.choices(LOJAS, PESO_LOJA)[0]
            canal = rng.choices([c for c, _ in CANAIS_VENDA], [p for _, p in CANAIS_VENDA])[0]
            if canal != "Loja física":
                loja = "Centro de distribuição"
            categoria = rng.choices(list(CATEGORIAS), [45, 25, 20, 10])[0]
            produto, preco = rng.choice(CATEGORIAS[categoria])
            qtd = rng.choices([1, 2, 3, 4], [70, 20, 7, 3])[0]
            desc = rng.choices([0, 5, 10, 15, 20], [60, 15, 12, 8, 5])[0]
            if d.month == 11 and d.day >= 24:
                desc = max(desc, 20)
            receita = qtd * preco * (1 - desc / 100)
            if rng.random() < 0.01:
                uf, regiao = "", ""
            linhas.append([d.strftime("%d/%m/%Y"), f"P{n:06d}", uf, regiao, loja, canal,
                           categoria, produto, qtd, br(preco), desc, br(receita)])
    with open(AQUI / "vendas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["data_pedido", "pedido_id", "uf", "regiao", "loja", "canal", "categoria",
                    "produto", "quantidade", "preco_unitario", "desconto_pct", "receita"])
        w.writerows(linhas)
    return len(linhas)


# ---------------------------------------------------------------- marketing

CAMPANHAS = {
    "Busca paga": [("Marca", 0.09, 0.80, 0.060), ("Genérica", 0.04, 1.90, 0.025), ("Remarketing de busca", 0.07, 1.10, 0.050)],
    "Social pago": [("Prospecção", 0.011, 0.95, 0.012), ("Remarketing social", 0.018, 0.70, 0.030)],
    "Display": [("Alcance", 0.003, 0.60, 0.006), ("Catálogo dinâmico", 0.006, 0.85, 0.015)],
    "E-mail": [("Newsletter", 0.035, 0.0, 0.020), ("Carrinho abandonado", 0.090, 0.0, 0.080)],
}
IMPRESSOES_BASE = {"Busca paga": 9000, "Social pago": 60000, "Display": 120000, "E-mail": 15000}


def gerar_marketing(rng):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "campanhas"
    ws.append(["data", "canal", "campanha", "impressoes", "cliques", "investimento",
               "conversoes", "receita_atribuida"])
    n = 0
    for d in dias(date(2025, 1, 1), date(2025, 12, 31)):
        s = sazonalidade(d)
        for canal, campanhas in CAMPANHAS.items():
            for nome, ctr, cpc, taxa_conv in campanhas:
                imp = int(IMPRESSOES_BASE[canal] * s * rng.uniform(0.7, 1.3) / len(campanhas))
                cliques = int(imp * ctr * rng.uniform(0.8, 1.2))
                invest = round(cliques * cpc * rng.uniform(0.9, 1.1), 2) if cpc else round(rng.uniform(15, 40), 2)
                conv = int(cliques * taxa_conv * rng.uniform(0.7, 1.3))
                receita = round(conv * rng.uniform(140, 260), 2)
                ws.append([d, canal, nome, imp, cliques, invest, conv, receita])
                ws.cell(row=ws.max_row, column=1).number_format = "DD/MM/YYYY"
                n += 1
    dic = wb.create_sheet("dicionario")
    dic.append(["coluna", "significado"])
    for linha in [
        ("data", "dia da veiculação"), ("canal", "canal de mídia"), ("campanha", "nome da campanha"),
        ("impressoes", "vezes em que o anúncio apareceu"), ("cliques", "cliques no anúncio"),
        ("investimento", "valor gasto no dia, em reais"), ("conversoes", "pedidos atribuídos à campanha"),
        ("receita_atribuida", "receita dos pedidos atribuídos, em reais"),
    ]:
        dic.append(list(linha))
    wb.save(AQUI / "marketing.xlsx")
    return n


# ---------------------------------------------------------------- financeiro

CONTAS = [
    ("Receita bruta", "Receita", "Comercial", 2_100_000, 1),
    ("Devoluções e cancelamentos", "Deduções", "Comercial", 70_000, -1),
    ("Impostos sobre vendas", "Deduções", "Comercial", 230_000, -1),
    ("Custo das mercadorias vendidas", "Custos", "Operações", 880_000, -1),
    ("Frete de entrega", "Custos", "Operações", 95_000, -1),
    ("Salários e encargos", "Despesas operacionais", "Administrativo", 310_000, -1),
    ("Aluguel e condomínio", "Despesas operacionais", "Administrativo", 120_000, -1),
    ("Marketing e mídia", "Despesas operacionais", "Comercial", 140_000, -1),
    ("Tecnologia", "Despesas operacionais", "Administrativo", 45_000, -1),
    ("Comissões de venda", "Despesas operacionais", "Comercial", 63_000, -1),
    ("Depreciação", "Depreciação e amortização", "Administrativo", 38_000, -1),
    ("Receitas financeiras", "Resultado financeiro", "Administrativo", 9_000, 1),
    ("Despesas financeiras", "Resultado financeiro", "Administrativo", 26_000, -1),
]


def gerar_financeiro(rng):
    linhas = []
    for ano in (2024, 2025):
        for mes in range(1, 13):
            s = {11: 1.35, 12: 1.6}.get(mes, 1.0) * (1.0 if ano == 2024 else 1.12)
            for conta, grupo, centro, base, sinal in CONTAS:
                fixo = grupo in ("Despesas operacionais", "Depreciação e amortização") and conta not in (
                    "Marketing e mídia", "Comissões de venda")
                orcado = base * (1.0 if fixo else s) * (1.0 if ano == 2024 else 1.08)
                realizado = orcado * rng.uniform(0.9, 1.1)
                for cenario, valor in (("Orçado", orcado), ("Realizado", realizado)):
                    linhas.append([f"{ano}-{mes:02d}", conta, grupo, centro, cenario, f"{sinal * valor:.2f}"])
    with open(AQUI / "financeiro.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["competencia", "conta", "grupo", "centro_custo", "cenario", "valor"])
        w.writerows(linhas)
    return len(linhas)


# ---------------------------------------------------------------- dados pessoais fictícios

def cpf_ficticio(rng):
    """CPF com dígitos verificadores corretos e base aleatória: formato realista, pessoa inexistente."""
    base = [rng.randint(0, 9) for _ in range(9)]
    for pesos in (range(10, 1, -1), range(11, 1, -1)):
        resto = sum(d * p for d, p in zip(base, pesos)) % 11
        base.append(0 if resto < 2 else 11 - resto)
    s = "".join(map(str, base))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def gerar_clientes(rng):
    ufs = [uf for uf, _, _ in LOJAS]
    with open(AQUI / "clientes_ficticios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["cliente_id", "nome", "cpf", "email", "telefone", "uf", "data_cadastro"])
        for i in range(1, 201):
            cadastro = date(2023, 1, 1) + timedelta(days=rng.randint(0, 1000))
            w.writerow([f"C{i:04d}", f"Cliente Fictício {i:04d}", cpf_ficticio(rng),
                        f"cliente{i:04d}@example.com", f"(11) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
                        rng.choice(ufs), cadastro.strftime("%d/%m/%Y")])
    return 200


def gerar_malformado():
    texto = (
        "data;loja;receita;observacao\n"
        "01/03/2025;Loja Paulista;1234,50;ok\n"
        "02/03/2025;Loja Batel;987,10\n"
        "03/03/2025;Loja Pituba;450,00;linha com coluna a mais;extra\n"
        "04/03/2025;Loja Savassi;12x,00;valor com letra\n"
    ).encode("utf-8") + "05/03/2025;Loja Aldeota;300,00;acentua\xe7\xe3o em latin-1\n".encode("latin-1")
    (AQUI / "malformado.csv").write_bytes(texto)
    return 5


if __name__ == "__main__":
    rng = random.Random(SEMENTE)
    print(f"vendas.csv: {gerar_vendas(rng)} linhas")
    print(f"marketing.xlsx: {gerar_marketing(rng)} linhas")
    print(f"financeiro.csv: {gerar_financeiro(rng)} linhas")
    print(f"clientes_ficticios.csv: {gerar_clientes(rng)} linhas")
    print(f"malformado.csv: {gerar_malformado()} linhas de dados")
