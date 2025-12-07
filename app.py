import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import json
import os
import io
import numpy as np # Importamos numpy para manejo seguro de divisiones

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard Pesca", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS (INTACTOS) ---
st.markdown("""
    <style>
        .main-title {
            text-align: center !important;
            color: #004080;
            font-weight: 800;
            font-family: 'Arial Black', sans-serif;
        }
        
        /* =========================================
           1. HEADER SUPERIOR
           ========================================= */
        header[data-testid="stHeader"] {
            background-color: #004080;
        }
        
        header[data-testid="stHeader"] svg,
        header[data-testid="stHeader"] button {
            color: white !important;
            fill: white !important;
        }

        /* =========================================
           2. FLECHA DE BARRA LATERAL CONTRAÍDA
           ========================================= */
        .st-emotion-cache-pd6qx2 {
            color: white !important;
            fill: white !important;
            opacity: 1 !important;
        }
        
        [data-testid="stSidebarCollapsedControl"] {
            color: white !important;
            background-color: #004080 !important;
            opacity: 1 !important;
        }
        
        [data-testid="stSidebarCollapsedControl"] svg {
            fill: white !important;
        }

        /* =========================================
           3. BARRA LATERAL (SIDEBAR) - ESTILOS GENERALES
           ========================================= */
        section[data-testid="stSidebar"] {
            background-color: #004080;
        }
        
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3, 
        section[data-testid="stSidebar"] label, 
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
            color: white !important;
        }

        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] .stSelectbox div,
        section[data-testid="stSidebar"] .stMultiSelect div {
            color: #31333F !important;
        }
        
        /* Regla para Selects y Inputs base (sin forzar el calendario global) */
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div,
        section[data-testid="stSidebar"] div[data-baseweb="base-input"] {
            background-color: white !important;
            color: #31333F !important;
        }

        /* =========================================
           4. TAGS DE MULTISELECT
           ========================================= */
        .st-c2,
        span[data-baseweb="tag"] {
            background-color: #004080 !important; /* Fondo azul para contraste */
            color: white !important;
        }

        /* =========================================
           5. PESTAÑAS (TABS)
           ========================================= */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            border-bottom: 1px solid #d0d7de;
            background-color: transparent !important;
            padding-top: 10px;
            padding-left: 10px;
            border-radius: 5px 5px 0 0;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 55px;
            white-space: pre-wrap;
            background-color: #f8f9fa;
            border-radius: 8px 8px 0px 0px;
            border: 1px solid #e1e4e8;
            border-bottom: none;
            padding: 10px 25px; 
            font-size: 16px;
            font-weight: 600;
            color: #555;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #eef2f6;
            color: #004080;
        }

        .stTabs [aria-selected="true"] {
            background-color: #004080 !important;
            color: white !important;
            border-color: #004080;
        }
    </style>
    <h1 class='main-title'>&#128031; Dashboard de Producción Pesquera</h1>
    <hr style='border: 2px solid #004080; border-radius: 5px;'>
""", unsafe_allow_html=True)

# --- FUNCIÓN DE ESTILO DE GRÁFICOS ---
def estilo_grafico(fig):
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black', size=12, family="Arial"),
        margin=dict(l=40, r=40, t=50, b=50),
        xaxis=dict(
            showline=True, linewidth=1, linecolor='black', mirror=True,
            title_font=dict(size=14, color='black', family="Arial Black"),
            tickfont=dict(color='black', size=12, family="Arial", weight="bold")
        ),
        yaxis=dict(
            showline=True, linewidth=1, linecolor='black', mirror=True,
            title_font=dict(size=14, color='black', family="Arial Black"),
            tickfont=dict(color='black', size=12, family="Arial", weight="bold"),
            gridcolor='#eeeeee'
        ),
        legend=dict(
            title_font=dict(size=13, color='black', family="Arial Black"),
            font=dict(size=12, color='black', family="Arial"),
            bgcolor="rgba(255,255,255, 0.9)",
            bordercolor="rgba(0,0,0,0)", 
            borderwidth=0
        )
    )
    return fig

# --- CONEXIÓN HÍBRIDA ---
@st.cache_resource
def conectar_google_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

    if os.path.exists("credenciales.json"):
        credentials = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    elif "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        st.error("❌ No se encontraron credenciales.")
        st.stop()
        
    client = gspread.authorize(credentials)
    return client

# --- CARGA DE DATOS ---
def cargar_datos():
    client = conectar_google_sheets()
    sheet = client.open("Base de datos").worksheet("Respuestas de formulario 2")
    data = sheet.get_all_values()
    if not data: return pd.DataFrame()
    headers = data[0]
    rows = data[1:]
    return pd.DataFrame(rows, columns=headers)

try:
    df_raw = cargar_datos()

    if not df_raw.empty:
        # --- PROCESAMIENTO ---
        df_raw['Marca temporal'] = pd.to_datetime(df_raw['Marca temporal'], dayfirst=True, errors='coerce')
        df_raw['Fecha_Filtro'] = df_raw['Marca temporal'].dt.date
        df_raw['Bandejas'] = pd.to_numeric(df_raw['Bandejas'], errors='coerce').fillna(0)
        df_raw['Lote'] = df_raw['Lote'].astype(str).str.strip()
        
        columnas_requeridas = ['Calidad', 'Calibre', 'N° de Coche', 'Cuadrilla', 'Producto']
        for col in columnas_requeridas:
            if col not in df_raw.columns: df_raw[col] = "S/D"
        
        df_raw['Calidad'] = df_raw['Calidad'].astype(str)
        df_raw['Calibre'] = df_raw['Calibre'].astype(str)
        df_raw['N° de Coche'] = df_raw['N° de Coche'].astype(str).str.strip()

        # --- FECHA PERÚ ---
        zona_peru = pytz.timezone('America/Lima')
        hoy_peru = datetime.now(zona_peru).date()

        # --- BARRA LATERAL ---
        st.sidebar.header("📅 Configuración")
        fecha_seleccionada = st.sidebar.date_input("Selecciona la Fecha (Diario)", hoy_peru)
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Conversión")
        kilos_por_bandeja = st.sidebar.number_input("Kg promedio por Bandeja", min_value=0.1, value=10.0, step=0.5, format="%.1f")
        
        # Calculamos columnas métricas globales
        df_raw['Kilos Calc'] = df_raw['Bandejas'] * kilos_por_bandeja
        df_raw['Toneladas Calc'] = df_raw['Kilos Calc'] / 1000

        # --- FILTRADO GLOBAL ---
        df_filtrado = df_raw[df_raw['Fecha_Filtro'] == fecha_seleccionada].copy()

        # --- TABS ---
        # Titulos cortos y sin emojis para mejor visualización en móviles
        tab_reporte, tab_rendimiento, tab_historico, tab_datos = st.tabs(["Reporte", "Rendimiento", "Histórico", "Datos"])

        # ==============================================================================
        # PESTAÑA 1: REPORTE DIARIO
        # ==============================================================================
        with tab_reporte:
            if df_filtrado.empty:
                st.warning(f"⚠️ No hay datos para el día: {fecha_seleccionada}")
            else:
                # KPIs
                st.markdown("### 📊 Métricas del Día")
                col_fecha, col1, col2, col3, col4, col5 = st.columns(6)
                
                col_fecha.metric("Fecha", f"{fecha_seleccionada.strftime('%d/%m/%Y')} 🗓️")
                col1.metric("Bandejas", f"{df_filtrado['Bandejas'].sum():,.0f} 📦")
                col2.metric("Toneladas", f"{df_filtrado['Toneladas Calc'].sum():,.2f} t ⚖️")
                col3.metric("Lotes", f"{df_filtrado['Lote'].nunique()} 🏷️")
                col4.metric("Cuadrillas", f"{df_filtrado['Cuadrilla'].nunique()} 👷")
                
                # MÉTRICA CÁLCULO POR VOLUMEN
                coches_estimados = df_filtrado['Bandejas'].sum() / 50
                col5.metric("N° Coches completos", f"{coches_estimados:,.2f} 🛒")
                
                st.markdown("---")

                # Timeline Scatter
                st.subheader("⏰ Actividad en Tiempo Real")
                fig_timeline = px.scatter(
                    df_filtrado.sort_values("Marca temporal"),
                    x="Marca temporal",
                    y="Cuadrilla",
                    color="Producto",
                    hover_data=["Lote", "Bandejas", "Kilos Calc", "N° de Coche"],
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    height=450
                )
                fig_timeline.update_traces(marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
                fig_timeline.update_xaxes(tickformat="%H:%M", title_text="<b>Hora del Día</b>")
                fig_timeline.update_yaxes(title_text="<b>Cuadrilla</b>")
                
                fig_timeline = estilo_grafico(fig_timeline)
                fig_timeline.update_layout(
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, title=None),
                    margin=dict(b=100)
                )
                st.plotly_chart(fig_timeline, use_container_width=True)
                st.markdown("---")
                
                # Barras
                col_graf1, col_graf2 = st.columns(2)
                with col_graf1:
                    st.subheader("🏭 Toneladas por Cuadrilla")
                    df_cuadrilla = df_filtrado.groupby(['Cuadrilla', 'Producto'])[['Toneladas Calc']].sum().reset_index()
                    fig_cuadrilla = px.bar(df_cuadrilla, x="Cuadrilla", y="Toneladas Calc", color="Producto", barmode='group',
                        labels={"Toneladas Calc": "<b>Toneladas (t)</b>", "Cuadrilla": "<b>Cuadrilla</b>"},
                        color_discrete_sequence=px.colors.qualitative.Pastel, text_auto='.2f')
                    fig_cuadrilla.update_traces(textfont_weight='bold')
                    st.plotly_chart(estilo_grafico(fig_cuadrilla), use_container_width=True)
                    
                with col_graf2:
                    st.subheader("📦 Toneladas por Lote")
                    df_lote = df_filtrado.groupby(['Lote', 'Producto'])[['Toneladas Calc']].sum().reset_index()
                    fig_lote = px.bar(df_lote, x="Lote", y="Toneladas Calc", color="Producto", barmode='group',
                        labels={"Toneladas Calc": "<b>Toneladas (t)</b>", "Lote": "<b>N° Lote</b>"},
                        color_discrete_sequence=px.colors.qualitative.Pastel, text_auto='.2f')
                    fig_lote.update_traces(textfont_weight='bold')
                    fig_lote.update_xaxes(type='category', title="<b>N° Lote</b>")
                    st.plotly_chart(estilo_grafico(fig_lote), use_container_width=True)

                st.markdown("---")
                
                # Sunburst
                st.subheader("🔍 Desglose Multidimensional")
                col_sun_config, col_sun_graf = st.columns([1, 4])
                with col_sun_config:
                    st.markdown("**Configuración:**")
                    columnas_disponibles = ['Producto', 'Calidad', 'Calibre', 'Cuadrilla']
                    columnas_reales = [c for c in columnas_disponibles if c in df_filtrado.columns]
                    path_seleccionado = st.multiselect("Jerarquía:", options=columnas_reales, default=['Producto', 'Calidad', 'Calibre'])
                    st.markdown("---")
                    lotes_activos = sorted(df_filtrado['Lote'].unique())
                    lotes_seleccionados = st.multiselect("Lotes visibles:", options=lotes_activos, default=lotes_activos)
                with col_sun_graf:
                    if path_seleccionado and lotes_seleccionados:
                        num_cols = 1 if len(lotes_seleccionados) == 1 else 2
                        cols = st.columns(num_cols)
                        for i, lote in enumerate(lotes_seleccionados):
                            with cols[i % num_cols]:
                                df_lote = df_filtrado[df_filtrado['Lote'] == lote]
                                total_lote = df_lote['Toneladas Calc'].sum()
                                fig_sun = px.sunburst(
                                    df_lote, path=path_seleccionado, values='Toneladas Calc', color='Producto', 
                                    color_discrete_sequence=px.colors.qualitative.Pastel,
                                    title=f"<b>Lote {lote}</b><br>Total: {total_lote:.2f} t", branchvalues="total"
                                )
                                fig_sun.update_layout(margin=dict(t=50, l=0, r=0, b=0), height=350)
                                st.plotly_chart(fig_sun, use_container_width=True)

                st.markdown("---")

                # Tablas Detalle
                st.subheader("📋 Tablas de Detalle Global")
                col_tabla1, col_tabla2 = st.columns(2)
                
                # Configuración de columnas
                config_tablas = {
                    "Total Kilos": st.column_config.NumberColumn(format="%.1f kg"),
                    "Total Toneladas": st.column_config.NumberColumn(format="%.2f t"),
                    "Total Bandejas": st.column_config.NumberColumn(format="%.0f"),
                    "Lote": st.column_config.TextColumn("N° Lote"),
                    "N° Coches completos": st.column_config.NumberColumn("N° Coches completos", format="%.2f"), 
                }
                
                with col_tabla1:
                    st.markdown("##### 📦 Resumen por Lote")
                    resumen_lote = df_filtrado.groupby('Lote').agg({
                        'Bandejas': 'sum',
                        'Kilos Calc': 'sum',
                        'Toneladas Calc': 'sum'
                    }).reset_index()
                    resumen_lote['N° Coches completos'] = resumen_lote['Bandejas'] / 50
                    resumen_lote = resumen_lote[['Lote', 'N° Coches completos', 'Bandejas', 'Kilos Calc', 'Toneladas Calc']]
                    resumen_lote.columns = ['Lote', 'N° Coches completos', 'Total Bandejas', 'Total Kilos', 'Total Toneladas']
                    st.dataframe(resumen_lote, column_config=config_tablas, hide_index=True, use_container_width=True)

                with col_tabla2:
                    st.markdown("##### 👷 Resumen por Cuadrilla")
                    resumen_cuadrilla = df_filtrado.groupby('Cuadrilla').agg({
                        'Bandejas': 'sum',
                        'Kilos Calc': 'sum',
                        'Toneladas Calc': 'sum'
                    }).reset_index()
                    resumen_cuadrilla['N° Coches completos'] = resumen_cuadrilla['Bandejas'] / 50
                    resumen_cuadrilla = resumen_cuadrilla[['Cuadrilla', 'N° Coches completos', 'Bandejas', 'Kilos Calc', 'Toneladas Calc']]
                    resumen_cuadrilla.columns = ['Cuadrilla', 'N° Coches completos', 'Total Bandejas', 'Total Kilos', 'Total Toneladas']
                    config_cuadrilla = config_tablas.copy(); config_cuadrilla.pop("Lote", None) 
                    st.dataframe(resumen_cuadrilla, column_config=config_cuadrilla, hide_index=True, use_container_width=True)
                
                st.markdown("---")
                st.subheader("🧩 Detalle de Productos por Lote")
                lotes_unicos = sorted(df_filtrado['Lote'].unique())
                if len(lotes_unicos) > 0:
                    cols_detalle = st.columns(2)
                    for index, lote_actual in enumerate(lotes_unicos):
                        with cols_detalle[index % 2]:
                            st.markdown(f"#### 🏷️ Lote: {lote_actual}")
                            df_lote_especifico = df_filtrado[df_filtrado['Lote'] == lote_actual]
                            tabla_detalle = df_lote_especifico.groupby(['Producto', 'Calidad', 'Calibre'])[['Toneladas Calc']].sum().reset_index()
                            tabla_detalle.columns = ['Producto', 'Calidad', 'Calibre', 'Total Toneladas']
                            st.dataframe(
                                tabla_detalle, column_config={"Total Toneladas": st.column_config.NumberColumn(format="%.2f t")},
                                hide_index=True, use_container_width=True
                            )
                            st.markdown("<br>", unsafe_allow_html=True)
        
        # ==============================================================================
        # PESTAÑA 2: RENDIMIENTO DIARIO
        # ==============================================================================
        with tab_rendimiento:
            st.markdown("### ⚡ Cálculo de Rendimiento Diario")
            
            if df_filtrado.empty:
                st.warning(f"⚠️ No hay datos para el día: {fecha_seleccionada}")
            else:
                # 1. Preparar Datos Base
                df_rend = df_filtrado.groupby('Lote')[['Toneladas Calc']].sum().reset_index()
                df_rend.columns = ['Lote', 'Total Envasado (tn)']
                
                # 2. Inicializar columna de Descarga vacía (0.0)
                if 'Total de descarga (tn)' not in df_rend.columns:
                    df_rend['Total de descarga (tn)'] = 0.0

                # Reordenamos columnas
                df_rend = df_rend[['Lote', 'Total de descarga (tn)', 'Total Envasado (tn)']]

                st.info("📝 Ingresa los valores de 'Total de descarga (tn)' y presiona el botón para calcular.")
                
                # 3. Formulario para evitar recargas constantes
                with st.form("calculo_rendimiento_form"):
                    edited_df = st.data_editor(
                        df_rend,
                        column_config={
                            "Lote": st.column_config.TextColumn("Lote", disabled=True),
                            "Total Envasado (tn)": st.column_config.NumberColumn("Total Envasado (tn)", format="%.3f t", disabled=True),
                            # MODIFICADO: step=0.001 y formato a 3 decimales
                            "Total de descarga (tn)": st.column_config.NumberColumn(
                                "Total de descarga (tn)", 
                                format="%.3f t", 
                                min_value=0.0, 
                                step=0.001, 
                                required=True
                            ),
                        },
                        hide_index=True,
                        use_container_width=True,
                        key="editor_rendimiento"
                    )
                    
                    # Botón de cálculo
                    calcular_btn = st.form_submit_button("🔄 Calcular Rendimiento")

                # 4. Cálculos y Resultados (Solo al presionar el botón)
                if calcular_btn and not edited_df.empty:
                    # Fórmula CORREGIDA: (Total Envasado / Total Descarga) * 100
                    with np.errstate(divide='ignore', invalid='ignore'):
                         edited_df['Rendimiento (%)'] = (edited_df['Total Envasado (tn)'] / edited_df['Total de descarga (tn)']) * 100
                    
                    edited_df['Rendimiento (%)'] = edited_df['Rendimiento (%)'].fillna(0.0)
                    edited_df['Rendimiento (%)'] = edited_df['Rendimiento (%)'].replace([np.inf, -np.inf], 0.0)

                    st.markdown("#### 📊 Resultados por Lote")
                    
                    st.dataframe(
                        edited_df,
                        column_config={
                            "Lote": st.column_config.TextColumn("Lote"),
                            "Total de descarga (tn)": st.column_config.NumberColumn("Total de descarga (tn)", format="%.3f t"),
                            "Total Envasado (tn)": st.column_config.NumberColumn("Total Envasado (tn)", format="%.3f t"),
                            "Rendimiento (%)": st.column_config.ProgressColumn(
                                "Rendimiento (%)", 
                                format="%.1f%%", 
                                min_value=0, 
                                max_value=100, 
                            ), 
                        },
                        hide_index=True,
                        use_container_width=True
                    )

        # ==============================================================================
        # PESTAÑA 3: TENDENCIAS HISTÓRICAS
        # ==============================================================================
        with tab_historico:
            st.markdown("### 📈 Evolución de la Producción")
            
            col_fechas, col_cuadrillas = st.columns(2)
            
            with col_fechas:
                fecha_inicio_def = hoy_peru - timedelta(days=7)
                rango_fechas = st.date_input(
                    "Selecciona Rango de Fechas:",
                    value=(fecha_inicio_def, hoy_peru),
                    max_value=hoy_peru
                )
            
            with col_cuadrillas:
                todas_cuadrillas = sorted(df_raw['Cuadrilla'].unique())
                cuadrillas_seleccionadas = st.multiselect(
                    "Filtrar por Cuadrillas:",
                    options=todas_cuadrillas,
                    default=todas_cuadrillas
                )
            
            if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                fecha_inicio, fecha_fin = rango_fechas
                
                mask_fecha = (df_raw['Fecha_Filtro'] >= fecha_inicio) & (df_raw['Fecha_Filtro'] <= fecha_fin)
                df_hist = df_raw.loc[mask_fecha].copy()
                
                if cuadrillas_seleccionadas:
                    df_hist = df_hist[df_hist['Cuadrilla'].isin(cuadrillas_seleccionadas)]
                else:
                    st.warning("⚠️ Debes seleccionar al menos una cuadrilla.")
                    df_hist = pd.DataFrame()

                if not df_hist.empty:
                    st.subheader(f"Producción Total Diaria ({len(cuadrillas_seleccionadas)} cuadrillas seleccionadas)")
                    
                    df_evolucion = df_hist.groupby('Fecha_Filtro')[['Toneladas Calc']].sum().reset_index()
                    
                    fig_evolucion = px.line(
                        df_evolucion, 
                        x='Fecha_Filtro', 
                        y='Toneladas Calc',
                        markers=True,
                        line_shape='spline',
                        text='Toneladas Calc'
                    )
                    fig_evolucion.update_traces(textposition="top center", texttemplate='%{text:.1f} t')
                    fig_evolucion.update_xaxes(title="Fecha", tickformat="%d/%m")
                    fig_evolucion.update_yaxes(title="Toneladas")
                    
                    st.plotly_chart(estilo_grafico(fig_evolucion), use_container_width=True)
                    
                elif cuadrillas_seleccionadas:
                    st.warning("⚠️ No hay datos en el rango de fechas seleccionado.")

            else:
                st.info("Selecciona una fecha de inicio y fin para ver el histórico.")


        # ==============================================================================
        # PESTAÑA 4: BASE DE DATOS
        # ==============================================================================
        with tab_datos:
            st.header("Base de Datos de Registros")
            ver_todo = st.toggle("Ver todo el historial", value=False)
            
            if ver_todo:
                df_tabla = df_raw.copy()
                st.info(f"Mostrando el historial completo: {len(df_tabla)} registros.")
            else:
                df_tabla = df_raw[df_raw['Fecha_Filtro'] == fecha_seleccionada].copy()
                st.info(f"Mostrando registros del día {fecha_seleccionada}: {len(df_tabla)} registros.")

            columnas_a_mostrar = ['Marca temporal', 'Fecha_Filtro', 'Cuadrilla', 'Producto', 'Calibre', 'Calidad', 'N° de Coche', 'Lote', 'Bandejas']
            cols_finales = [c for c in columnas_a_mostrar if c in df_tabla.columns]
            df_tabla_view = df_tabla[cols_finales]

            st.dataframe(
                df_tabla_view,
                use_container_width=True, hide_index=True,
                column_config={
                    "Marca temporal": st.column_config.DatetimeColumn("Marca temporal", format="DD/MM/YYYY HH:mm"),
                    "Fecha_Filtro": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "Bandejas": st.column_config.NumberColumn("Bandejas", format="%d"),
                    "Lote": st.column_config.TextColumn("Lote"), 
                }
            )
            
            # --- DESCARGA EXCEL ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_tabla_view.to_excel(writer, index=False, sheet_name='BaseDatos')
                worksheet = writer.sheets['BaseDatos']
                for i, col in enumerate(df_tabla_view.columns):
                    column_len = max(df_tabla_view[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, column_len)
            
            st.download_button(
                label="📥 Descargar Excel",
                data=buffer.getvalue(),
                file_name=f'registros_pesca_{fecha_seleccionada}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

    else:
        st.error("❌ No hay datos cargados.")

except Exception as e:
    st.error(f"❌ Error: {e}")

















