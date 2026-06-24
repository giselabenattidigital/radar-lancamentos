#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Lançamentos — gerador automático da página.

Busca novidades/lançamentos do setor (saudáveis, granel, fitness) no Brasil
usando o feed RSS do Google Notícias (gratuito, sem chave de API) e gera um
arquivo index.html pronto para publicar no GitHub Pages.

Roda 100% sozinho na nuvem (GitHub Actions). Sem dependências pagas.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import html
import re
from datetime import datetime, timezone, timedelta

# ----------------------------------------------------------------------------
# CONFIGURAÇÃO — é só editar aqui se quiser mudar categorias ou buscas
# ----------------------------------------------------------------------------

# Quantos dias para trás contam como "novidade"
JANELA_DIAS = 30
# Máximo de itens exibidos por categoria
MAX_POR_CATEGORIA = 6

# Cada categoria tem uma cor (classe CSS) e uma lista de buscas no Google Notícias.
CATEGORIAS = [
    {
        "nome": "Sem glúten / sem açúcar",
        "classe": "glu",
        "buscas": [
            "lançamento produto sem glúten",
            "lançamento produto sem açúcar",
            "novo produto zero açúcar Brasil",
        ],
    },
    {
        "nome": "Suplementos / fitness",
        "classe": "sup",
        "buscas": [
            "lançamento suplemento whey proteína Brasil",
            "novo suplemento fitness lançamento",
            "lançamento barra proteína pré-treino Brasil",
        ],
    },
    {
        "nome": "Funcionais / naturais",
        "classe": "fun",
        "buscas": [
            "lançamento produto natural funcional Brasil",
            "lançamento superalimento alimento saudável Brasil",
        ],
    },
    {
        "nome": "Granel",
        "classe": "gra",
        "buscas": [
            "produto a granel novidade Brasil",
            "loja produtos naturais granel lançamento Brasil",
        ],
    },
]

# Palavras que indicam que é realmente um lançamento/novidade (dá prioridade)
PALAVRAS_BOAS = [
    "lança", "lançamento", "lançou", "novo", "nova", "novidade",
    "estreia", "chega ao mercado", "apresenta", "inova",
]
# Palavras de ruído que geralmente NÃO são lançamento (descarta)
PALAVRAS_RUIM = [
    "receita", "como fazer", "benefícios de", "vale a pena",
    "ranking", "melhores", "passo a passo",
]

GNEWS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
TZ_BR = timezone(timedelta(hours=-3))


def buscar(query):
    url = GNEWS.format(q=urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
    except Exception as e:
        print(f"  ! falha na busca '{query}': {e}")
        return []
    itens = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    for item in root.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        fonte_el = item.find("{http://www.w3.org/2005/Atom}source")
        if fonte_el is None:
            fonte_el = item.find("source")
        fonte = fonte_el.text.strip() if fonte_el is not None and fonte_el.text else ""
        pub = item.findtext("pubDate") or ""
        dt = parse_data(pub)
        if not titulo or not link:
            continue
        itens.append({"titulo": titulo, "link": link, "fonte": fonte, "dt": dt})
    return itens


def parse_data(s):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def pontuar(item):
    t = item["titulo"].lower()
    score = 0
    for p in PALAVRAS_BOAS:
        if p in t:
            score += 2
    for p in PALAVRAS_RUIM:
        if p in t:
            score -= 3
    if item["dt"]:
        dias = (datetime.now(timezone.utc) - item["dt"]).days
        if dias <= JANELA_DIAS:
            score += max(0, (JANELA_DIAS - dias) / 6)
        else:
            score -= 4
    return score


def coletar_categoria(cat):
    vistos = set()
    todos = []
    for q in cat["buscas"]:
        for it in buscar(q):
            chave = re.sub(r"\W+", "", it["titulo"].lower())[:60]
            if chave in vistos:
                continue
            vistos.add(chave)
            it["score"] = pontuar(it)
            todos.append(it)
    bons = [i for i in todos if i["score"] > 0]
    bons.sort(key=lambda x: x["score"], reverse=True)
    return bons[:MAX_POR_CATEGORIA]


def fmt_data_item(it):
    if not it["dt"]:
        return ""
    return it["dt"].astimezone(TZ_BR).strftime("%d/%m/%Y")


def limpar_titulo(t, fonte):
    # Google costuma anexar " - Fonte" no fim do título
    if fonte and t.endswith(" - " + fonte):
        t = t[: -(len(fonte) + 3)]
    return t.strip()


def card_html(it):
    titulo = html.escape(limpar_titulo(it["titulo"], it["fonte"]))
    fonte = html.escape(it["fonte"]) if it["fonte"] else "Fonte"
    data = fmt_data_item(it)
    data_html = f'<span class="data">{data}</span>' if data else ""
    return f"""      <div class="card">
        <div class="brand">{fonte} {data_html}</div>
        <h3>{titulo}</h3>
        <a href="{html.escape(it['link'])}" target="_blank" rel="noopener">Ler novidade →</a>
      </div>"""


def card_vazio():
    return """      <div class="card vazio">
        <h3>Sem lançamentos novos hoje nesta categoria</h3>
        <p>Nenhuma novidade relevante encontrada na última varredura. O radar volta a checar amanhã de manhã.</p>
      </div>"""


def gerar():
    hoje = datetime.now(TZ_BR)
    data_extenso = hoje.strftime("%d/%m/%Y às %H:%M")
    secoes = []
    total = 0
    for cat in CATEGORIAS:
        print(f"Buscando: {cat['nome']}")
        itens = coletar_categoria(cat)
        total += len(itens)
        cards = "\n".join(card_html(i) for i in itens) if itens else card_vazio()
        secoes.append(f"""  <div class="section">
    <h2><span class="tag {cat['classe']}">{html.escape(cat['nome'])}</span></h2>
    <div class="grid">
{cards}
    </div>
  </div>""")
    corpo = "\n\n".join(secoes)
    pagina = TEMPLATE.format(data=data_extenso, total=total, secoes=corpo)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(pagina)
    print(f"\nOK — index.html gerado com {total} novidades.")


TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radar de Lançamentos — Saudáveis, Granel & Fitness</title>
<style>
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #f6f7f4; color: #1f2421; line-height: 1.5; padding: 24px 18px 60px; }}
.wrap {{ max-width: 820px; margin: 0 auto; }}
.kicker {{ font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: #6b8e23; font-weight: 700; }}
h1 {{ font-size: 27px; font-weight: 800; margin: 4px 0 6px; letter-spacing: -.02em; }}
.sub {{ color: #586159; font-size: 14px; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; margin: 16px 0 22px;
  padding: 12px 14px; background: #fff; border: 1px solid #e6e9e2; border-radius: 12px; font-size: 13px; color: #586159; }}
.meta b {{ color: #1f2421; }}
.dot {{ width: 8px; height: 8px; border-radius: 50%; background: #6b8e23; display: inline-block; margin-right: 6px; }}
.section {{ margin: 26px 0 8px; }}
.section h2 {{ font-size: 17px; font-weight: 800; }}
.tag {{ font-size: 11px; font-weight: 700; color: #fff; background: #6b8e23; border-radius: 999px; padding: 3px 11px; }}
.tag.glu {{ background: #c0792e; }} .tag.sup {{ background: #2e6fc0; }}
.tag.fun {{ background: #7a4ec0; }} .tag.gra {{ background: #3f9d6b; }}
.grid {{ display: grid; gap: 12px; margin-top: 12px; }}
.card {{ background: #fff; border: 1px solid #e6e9e2; border-radius: 12px; padding: 14px 16px; }}
.card.vazio {{ background: #fafbf8; border-style: dashed; }}
.card .brand {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #6b8e23; }}
.card .data {{ color: #9aa196; font-weight: 600; margin-left: 6px; }}
.card h3 {{ font-size: 15.5px; font-weight: 700; margin: 3px 0 5px; }}
.card p {{ font-size: 13.5px; color: #4a534b; }}
.card a {{ display: inline-block; margin-top: 8px; font-size: 12.5px; color: #2e6fc0; text-decoration: none; font-weight: 600; }}
.card a:hover {{ text-decoration: underline; }}
.note {{ margin-top: 30px; padding: 14px 16px; background: #eef3e6; border: 1px solid #d8e3c6;
  border-radius: 12px; font-size: 13px; color: #46512f; }}
footer {{ margin-top: 34px; text-align: center; font-size: 12px; color: #9aa196; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="kicker">Radar de Lançamentos</div>
  <h1>Tudo que está sendo lançado no setor</h1>
  <div class="sub">Granel · Sem glúten & sem açúcar · Suplementos & fitness · Funcionais e naturais — mercado Brasil</div>

  <div class="meta">
    <span><span class="dot"></span><b>Atualização automática</b> todo dia de manhã</span>
    <span>Última varredura: <b>{data}</b></span>
    <span><b>{total}</b> novidades nesta edição</span>
  </div>

{secoes}

  <div class="note">
    💡 Esta página é atualizada sozinha toda manhã por um robô que varre as notícias do setor.
    Basta abrir e dar uma passada de olho — sem caçar nada.
  </div>

  <footer>Radar de Lançamentos · atualizado automaticamente</footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    gerar()
