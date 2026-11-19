"""Resultado fiscal Abaixo da Linha - Governo Federal (BCB/SGS).

Fonte: Banco Central do Brasil, Sistema Gerenciador de Séries Temporais.
Unidade das séries: R$ milhões, fluxo mensal corrente.
Convenção BCB/NFSP: valores positivos indicam déficit/necessidade de financiamento;
valores negativos indicam superávit/capacidade de financiamento.

Este script NÃO estima receitas/despesas e NÃO reconstrói o resultado abaixo da
linha a partir da metodologia acima da linha. Ele consulta diretamente as séries
oficiais do BCB.
"""

from pathlib import Path
import pandas as pd
from bcb import sgs
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

console = Console()

# Séries mensais correntes do Governo Federal (R$ milhões)
SERIES_SGS = {
    "RESULTADO_PRIMARIO_ABAIXO": 4640,
    "JUROS_NOMINAIS_ABAIXO": 4607,
    "RESULTADO_NOMINAL_ABAIXO": 4574,
}

ROTULOS = {
    "RESULTADO_PRIMARIO_ABAIXO": "Resultado primário (abaixo da linha)",
    "JUROS_NOMINAIS_ABAIXO": "Juros nominais",
    "RESULTADO_NOMINAL_ABAIXO": "Resultado nominal",
}


def obter_dados_abaixo_da_linha(inicio="2024-01-01", fim=None):
    """Consulta as séries oficiais do BCB e retorna a base em formato longo."""
    console.print("[cyan]Consultando as séries fiscais do BCB/SGS...[/cyan]")

    # Uma chamada para obter as três séries, evitando consultas separadas.
    dados = sgs.get(SERIES_SGS, start=inicio, end=fim)

    if dados is None or dados.empty:
        raise RuntimeError("O BCB/SGS não retornou dados para o período solicitado.")

    dados.index = pd.to_datetime(dados.index)
    dados.index = dados.index.to_period("M").to_timestamp("M")
    dados.index.name = "periodo"

    # Mantém somente as séries efetivamente retornadas pela API.
    colunas = [c for c in SERIES_SGS if c in dados.columns]
    ausentes = sorted(set(SERIES_SGS) - set(colunas))
    if ausentes:
        raise ValueError(f"Séries não retornadas pelo BCB: {ausentes}")

    longo = (
        dados[colunas]
        .sort_index()
        .reset_index()
        .melt(
            id_vars="periodo",
            var_name="indicador",
            value_name="valor",
        )
        .dropna(subset=["valor"])
    )
    longo["valor"] = pd.to_numeric(longo["valor"], errors="coerce")
    longo = longo.dropna(subset=["valor"])
    longo["periodo_str"] = longo["periodo"].dt.strftime("%Y%m%d")
    longo["fonte"] = "Banco Central do Brasil - SGS"
    longo["codigo_sgs"] = longo["indicador"].map(SERIES_SGS)

    return longo[["periodo", "periodo_str", "indicador", "valor", "codigo_sgs", "fonte"]]


def gerar_tabelas_acumuladas(df_base):
    """Gera acumulado no ano (YTD) e acumulado móvel de 12 meses (12M)."""
    largo = df_base.pivot(index="periodo", columns="indicador", values="valor").sort_index()

    # Fluxos mensais: soma desde janeiro para o acumulado no ano.
    ytd = largo.groupby(largo.index.year).cumsum()

    # Fluxos mensais: soma dos últimos 12 meses completos.
    doze_meses = largo.rolling(window=12, min_periods=12).sum()

    def para_longo(df, tipo):
        resultado = (
            df.rename_axis(index="periodo", columns="indicador")
            .reset_index()
            .melt(id_vars="periodo", var_name="indicador", value_name="valor")
            .dropna(subset=["valor"])
        )
        resultado["periodo_str"] = resultado["periodo"].dt.strftime("%Y%m%d")
        resultado["tipo_acumulacao"] = tipo
        resultado["fonte"] = "Banco Central do Brasil - SGS"
        resultado["codigo_sgs"] = resultado["indicador"].map(SERIES_SGS)
        return resultado[["periodo", "periodo_str", "indicador", "valor", "tipo_acumulacao", "codigo_sgs", "fonte"]]

    return para_longo(ytd, "Acumulado no ano"), para_longo(doze_meses, "Acumulado em 12 meses")


def montar_tabela_resumo(df_base, df_ytd, df_12m, quantidade_meses=4):
    """Monta uma visão comparativa: mesmo mês do ano anterior, meses recentes,
    acumulado no ano e acumulado em 12 meses.
    """
    mensal = df_base.pivot(index="indicador", columns="periodo", values="valor")
    acumulado_ano = df_ytd.pivot(index="indicador", columns="periodo", values="valor")
    acumulado_12m = df_12m.pivot(index="indicador", columns="periodo", values="valor")

    datas = sorted(pd.to_datetime(df_base["periodo"].unique()))
    if not datas:
        raise ValueError("Não há períodos disponíveis para montar a tabela.")

    ultima_data = pd.Timestamp(datas[-1])
    data_comparavel = ultima_data - pd.DateOffset(years=1)
    meses = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
             7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

    colunas = {}
    ordem = []

    nome_mes_ant = f"{meses[ultima_data.month]}/{data_comparavel.year}"
    nome_ytd_ant = f"No ano ({data_comparavel.year})"
    if data_comparavel in mensal.columns:
        colunas[nome_mes_ant] = mensal[data_comparavel]
        ordem.append(nome_mes_ant)
    if data_comparavel in acumulado_ano.columns:
        colunas[nome_ytd_ant] = acumulado_ano[data_comparavel]
        ordem.append(nome_ytd_ant)

    meses_recentes = [d for d in datas if d.year == ultima_data.year][-quantidade_meses:]
    for data in meses_recentes:
        nome = f"{meses[data.month]}/{data.year}"
        colunas[nome] = mensal[data]
        ordem.append(nome)

    nome_ytd = f"No ano ({ultima_data.year})"
    nome_12m = f"12 meses ({meses[ultima_data.month]}/{str(ultima_data.year)[2:]})"
    if ultima_data in acumulado_ano.columns:
        colunas[nome_ytd] = acumulado_ano[ultima_data]
        ordem.append(nome_ytd)
    if ultima_data in acumulado_12m.columns:
        colunas[nome_12m] = acumulado_12m[ultima_data]
        ordem.append(nome_12m)

    resumo = pd.DataFrame(colunas).reindex(list(ROTULOS)).reindex(columns=ordem)
    return resumo, data_comparavel.year, ultima_data.year


def exibir_tabela(df, ano_anterior, ano_atual):
    tabela = Table(
        title=(
            "\n[bold white]Resultado Fiscal do Governo Federal — Abaixo da Linha[/bold white]\n"
            f"[dim]Comparativo {ano_anterior} vs. {ano_atual} | R$ milhões[/dim]"
        ),
        box=box.HORIZONTALS,
        header_style="bold white on #1b365d",
        border_style="bright_black",
    )
    tabela.add_column("Indicador", min_width=38)
    for coluna in df.columns:
        tabela.add_column(coluna, justify="right")

    for indicador, linha in df.iterrows():
        valores = [ROTULOS.get(indicador, indicador)]
        for valor in linha:
            if pd.isna(valor):
                valores.append("—")
            else:
                numero = f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
                # Na convenção NFSP do BCB, positivo = déficit; negativo = superávit.
                valores.append(f"[red]{numero}[/red]" if valor > 0 else f"[green]{numero}[/green]" if valor < 0 else numero)
        tabela.add_row(*valores)

    console.print(tabela)
    console.print(
        "[dim]Convenção BCB/NFSP: valores positivos representam déficit/necessidade de financiamento; "
        "valores negativos representam superávit/capacidade de financiamento.\n"
        "Acumulado no ano = soma desde janeiro. 12 meses = soma móvel dos últimos 12 meses.\n"
        "Fonte: Banco Central do Brasil — SGS. Não há dados simulados nem cálculo a partir da metodologia acima da linha.[/dim]"
    )


def salvar_bases(df_mensal, df_ytd, df_12m, pasta="."):
    """Salva as três bases em CSV para uso posterior no projeto."""
    destino = Path(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    df_mensal.to_csv(destino / "abaixo_linha_mensal.csv", index=False, encoding="utf-8-sig")
    df_ytd.to_csv(destino / "abaixo_linha_acumulado_ano.csv", index=False, encoding="utf-8-sig")
    df_12m.to_csv(destino / "abaixo_linha_acumulado_12_meses.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    console.print(Panel.fit(
        "[bold cyan]POLÍTICA FISCAL — METODOLOGIA ABAIXO DA LINHA[/bold cyan]\n"
        "[white]Governo Federal | Banco Central do Brasil (SGS)[/white]",
        border_style="cyan",
    ))

    base_mensal = obter_dados_abaixo_da_linha(inicio="2024-01-01")
    base_ytd, base_12m = gerar_tabelas_acumuladas(base_mensal)
    tabela, ano_anterior, ano_atual = montar_tabela_resumo(
        base_mensal, base_ytd, base_12m, quantidade_meses=4
    )
    exibir_tabela(tabela, ano_anterior, ano_atual)
    salvar_bases(base_mensal, base_ytd, base_12m, pasta=".")
    console.print("\n[green]Bases CSV salvas com sucesso.[/green]")
