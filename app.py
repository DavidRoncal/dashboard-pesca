import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime # <--- CAMBIO: Importamos datetime completo
import pytz # <--- CAMBIO: Importamos librería de zonas horarias
import plotly.express as px
import json
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard Pesca", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
        .main-title {
            text-align: center; 
            color: #004080;
            font-weight: 800;
            font-family: 'Arial Black', sans-serif;
        }
    </style>
    <!-- Usamos el código HTML &#128031; para el pescado para evitar errores de codificación en Windows -->
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
        
        # Ejes
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
        
        # Leyenda
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

    # Opción A: Estamos en la PC y existe el archivo json
    if os.path.exists("credenciales.json"):
        credentials = Credentials.from_service_account_file("credenciales.json", scopes=scopes)
    
    # Opción B: Estamos en Streamlit Cloud (usamos st.secrets)
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
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

try:
    df_raw = cargar_datos()

    if not df_raw.empty:
        # --- PROCESAMIENTO ---
        df_raw['Marca temporal'] = pd.to_datetime(df_raw['Marca temporal'], dayfirst=True, errors='coerce')
        df_raw['Fecha_Filtro'] = df_raw['Marca temporal'].dt.date
        df_raw['Bandejas'] = pd.to_numeric(df_raw['Bandejas'], errors='coerce').fillna(0)
        df_raw['Lote'] = df_raw['Lote'].astype(str)
        
        # Aseguramos columnas de texto
        if 'Calidad' not in df_raw.columns: df_raw['Calidad'] = "S/D"
        if 'Calibre' not in df_raw.columns: df_raw['Calibre'] = "S/D"
        
        df_raw['Calidad'] = df_raw['Calidad'].astype(str)
        df_raw['Calibre'] = df_raw['Calibre'].astype(str)


        # --- CÁLCULO DE FECHA PERÚ (NUEVO) ---
        zona_peru = pytz.timezone('America/Lima')
        hoy_peru = datetime.now(zona_peru).date()

        # --- BARRA LATERAL ---
        st.sidebar.header("📅 Configuración")
        # Usamos hoy_peru en lugar de date.today()
        fecha_seleccionada = st.sidebar.date_input("Selecciona la Fecha", hoy_peru)
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Conversión")
        kilos_por_bandeja = st.sidebar.number_input(
            "Kg promedio por Bandeja", 
            min_value=0.1, value=10.0, step=0.5, format="%.1f"
        )

        # --- FILTRADO ---
        df_filtrado = df_raw[df_raw['Fecha_Filtro'] == fecha_seleccionada].copy()
        
        # Cálculos
        df_filtrado['Kilos Calc'] = df_filtrado['Bandejas'] * kilos_por_bandeja
        df_filtrado['Toneladas Calc'] = df_filtrado['Kilos Calc'] / 1000

        if df_filtrado.empty:
            st.warning(f"⚠️ No hay datos para el día: {fecha_seleccionada}")
        else:
            # --- KPIs ---
            st.markdown("### 📊 Métricas Clave")
            col_fecha, col1, col2, col3, col4 = st.columns(5)
            
            col_fecha.metric("Fecha Reporte", f"{fecha_seleccionada.strftime('%d/%m/%Y')} 🗓️")
            col1.metric("Total Bandejas", f"{df_filtrado['Bandejas'].sum():,.0f} 📦")
            col2.metric("Total Toneladas", f"{df_filtrado['Toneladas Calc'].sum():,.2f} t ⚖️")
            col3.metric("Lotes", f"{df_filtrado['Lote'].nunique()} 🏷️")
            col4.metric("Cuadrillas", f"{df_filtrado['Cuadrilla'].nunique()} 👷")
             
            st.markdown("---")

            # --- 1. LÍNEA DE TIEMPO ---
            st.subheader("⏰ Actividad en Tiempo Real")
            fig_timeline = px.scatter(
                df_filtrado.sort_values("Marca temporal"),
                x="Marca temporal",
                y="Cuadrilla",
                size="Bandejas",
                color="Producto",
                hover_data=["Lote", "Kilos Calc"],
                color_discrete_sequence=px.colors.qualitative.Bold,
                height=400
            )
            fig_timeline.update_xaxes(tickformat="%H:%M", title_text="<b>Hora del Día</b>")
            fig_timeline.update_yaxes(title_text="<b>Cuadrilla</b>")
            
            st.plotly_chart(estilo_grafico(fig_timeline), use_container_width=True)

            st.markdown("---")
            
            # --- 2. GRÁFICOS DE BARRAS ---
            col_graf1, col_graf2 = st.columns(2)
            paleta = px.colors.qualitative.Pastel
            formato_etiqueta = '.3f'

            with col_graf1:
                st.subheader("🏭 Toneladas por Cuadrilla")
                
                df_cuadrilla = df_filtrado.groupby(['Cuadrilla', 'Producto'])[['Toneladas Calc']].sum().reset_index()
                
                fig_cuadrilla = px.bar(
                    df_cuadrilla,
                    x="Cuadrilla",
                    y="Toneladas Calc",
                    color="Producto",
                    barmode='group',
                    labels={"Toneladas Calc": "<b>Toneladas (t)</b>", "Cuadrilla": "<b>Cuadrilla</b>"},
                    color_discrete_sequence=paleta,
                    text_auto=formato_etiqueta
                )
                
                fig_cuadrilla = estilo_grafico(fig_cuadrilla)
                fig_cuadrilla.update_traces(textposition='outside', cliponaxis=False)
                
                st.plotly_chart(fig_cuadrilla, use_container_width=True)
                
            with col_graf2:
                st.subheader("📦 Toneladas por Lote")
                
                df_lote = df_filtrado.groupby(['Lote', 'Producto'])[['Toneladas Calc']].sum().reset_index()
                
                fig_lote = px.bar(
                    df_lote,
                    x="Lote",
                    y="Toneladas Calc",
                    color="Producto",
                    barmode='group',
                    labels={"Toneladas Calc": "<b>Toneladas (t)</b>", "Lote": "<b>N° Lote</b>"},
                    color_discrete_sequence=paleta,
                    text_auto=formato_etiqueta
                )
                fig_lote.update_layout(xaxis_title="<b>N° Lote</b>")
                
                fig_lote = estilo_grafico(fig_lote)
                fig_lote.update_traces(textposition='outside', cliponaxis=False)
                
                st.plotly_chart(fig_lote, use_container_width=True)

            st.markdown("---")
            
            # --- 3. GRÁFICOS SOLARES POR LOTE ---
            st.subheader("🔍 Desglose Multidimensional")
            st.info("💡 Cada gráfico representa un Lote. Los anillos se generan en el orden que configures en el menú de la izquierda.")
            
            col_sun_config, col_sun_graf = st.columns([1, 4])
            
            with col_sun_config:
                st.markdown("**Configuración:**")
                
                columnas_disponibles = ['Producto', 'Calidad', 'Calibre', 'Cuadrilla']
                columnas_reales = [c for c in columnas_disponibles if c in df_filtrado.columns]
                
                path_seleccionado = st.multiselect(
                    "Jerarquía (Anillos):",
                    options=columnas_reales,
                    default=['Producto', 'Calidad', 'Calibre']
                )
                
                st.markdown("---")
                
                lotes_activos = sorted(df_filtrado['Lote'].unique())
                lotes_seleccionados = st.multiselect(
                    "Lotes visibles:",
                    options=lotes_activos,
                    default=lotes_activos
                )
            
            with col_sun_graf:
                if path_seleccionado and lotes_seleccionados:
                    num_cols = 1 if len(lotes_seleccionados) == 1 else 2
                    cols = st.columns(num_cols)
                    
                    for i, lote in enumerate(lotes_seleccionados):
                        with cols[i % num_cols]:
                            df_lote = df_filtrado[df_filtrado['Lote'] == lote]
                            total_lote = df_lote['Toneladas Calc'].sum()
                            
                            fig_sun = px.sunburst(
                                df_lote,
                                path=path_seleccionado,
                                values='Toneladas Calc',
                                color='Producto', 
                                color_discrete_sequence=px.colors.qualitative.Pastel,
                                title=f"<b>Lote {lote}</b><br>Total: {total_lote:.2f} t",
                                branchvalues="total"
                            )
                            fig_sun.update_layout(
                                margin=dict(t=50, l=0, r=0, b=0),
                                font=dict(family="Arial", size=14),
                                height=450 if num_cols == 1 else 350
                            )
                            st.plotly_chart(fig_sun, use_container_width=True)
                            
                elif not path_seleccionado:
                    st.warning("⚠️ Selecciona al menos una categoría para la jerarquía.")
                elif not lotes_seleccionados:
                    st.warning("⚠️ Selecciona al menos un Lote para visualizar.")


            st.markdown("---")

            # --- 4. TABLAS DE DETALLE ---
            st.subheader("📋 Tablas de Detalle")
            
            col_tabla1, col_tabla2 = st.columns(2)

            with col_tabla1:
                st.markdown("##### 📦 Resumen por Lote")
                resumen_lote = df_filtrado.groupby('Lote')[['Bandejas', 'Kilos Calc', 'Toneladas Calc']].sum().reset_index()
                resumen_lote.columns = ['Lote', 'Total Bandejas', 'Total Kilos', 'Total Toneladas']
                
                st.dataframe(
                    resumen_lote.style.format({
                        "Total Kilos": "{:,.1f}",
                        "Total Toneladas": "{:,.1f}",
                        "Total Bandejas": "{:,.0f}"
                    }), 
                    width="stretch",
                    hide_index=True
                )

            with col_tabla2:
                st.markdown("##### 👷 Resumen por Cuadrilla")
                resumen_cuadrilla = df_filtrado.groupby('Cuadrilla')[['Bandejas', 'Kilos Calc', 'Toneladas Calc']].sum().reset_index()
                resumen_cuadrilla.columns = ['Cuadrilla', 'Total Bandejas', 'Total Kilos', 'Total Toneladas']
                
                st.dataframe(
                    resumen_cuadrilla.style.format({
                        "Total Kilos": "{:,.1f}",
                        "Total Toneladas": "{:,.2f}",
                        "Total Bandejas": "{:,.0f}"
                    }), 
                    width="stretch",
                    hide_index=True
                )

    else:
        st.error("❌ No hay datos cargados.")

except Exception as e:
    st.error(f"❌ Error: {e}")






