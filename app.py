import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
warnings.filterwarnings('ignore')

# --- Configurações Globais ---
GOOGLE_SHEETS_ID = '1bKyxuaOkGHKkVx2e5gdYISMi7zckmyjy'
SHEET_NAME = 'Mesas'

st.set_page_config(
    page_title='Dashboard Baile 2025',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded'
)

# --- Funções Auxiliares ---
def formatar_moeda_br(valor):
    """Formata um valor numérico para o formato de moeda brasileira (R$ X.XXX,XX)."""
    if pd.isna(valor):
        return 'R$ 0,00'
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def classificar_mesa(row):
    """Classifica a mesa com base no valor."""
    valor = row['VALOR']
    if pd.isna(valor) or valor == 0:
        return 'PENDENTE'
    elif valor == 600:
        return 'MESA PAGA'
    elif valor == 300:
        return 'MEIA ENTRADA'
    elif valor >= 1000:
        return 'PATROCÍNIO'
    else:
        return 'OUTRO'

@st.cache_data(show_spinner=False)
def carregar_e_processar_dados():
    """
    Carrega os dados do Google Sheets, processa e calcula as métricas.
    Retorna o DataFrame limpo e todas as métricas calculadas.
    """
    try:
        url = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/export?format=xlsx'
        df = pd.read_excel(url, sheet_name=SHEET_NAME, header=3)
        
        # Limpeza inicial
        df = df.dropna(axis=1, how='all') # Remove colunas totalmente vazias
        df = df.dropna(how='all')        # Remove linhas totalmente vazias
        df.columns = df.columns.str.strip() # Remove espaços em branco dos nomes das colunas
        
        # Seleciona colunas desejadas e cria cópia para evitar SettingWithCopyWarning
        colunas_desejadas = ['ORD', 'NOME', 'Cliente', 'MESA', 'VALOR', 'DATA_REC']
        df_limpo = df[colunas_desejadas].copy()
        
        # Conversão de tipos e tratamento de NaNs
        df_limpo['ORD'] = pd.to_numeric(df_limpo['ORD'], errors='coerce')
        df_limpo['MESA'] = pd.to_numeric(df_limpo['MESA'], errors='coerce')
        df_limpo = df_limpo[df_limpo['ORD'].notna()].copy() # Remove linhas com ORD NaN
        
        df_limpo['VALOR'] = pd.to_numeric(df_limpo['VALOR'], errors='coerce')
        df_limpo['VALOR_CALCULADO'] = df_limpo['VALOR'].fillna(0) # Valor para cálculos
        
        df_limpo['NOME'] = df_limpo['NOME'].fillna('-')
        df_limpo['Cliente'] = df_limpo['Cliente'].fillna('-')
        df_limpo['MESA'] = df_limpo['MESA'].fillna(-1) # -1 para mesas não atribuídas
        df_limpo['DATA_REC'] = df_limpo['DATA_REC'].fillna('-')
        
        # Aplica classificação
        df_limpo['CLASSIFICACAO'] = df_limpo.apply(classificar_mesa, axis=1)
        
        # --- Cálculos de Métricas Globais ---
        TOTAL_ATUALMENTE_ESPERADO = int(df_limpo['ORD'].max()) if not df_limpo.empty else 0
        
        ord_distribuidos = sorted(df_limpo['ORD'].astype(int).unique()) if not df_limpo.empty else []
        mesas_esperadas = set(range(1, TOTAL_ATUALMENTE_ESPERADO + 1))
        ord_faltantes = sorted(mesas_esperadas - set(ord_distribuidos))
        
        df_patrocinios = df_limpo[df_limpo['CLASSIFICACAO'] == 'PATROCÍNIO'].copy()
        total_patrocinios = len(df_patrocinios)
        valor_patrocinios_total = df_patrocinios['VALOR_CALCULADO'].sum()
        valor_patrocinios_extra = valor_patrocinios_total - (total_patrocinios * 1000)
        
        mesas_pagas = len(df_limpo[df_limpo['CLASSIFICACAO'] == 'MESA PAGA'])
        total_mesas_pagas = df_limpo[df_limpo['CLASSIFICACAO'] == 'MESA PAGA']['VALOR_CALCULADO'].sum()
        meia_entrada = len(df_limpo[df_limpo['CLASSIFICACAO'] == 'MEIA ENTRADA'])
        total_meia_entrada = df_limpo[df_limpo['CLASSIFICACAO'] == 'MEIA ENTRADA']['VALOR_CALCULADO'].sum()
        mesas_pendentes_com_dados = len(df_limpo[df_limpo['CLASSIFICACAO'] == 'PENDENTE'])
        total_mesas_pendentes = mesas_pendentes_com_dados + len(ord_faltantes)
        
        total_recebido = df_limpo[df_limpo['VALOR_CALCULADO'] > 0]['VALOR_CALCULADO'].sum()
        previsao = (TOTAL_ATUALMENTE_ESPERADO * 600) + (total_patrocinios * 400) # 600 por mesa + 400 extra por patrocínio
        saldo_a_receber = previsao - total_recebido
        
        # --- Resumo por Responsável ---
        resumo_responsavel = df_limpo.groupby('NOME').agg(
            Mesas_Distribuidas=('ORD', 'count'),
            Total_Recebido=('VALOR_CALCULADO', 'sum')
        ).reset_index()
        
        patrocinios_por_responsavel = df_limpo[df_limpo['CLASSIFICACAO'] == 'PATROCÍNIO'].groupby('NOME').size().reset_index(name='Patrocinios')
        resumo_responsavel = pd.merge(resumo_responsavel, patrocinios_por_responsavel, on='NOME', how='left').fillna(0)
        resumo_responsavel['Patrocinios'] = resumo_responsavel['Patrocinios'].astype(int)
        
        resumo_responsavel['Previsao_por_Responsavel'] = (resumo_responsavel['Mesas_Distribuidas'] * 600) + (resumo_responsavel['Patrocinios'] * 400)
        resumo_responsavel['A_Receber'] = resumo_responsavel['Previsao_por_Responsavel'] - resumo_responsavel['Total_Recebido']
        resumo_responsavel = resumo_responsavel.sort_values('Mesas_Distribuidas', ascending=False)
        
        # Versão formatada para exibição
        resumo_responsavel_display = resumo_responsavel.copy()
        resumo_responsavel_display['Total_Recebido'] = resumo_responsavel_display['Total_Recebido'].apply(formatar_moeda_br)
        resumo_responsavel_display['A_Receber'] = resumo_responsavel_display['A_Receber'].apply(formatar_moeda_br)
        resumo_responsavel_display['Previsao_por_Responsavel'] = resumo_responsavel_display['Previsao_por_Responsavel'].apply(formatar_moeda_br)
        
        return df_limpo, TOTAL_ATUALMENTE_ESPERADO, ord_faltantes, df_patrocinios, total_patrocinios, valor_patrocinios_total, valor_patrocinios_extra, mesas_pagas, total_mesas_pagas, meia_entrada, total_meia_entrada, mesas_pendentes_com_dados, total_mesas_pendentes, total_recebido, previsao, saldo_a_receber, resumo_responsavel, resumo_responsavel_display
    except Exception as e:
        st.error(f'❌ Erro ao carregar ou processar o arquivo: {e}')
        return None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None

def gerar_pdf_relatorio(df_filtrado, resumo_exec, resumo_responsavel_display_pdf):
    """Gera um relatório PDF com base nos dados filtrados."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    # Estilos personalizados
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1a1a1a'), spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#666666'), alignment=TA_CENTER)
    header2_style = ParagraphStyle('Header2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#2c3e50'), spaceBefore=12, spaceAfter=6)
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)

    # Título e data
    elements.append(Paragraph('BAILE 2025 - RELATÓRIO FILTRADO', title_style))
    elements.append(Spacer(1, 0.2*inch))
    data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')
    elements.append(Paragraph(f'Gerado em: {data_geracao}', subtitle_style))
    elements.append(Spacer(1, 0.3*inch))

    # Resumo Executivo
    elements.append(Paragraph('📊 RESUMO EXECUTIVO', header2_style))
    elements.append(Spacer(1, 0.1*inch))
    resumo_data = [['Métrica', 'Valor']]
    for _, row in resumo_exec.iterrows():
        resumo_data.append([str(row.get('Métrica', '')), str(row.get('Valor', ''))])
    resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
    ]))
    elements.append(resumo_table)
    elements.append(Spacer(1, 0.3*inch))

    # Tabela de Responsáveis
    elements.append(Paragraph('👤 TODOS OS RESPONSÁVEIS', header2_style))
    elements.append(Spacer(1, 0.1*inch))
    if not resumo_responsavel_display_pdf.empty:
        responsaveis_data = [['Responsável', 'Mesas Dist.', 'Total Recebido', 'A Receber', 'Previsão', 'Patrocínios']]
        for idx, row in resumo_responsavel_display_pdf.iterrows():
            responsaveis_data.append([
                str(row.get('NOME', '-'))[:40],
                str(row.get('Mesas_Distribuidas', '0')),
                row.get('Total_Recebido', 'R$ 0,00'),
                row.get('A_Receber', 'R$ 0,00'),
                row.get('Previsao_por_Responsavel', 'R$ 0,00'),
                str(row.get('Patrocinios', '0'))
            ])
        responsaveis_table = Table(responsaveis_data, colWidths=[2.2*inch, 0.6*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
        responsaveis_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'), # Alinha nome do responsável à esquerda
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        elements.append(responsaveis_table)
    else:
        elements.append(Paragraph('Nenhum responsável encontrado com os filtros aplicados.', styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(PageBreak()) # Quebra de página para dados brutos

    # Dados Brutos Filtrados
    elements.append(Paragraph('📋 DADOS BRUTOS FILTRADOS', header2_style))
    elements.append(Spacer(1, 0.1*inch))
    if not df_filtrado.empty:
        df_pdf = df_filtrado[['ORD', 'NOME', 'Cliente', 'MESA', 'VALOR', 'CLASSIFICACAO', 'DATA_REC']].copy()
        df_pdf['MESA'] = df_pdf['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
        df_pdf['VALOR'] = df_pdf['VALOR'].apply(formatar_moeda_br)
        data_bruta = [df_pdf.columns.tolist()] + df_pdf.values.tolist()
        col_widths = [0.5*inch, 1.5*inch, 1.5*inch, 0.6*inch, 0.8*inch, 1*inch, 0.8*inch]
        table_bruta = Table(data_bruta, colWidths=col_widths)
        table_bruta.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'), # NOME alinhado à esquerda
            ('ALIGN', (2, 1), (2, -1), 'LEFT'), # Cliente alinhado à esquerda
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        elements.append(table_bruta)
    else:
        elements.append(Paragraph('Nenhum dado encontrado.', styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))

    # Rodapé
    elements.append(Paragraph('Relatório gerado automaticamente - Dashboard Baile 2025 v4.2', footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- Carregamento e Processamento Principal ---
with st.spinner('Carregando dados...'):
    df_limpo, TOTAL_ATUALMENTE_ESPERADO, ord_faltantes, df_patrocinios, total_patrocinios, valor_patrocinios_total, valor_patrocinios_extra, mesas_pagas, total_mesas_pagas, meia_entrada, total_meia_entrada, mesas_pendentes_com_dados, total_mesas_pendentes, total_recebido, previsao, saldo_a_receber, resumo_responsavel, resumo_responsavel_display = carregar_e_processar_dados()

if df_limpo is None:
    st.stop() # Para a execução se houver erro no carregamento dos dados
else:
    # --- Inicialização do Session State para Filtros ---
    if 'classificacao_selecionada' not in st.session_state:
        st.session_state.classificacao_selecionada = df_limpo['CLASSIFICACAO'].unique().tolist()
    if 'responsavel_selecionado' not in st.session_state:
        st.session_state.responsavel_selecionado = 'Todos'
    if 'valor_range' not in st.session_state:
        min_val = float(df_limpo['VALOR_CALCULADO'].min()) if not df_limpo.empty else 0.0
        max_val = float(df_limpo['VALOR_CALCULADO'].max()) if not df_limpo.empty else 0.0
        st.session_state.valor_range = (min_val, max_val)
    
    # --- Sidebar de Filtros ---
    st.sidebar.header('Filtros')
    if st.sidebar.button('Resetar Filtros'):
        st.session_state.clear()
        st.rerun() # Reinicia o app para aplicar o reset
    
    todas_classificacoes = df_limpo['CLASSIFICACAO'].unique().tolist()
    classificacao_selecionada = st.sidebar.multiselect(
        'Filtrar por Classificação:', 
        options=todas_classificacoes, 
        default=st.session_state.classificacao_selecionada, 
        key='classificacao_multiselect'
    )
    st.session_state.classificacao_selecionada = classificacao_selecionada
    
    todos_responsaveis = ['Todos'] + sorted(df_limpo['NOME'].unique().tolist())
    responsavel_selecionado = st.sidebar.selectbox(
        'Filtrar por Responsável:', 
        options=todos_responsaveis, 
        index=todos_responsaveis.index(st.session_state.responsavel_selecionado) if st.session_state.responsavel_selecionado in todos_responsaveis else 0, 
        key='responsavel_selectbox'
    )
    st.session_state.responsavel_selecionado = responsavel_selecionado
    
    min_valor_df = float(df_limpo['VALOR_CALCULADO'].min()) if not df_limpo.empty else 0.0
    max_valor_df = float(df_limpo['VALOR_CALCULADO'].max()) if not df_limpo.empty else 0.0
    valor_range = st.sidebar.slider(
        'Filtrar por Faixa de Valor (R$):', 
        min_value=min_valor_df, 
        max_value=max_valor_df, 
        value=st.session_state.valor_range, 
        step=50.0, 
        format='R$ %.2f', 
        key='valor_slider'
    )
    st.session_state.valor_range = valor_range
    
    # --- Aplicação dos Filtros ---
    df_filtrado = df_limpo[df_limpo['CLASSIFICACAO'].isin(classificacao_selecionada)]
    if responsavel_selecionado != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['NOME'] == responsavel_selecionado]
    df_filtrado = df_filtrado[(df_filtrado['VALOR_CALCULADO'] >= valor_range[0]) & (df_filtrado['VALOR_CALCULADO'] <= valor_range[1])]
    
    # --- Recálculo de Métricas com Filtros ---
    total_recebido_filtrado = df_filtrado[df_filtrado['VALOR_CALCULADO'] > 0]['VALOR_CALCULADO'].sum()
    total_patrocinios_filtrado = len(df_filtrado[df_filtrado['CLASSIFICACAO'] == 'PATROCÍNIO'])
    previsao_filtrada = (len(df_filtrado) * 600) + (total_patrocinios_filtrado * 400)
    saldo_a_receber_filtrado = previsao_filtrada - total_recebido_filtrado
    percentual_recebido_filtrado = (total_recebido_filtrado / previsao_filtrada * 100) if previsao_filtrada > 0 else 0
    
    # --- Layout Principal do Dashboard ---
    st.title('📊 Dashboard Baile 2025')
    st.markdown(f'Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}')
    
    # Métricas no Topo
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label='Total Recebido', value=formatar_moeda_br(total_recebido_filtrado))
    with col2:
        st.metric(label='Previsão', value=formatar_moeda_br(previsao_filtrada))
    with col3:
        st.metric(label='Saldo a Receber', value=formatar_moeda_br(saldo_a_receber_filtrado))
    with col4:
        st.metric(label='Percentual', value=f'{percentual_recebido_filtrado:.1f}%')
    
    st.markdown('---')
    
    # Abas
    tab1, tab2, tab3, tab4 = st.tabs(['🎯 Visão Geral', '👤 Responsáveis', '🏆 Patrocínios', '📋 Dados Brutos'])
    
    with tab1:
        st.header('Visão Geral')
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader('Distribuição por Classificação')
            classificacao_counts = df_filtrado['CLASSIFICACAO'].value_counts().reset_index()
            classificacao_counts.columns = ['Classificacao', 'Contagem']
            fig_classificacao = px.pie(classificacao_counts, values='Contagem', names='Classificacao', title='Distribuição de Mesas por Classificação', hole=0.3, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_classificacao, use_container_width=True)
        
        with col_chart2:
            st.subheader('Valor Recebido por Classificação')
            valor_por_classificacao = df_filtrado.groupby('CLASSIFICACAO')['VALOR_CALCULADO'].sum().reset_index()
            valor_por_classificacao.columns = ['Classificacao', 'Valor']
            fig_valor_classificacao = px.bar(valor_por_classificacao.sort_values('Valor', ascending=True), x='Valor', y='Classificacao', orientation='h', title='Valor Total Recebido por Classificação', color='Classificacao', color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_valor_classificacao.update_layout(xaxis_title='Valor (R$)', yaxis_title='Classificação')
            st.plotly_chart(fig_valor_classificacao, use_container_width=True)
        
        st.subheader('Top 10 Responsáveis por Valor Recebido')
        top_responsaveis = df_filtrado.groupby('NOME')['VALOR_CALCULADO'].sum().nlargest(10).reset_index()
        top_responsaveis.columns = ['Responsavel', 'Valor']
        top_responsaveis_sorted = top_responsaveis.sort_values('Valor', ascending=True)

        fig_top_responsaveis = px.bar(
            top_responsaveis_sorted, 
            x='Valor', 
            y='Responsavel', 
            orientation='h', 
            title='Top 10 Responsáveis por Valor Recebido',
            color='Responsavel', # Adiciona cor por responsável
            color_discrete_sequence=px.colors.qualitative.Vivid # Paleta de cores
        )

        fig_top_responsaveis.update_traces(
            text=top_responsaveis_sorted['Valor'].apply(formatar_moeda_br),
            textposition='outside', # Valores fora das barras
            marker_color='#3498db' # Cor das barras
        )

        fig_top_responsaveis.update_layout(
            xaxis_title='Valor (R$)',
            yaxis_title='Responsável',
            showlegend=False, # Não mostra legenda de cores se for por responsável
            height=500
        )
        st.plotly_chart(fig_top_responsaveis, use_container_width=True)
    
    with tab2:
        st.header('Detalhes por Responsável')
        # Recalcula resumo_responsavel_display com base nos filtros
        resumo_responsavel_filtrado = df_filtrado.groupby('NOME').agg(
            Mesas_Distribuidas=('ORD', 'count'),
            Total_Recebido=('VALOR_CALCULADO', 'sum')
        ).reset_index()
        
        patrocinios_por_responsavel_filtrado = df_filtrado[df_filtrado['CLASSIFICACAO'] == 'PATROCÍNIO'].groupby('NOME').size().reset_index(name='Patrocinios')
        resumo_responsavel_filtrado = pd.merge(resumo_responsavel_filtrado, patrocinios_por_responsavel_filtrado, on='NOME', how='left').fillna(0)
        resumo_responsavel_filtrado['Patrocinios'] = resumo_responsavel_filtrado['Patrocinios'].astype(int)
        
        resumo_responsavel_filtrado['Previsao_por_Responsavel'] = (resumo_responsavel_filtrado['Mesas_Distribuidas'] * 600) + (resumo_responsavel_filtrado['Patrocinios'] * 400)
        resumo_responsavel_filtrado['A_Receber'] = resumo_responsavel_filtrado['Previsao_por_Responsavel'] - resumo_responsavel_filtrado['Total_Recebido']
        resumo_responsavel_filtrado = resumo_responsavel_filtrado.sort_values('Mesas_Distribuidas', ascending=False)
        
        resumo_responsavel_display_filtrado = resumo_responsavel_filtrado.copy()
        resumo_responsavel_display_filtrado['Total_Recebido'] = resumo_responsavel_display_filtrado['Total_Recebido'].apply(formatar_moeda_br)
        resumo_responsavel_display_filtrado['A_Receber'] = resumo_responsavel_display_filtrado['A_Receber'].apply(formatar_moeda_br)
        resumo_responsavel_display_filtrado['Previsao_por_Responsavel'] = resumo_responsavel_display_filtrado['Previsao_por_Responsavel'].apply(formatar_moeda_br)
        
        st.dataframe(
            resumo_responsavel_display_filtrado.rename(columns={
                'NOME': 'Responsável', 
                'Mesas_Distribuidas': 'Mesas Distribuídas', 
                'Total_Recebido': 'Total Recebido', 
                'A_Receber': 'A Receber', 
                'Previsao_por_Responsavel': 'Previsão por Responsável', 
                'Patrocinios': 'Patrocínios'
            }), 
            use_container_width=True
        )
    
    with tab3:
        st.header('Análise de Patrocínios')
        
        # Filtrar patrocínios do DataFrame filtrado
        df_patron = df_filtrado[df_filtrado['VALOR_CALCULADO'] >= 1000].copy()
        
        st.write(f'**Total de Patrocínios (VALOR >= 1000):** {len(df_patron)}')
        
        if len(df_patron) > 0:
            st.write(f'**Valor Total em Patrocínios:** {formatar_moeda_br(df_patron["VALOR_CALCULADO"].sum())}')
            
            # Mostrar tabela de patrocínios
            patron_display = df_patron.copy()
            patron_display['MESA'] = patron_display['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
            patron_display['VALOR_CALCULADO'] = patron_display['VALOR_CALCULADO'].apply(formatar_moeda_br)
            
            st.subheader('📋 Lista de Patrocínios')
            st.dataframe(
                patron_display[['ORD', 'MESA', 'NOME', 'Cliente', 'VALOR_CALCULADO']].rename(columns={'VALOR_CALCULADO': 'Valor Patrocínio'}),
                use_container_width=True
            )
            
            # Mostrar patrocínios com valores acima de 1000
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
                    use_container_width=True
                )
        else:
            st.info('❌ Nenhum patrocínio encontrado com os filtros aplicados.')
    
    with tab4:
        st.header('Dados Brutos')
        df_display = df_filtrado.copy()
        df_display['MESA'] = df_display['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
        df_display['VALOR_CALCULADO'] = df_display['VALOR_CALCULADO'].apply(formatar_moeda_br)
        st.dataframe(df_display, use_container_width=True)
        
        st.markdown('---')
        st.subheader('Opções de Download')
        
        # Download CSV
        csv_data = df_filtrado.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label='📥 Baixar CSV Filtrado', 
            data=csv_data, 
            file_name=f'relatorio_baile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv', 
            mime='text/csv'
        )
        
        # Download PDF
        resumo_exec_pdf = pd.DataFrame({
            'Métrica': ['Mesas', 'Pagas', 'Patrocínios', 'Total Recebido', 'Previsão', 'Saldo', 'Percentual'], 
            'Valor': [
                f'{len(df_filtrado)}', 
                f'{len(df_filtrado[df_filtrado["CLASSIFICACAO"] == "MESA PAGA"])}', 
                f'{total_patrocinios_filtrado}', 
                formatar_moeda_br(total_recebido_filtrado), 
                formatar_moeda_br(previsao_filtrada), 
                formatar_moeda_br(saldo_a_receber_filtrado), 
                f'{percentual_recebido_filtrado:.1f}%'
            ]
        })
        pdf_buffer = gerar_pdf_relatorio(df_filtrado, resumo_exec_pdf, resumo_responsavel_display_filtrado)
        st.download_button(
            label='📄 Baixar PDF Filtrado', 
            data=pdf_buffer, 
            file_name=f'relatorio_baile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf', 
            mime='application/pdf'
        )

st.sidebar.markdown('---')
st.sidebar.info('Dashboard Baile 2025 v4.2')
