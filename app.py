import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
import plotly.express as px
import json
import os
import io  # <--- NUEVO: Necesario para manipular el archivo Excel en memoria

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard Pesca", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
        .main-title {
            text-align: center; 
            color: #004080;
            font-weight: 800;
            font-family: 'Arial Black', sans-serif;
        }
        
        /* --- ESTILOS MEJORADOS PARA TABS --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            border-bottom: 1px solid #d0d7de;
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

# --- CONEXIÓN HÍBRIDA (PC / NUBE) ---
@st.cache_resource
def conectar_google_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

    if os.path.exists("credenciales.json"):
        credentials = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    elif "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        st.error("❌ No se encontraron credenciales (ni archivo local ni secrets).")
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

        # --- FECHA PERÚ ---
        zona_peru = pytz.timezone('America/Lima')
        hoy_peru = datetime.now(zona_peru).date()

        # --- BARRA LATERAL ---
        st.sidebar.header("📅 Configuración")
        fecha_seleccionada = st.sidebar.date_input("Selecciona la Fecha", hoy_peru)
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Conversión")
        kilos_por_bandeja = st.sidebar.number_input("Kg promedio por Bandeja", min_value=0.1, value=10.0, step=0.5, format="%.1f")

        # --- TABS ---
        tab_reporte, tab_datos = st.tabs(["Reporte Diario", "Base de Datos"])

        # ==============================================================================
        # PESTAÑA 1: REPORTE DIARIO
        # ==============================================================================
        with tab_reporte:
            df_filtrado = df_raw[df_raw['Fecha_Filtro'] == fecha_seleccionada].copy()
            df_filtrado['Kilos Calc'] = df_filtrado['Bandejas'] * kilos_por_bandeja
            df_filtrado['Toneladas Calc'] = df_filtrado['Kilos Calc'] / 1000

            if df_filtrado.empty:
                st.warning(f"⚠️ No hay datos para el día: {fecha_seleccionada}")
            else:
                # KPIs
                st.markdown("### 📊 Métricas Clave")
                col_fecha, col1, col2, col3, col4 = st.columns(5)
                col_fecha.metric("Fecha Reporte", f"{fecha_seleccionada.strftime('%d/%m/%Y')} 🗓️")
                col1.metric("Total Bandejas", f"{df_filtrado['Bandejas'].sum():,.0f} 📦")
                col2.metric("Total Toneladas", f"{df_filtrado['Toneladas Calc'].sum():,.2f} t ⚖️")
                col3.metric("Lotes", f"{df_filtrado['Lote'].nunique()} 🏷️")
                col4.metric("Cuadrillas", f"{df_filtrado['Cuadrilla'].nunique()} 👷")
                st.markdown("---")

                # Timeline
                st.subheader("⏰ Actividad en Tiempo Real")
                fig_timeline = px.scatter(
                    df_filtrado.sort_values("Marca temporal"), x="Marca temporal", y="Cuadrilla",
                    size="Bandejas", color="Producto", hover_data=["Lote", "Kilos Calc"],
                    color_discrete_sequence=px.colors.qualitative.Bold, height=400
                )
                fig_timeline.update_xaxes(tickformat="%H:%M", title_text="<b>Hora del Día</b>")
                st.plotly_chart(estilo_grafico(fig_timeline), use_container_width=True)
                st.markdown("---")
                
                # Barras
                col_graf1, col_graf2 = st.columns(2)
                with col_graf1:
                    st.subheader("🏭 Toneladas por Cuadrilla")
                    df_cuadrilla = df_filtrado.groupby(['Cuadrilla', 'Producto'])[['Toneladas Calc']].sum().reset_index()
                    fig_cuadrilla = px.bar(df_cuadrilla, x="Cuadrilla", y="Toneladas Calc", color="Producto", barmode='group',
                        labels={"Toneladas Calc": "<b>Toneladas (t)</b>", "Cuadrilla": "<b>Cuadrilla</b>"},
                        color_discrete_sequence=px.colors.qualitative.Pastel, text_auto='.3f')
                    st.plotly_chart(estilo_grafico(fig_cuadrilla), use_container_width=True)
                    
                with col_graf2:
                    st.subheader("📦 Toneladas por Lote")
                    df_lote = df_filtrado.groupby(['Lote', 'Producto'])[['Toneladas Calc']].sum().reset_index()
                    fig_lote = px.bar(df_lote, x="Lote", y="Toneladas Calc", color="Producto", barmode='group',
                        labels={"Toneladas Calc": "<b>Toneladas (t)</b>", "Lote": "<b>N° Lote</b>"},
                        color_discrete_sequence=px.colors.qualitative.Pastel, text_auto='.3f')
                    fig_lote.update_xaxes(type='category', title="<b>N° Lote</b>")
                    st.plotly_chart(estilo_grafico(fig_lote), use_container_width=True)

                st.markdown("---")
                
                # Sunburst
                st.subheader("🔍 Desglose Multidimensional")
                st.info("💡 Cada gráfico representa un Lote.")
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

                # Tablas Detalle Global
                st.subheader("📋 Tablas de Detalle Global")
                col_tabla1, col_tabla2 = st.columns(2)
                config_tablas = {
                    "Total Kilos": st.column_config.NumberColumn(format="%.1f kg"),
                    "Total Toneladas": st.column_config.NumberColumn(format="%.2f t"),
                    "Total Bandejas": st.column_config.NumberColumn(format="%.0f"),
                    "Lote": st.column_config.TextColumn("N° Lote"),
                }
                with col_tabla1:
                    st.markdown("##### 📦 Resumen por Lote")
                    resumen_lote = df_filtrado.groupby('Lote')[['Bandejas', 'Kilos Calc', 'Toneladas Calc']].sum().reset_index()
                    resumen_lote.columns = ['Lote', 'Total Bandejas', 'Total Kilos', 'Total Toneladas']
                    st.dataframe(resumen_lote, column_config=config_tablas, hide_index=True, use_container_width=True)

                with col_tabla2:
                    st.markdown("##### 👷 Resumen por Cuadrilla")
                    resumen_cuadrilla = df_filtrado.groupby('Cuadrilla')[['Bandejas', 'Kilos Calc', 'Toneladas Calc']].sum().reset_index()
                    resumen_cuadrilla.columns = ['Cuadrilla', 'Total Bandejas', 'Total Kilos', 'Total Toneladas']
                    config_cuadrilla = config_tablas.copy(); config_cuadrilla.pop("Lote", None) 
                    st.dataframe(resumen_cuadrilla, column_config=config_cuadrilla, hide_index=True, use_container_width=True)
                
                # Detalle por Producto/Lote
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
                                tabla_detalle,
                                column_config={
                                    "Total Toneladas": st.column_config.NumberColumn(format="%.2f t"),
                                    "Producto": st.column_config.TextColumn("Producto"),
                                    "Calidad": st.column_config.TextColumn("Calidad"),
                                    "Calibre": st.column_config.TextColumn("Calibre"),
                                },
                                hide_index=True, use_container_width=True
                            )
                            st.markdown("<br>", unsafe_allow_html=True)

        # ==============================================================================
        # PESTAÑA 2: BASE DE DATOS
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
                # Autoajuste columnas
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










