# -- coding: utf-8 --

import funcoes2 as funcoes


def main():
    periodo_atual = funcoes.PERIODO_SIDRA

    while True:
        print("\n" + "=" * 73)
        print("MENU DE TABELAS DO PIB (IBGE)".center(73))
        print(f"Fonte: SIDRA/IBGE | Período: {periodo_atual}".center(73))
        print("=" * 73)
        print("1 - Tabela por Trimestre (tabela_pib)")
        print("2 - Tabela Soma por Ano (soma_ano)")
        print("3 - Tabela Soma de 4 em 4 Trimestres (soma_4t)")
        print("4 - Tabela Diferença 1º Semestre vs Anteriores (diferenca_semestres)")
        print("5 - Tabela Comparação de Trimestres Escolhidos (comparar_trimestres)")
        print("6 - Alterar período da consulta SIDRA (ex: last 24, all, 202001-202602)")
        print("7 - Atualizar dados agora (limpar cache e consultar API)")
        print("0 - Sair")
        print("=" * 73)

        escolha = input("Digite o número da opção desejada: ").strip()

        try:
            if escolha == '1':
                print("\n--- TABELA POR TRIMESTRE ---")
                print(funcoes.tabela_pib(periodo=periodo_atual))

            elif escolha == '2':
                print("\n--- TABELA SOMA POR ANO ---")
                print(funcoes.soma_ano(periodo=periodo_atual))

            elif escolha == '3':
                print("\n--- TABELA SOMA DE 4 EM 4 TRIMESTRES ---")
                print(funcoes.soma_4t(periodo=periodo_atual))

            elif escolha == '4':
                print("\n--- TABELA DIFERENÇA DE SEMESTRES ---")
                ano_digitado = input(
                    "Digite o ano de referência (ou pressione Enter para o mais recente): "
                ).strip()
                ano_ref = ano_digitado if ano_digitado else None
                print(funcoes.diferenca_semestres(ano_ref=ano_ref, periodo=periodo_atual))

            elif escolha == '5':
                print("\n--- TABELA COMPARAÇÃO DE TRIMESTRES ---")
                print(funcoes.comparar_trimestres(periodo=periodo_atual))

            elif escolha == '6':
                print(f"\nPeríodo atual: {periodo_atual}")
                print("Exemplos válidos no SIDRA: 'last 24', 'last 12', 'all', '202001-202602'")
                novo_periodo = input(
                    "Digite o novo período (ou pressione Enter para cancelar): "
                ).strip()
                if novo_periodo:
                    print(f"Carregando dados do SIDRA para o período '{novo_periodo}'...")
                    funcoes.carregar_dados_pib(periodo=novo_periodo)
                    periodo_atual = novo_periodo
                    print(f"Período atualizado com sucesso para: {periodo_atual}")
                else:
                    print("Alteração de período cancelada.")

            elif escolha == '7':
                print(f"\nConsultando API do SIDRA para atualizar o período '{periodo_atual}'...")
                funcoes.carregar_dados_pib(periodo=periodo_atual, forcar_atualizacao=True)
                print("Dados atualizados com sucesso!")

            elif escolha == '0':
                print("Saindo...")
                break

            else:
                print("Opção inválida! Escolha de 0 a 7.")

        except Exception as erro:
            print(f"\nErro ao consultar ou processar os dados do SIDRA: {erro}")
            print("Verifique sua conexão com a internet ou se o período informado é válido.")


if _name_ == '_main_':
    main()