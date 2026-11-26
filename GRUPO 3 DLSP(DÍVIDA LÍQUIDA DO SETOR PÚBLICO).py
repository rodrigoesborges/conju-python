import time
import pandas as pd
import numpy as np
from bcb import sgs

# ==============================================================================
# 0) OBTER DADOS VIA PACOTE (API BCB)
# ==============================================================================
series = {
    'Dívida Líquida Total (DLT)': 4478,      # R$ milhões
    'Governo Central *': 4468,               # R$ milhões
    'BNDES': 4516,                           # R$ milhões
    'Governos estaduais **': 4472,           # R$ milhões
    'Governos municipais ***': 4473,         # R$ milhões
    'Dívida líquida interna(DIL)': 4488,     # R$ milhões
    'Dívida líquida externa': 4467,          # R$ milhões
    'DLT em % do PIB': 4505                  # % do PIB (Corrigido para percentual)
}

def obter_series_bcb(dicionario_series, start='2023-01-01', end='2025-12-31'):
    """Busca séries individualmente e retorna a TABELA BASE em formato longo."""
    dfs = []
    for nome, codigo in dicionario_series.items():
        print(f"Baixando '{nome}' ({codigo})...", end=" ", flush=True)
        try:
            df_temp = sgs.get({nome: codigo}, start=start, end=end, timeout=60)
            dfs.append(df_temp)
            print("OK!")
        except Exception as e:
            print(f"FALHOU ({e})")
        time.sleep(0.5)
        
    df_wide = pd.concat(dfs, axis=1)
    df_wide.index = pd.to_datetime(df_wide.index)
    
    # Transformar para formato longo (TABELA BASE)
    df_long = df_wide.reset_index().melt(
        id_vars='Date', 
        var_name='indicador', 
        value_name='valor'
    ).rename(columns={'Date': 'periodo'})
    
    return df_long.sort_values(['indicador', 'periodo']).reset_index(drop=True)

# 1) OBTENÇÃO DA TABELA BASE (FORMATO LONGO)
tabela_base = obter_series_bcb(series, start='2023-01-01', end='2025-12-31')


# ==============================================================================
# 2) FUNÇÕES DE CÁLCULO (ESTOQUE / FLUXO)
# ==============================================================================
def calc_acumulado_ano(df, tipo_variavel='estoque'):
    df = df.sort_values(['indicador', 'periodo']).copy()
    df['ano'] = df['periodo'].dt.year
    
    if tipo_variavel == 'estoque':
        dezembros = df[df['periodo'].dt.month == 12][['indicador', 'ano', 'valor']].copy()
        dezembros['ano'] = dezembros['ano'] + 1
        dezembros = dezembros.rename(columns={'valor': 'valor_dez_ant'})
        
        df = df.merge(dezembros, on=['indicador', 'ano'], how='left')
        df['valor_acum_ano'] = df['valor'] - df['valor_dez_ant']
        
    elif tipo_variavel == 'fluxo_soma':
        df['valor_acum_ano'] = df.groupby(['indicador', 'ano'])['valor'].cumsum()
        
    elif tipo_variavel == 'fluxo_taxa':
        df['fator'] = 1 + (df['valor'] / 100)
        df['valor_acum_ano'] = (df.groupby(['indicador', 'ano'])['fator'].cumprod() - 1) * 100
        
    return df[['periodo', 'indicador', 'valor_acum_ano']].rename(columns={'valor_acum_ano': 'valor'})


def calc_acumulado_12m(df, tipo_variavel='estoque', freq='M'):
    df = df.sort_values(['indicador', 'periodo']).copy()
    janela = 12 if freq == 'M' else 4
    
    if tipo_variavel == 'estoque':
        df['valor_12m_ant'] = df.groupby('indicador')['valor'].shift(janela)
        df['valor_acum_12m'] = df['valor'] - df['valor_12m_ant']
        
    elif tipo_variavel == 'fluxo_soma':
        df['valor_acum_12m'] = df.groupby('indicador')['valor'].transform(lambda x: x.rolling(janela).sum())
        
    elif tipo_variavel == 'fluxo_taxa':
        df['fator'] = 1 + (df['valor'] / 100)
        df['valor_acum_12m'] = df.groupby('indicador')['fator'].transform(
            lambda x: (x.rolling(janela).apply(np.prod, raw=True) - 1) * 100
        )
        
    return df[['periodo', 'indicador', 'valor_acum_12m']].rename(columns={'valor_acum_12m': 'valor'})


def calc_var_interanual_acumulado(df_intermediaria):
    df = df_intermediaria.copy()
    df['periodo_anterior'] = df['periodo'] - pd.DateOffset(years=1)
    
    df_merged = df.merge(
        df[['periodo', 'indicador', 'valor']],
        left_on=['indicador', 'periodo_anterior'],
        right_on=['indicador', 'periodo'],
        suffixes=('', '.y'),
        how='left'
    )
    
    # Já calcula diretamente em porcentagem: ((valor / valor.y) - 1) * 100
    df_merged['var_relativa'] = np.where(
        df_merged['valor.y'] != 0,
        ((df_merged['valor'] / df_merged['valor.y']) - 1) * 100,
        np.nan
    )
    
    return df_merged[['periodo', 'indicador', 'var_relativa']].rename(columns={'var_relativa': 'valor'})


# ==============================================================================
# 3) GERAÇÃO DAS TABELAS INTERMEDIÁRIAS (FORMATO LONGO)
# ==============================================================================
tab_interm_1_long = calc_acumulado_ano(tabela_base, tipo_variavel='estoque')
tab_interm_2_long = calc_acumulado_12m(tabela_base, tipo_variavel='estoque', freq='M')
tab_interm_3_long = calc_var_interanual_acumulado(tab_interm_1_long)
tab_interm_4_long = calc_var_interanual_acumulado(tab_interm_2_long)


# ==============================================================================
# 4) FUNÇÃO AUXILIAR PARA TRANSFORMAR E FORMATAR CADA TABELA INDIVIDUALMENTE
# ==============================================================================
def preparar_tabela_individual(df_long, n_ultimos_meses=3, tipo_tabela='base'):
    """
    Transforma uma tabela longa em formato largo (wide) e aplica a formatação adequada:
    - 'base': R$ mi e % (sem sinal negativo no DLT % PIB)
    - 'variacao_estoque': R$ mi e p.p. (pontos percentuais)
    - 'percentual': todas as linhas em % (com símbolo % ao lado)
    """
    ultimas_datas = sorted(df_long['periodo'].dropna().unique())[-n_ultimos_meses:]
    df_rec = df_long[df_long['periodo'].isin(ultimas_datas)].copy()
    df_rec['col_nome'] = df_rec['periodo'].dt.strftime('%Y%m%d')
    
    tab_wide = df_rec.pivot(index='indicador', columns='col_nome', values='valor')
    tab_wide = tab_wide.reindex(index=list(series.keys()))
    
    def fmt(linha):
        if tipo_tabela == 'base':
            if 'PIB' in linha.name:
                # abs(v) remove o sinal negativo na Tabela 1 para DLT em % do PIB
                return linha.map(lambda v: f'{abs(v):.2f}%' if pd.notnull(v) else '')
            return linha.map(lambda v: f'R$ {v:,.2f} mi' if pd.notnull(v) else '')
            
        elif tipo_tabela == 'variacao_estoque':
            if 'PIB' in linha.name:
                return linha.map(lambda v: f'{v:+.2f} p.p.' if pd.notnull(v) else '')
            return linha.map(lambda v: f'R$ {v:,.2f} mi' if pd.notnull(v) else '')
            
        elif tipo_tabela == 'percentual':
            return linha.map(lambda v: f'{v:.2f}%' if pd.notnull(v) else 'N/D')

    return tab_wide.apply(fmt, axis=1)


# ==============================================================================
# 5) EXIBIÇÃO DAS TABELAS SEPARADAS E NOTAS EXPLICATIVAS
# ==============================================================================
tabela_1_base = preparar_tabela_individual(tabela_base, n_ultimos_meses=3, tipo_tabela='base')
tabela_2_acum_ano = preparar_tabela_individual(tab_interm_1_long, n_ultimos_meses=3, tipo_tabela='variacao_estoque')
tabela_3_acum_12m = preparar_tabela_individual(tab_interm_2_long, n_ultimos_meses=3, tipo_tabela='variacao_estoque')
tabela_4_var_interanual_ano = preparar_tabela_individual(tab_interm_3_long, n_ultimos_meses=3, tipo_tabela='percentual')
tabela_5_var_interanual_12m = preparar_tabela_individual(tab_interm_4_long, n_ultimos_meses=3, tipo_tabela='percentual')

print("\n=== 1. TABELA BASE (SALDOS ORIGINAIS) ===")
print(tabela_1_base.to_string())

print("\n=== 2. TABELA INTERMEDIÁRIA 1 (VARIAÇÃO ACUMULADA NO ANO) ===")
print(tabela_2_acum_ano.to_string())

print("\n=== 3. TABELA INTERMEDIÁRIA 2 (VARIAÇÃO ACUMULADA EM 12 MESES) ===")
print(tabela_3_acum_12m.to_string())

print("\n=== 4. TABELA INTERMEDIÁRIA 3 (VAR. DO ACUMULADO NO ANO VS. 12M ANTES) ===")
print(tabela_4_var_interanual_ano.to_string())

print("\n=== 5. TABELA INTERMEDIÁRIA 4 (VAR. DE 12 MESES VS. 12M ANTES) ===")
print(tabela_5_var_interanual_12m.to_string())

# ==============================================================================
# 6) NOTA METODOLÓGICA EXPLICATIVA
# ==============================================================================
nota_explicativa = """
================================================================================
NOTA EXPLICATIVA - METODOLOGIA DAS TABELAS INTERMEDIÁRIAS (VARIÁVEIS DE ESTOQUE)
================================================================================
1. Natureza dos Dados: A Dívida Líquida do Setor Público (DLSP) e seus componentes 
   representam variáveis de estoque (saldos apurados ao final de cada mês). 
   Valores negativos na Tabela Base (como BNDES e Dívida Líquida Externa) 
   indicam posição credora líquida (ativos/reservas superiores às obrigações).

2. Tabelas Intermediárias 1 e 2 (Variação Acumulada no Ano e em 12 Meses):
   - Expressam a variação absoluta do estoque (em R$ milhões ou pontos percentuais 
     do PIB) em relação a dezembro do ano anterior (Tabela 1) e em relação ao 
     mesmo mês do ano anterior (Tabela 2).
   - Valores positivos indicam expansão da dívida líquida no período; valores 
     negativos indicam contração/redução da dívida líquida.

3. Tabelas Intermediárias 3 e 4 (Variação Relativa Interanual em %):
   - Medem a aceleração ou desaceleração do ritmo de variação da dívida em 
     comparação ao mesmo intervalo de 12 meses anteriores: [(Var_atual / Var_12m_antes) - 1] * 100.
   - Valores percentuais positivos indicam que a dívida cresceu em ritmo mais 
     acelerado do que no ano anterior.
   - Valores percentuais negativos indicam desaceleração no ritmo de crescimento 
     (entre -100% e 0%) ou reversão de trajetória de alta para queda (abaixo de -100%).
   - 'N/D' indica ausência de variação na base de comparação (divisão por zero).
================================================================================
"""
print(nota_explicativa)