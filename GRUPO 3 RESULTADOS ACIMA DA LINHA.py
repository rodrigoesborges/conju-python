import os
import re
import socket
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

TIMEOUT_SEGUNDOS = 5
socket.setdefaulttimeout(TIMEOUT_SEGUNDOS)
console = Console()

# ==============================================================================
# 0) ESTRUTURA OFICIAL DA TABELA X.1 (BOLETIM DE CONJUNTURA - PÁG. 29)
# ==============================================================================
ESTRUTURA_TABELA_X1 = [
    ('I_RECEITA_TOTAL',          'I RECEITA TOTAL',                              'titulo'),
    ('REC_TESOURO',              '  Receita do Tesouro',                         'item'),
    ('REC_PREVIDENCIA',          '  Receita Previdência Social',                 'item'),
    ('REC_BCB',                  '  Receitas do Banco Central',                  'item'),
    ('II_TRANSFERENCIAS',        'II Transferência a Estados e Municípios',      'subtitulo'),
    ('III_RECEITA_LIQUIDA',      'III Receita Líquida Total (I-II)',             'titulo'),
    ('IV_DESPESA_TOTAL',         'IV DESPESA TOTAL',                             'titulo'),
    ('DESP_PESSOAL',             '  Pessoal e Encargos Sociais',                 'item'),
    ('DESP_PREVIDENCIA',         '  Benefícios Previdenciários',                 'item'),
    ('DESP_CUSTEIO_CAPITAL',     '  Custeio e Capital',                          'item'),
    ('DESP_TRANSF_BCB',          '  Transferência do Tesouro ao BCB',            'item'),
    ('DESP_BCB',                 '  Despesas do Banco Central',                  'item'),
    ('V_RES_PRIM_ACIMA',         'V RES. PRIM. GOV. CENTRAL (III-IV)*',          'destaque'),
    ('VI_TESOURO',               'VI Tesouro Nacional',                          'item'),
    ('VII_PREVIDENCIA',          'VII Previdência Social (RGPS)',                'item'),
    ('VIII_BCB',                 'VIII Banco Central',                           'item'),
    ('IX_AJUSTE_METOD',          'IX Ajuste Metodológico e Discr. Est.**',       'item'),
    ('X_RES_PRIM_ABAIXO',        'X RES. PRIM. GOV. CENTR.*** (VI+VII+VIII+IX)',  'destaque'),
    ('JUROS_NOMINAIS',           'Juros Nominais',                               'item'),
    ('RESULTADO_NOMINAL',        'Resultado Nominal',                            'subtitulo'),
    ('RES_PRIM_PIB',             'RES. PRIMÁRIO (% PIB) - Acima da Linha',       'pct_pib'),
    ('RES_NOMINAL_PIB',          'RES. NOMINAL (% PIB) - Abaixo da Linha',       'pct_pib'),
]

# ==============================================================================
# 1) CONTINGÊNCIA OFFLINE E COLETA DE DADOS
# ==============================================================================
def _gerar_base_contingencia():
    datas = pd.date_range('2025-01-01', periods=22, freq='MS')
    rng = np.random.default_rng(42)
    registros = []
    for dt in datas:
        saz_dez = 1.25 if dt.month == 12 else 1.0
        rec_tes = round(165000 * saz_dez + rng.normal(0, 8000), 1)
        rec_prev = round(54000 * (1.4 if dt.month == 12 else 1.0) + rng.normal(0, 1500), 1)
        rec_bcb = round(450 + rng.normal(0, 80), 1)
        rec_tot = round(rec_tes + rec_prev + rec_bcb, 1)
        transf = round(38000 + rng.normal(0, 2500), 1)
        rec_liq = round(rec_tot - transf, 1)
        desp_pess = round(31000 * (1.3 if dt.month == 12 else 1.0) + rng.normal(0, 1000), 1)
        desp_prev = round(76000 * (1.45 if dt.month == 12 else 1.0) + rng.normal(0, 2000), 1)
        desp_cust = round(68000 + rng.normal(0, 5000), 1)
        desp_tr_bcb = round(250 + rng.normal(0, 40), 1)
        desp_bcb = round(520 + rng.normal(0, 60), 1)
        desp_tot = round(desp_pess + desp_prev + desp_cust + desp_tr_bcb + desp_bcb, 1)
        res_prim_acima = round(rec_liq - desp_tot, 1)
        tesouro = round(rec_tes - transf - desp_pess - desp_cust - desp_tr_bcb, 1)
        previdencia = round(rec_prev - desp_prev, 1)
        bcb_res = round(rec_bcb - desp_bcb, 1)
        ajuste = round(rng.normal(-1200, 400), 1)
        res_prim_abaixo = round(-(res_prim_acima + ajuste), 1)
        juros = round(62000 + rng.normal(0, 4000), 1)
        res_nominal = round(res_prim_abaixo + juros, 1)
        pib_mensal = round(980000 + (dt.month * 4000), 1)

        mapa = {
            'I_RECEITA_TOTAL': rec_tot, 'REC_TESOURO': rec_tes,
            'REC_PREVIDENCIA': rec_prev, 'REC_BCB': rec_bcb,
            'II_TRANSFERENCIAS': transf, 'III_RECEITA_LIQUIDA': rec_liq,
            'IV_DESPESA_TOTAL': desp_tot, 'DESP_PESSOAL': desp_pess,
            'DESP_PREVIDENCIA': desp_prev, 'DESP_CUSTEIO_CAPITAL': desp_cust,
            'DESP_TRANSF_BCB': desp_tr_bcb, 'DESP_BCB': desp_bcb,
            'V_RES_PRIM_ACIMA': res_prim_acima, 'VI_TESOURO': tesouro,
            'VII_PREVIDENCIA': previdencia, 'VIII_BCB': bcb_res,
            'IX_AJUSTE_METOD': ajuste, 'X_RES_PRIM_ABAIXO': res_prim_abaixo,
            'JUROS_NOMINAIS': juros, 'RESULTADO_NOMINAL': res_nominal,
            'PIB_MENSAL': pib_mensal
        }
        for ind, val in mapa.items():
            registros.append({'periodo': dt, 'indicador': ind, 'valor': val})
    return pd.DataFrame(registros)


def _finalizar_calculos_base(df_base):
    df_base = df_base.copy()
    df_base['periodo'] = pd.to_datetime(df_base['periodo'])
    piv = df_base.pivot(index='periodo', columns='indicador', values='valor')

    if 'V_RES_PRIM_ACIMA' not in piv.columns and 'X_RES_PRIM_ABAIXO' in piv.columns:
        s_proxy = (-piv['X_RES_PRIM_ABAIXO']).dropna().reset_index()
        s_proxy.columns = ['periodo', 'valor']
        s_proxy['indicador'] = 'V_RES_PRIM_ACIMA'
        df_base = pd.concat([df_base, s_proxy], ignore_index=True)
        piv = df_base.pivot(index='periodo', columns='indicador', values='valor')

    if 'IX_AJUSTE_METOD' not in piv.columns and {'X_RES_PRIM_ABAIXO', 'V_RES_PRIM_ACIMA'}.issubset(piv.columns):
        ajuste = (-piv['X_RES_PRIM_ABAIXO']) - piv['V_RES_PRIM_ACIMA']
        df_ajuste = ajuste.dropna().reset_index()
        df_ajuste.columns = ['periodo', 'valor']
        df_ajuste['indicador'] = 'IX_AJUSTE_METOD'
        df_base = pd.concat([df_base, df_ajuste], ignore_index=True)
        piv = df_base.pivot(index='periodo', columns='indicador', values='valor')

    if 'PIB_MENSAL' in piv.columns:
        if 'V_RES_PRIM_ACIMA' in piv.columns:
            s_pp = ((piv['V_RES_PRIM_ACIMA'] / piv['PIB_MENSAL']) * 100).dropna().reset_index()
            s_pp.columns = ['periodo', 'valor']
            s_pp['indicador'] = 'RES_PRIM_PIB'
            df_base = pd.concat([df_base, s_pp], ignore_index=True)

        if 'RESULTADO_NOMINAL' in piv.columns:
            s_np = ((piv['RESULTADO_NOMINAL'] / piv['PIB_MENSAL']) * 100).dropna().reset_index()
            s_np.columns = ['periodo', 'valor']
            s_np['indicador'] = 'RES_NOMINAL_PIB'
            df_base = pd.concat([df_base, s_np], ignore_index=True)

    df_base['periodo'] = pd.to_datetime(df_base['periodo'])
    df_base = df_base.sort_values(['indicador', 'periodo']).reset_index(drop=True)
    df_base['periodo_str'] = df_base['periodo'].dt.strftime('%Y%m%d')
    return df_base[['periodo', 'periodo_str', 'indicador', 'valor']]


def obter_tabela_base_completa(start='2024-01-01'):
    pasta_script = os.path.dirname(os.path.abspath(__file__))
    caminho_rtn = os.path.join(pasta_script, "rtn.xlsx")
    df_rtn = pd.DataFrame(columns=['periodo', 'indicador', 'valor'])

    if os.path.exists(caminho_rtn):
        console.print("[green]✔[/green] Lendo planilha local 'rtn.xlsx'...")
        excel = pd.ExcelFile(caminho_rtn)
        aba_alvo = next((s for s in excel.sheet_names if '1.1' in s), excel.sheet_names[1])
        raw = pd.read_excel(excel, sheet_name=aba_alvo, header=None)
        linha_datas = next(
            idx for idx, row in raw.iterrows()
            if sum(isinstance(v, (pd.Timestamp, np.datetime64)) or bool(re.search(r'(199\d|20[0-2]\d)', str(v))) for v in row.values[1:]) >= 12
        )
        datas = pd.to_datetime(raw.iloc[linha_datas, 1:], errors='coerce')
        cols_validas = datas.notna()
        datas = datas[cols_validas]

        padroes_rtn = {
            'I_RECEITA_TOTAL':      r'^\s*1\.\s*RECEITA TOTAL',
            'REC_TESOURO':          r'^\s*1\.1\s*Receita Administrada|^\s*1\.1\s*Receita do Tesouro',
            'REC_PREVIDENCIA':      r'^\s*1\.2\s*Arrecadação Líquida para o RGPS|^\s*1\.2\s*Receita Previd',
            'REC_BCB':              r'^\s*1\.3\s*Receitas.*Banco Central|^\s*1\.4\s*Receitas.*Banco Central',
            'II_TRANSFERENCIAS':    r'^\s*2\.\s*Transferências por Repartição',
            'III_RECEITA_LIQUIDA':  r'^\s*3\.\s*RECEITA LÍQUIDA',
            'IV_DESPESA_TOTAL':     r'^\s*4\.\s*DESPESA TOTAL',
            'DESP_PESSOAL':         r'^\s*4\.2\s*Pessoal e Encargos',
            'DESP_PREVIDENCIA':     r'^\s*4\.1\s*Benefícios Previdenciários',
            'DESP_CUSTEIO_CAPITAL': r'^\s*4\.3\s*Outras Despesas Correntes e de Capital|^\s*4\.3\s*Custeio e Capital',
            'DESP_TRANSF_BCB':      r'Transferência.*Banco Central',
            'DESP_BCB':             r'Despesas do Banco Central',
            'V_RES_PRIM_ACIMA':     r'^\s*5\.\s*RESULTADO PRIMÁRIO DO GOVERNO CENTRAL',
            'VI_TESOURO':           r'^\s*5\.1\s*Tesouro Nacional',
            'VII_PREVIDENCIA':      r'^\s*5\.2\s*Previdência Social',
            'VIII_BCB':             r'^\s*5\.3\s*Banco Central',
        }
        registros = []
        for idx in range(linha_datas + 1, len(raw)):
            discriminacao = str(raw.iloc[idx, 0]).strip()
            for chave, regex in padroes_rtn.items():
                if re.search(regex, discriminacao, flags=re.IGNORECASE):
                    vals = pd.to_numeric(raw.iloc[idx, 1:][cols_validas], errors='coerce')
                    for dt, val in zip(datas, vals):
                        if pd.notna(val):
                            registros.append({'periodo': dt.to_period('M').to_timestamp(), 'indicador': chave, 'valor': float(val)})
                    break
        df_rtn = pd.DataFrame(registros).drop_duplicates(subset=['periodo', 'indicador'])
        df_rtn = df_rtn[df_rtn['periodo'] >= pd.to_datetime(start)]

    dfs_bcb = []
    fonte_usada = "Dados Reais (SGS/BCB + STN)"
    try:
        from bcb import sgs
        series_bcb = {
            'X_RES_PRIM_ABAIXO': 5727,
            'JUROS_NOMINAIS':    4641,
            'RESULTADO_NOMINAL': 4640,
            'PIB_MENSAL':        4382,
        }
        for chave, cod in series_bcb.items():
            console.print(f"-> Buscando SGS/BCB {chave} (timeout={TIMEOUT_SEGUNDOS}s)...")
            s = sgs.get({chave: cod}, start=start, timeout=TIMEOUT_SEGUNDOS)
            dfs_bcb.append(s)
        console.print("[green]✔[/green] Séries do Banco Central baixadas com sucesso.")
    except Exception as e:
        console.print(f"[yellow]⚠ Timeout ou bloqueio de rede ({type(e).__name__}).[/yellow]")
        console.print("[cyan]ℹ Ativando base de contingência para exibir o layout imediatamente...[/cyan]")
        df_base = _gerar_base_contingencia()
        return _finalizar_calculos_base(df_base), "Modo Demonstração (Timeout de rede)"

    df_bcb_wide = pd.concat(dfs_bcb, axis=1)
    df_bcb_wide.index = pd.to_datetime(df_bcb_wide.index).to_period('M').to_timestamp()
    df_bcb_wide.index.name = 'periodo'
    df_bcb_long = df_bcb_wide.reset_index().melt(id_vars='periodo', var_name='indicador', value_name='valor').dropna(subset=['valor'])

    df_base = pd.concat([df_rtn, df_bcb_long], ignore_index=True) if not df_rtn.empty else df_bcb_long
    return _finalizar_calculos_base(df_base), fonte_usada


# ==============================================================================
# 2) TABELAS INTERMEDIÁRIAS 1, 2, 3 E 4
# ==============================================================================
def gerar_tabelas_intermediarias(df_base):
    piv = df_base.pivot(index='periodo', columns='indicador', values='valor').sort_index()
    anos = piv.index.year

    ytd_wide = piv.groupby(anos).cumsum()
    ltm_wide = piv.rolling(window=12, min_periods=12).sum()

    if 'PIB_MENSAL' in piv.columns:
        if 'V_RES_PRIM_ACIMA' in piv.columns:
            ytd_wide['RES_PRIM_PIB'] = (ytd_wide['V_RES_PRIM_ACIMA'] / ytd_wide['PIB_MENSAL']) * 100
            ltm_wide['RES_PRIM_PIB'] = (ltm_wide['V_RES_PRIM_ACIMA'] / ltm_wide['PIB_MENSAL']) * 100
        if 'RESULTADO_NOMINAL' in piv.columns:
            ytd_wide['RES_NOMINAL_PIB'] = (ytd_wide['RESULTADO_NOMINAL'] / ytd_wide['PIB_MENSAL']) * 100
            ltm_wide['RES_NOMINAL_PIB'] = (ltm_wide['RESULTADO_NOMINAL'] / ltm_wide['PIB_MENSAL']) * 100

    def _to_long(df_w):
        dl = df_w.reset_index().melt(id_vars='periodo', var_name='indicador', value_name='valor').dropna(subset=['valor'])
        dl['periodo'] = pd.to_datetime(dl['periodo'])
        dl['periodo_str'] = dl['periodo'].dt.strftime('%Y%m%d')
        return dl[['periodo', 'periodo_str', 'indicador', 'valor']]

    tab_1 = _to_long(ytd_wide)
    tab_2 = _to_long(ltm_wide)

    def _var_ano_anterior(df_interm):
        df = df_interm.copy()
        df['periodo_anterior'] = df['periodo'] - pd.DateOffset(years=1)
        ref = df[['periodo', 'indicador', 'valor']].rename(columns={'periodo': 'periodo_anterior', 'valor': 'valor_y'})
        m = pd.merge(df, ref, on=['indicador', 'periodo_anterior'], how='inner')
        saldos = {
            'V_RES_PRIM_ACIMA', 'VI_TESOURO', 'VII_PREVIDENCIA', 'VIII_BCB',
            'IX_AJUSTE_METOD', 'X_RES_PRIM_ABAIXO', 'RESULTADO_NOMINAL',
            'RES_PRIM_PIB', 'RES_NOMINAL_PIB'
        }
        m['valor'] = np.where(
            m['indicador'].isin(saldos),
            m['valor'] - m['valor_y'],
            ((m['valor'] / m['valor_y']) - 1) * 100
        )
        return m[['periodo', 'periodo_str', 'indicador', 'valor']]

    return tab_1, tab_2, _var_ano_anterior(tab_1), _var_ano_anterior(tab_2)


# ==============================================================================
# 3) JUNÇÃO FINAL NO FORMATO DA TABELA X.1
# ==============================================================================
def montar_tabela_boletim_x1(df_base, tab_1, tab_2, n_meses_atuais=4):
    ref_ind = 'V_RES_PRIM_ACIMA' if 'V_RES_PRIM_ACIMA' in df_base['indicador'].values else 'X_RES_PRIM_ABAIXO'
    datas_disp = sorted(df_base[df_base['indicador'] == ref_ind]['periodo'].unique())

    ult_data = pd.Timestamp(datas_disp[-1])
    ano_atual = ult_data.year
    ano_ant = ano_atual - 1
    mes_ref = ult_data.month
    data_equiv_ant = ult_data - pd.DateOffset(years=1)

    meses_pt = {
        1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
    }

    ultimas_datas_atual = [pd.Timestamp(d) for d in datas_disp[-n_meses_atuais:]]
    piv_base = df_base.pivot(index='indicador', columns='periodo', values='valor')
    piv_ytd = tab_1.pivot(index='indicador', columns='periodo', values='valor')
    piv_ltm = tab_2.pivot(index='indicador', columns='periodo', values='valor')

    colunas_ordenadas = []
    dados_cols = {}

    col_ant_mes = f"{meses_pt[mes_ref]}/{ano_ant}"
    col_ant_ano = f"No ano ({ano_ant})*"
    dados_cols[col_ant_mes] = piv_base[data_equiv_ant] if data_equiv_ant in piv_base.columns else pd.Series(dtype=float)
    dados_cols[col_ant_ano] = piv_ytd[data_equiv_ant] if data_equiv_ant in piv_ytd.columns else pd.Series(dtype=float)
    colunas_ordenadas.extend([col_ant_mes, col_ant_ano])

    for dt in ultimas_datas_atual:
        nome_c = f"{meses_pt[dt.month]}/{dt.year}"
        dados_cols[nome_c] = piv_base[dt]
        colunas_ordenadas.append(nome_c)

    col_atual_ano = f"No ano ({ano_atual})"
    col_12m = f"12 meses ({meses_pt[mes_ref]}/{str(ano_atual)[2:]})"
    dados_cols[col_atual_ano] = piv_ytd[ult_data]
    dados_cols[col_12m] = piv_ltm[ult_data]
    colunas_ordenadas.extend([col_atual_ano, col_12m])

    df_final = pd.DataFrame(dados_cols)[colunas_ordenadas]
    chaves_ordenadas = [item[0] for item in ESTRUTURA_TABELA_X1 if item[0] in df_final.index]
    return df_final.reindex(chaves_ordenadas), ano_ant, ano_atual


# ==============================================================================
# 4) RENDERIZAÇÃO VISUAL COM RICH
# ==============================================================================
def exibir_tabela_x1_rich(df_final, ano_ant, ano_atual, fonte_usada):
    meta_map = {chave: (rotulo, estilo) for chave, rotulo, estilo in ESTRUTURA_TABELA_X1}

    table = Table(
        title=(
            f"\n[bold white]Tabela X.1 - Resultado Primário do Governo Central (R$ milhões)[/bold white]\n"
            f"[dim]Comparativo {ano_ant} vs. {ano_atual} | Fonte: {fonte_usada}[/dim]"
        ),
        box=box.HORIZONTALS,
        header_style="bold white on #1b365d",
        border_style="bright_black",
        show_lines=False,
        pad_edge=True
    )

    table.add_column("Discriminação", no_wrap=True, min_width=42)

    for col in df_final.columns:
        if "No ano" in col or "12 meses" in col:
            table.add_column(col, justify="right", style="bold")
        else:
            table.add_column(col, justify="right")

    for chave, row in df_final.iterrows():
        rotulo, nivel = meta_map.get(chave, (chave, 'item'))

        if nivel in ('titulo', 'destaque', 'pct_pib') and chave != 'I_RECEITA_TOTAL':
            table.add_section()

        if nivel in ('titulo', 'destaque'):
            rotulo_fmt = f"[bold cyan]{rotulo}[/bold cyan]"
        elif nivel in ('subtitulo', 'pct_pib'):
            rotulo_fmt = f"[bold white]{rotulo}[/bold white]"
        else:
            rotulo_fmt = f"[white]{rotulo}[/white]"

        celulas = [rotulo_fmt]
        casas = 2 if nivel == 'pct_pib' else 1

        for val in row.values:
            if pd.isna(val):
                celulas.append("[dim]—[/dim]")
            else:
                num_str = f"{val:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if val < 0:
                    celulas.append(f"[bold red]{num_str}[/bold red]" if nivel in ('destaque', 'pct_pib') else f"[red]{num_str}[/red]")
                else:
                    celulas.append(f"[bold green]{num_str}[/bold green]" if nivel in ('destaque', 'pct_pib') else num_str)

        table.add_row(*celulas)

    console.print(table)
    console.print(
        "[dim]* Acumulado no ano até o mês de referência equivalente. ** Discrepância estatística e ajuste metodológico.\n"
        "*** Na metodologia do BCB (abaixo da linha), valores positivos representam déficit e negativos representam superávit.[/dim]\n"
    )


if __name__ == '__main__':
    console.print(Panel.fit(
        "[bold cyan]BOLETIM DE CONJUNTURA — POLÍTICA FISCAL DO BRASIL (TABELA X.1)[/bold cyan]",
        border_style="cyan"
    ))

    tabela_base, fonte = obter_tabela_base_completa(start='2024-01-01')
    tab_1, tab_2, tab_3, tab_4 = gerar_tabelas_intermediarias(tabela_base)
    tabela_x1, ano_ant, ano_atual = montar_tabela_boletim_x1(tabela_base, tab_1, tab_2, n_meses_atuais=4)
    exibir_tabela_x1_rich(tabela_x1, ano_ant, ano_atual, fonte)