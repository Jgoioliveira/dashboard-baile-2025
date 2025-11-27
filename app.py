# SEÇÃO 4.3 - TAB1 (Visão Geral) - Gráfico Horizontal CORRIGIDO
with tab1:
    st.header('Visão Geral')
    col_chart1, col_chart2 = st.columns(2)
    
    # Gráfico de Distribuição por Classificação (Pie Chart)
    with col_chart1:
        classificacao_counts = df_filtrado['CLASSIFICACAO'].value_counts().reset_index()
        classificacao_counts.columns = ['Classificacao', 'Contagem']
        fig = px.pie(classificacao_counts, values='Contagem', names='Classificacao', title='Distribuição por Classificação', hole=0.3)
        st.plotly_chart(fig, use_container_width=True)
    
    # Gráfico de Valor por Classificação (Bar Chart Horizontal) - CORRIGIDO
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
            textfont=dict(color='black', size=12),
            marker_color='#28a745'
        )
        
        fig.update_layout(
            xaxis_title='Valor (R$)',
            yaxis_title='Classificação',
            showlegend=False,
            height=500,
            margin=dict(r=200)  # ADICIONE: Aumenta a margem direita para o texto não ser cortado
        )
        
        st.plotly_chart(fig, use_container_width=True)
