#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Radar de Lancamentos v3 - novidades do setor + Agenda de Feiras.
# Busca via RSS do Google Noticias. Roda no GitHub Actions.
import urllib.request, urllib.parse, html, re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date

JANELA_DIAS = 30
MAX_POR_CATEGORIA = 6

CATEGORIAS = [
    {"nome": "Sem gluten / sem acucar", "classe": "glu", "buscas": [
        "lancamento produto sem gluten", "lancamento alimento sem acucar",
        "novo produto zero acucar Brasil", "lancamento produto sem lactose"]},
    {"nome": "Suplementos / fitness", "classe": "sup", "buscas": [
        "lancamento suplemento whey proteina Brasil",
        "novo suplemento fitness lancamento Brasil",
        "lancamento barra de proteina pre-treino Brasil",
        "marca de suplementos lanca novo produto Brasil"]},
    {"nome": "Funcionais / naturais", "classe": "fun", "buscas": [
        "lancamento produto natural funcional Brasil",
        "lancamento superalimento saudavel Brasil",
        "marca natural lanca novo produto Brasil"]},
    {"nome": "Granel", "classe": "gra", "buscas": [
        "produto a granel novidade Brasil",
        "loja produtos naturais granel lancamento Brasil"]},
]

KW = {
    "glu": ["sem gluten", "zero acucar", "sem acucar", "sem lactose", "sem leite",
            "low carb", "diet", "celiac", "plant based"],
    "sup": ["whey", "protei", "protein", "suplement", "creatina", "bcaa", "pre-treino",
            "pre treino", "aminoacid", "colageno", "collagen", "nutrition", "isolado",
            "termogenic", "glutamina", "barrinha"],
    "fun": ["funcional", "superalimento", "super alimento", "probiotic", "kombucha",
            "matcha", "propolis", "adaptog", "fermentad", "cha ", "curcuma", "snack natural"],
    "gra": ["a granel", "granel", "cereal", "grao", "castanha", "amendoa", "amendoim",
            "farinha", "mix de", "emporio", "pinhao", "canjica", "semente"],
}

SINAL = ["lanca", "lancou", "lancam", "lancamento", "novo", "nova", "novidade",
         "estreia", "estreou", "apresenta", "apresentou", "chega ao mercado", "inova",
         "amplia", "reforca", "aposta", "investe", "expande", "anuncia", "inedit",
         "nova linha"]

RUIDO = ["receita", "como fazer", "beneficios", "vale a pena", "ranking", "melhores",
         "passo a passo", "dieta de", "preferid", "odei", "emagrec", "cristiano ronaldo",
         "famos", "celebridade", "horoscopo", "saiba por que", "veja como", "tendencia",
         "ganha espaco", "fenomeno", "o que e", "entenda", "lista de"]

# Agenda de feiras (curada). "fim" = ultimo dia (YYYY-MM-DD); feira passada some sozinha.
FEIRAS = [
    {"nome": "Fi South America (FiSA) 2026", "fim": "2026-08-06",
     "quando": "4 a 6 de agosto de 2026", "local": "Sao Paulo Expo, SP",
     "promessa": "Maior feira de ingredientes de alimentos e bebidas da America do Sul; "
                 "foco em saudaveis, naturais, plant-based, adocantes, proteinas e vitaminas."},
    {"nome": "Fitness Brasil Expo 2026", "fim": "2026-08-29",
     "quando": "27 a 29 de agosto de 2026", "local": "Sao Paulo, SP",
     "promessa": "Um dos maiores eventos fitness da America Latina: marcas, cursos tecnicos e gestao de negocios."},
    {"nome": "Arnold Sports Festival South America 2026", "fim": "2026-08-29",
     "quando": "27 a 29 de agosto de 2026", "local": "Transamerica Expo Center, SP",
     "promessa": "Festival multiesportivo com grande expo de suplementos e nutricao esportiva; palco de lancamentos de marca."},
    {"nome": "Connect Fitness Experience 2026", "fim": "2026-09-30",
     "quando": "Setembro de 2026", "local": "Fortaleza, CE",
     "promessa": "Experiencia fitness com foco no mercado do Nordeste."},
    {"nome": "NEEX Expo - Nutricao Esportiva 2026", "fim": "2026-10-31",
     "quando": "Outubro de 2026 (data a confirmar)", "local": "Expo Center Norte, SP",
     "promessa": "Encontro B2B dos maiores players de nutricao e suplementacao alimentar."},
    {"nome": "APAS Show 2027", "fim": "2027-05-31",
     "quando": "Maio de 2027", "local": "Expo Center Norte, SP",
     "promessa": "Maior feira supermercadista do mundo; saudabilidade, conveniencia e novidades de varejo."},
    {"nome": "Naturaltech / Bio Brazil Fair 2027", "fim": "2027-06-30",
     "quando": "Junho de 2027", "local": "Distrito Anhembi, SP",
     "promessa": "Maior feira de produtos naturais da America Latina; alimentos, saude e beleza."},
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
        print("  ! falha '" + query + "': " + str(e)); return []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        ti = (item.findtext("title") or "").strip()
        ln = (item.findtext("link") or "").strip()
        fe = item.find("{http://www.w3.org/2005/Atom}source") or item.find("source")
        fo = fe.text.strip() if fe is not None and fe.text else ""
        dt = parse_data(item.findtext("pubDate") or "")
        if ti and ln:
            out.append({"titulo": ti, "link": ln, "fonte": fo, "dt": dt})
    return out


def parse_data(s):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def e_relevante(it):
    t = it["titulo"].lower()
    if not it["dt"]:
        return False
    dias = (datetime.now(timezone.utc) - it["dt"]).days
    if dias < 0 or dias > JANELA_DIAS:
        return False
    if any(n in t for n in RUIDO):
        return False
    return any(s in t for s in SINAL)


def classificar(it, origem):
    t = it["titulo"].lower()
    best, ms = origem, 0
    for c, kws in KW.items():
        sc = sum(1 for k in kws if k in t)
        if sc > ms:
            ms, best = sc, c
    return best


def coletar():
    pool = {}
    for cat in CATEGORIAS:
        for q in cat["buscas"]:
            for it in buscar(q):
                ch = re.sub(r"\W+", "", it["titulo"].lower())[:70]
                if ch not in pool:
                    it["origem"] = cat["classe"]; pool[ch] = it
    return list(pool.values())


def feiras_html():
    hoje = datetime.now(TZ_BR).date()
    vig = [f for f in FEIRAS if date.fromisoformat(f["fim"]) >= hoje]
    vig.sort(key=lambda f: f["fim"])
    if not vig:
        return ""
    cards = ""
    for f in vig:
        cards += ('<div class="card"><div class="brand">' + html.escape(f["local"]) +
                  ' <span class="data">' + html.escape(f["quando"]) + "</span></div><h3>" +
                  html.escape(f["nome"]) + "</h3><p>" + html.escape(f["promessa"]) + "</p></div>")
    return ('<div class="section"><h2><span class="tag fei">Agenda de Feiras do Setor</span></h2>'
            '<div class="grid">' + cards + "</div></div>")


def card(it):
    ti = it["titulo"]
    if it["fonte"] and ti.endswith(" - " + it["fonte"]):
        ti = ti[:-(len(it["fonte"]) + 3)]
    ti = html.escape(ti.strip())
    fo = html.escape(it["fonte"]) if it["fonte"] else "Fonte"
    dt = it["dt"].astimezone(TZ_BR).strftime("%d/%m/%Y") if it["dt"] else ""
    dh = ('<span class="data">' + dt + "</span>") if dt else ""
    return ('<div class="card"><div class="brand">' + fo + " " + dh + "</div><h3>" + ti +
            '</h3><a href="' + html.escape(it["link"]) + '" target="_blank" rel="noopener">Ler novidade &rarr;</a></div>')


def gerar():
    quando = datetime.now(TZ_BR).strftime("%d/%m/%Y as %H:%M")
    porcat = {c["classe"]: [] for c in CATEGORIAS}
    for it in coletar():
        if e_relevante(it):
            porcat[classificar(it, it["origem"])].append(it)
    secoes, total = [], 0
    for cat in CATEGORIAS:
        itens = sorted(porcat[cat["classe"]], key=lambda x: x["dt"], reverse=True)[:MAX_POR_CATEGORIA]
        total += len(itens)
        if itens:
            cards = "".join(card(i) for i in itens)
        else:
            cards = ('<div class="card vazio"><h3>Sem lancamentos novos hoje</h3>'
                     "<p>Nenhuma novidade relevante nesta varredura. O radar checa de novo amanha.</p></div>")
        secoes.append('<div class="section"><h2><span class="tag ' + cat["classe"] + '">' +
                      html.escape(cat["nome"]) + '</span></h2><div class="grid">' + cards + "</div></div>")
        print(cat["nome"] + ": " + str(len(itens)))
    pagina = (TEMPLATE.replace("__DATA__", html.escape(quando))
              .replace("__TOTAL__", str(total))
              .replace("__FEIRAS__", feiras_html())
              .replace("__SECOES__", "".join(secoes)))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(pagina)
    print("OK - " + str(total) + " novidades.")


CSS = ("*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;"
       "background:#f6f7f4;color:#1f2421;line-height:1.5;padding:24px 18px 60px}.wrap{max-width:820px;margin:0 auto}"
       ".kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6b8e23;font-weight:700}"
       "h1{font-size:27px;font-weight:800;margin:4px 0 6px}.sub{color:#586159;font-size:14px}"
       ".meta{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;margin:16px 0 22px;padding:12px 14px;"
       "background:#fff;border:1px solid #e6e9e2;border-radius:12px;font-size:13px;color:#586159}.meta b{color:#1f2421}"
       ".dot{width:8px;height:8px;border-radius:50%;background:#6b8e23;display:inline-block;margin-right:6px}"
       ".section{margin:26px 0 8px}.section h2{font-size:17px;font-weight:800;margin-bottom:12px}"
       ".tag{font-size:11px;font-weight:700;color:#fff;border-radius:999px;padding:3px 11px}"
       ".tag.glu{background:#c0792e}.tag.sup{background:#2e6fc0}.tag.fun{background:#7a4ec0}.tag.gra{background:#3f9d6b}"
       ".tag.fei{background:#11707a}"
       ".grid{display:grid;gap:12px}.card{background:#fff;border:1px solid #e6e9e2;border-radius:12px;padding:14px 16px;margin-bottom:12px}"
       ".card.vazio{background:#fafbf8;border-style:dashed}"
       ".brand{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#6b8e23}"
       ".data{color:#9aa196;font-weight:600;margin-left:6px}.card h3{font-size:15.5px;font-weight:700;margin:3px 0 5px}"
       ".card p{font-size:13.5px;color:#4a534b}"
       ".card a{display:inline-block;margin-top:8px;font-size:12.5px;color:#2e6fc0;text-decoration:none;font-weight:600}"
       ".note{margin-top:30px;padding:14px 16px;background:#eef3e6;border:1px solid #d8e3c6;border-radius:12px;font-size:13px;color:#46512f}"
       "footer{margin-top:34px;text-align:center;font-size:12px;color:#9aa196}")

TEMPLATE = ('<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            "<title>Radar de Lancamentos</title><style>" + CSS + "</style></head><body><div class=\"wrap\">"
            '<div class="kicker">Radar de Lancamentos</div><h1>Tudo que esta sendo lancado no setor</h1>'
            '<div class="sub">Granel &middot; Sem gluten &amp; sem acucar &middot; Suplementos &amp; fitness '
            "&middot; Funcionais e naturais &middot; mercado Brasil</div>"
            '<div class="meta"><span><span class="dot"></span><b>Atualizacao automatica</b> todo dia de manha</span>'
            "<span>Ultima varredura: <b>__DATA__</b></span><span><b>__TOTAL__</b> novidades nesta edicao</span></div>"
            "__FEIRAS__"
            "__SECOES__"
            '<div class="note">Esta pagina e atualizada sozinha toda manha por um robo que varre as noticias do '
            "setor. Basta abrir e dar uma passada de olho.</div>"
            "<footer>Radar de Lancamentos - atualizado automaticamente</footer></div></body></html>")

if __name__ == "__main__":
    gerar()
