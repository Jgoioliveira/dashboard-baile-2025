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

# ==============================================================================
# 1. CONFIGURAÇÕES GLOBAIS E CREDENCIAIS
# ==============================================================================

# ID da planilha do Google Sheets e nome da aba
GOOGLE_SHEETS_ID = '1bKyxuaOkGHKkVx2e5gdYISMi7zckmyjy'
SHEET_NAME = 'Mesas'

# Credenciais de login para autenticação
USUARIOS_PERMITIDOS = {
    'baile': 'baile2025',  # usuario: baile, senha: baile2025
    'jorge': 'jorge123',    # usuario: jorge, senha: jorge123
    'admin': 'admin2025'    # usuario: admin, senha: admin2025
}

# Configuração da página Streamlit
st.set_page_config(
    page_title='Dashboard Baile 2025',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded'
)

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

def formatar_moeda_br(valor):
    """Formata um valor numérico para o padrão de moeda brasileira (R$ X.XXX,XX)."""
    if pd.isna(valor):
        return 'R$ 0,00'
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def classificar_mesa(row):
    """Classifica uma mesa com base no seu valor."""
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

def carregar_e_processar_dados():
    """
    Carrega os dados da planilha do Google Sheets, limpa e processa-os.
    Retorna o DataFrame processado e métricas importantes.
    NÃO POSSUI CACHE - ATUALIZA SEMPRE!
    """
    try:
        url = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/export?format=xlsx'
        df = pd.read_excel(url, sheet_name=SHEET_NAME, header=3)
        
        # Limpeza inicial: remover colunas e linhas totalmente vazias
        df = df.dropna(axis=1, how='all')
        df = df.dropna(how='all')
        df.columns = df.columns.str.strip() # Remover espaços em branco dos nomes das colunas
        
        # Selecionar colunas desejadas para evitar dados extras
        colunas_desejadas = ['ORD', 'NOME', 'Cliente', 'MESA', 'VALOR', 'DATA_REC']
        df_limpo = df[colunas_desejadas].copy()
        
        # Converter tipos de dados e tratar valores ausentes
        df_limpo['ORD'] = pd.to_numeric(df_limpo['ORD'], errors='coerce')
        df_limpo['MESA'] = pd.to_numeric(df_limpo['MESA'], errors='coerce')
        df_limpo = df_limpo[df_limpo['ORD'].notna()].copy() # Remover linhas sem ORD
        
        df_limpo['VALOR'] = pd.to_numeric(df_limpo['VALOR'], errors='coerce')
        df_limpo['VALOR_CALCULADO'] = df_limpo['VALOR'].fillna(0) # Usar 0 para valores nulos de VALOR
        
        # Preencher valores ausentes em colunas de texto/identificação
        df_limpo['NOME'] = df_limpo['NOME'].fillna('-')
        df_limpo['Cliente'] = df_limpo['Cliente'].fillna('-')
        df_limpo['MESA'] = df_limpo['MESA'].fillna(-1) # -1 para mesas não atribuídas
        df_limpo['DATA_REC'] = df_limpo['DATA_REC'].fillna('-')
        
        # Aplicar classificação das mesas
        df_limpo['CLASSIFICACAO'] = df_limpo.apply(classificar_mesa, axis=1)
        
        # Calcular métricas gerais
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
        previsao = (TOTAL_ATUALMENTE_ESPERADO * 600) + (total_patrocinios * 400)
        saldo_a_receber = previsao - total_recebido
        
        # Resumo por responsável
        resumo_responsavel = df_limpo.groupby('NOME').agg(Mesas_Distribuidas=('ORD', 'count'), Total_Recebido=('VALOR_CALCULADO', 'sum')).reset_index()
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
        st.error(f'❌ Erro ao carregar os dados: {e}')
        return None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None

def gerar_pdf_relatorio(df_filtrado, resumo_exec):
    """Gera um relatório em PDF com os dados filtrados e um resumo executivo."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados para o PDF
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1a1a1a'), spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('CustomSubtitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#666666'), alignment=TA_CENTER)
    header2_style = ParagraphStyle('Header2', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor('#2c3e50'), spaceBefore=12, spaceAfter=6)
    normal_style = styles['Normal']
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#999999'), alignment=TA_CENTER)

    # Título e data de geração
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

    # Dados Brutos Filtrados
    elements.append(Paragraph('📋 DADOS BRUTOS FILTRADOS', header2_style))
    elements.append(Spacer(1, 0.1*inch))
    if not df_filtrado.empty:
        df_pdf = df_filtrado[['ORD', 'NOME', 'Cliente', 'MESA', 'VALOR_CALCULADO', 'CLASSIFICACAO', 'DATA_REC']].copy()
        df_pdf['MESA'] = df_pdf['MESA'].apply(lambda x: str(int(x)) if x != -1 else '-')
        df_pdf['VALOR_CALCULADO'] = df_pdf['VALOR_CALCULADO'].apply(formatar_moeda_br)
        df_pdf = df_pdf.rename(columns={
            'VALOR_CALCULADO': 'VALOR',
            'CLASSIFICACAO': 'CLASSE',
            'DATA_REC': 'DATA'
        })
        data_bruta = [df_pdf.columns.tolist()] + df_pdf.values.tolist()
        col_widths = [0.5*inch, 1.5*inch, 1.5*inch, 0.6*inch, 0.8*inch, 1*inch, 0.8*inch]
        table_bruta = Table(data_bruta, colWidths=col_widths)
        table_bruta.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'), # Alinhar NOME à esquerda
            ('ALIGN', (2, 1), (2, -1), 'LEFT'), # Alinhar Cliente à esquerda
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
        elements.append(Paragraph('Nenhum dado encontrado com os filtros aplicados.', normal_style))
    elements.append(Spacer(1, 0.3*inch))

    # Rodapé
    elements.append(Paragraph('Relatório gerado automaticamente - Dashboard Baile 2025 v4.3', footer_style))
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 3. FUNÇÕES DE AUTENTICAÇÃO
# ==============================================================================

def verificar_senha(usuario, senha):
    """Verifica se o usuário e senha fornecidos correspondem às credenciais permitidas."""
    return usuario in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[usuario] == senha

def tela_login():
    """Exibe a tela de login para o usuário."""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #2c3e50;'>🎭 BAILE 2025</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #7f8c8d;'>Dashboard de Controle</h3>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.write("")
        st.write("")
        
        usuario = st.text_input("👤 Usuário:", placeholder="Digite seu usuário")
        senha = st.text_input("🔐 Senha:", type="password", placeholder="Digite sua senha")
        
        st.write("")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔓 Entrar", use_container_width=True):
                if usuario and senha:
                    if verificar_senha(usuario, senha):
                        st.session_state.autenticado = True
                        st.session_state.usuario_atual = usuario
                        st.success(f"✅ Bem-vindo, {usuario}!")
                        st.rerun() # Recarrega a página para mostrar o dashboard
                    else:
                        st.error("❌ Usuário ou senha incorretos!")
                else:
                    st.warning("⚠️ Digite usuário e senha!")
        
        with col_btn2:
            if st.button("ℹ️ Ver Credenciais", use_container_width=True):
                st.info("""
                **Credenciais de Teste:**
                
                👤 Usuário: **baile**
                🔐 Senha: **baile2025**
                
                ---
                
                👤 Usuário: **jorge**
                🔐 Senha: **jorge123**
                
                ---
                
                👤 Usuário: **admin**
                🔐 Senha: **admin2025**
                """)
        
        st.write("")
        st.write("")
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #95a5a6; font-size: 12px;'>Dashboard Baile 2025 v4.3 - Protegido por Senha</p>", unsafe_allow_html=True)

# ==============================================================================
# 4. LÓGICA PRINCIPAL DO APP STREAMLIT
# ==============================================================================

# Inicializa o estado de autenticação
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# Se não estiver autenticado, mostra a tela de login
if not st.session_state.autenticado:
    tela_login()
else:
    # Se autenticado, carrega os dados e exibe o dashboard
    with st.spinner('Carregando dados...'):
        resultado = carregar_e_processar_dados()
        if resultado[0] is None:
            st.error('Não foi possível carregar os dados. Verifique a conexão com a planilha.')
        else:
            df_limpo, TOTAL_ATUALMENTE_ESPERADO, ord_faltantes, df_patrocinios, total_patrocinios, valor_patrocinios_total, valor_patrocinios_extra, mesas_pagas, total_mesas_pagas, meia_entrada, total_meia_entrada, mesas_pendentes_com_dados, total_mesas_pendentes, total_recebido, previsao, saldo_a_receber, resumo_responsavel, resumo_responsavel_display = resultado
            
            # Inicializa estados dos filtros se não existirem
            if 'classificacao_selecionada' not in st.session_state:
                st.session_state.classificacao_selecionada = df_limpo['CLASSIFICACAO'].unique().tolist()
            if 'responsavel_selecionado' not in st.session_state:
                st.session_state.responsavel_selecionado = 'Todos'
            if 'valor_range' not in st.session_state:
                min_val = float(df_limpo['VALOR_CALCULADO'].min()) if not df_limpo.empty else 0.0
                max_val = float(df_limpo['VALOR_CALCULADO'].max()) if not df_limpo.empty else 1000.0
                st.session_state.valor_range = (min_val, max_val)
            
            # ==============================================================================
            # 4.1. SIDEBAR E FILTROS
            # ==============================================================================
            st.sidebar.header('Filtros')
            
            # Botões de Logout e Resetar Filtros
            col_logout, col_reset = st.sidebar.columns(2)
            with col_logout:
                if st.button('🚪 Sair', use_container_width=True):
                    st.session_state.autenticado = False
                    st.session_state.usuario_atual = None
                    st.rerun()
            with col_reset:
                if st.button('Resetar Filtros', use_container_width=True):
                    st.session_state.clear()
                    st.rerun()
            
            # Filtro por Classificação
            todas_classificacoes = df_limpo['CLASSIFICACAO'].unique().tolist()
            classificacao_selecionada = st.sidebar.multiselect('Filtrar por Classificação:', options=todas_classificacoes, default=st.session_state.classificacao_selecionada, key='classificacao_multiselect')
            st.session_state.classificacao_selecionada = classificacao_selecionada
            
            # Filtro por Responsável
            todos_responsaveis = ['Todos'] + sorted(df_limpo['NOME'].unique().tolist())
            responsavel_selecionado = st.sidebar.selectbox('Filtrar por Responsável:', options=todos_responsaveis, index=todos_responsaveis.index(st.session_state.responsavel_selecionado) if st.session_state.responsavel_selecionado in todos_responsaveis else 0, key='responsavel_selectbox')
            st.session_state.responsavel_selecionado = responsavel_selecionado
            
            # Filtro por Faixa de Valor
            min_valor_df = float(df_limpo['VALOR_CALCULADO'].min()) if not df_limpo.empty else 0.0
            max_valor_df = float(df_limpo['VALOR_CALCULADO'].max()) if not df_limpo.empty else 1000.0
            valor_range = st.sidebar.slider('Filtrar por Faixa de Valor (R$):', min_value=min_valor_df, max_value=max_valor_df, value=st.session_state.valor_range, step=50.0, format='R$ %.2f', key='valor_slider')
            st.session_state.valor_range = valor_range
            
            # Aplica os filtros ao DataFrame
            df_filtrado = df_limpo[df_limpo['CLASSIFICACAO'].isin(classificacao_selecionada)]
            if responsavel_selecionado != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['NOME'] == responsavel_selecionado]
            df_filtrado = df_filtrado[(df_filtrado['VALOR_CALCULADO'] >= valor_range[0]) & (df_filtrado['VALOR_CALCULADO'] <= valor_range[1])]
            
            # Recalcula métricas com base nos filtros
            total_recebido_filtrado = df_filtrado[df_filtrado['VALOR_CALCULADO'] > 0]['VALOR_CALCULADO'].sum()
            total_patrocinios_filtrado = len(df_filtrado[df_filtrado['CLASSIFICACAO'] == 'PATROCÍNIO'])
            previsao_filtrada = (len(df_filtrado) * 600) + (total_patrocinios_filtrado * 400)
            saldo_a_receber_filtrado = previsao_filtrada - total_recebido_filtrado
            percentual_recebido_filtrado = (total_recebido_filtrado / previsao_filtrada * 100) if previsao_filtrada > 0 else 0
            
            # ==============================================================================
            # 4.2. CABEÇALHO DO DASHBOARD
            # ==============================================================================
            st.title('📊 Dashboard Baile 2025')
            st.markdown(f'👤 Logado como: **{st.session_state.usuario_atual}** | Última atualização: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
            
            # Métricas principais
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
                        margin=dict(r=150, l=100) # Ajuste de margem para evitar corte de texto
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
                    margin=dict(r=150, l=120) # Ajuste de margem para evitar corte de texto
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
