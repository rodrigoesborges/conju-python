# -*- coding: utf-8 -*
import os
from itertools import combinations
import pandas as pd
import numpy as np
import sidrapy
if os.name == 'nt':
    os.system('')

pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.width', 2000)

TABELA_SIDRA = '1846'
NIVEL_TERRITORIAL = '1'      
CODIGO_TERRITORIAL = 'all'
VARIAVEL_SIDRA = '585'
CLASSIFICACAO_SETORES = {'11255': 'all'}
PERIODO_SIDRA = 'all'
AREAS_PRINCIPAIS = {
'Agropecuária - total',
'Indústria - total',
'Serviços - total',
'Valor adicionado a preços básicos',
'PIB a preços de mercado',
}
_CACHE_PIB = {}
def carregar_dados_pib(periodo=PERIODO_SIDRA, forcar_atualizacao=False):
if not forcar_atualizacao and periodo in _CACHE_PIB:
return _CACHE_PIB[periodo].copy()
df_bruto = sidrapy.get_table(
table_code=TABELA_SIDRA,
territorial_level=NIVEL_TERRITORIAL,
ibge_territorial_code=CODIGO_TERRITORIAL,
variable=VARIAVEL_SIDRA,
period=periodo,
classifications=CLASSIFICACAO_SETORES,
header='y',)
df = df_bruto.iloc[1:].copy()
df.columns = df_bruto.iloc[0]
df = df.rename(columns={'Setores e subsetores': 'Setor'})[['Setor', 'Trimestre', 
'Valor']]
df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')
df_limpo = df.dropna(subset=['Trimestre', 'Valor']).copy()
df_limpo['Valor'] = df_limpo['Valor'].round().astype(int)
_CACHE_PIB[periodo] = df_limpo
return df_limpo.copy()
def _formatar_inteiro(valor):
    return '-' if pd.isna(valor) else f"{valor:,.0f}".replace(",", ".")
def formatar_areas_principais(df_visivel, areas_principais=AREAS_PRINCIPAIS):
    linhas = df_visivel.to_string().split('\n')
    linhas_saida = []
    for linha in linhas:
        area_match = next(
            (
                area for area in areas_principais
                if linha.startswith(area) and (len(linha) == len(area) or linha[len(area)] 
== ' ')
            ),
            None
        )
        if area_match:
            linhas_saida.append(f"\033[1m{linha}\033[0m")
        else:
            linhas_saida.append(linha)
    return '\n'.join(linhas_saida)
def tabela_pib(periodo=PERIODO_SIDRA, forcar_atualizacao=False):
    df_limpo = carregar_dados_pib(periodo=periodo, forcar_atualizacao=forcar_atualizacao)
    df_limpo['Ano'] = df_limpo['Trimestre'].str.extract(r'(\d{4})')
    df_limpo['Trim_Num'] = df_limpo['Trimestre'].str.extract(r'(\d)º')
    df_limpo['Trimestre_Curto'] = df_limpo['Ano'] + ' T' + df_limpo['Trim_Num']
    tabela_trimestral = df_limpo.pivot_table(
        index='Setor',
        columns='Trimestre_Curto',
        values='Valor',
        aggfunc='sum',
        sort=False
    )
    tabela_trimestral_visivel = tabela_trimestral.apply(
        lambda col: col.map(_formatar_inteiro)
    )
    return formatar_areas_principais(tabela_trimestral_visivel, AREAS_PRINCIPAIS)
def soma_ano(periodo=PERIODO_SIDRA, forcar_atualizacao=False):
    df_limpo = carregar_dados_pib(periodo=periodo, forcar_atualizacao=forcar_atualizacao)
    df_limpo['Ano'] = df_limpo['Trimestre'].str.extract(r'(\d{4})').astype(int)
    tabela_ano = df_limpo.pivot_table(
        index='Setor',
        columns='Ano',
        values='Valor',
        aggfunc='sum',
        sort=False
    )
    tabela_ano_visivel = tabela_ano.apply(
        lambda col: col.map(_formatar_inteiro)
    )
    return formatar_areas_principais(tabela_ano_visivel, AREAS_PRINCIPAIS)
def soma_4t(periodo=PERIODO_SIDRA, forcar_atualizacao=False):
    df_limpo = carregar_dados_pib(periodo=periodo, forcar_atualizacao=forcar_atualizacao)
    df_limpo['Ano'] = df_limpo['Trimestre'].str.extract(r'(\d{4})').astype(int)
    df_limpo['Trim_Num'] = df_limpo['Trimestre'].str.extract(r'(\d)º').astype(int)
    df_limpo['Ano_Inicio'] = df_limpo['Ano'] - df_limpo['Trim_Num'].isin([1, 
2]).astype(int)
    df_limpo['Soma_4T'] = (
        df_limpo['Ano_Inicio'].astype(str) + '/' + (df_limpo['Ano_Inicio'] + 
1).astype(str)
    )
    contagem = df_limpo.groupby('Soma_4T')['Trimestre'].nunique()
    periodos_completos = contagem[contagem == 4].index
    df_4t = df_limpo[df_limpo['Soma_4T'].isin(periodos_completos)].copy()
    tabela_4t = df_4t.pivot_table(
        index='Setor',
        columns='Soma_4T',
        values='Valor',
        aggfunc='sum',
        sort=False
    )
    tabela_4t_visivel = tabela_4t.apply(
        lambda col: col.map(_formatar_inteiro)
    )
    return formatar_areas_principais(tabela_4t_visivel, AREAS_PRINCIPAIS)
def diferenca_semestres(ano_ref=None, periodo=PERIODO_SIDRA, forcar_atualizacao=False):
    df_limpo = carregar_dados_pib(periodo=periodo, forcar_atualizacao=forcar_atualizacao)
    df_limpo['Ano'] = df_limpo['Trimestre'].str.extract(r'(\d{4})')
    df_limpo['Trim_Num'] = df_limpo['Trimestre'].str.extract(r'(\d)º')
    df_1sem = df_limpo[df_limpo['Trim_Num'].isin(['1', '2'])].copy()
    contagem_1sem = df_1sem.groupby('Ano')['Trim_Num'].nunique()
    anos_completos = contagem_1sem[contagem_1sem == 2].index
    df_1sem = df_1sem[df_1sem['Ano'].isin(anos_completos)].copy()
    tabela_semestral = df_1sem.pivot_table(
        index='Setor',
        columns='Ano',
        values='Valor',
        aggfunc='sum',
        sort=False
    )
    if tabela_semestral.empty:
        return "Erro: Não há anos com 1º semestre completo no período consultado."
    if ano_ref is None:
        ano_ref = max(tabela_semestral.columns, key=int)
    else:
        ano_ref = str(ano_ref)
        if ano_ref not in tabela_semestral.columns:
            return f"Erro: Ano '{ano_ref}' não possui 1º semestre completo nos dados."
    anos_anteriores = [col for col in tabela_semestral.columns if col != ano_ref]
    tabela_dif_sem = tabela_semestral[anos_anteriores].apply(lambda col: 
tabela_semestral[ano_ref] - col)
    sufixo_ref = ano_ref[-2:]
    tabela_dif_sem.columns = [f"{sufixo_ref}-{ano}" for ano in anos_anteriores]
    tabela_dif_sem[f"{ano_ref}(1ºS)"] = tabela_semestral[ano_ref]
    tabela_dif_sem_visivel = tabela_dif_sem.apply(
        lambda col: col.map(_formatar_inteiro)
    )
    return formatar_areas_principais(tabela_dif_sem_visivel, AREAS_PRINCIPAIS)
def comparar_trimestres(periodo=PERIODO_SIDRA, forcar_atualizacao=False):
    df_limpo = carregar_dados_pib(periodo=periodo, forcar_atualizacao=forcar_atualizacao)
    df_limpo['Ano'] = df_limpo['Trimestre'].str.extract(r'(\d{4})')
    df_limpo['Trim_Num'] = df_limpo['Trimestre'].str.extract(r'(\d)º')
    df_limpo['Trim_Cod'] = df_limpo['Trim_Num'] + 'T/' + df_limpo['Ano']
    tabela_base = df_limpo.pivot_table(
        index='Setor',
        columns='Trim_Cod',
        values='Valor',
        aggfunc='sum',
        sort=False
    )
    colunas_ordenadas = sorted(
        tabela_base.columns,
        key=lambda c: (int(c.split('T/')[1]), int(c.split('T/')[0]))
    )
    tabela_base = tabela_base[colunas_ordenadas]
    disponiveis = list(tabela_base.columns)
    print("\nEscolha o modo de comparação:")
    print("  [1] Um trimestre de referência contra outros")
    print("  [2] Escolher vários trimestres e comparar todos entre eles (do mais recente aos mais antigos)")
    print("  [0] Cancelar")
    while True:
        modo = input("Digite 1, 2 ou 0 para cancelar: ").strip()
        if modo == "0":
            return "Operação cancelada."
        if modo in ("1", "2"):
            break
        print("Opção inválida! Por favor, digite apenas 1, 2 ou 0 para cancelar.\n")
    print(f"\nTrimestres disponíveis ({disponiveis[0]} até {disponiveis[-1]}):")
    print(", ".join(disponiveis))
    if modo == "1":
        col_ref = input("\nDigite trimestre principal de referência (ex: 2T/2026): ").strip().upper()
        if not col_ref:
            return "Erro: Você deve informar o trimestre principal de referência."
        entrada_comp = input(
            "Digite os trimestres para comparar separados por vírgula (ex: 1T/2026, 2T/2025): "
        ).strip().upper()
        cols_comp = [c.strip() for c in entrada_comp.split(",") if c.strip()]
        if not cols_comp:
            return "Erro: Você deve informar pelo menos um trimestre para comparar."
        for periodo_escolhido in [col_ref] + cols_comp:
            if periodo_escolhido not in tabela_base.columns:
                return f"Erro: Trimestre '{periodo_escolhido}' inválido. Opções 
disponíveis: {', '.join(disponiveis)}"
        pares = [(c, col_ref) for c in cols_comp]
    elif modo == "2":
entrada_trims = input(
"\nDigite os trimestres que deseja comparar entre si separados por vírgula 
(ex: 2T/2026, 1T/2026, 2T/2025): "
).strip().upper()
escolhidos = [c.strip() for c in entrada_trims.split(",") if c.strip()]
escolhidos_unicos = []
for periodo_escolhido in escolhidos:
if periodo_escolhido not in tabela_base.columns:
return f"Erro: Trimestre '{periodo_escolhido}' inválido. Opções 
disponíveis: {', '.join(disponiveis)}"
if periodo_escolhido not in escolhidos_unicos:
escolhidos_unicos.append(periodo_escolhido)
if len(escolhidos_unicos) < 2:
return "Erro: Escolha pelo menos 2 trimestres diferentes para comparar entre 
si."
cols_decrescente = [c for c in reversed(disponiveis) if c in escolhidos_unicos]
pares = [(t_base, t_alvo) for t_alvo, t_base in combinations(cols_decrescente, 2)]
tabela_resultado = pd.DataFrame(index=tabela_base.index)
for t_base, t_alvo in pares:
dif = tabela_base[t_alvo] - tabela_base[t_base]
pct = (dif / tabela_base[t_base].abs().replace(0, np.nan)) * 100
dif_fmt = dif.map(_formatar_inteiro)
pct_fmt = pct.map(
lambda x: "(-)" if pd.isna(x) else f"({x:+,.2f}%)".replace(",", 
"X").replace(".", ",").replace("X", ".")
)
largura_pct = pct_fmt.map(len).max()
tabela_resultado[f"{t_alvo} - {t_base}"] = [
f"{d} {p:>{largura_pct}}" for d, p in zip(dif_fmt, pct_fmt)
]
return formatar_areas_principais(tabela_resultado, AREAS_PRINCIPAIS