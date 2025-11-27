# ==============================================================================
# 4.3. ABAS DO DASHBOARD
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs(['🎯 Visão Geral', '👤 Responsáveis', '🏆 Patrocínios', '📋 Dados Brutos'])

with tab1:
    st.header('Visão Geral')
    col_chart1, col_chart2 = st.columns(2)
    
    # Gráfico de Distribuição por Classificação (Pie Chart)
    with col_chart1:
        classificacao_counts = df_filtrado['CLASSIFICACAO'].value_counts().reset_index()
        classificacao_counts.columns = ['Classificacao', 'Contagem']
        fig = px.pie(classificacao_counts, values='Contagem', names='Classificacao', title='Distribuição por Classificação', hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    
    # Gráfico de Valor por Classificação (Bar Chart Horizontal)
    with col_chart2:
        valor_por_classificacao = df_filtrado.groupby('CLASSIFICACAO')['VALOR_CALCULADO'].sum().reset_index()
        valor_por_classificacao.columns = ['Classificacao', 'Valor']
        valor_por_classificacao_sorted = valor_por_classificacao.sort_values('Valor', ascending=True)

        fig = px.bar(
            valor_por_classificacao_sorted,
            x='Valor',
            y='Classificacao',
            orientation='h',
            title='Valor por Classificação'
        )
        fig.update_traces(
            text=valor_por_classificacao_sorted['Valor'].apply(formatar_moeda_br),
            textposition='outside',
            textfont=dict(color='black', size=11),
            marker_color='#28a745'
        )
        fig.update_layout(
            xaxis_title='Valor (R$)',
            yaxis_title='Classificação',
            showlegend=False,
            height=500,
            margin=dict(r=150, l=100)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Gráfico Top 10 Responsáveis por Valor Recebido
    top_responsaveis = df_filtrado.groupby('NOME')['VALOR_CALCULADO'].sum().nlargest(10).reset_index()
    top_responsaveis.columns = ['Responsavel', 'Valor']
    top_responsaveis_sorted = top_responsaveis.sort_values('Valor', ascending=True)
    
    fig = px.bar(
        top_responsaveis_sorted, 
        x='Valor', 
        y='Responsavel', 
        orientation='h', 
        title='Top 10 Responsáveis por Valor Recebido'
    )
    
    fig.update_traces(
        text=top_responsaveis_sorted['Valor'].apply(formatar_moeda_br),
        textposition='outside',
        textfont=dict(color='black', size=11),
        marker_color='#3498db'
    )
    
    fig.update_layout(
        xaxis_title='Valor (R$)',
        yaxis_title='Responsável',
        showlegend=False,
        height=500,
        margin=dict(r=150, l=120)
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header('Detalhes por Responsável')
    # Tabela de responsáveis
    resumo_filtrado = df_filtrado.groupby('NOME').agg(Mesas=('ORD', 'count'), Recebido=('VALOR_CALCULADO', 'sum')).reset_index()
    patrocinios_filtrado = df_filtrado[df_filtrado['CLASSIFICACAO'] == 'PATROCÍNIO'].groupby('NOME').size().reset_index(name='Patrocinios')
    resumo_filtrado = pd.merge(resumo_filtrado, patrocinios_filtrado, on='NOME', how='left').fillna(0)
    resumo_filtrado['Patrocinios'] = resumo_filtrado['Patrocinios'].astype(int)
    resumo_filtrado['Previsao'] = (resumo_filtrado['Mesas'] * 600) + (resumo_filtrado['Patrocinios'] * 400)
    resumo_filtrado['A_Receber'] = resumo_filtrado['Previsao'] - resumo_filtrado['Recebido']
    resumo_filtrado = resumo_filtrado.sort_values('Mesas', ascending=False)
    resumo_display = resumo_filtrado.copy()
    resumo_display['Recebido'] = resumo_display['Recebido'].apply(formatar_moeda_br)
    resumo_display['Previsao'] = resumo_display['Previsao'].apply(formatar_moeda_br)
    resumo_display['A_Receber'] = resumo_display['A_Receber'].apply(formatar_moeda_br)
    st.dataframe(
        resumo_display.rename(columns={'NOME': 'Responsável', 'Mesas': 'Mesas Dist.', 'Recebido': 'Total Recebido'}), 
        use_container_width=True, 
        hide_index=True
    )

with tab3:
    st.header('Análise de Patrocínios')
    
    df_patron = df_filtrado[df_filtrado['VALOR_CALCULADO'] >= 1000].copy()
    
    st.write(f'**Total de Patrocínios (VALOR >= 1000):** {len(df_patron)}')
    
    if len(df_patron) > 0:
        st.write(f'**Valor Total em Patrocínios:** {formatar_moeda_br(df_patron["VALOR_CALCULADO"].sum())}')
        
        # Tabela de Patrocínios
        patron_display = df_patron.copy()
        patron_display['MESA'] = patron_display['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
        patron_display['VALOR_CALCULADO'] = patron_display['VALOR_CALCULADO'].apply(formatar_moeda_br)
        
        st.subheader('📋 Lista de Patrocínios')
        st.dataframe(
            patron_display[['ORD', 'MESA', 'NOME', 'Cliente', 'VALOR_CALCULADO']].rename(columns={'VALOR_CALCULADO': 'Valor Patrocínio'}),
            use_container_width=True,
            hide_index=True
        )
        
        # Seção de Patrocínios com Valor Extra
        patron_extra = df_patron[df_patron['VALOR_CALCULADO'] > 1000]
        if len(patron_extra) > 0:
            st.subheader('🎁 Patrocínios com Valor Extra (Acima de R$ 1.000)')
            patron_extra_display = patron_extra.copy()
            patron_extra_display['Valor Extra'] = patron_extra_display['VALOR_CALCULADO'] - 1000
            patron_extra_display['MESA'] = patron_extra_display['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
            patron_extra_display['VALOR_CALCULADO'] = patron_extra_display['VALOR_CALCULADO'].apply(formatar_moeda_br)
            patron_extra_display['Valor Extra'] = patron_extra_display['Valor Extra'].apply(formatar_moeda_br)
            
            st.dataframe(
                patron_extra_display[['ORD', 'MESA', 'NOME', 'Cliente', 'VALOR_CALCULADO', 'Valor Extra']].rename(columns={'VALOR_CALCULADO': 'Valor Total'}),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info('❌ Nenhum patrocínio encontrado com os filtros aplicados.')

with tab4:
    st.header('Dados Brutos')
    # Tabela de Dados Brutos com colunas específicas e renomeadas
    df_display = df_filtrado[['ORD', 'NOME', 'Cliente', 'MESA', 'VALOR_CALCULADO', 'CLASSIFICACAO', 'DATA_REC']].copy()
    df_display = df_display.reset_index(drop=True)
    df_display['MESA'] = df_display['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
    df_display['VALOR_CALCULADO'] = df_display['VALOR_CALCULADO'].apply(formatar_moeda_br)
    df_display = df_display.rename(columns={
        'VALOR_CALCULADO': 'VALOR',
        'CLASSIFICACAO': 'CLASSE',
        'DATA_REC': 'DATA'
    })
    
    # Exibe o DataFrame sem o índice padrão
    st.dataframe(df_display[['ORD', 'NOME', 'Cliente', 'MESA', 'VALOR', 'CLASSE', 'DATA']], use_container_width=True, hide_index=True)
    
    st.markdown('---')
    st.subheader('Opções de Download')
    
    # Botão para download CSV
    csv_data = df_filtrado.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(label='📥 Baixar CSV', data=csv_data, file_name=f'baile_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', mime='text/csv')
    
    # Botão para download PDF
    resumo_pdf = pd.DataFrame({'Métrica': ['Mesas', 'Pagas', 'Patrocínios', 'Total Recebido', 'Previsão', 'Saldo', 'Percentual'], 'Valor': [f'{len(df_filtrado)}', f'{len(df_filtrado[df_filtrado["CLASSIFICACAO"] == "MESA PAGA"])}', f'{total_patrocinios_filtrado}', formatar_moeda_br(total_recebido_filtrado), formatar_moeda_br(previsao_filtrada), formatar_moeda_br(saldo_a_receber_filtrado), f'{percentual_recebido_filtrado:.1f}%']})
    pdf_buffer = gerar_pdf_relatorio(df_filtrado, resumo_pdf)
    st.download_button(label='📄 Baixar PDF', data=pdf_buffer, file_name=f'baile_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf', mime='application/pdf')

# Rodapé do sidebar
st.sidebar.markdown('---')
st.sidebar.info(f'Dashboard Baile 2025 v4.3\n\n👤 Usuário: {st.session_state.usuario_atual}')
