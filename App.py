import base64
import datetime
import hashlib
import hmac
import io
import mimetypes
import re
import os
import random
import secrets
import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Pillow es opcional: si está disponible se usa para recortar/redimensionar la
# foto de perfil. Si no lo está, la imagen se guarda tal cual la subió el
# usuario (la app sigue funcionando igual).
try:
  from PIL import Image
  PIL_DISPONIBLE = True
except Exception:
  PIL_DISPONIBLE = False

# Carpeta local donde se guardará una copia de cada CSV subido por el usuario
CARPETA_CSV_SUBIDOS = "csv_subidos"

# Carpeta local donde se guardará el respaldo del histórico consolidado
# (reemplaza el respaldo que antes se subía a Google Drive)
CARPETA_RESPALDO_HISTORICO = "respaldo_historico"

# Archivos locales para el módulo de Ruleta y el sistema de Alertas
RUTA_HISTORICO_RULETA = "historico_ruleta.csv"
RUTA_HISTORICO_ALERTAS = "historico_alertas.csv"

# Archivos locales donde se persisten los usuarios del sistema (login) y el
# directorio de conductores, para que NO se pierdan al reiniciar la app o
# al desplegar cambios de código (antes solo vivían en memoria/sesión).
RUTA_USUARIOS_DB = "usuarios_db.csv"
RUTA_DRIVERS_DB = "directorio_conductores.csv"

# Carpeta donde se guardan las fotos de perfil de cada usuario.
# En el CSV de usuarios solo se guarda la RUTA del archivo (columna "Foto"),
# nunca la imagen completa, para que el CSV siga siendo liviano.
CARPETA_FOTOS_PERFIL = "fotos_perfil"
TAMANO_AVATAR_PX = 256
EXTENSIONES_FOTO_PERMITIDAS = ["png", "jpg", "jpeg", "webp"]
MAX_PESO_FOTO_MB = 5

st.set_page_config(
    page_title="Coffee Transportees ERP",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main { background-color: #1c1411; color: #fdfbf7; }
    .sidebar .sidebar-content { background-color: #120d0b; }
    h1, h2, h3 { color: #f4d06f !important; font-family: 'Helvetica Neue', sans-serif; }
    .stMetric { background-color: #261c17; padding: 15px; border-radius: 8px; border: 1px solid #4a3525; }
    .stButton>button {
        background-color: #d97736;
        color: white;
        border-radius: 6px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #f4d06f;
        color: #1c1411;
    }
    /* ---- Animación de carga (overlay) ---- */
    @keyframes ct-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes ct-pulse { 0%,100% { opacity: 0.45; } 50% { opacity: 1; } }
    .ct-loader-box {
        display: flex; align-items: center; gap: 14px;
        background-color: #261c17; border: 1px solid #4a3525;
        border-radius: 10px; padding: 14px 18px; margin: 10px 0;
    }
    .ct-loader-ring {
        width: 26px; height: 26px; flex: 0 0 26px;
        border: 3px solid #4a3525; border-top-color: #f4d06f;
        border-radius: 50%; animation: ct-spin 0.9s linear infinite;
    }
    .ct-loader-text { color: #f4d06f; font-weight: bold; font-size: 14px; animation: ct-pulse 1.4s ease-in-out infinite; }
    /* ---- Tabla de bitácora (paginada) ---- */
    .ct-table-wrap { max-height: 620px; overflow: auto; border: 1px solid #4a3525; border-radius: 8px; }
    .ct-table-wrap table { border-collapse: collapse; width: 100%; font-size: 13px; }
    .ct-table-wrap thead th {
        position: sticky; top: 0; z-index: 2;
        background-color: #120d0b; color: #f4d06f;
        text-align: left; padding: 8px 10px; border-bottom: 1px solid #4a3525; white-space: nowrap;
    }
    .ct-table-wrap tbody td { padding: 6px 10px; border-bottom: 1px solid #2b201a; color: #fdfbf7; white-space: nowrap; }
    .ct-table-wrap tbody tr:nth-child(even) { background-color: #1f1713; }
    /* Ocultar selector de tema / barra superior de Streamlit */
    div[data-testid="stToolbar"] {
        visibility: hidden;
    }
    /* Ocultar el menú de hamburguesa (Settings > Choose app theme) para forzar solo modo oscuro */
    #MainMenu {
        visibility: hidden;
    }

    /* Se oculta el control nativo de colapso de Streamlit (varía de nombre
       entre versiones y por eso a veces no aparece); se reemplaza por un
       botón propio, ver componente ct-mobile-menu-btn más abajo. */
    div[data-testid="stSidebarCollapsedControl"],
    div[data-testid="collapsedControl"] {
        display: none !important;
    }

    /* ============================================================
       MENÚ (SIDEBAR) FIJO EN VISTA DE ESCRITORIO
       En pantallas de PC el menú permanece siempre visible, sin
       poder colapsarse ni desaparecer.
       ============================================================ */
    @media (min-width: 769px) {
        section[data-testid="stSidebar"] {
            transform: none !important;
            visibility: visible !important;
            position: relative !important;
            min-width: 300px !important;
        }
        .ct-mobile-menu-btn { display: none !important; }
    }

    /* ============================================================
       RESPONSIVIDAD PARA DISPOSITIVOS MÓVILES
       El menú se desliza como panel lateral oculto por defecto y se
       abre/cierra con el botón redondo (☰) fijo en la esquina
       superior izquierda, agregado vía componente más abajo.
       ============================================================ */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 3.2rem !important;
        }
        h1 { font-size: 1.35rem !important; }
        h2 { font-size: 1.15rem !important; }
        h3 { font-size: 1rem !important; }
        .stMetric { padding: 10px !important; }
        .ct-loader-box { padding: 10px 12px !important; gap: 10px !important; }
        .ct-loader-text { font-size: 12px !important; }
        .ct-table-wrap { max-height: 420px !important; }
        .ct-table-wrap table { font-size: 11px !important; }
        .ct-table-wrap thead th, .ct-table-wrap tbody td { padding: 5px 6px !important; }

        section[data-testid="stSidebar"] {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            height: 100vh !important;
            min-width: 68vw !important;
            width: 68vw !important;
            max-width: 270px !important;
            z-index: 999998 !important;
            transform: translateX(-105%);
            transition: transform 0.25s ease-in-out;
            box-shadow: 2px 0 18px rgba(0, 0, 0, 0.55);
            overflow-y: auto !important;
        }
        section[data-testid="stSidebar"].ct-sidebar-open {
            transform: translateX(0) !important;
        }

        /* El logo grande de la tarjeta de marca se oculta en móvil para
           liberar espacio vertical: el menú es lo que importa ver sin
           tener que hacer scroll. Queda solo el nombre en texto. */
        section[data-testid="stSidebar"] div[data-testid="stImage"] {
            display: none !important;
        }
        section[data-testid="stSidebar"] .ct-brand-title {
            font-size: 13px !important;
            margin-top: 4px !important;
        }
        section[data-testid="stSidebar"] .ct-brand-subtitle {
            font-size: 9px !important;
        }
        /* Tarjetas del sidebar (marca, perfil, menú, enlaces) más compactas */
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 8px !important;
            margin-bottom: 8px !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
            padding: 4px 0 !important;
            font-size: 13px !important;
        }
    }

    /* Botón flotante (☰) que abre/cierra el menú en móvil */
    .ct-mobile-menu-btn {
        display: none;
        position: fixed;
        top: 12px;
        left: 12px;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background-color: #d97736;
        color: #1c1411;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        font-weight: bold;
        z-index: 999999;
        border: none;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }
    @media (max-width: 768px) {
        .ct-mobile-menu-btn { display: flex; }
    }

    /* ============================================================
       TARJETA DE MARCA (logo + nombre de la VTC) en el sidebar
       ============================================================ */
    div[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        border-color: #4a3525 !important;
        background-color: #211814;
    }
    .ct-brand-title {
        text-align: center; color: #f4d06f; font-weight: 800;
        font-size: 15px; letter-spacing: 1.5px; margin-top: 6px;
        text-transform: uppercase;
    }
    .ct-brand-subtitle {
        text-align: center; color: #9c8f84; font-size: 11px;
        letter-spacing: 0.6px; text-transform: uppercase; margin-top: 2px;
    }

    /* ============================================================
       TARJETA DE PERFIL (avatar + usuario + rol)
       ============================================================ */
    .ct-avatar {
        width: 44px; height: 44px; border-radius: 50%;
        background: linear-gradient(135deg, #d97736, #f4d06f);
        color: #1c1411; display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 18px; margin-top: 2px;
        flex: 0 0 auto;
    }
    /* st.image() se alinea a la izquierda de su columna por defecto;
       esto lo centra siempre (afecta el logo del login y del sidebar). */
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }
    /* Cuando el avatar es una foto real (etiqueta <img>) */
    img.ct-avatar {
        object-fit: cover;            /* recorta sin deformar la cara */
        border: 2px solid #f4d06f;
        display: block;
        background: #261c17;
    }
    .ct-avatar-lg { border-width: 3px; }
    /* Fila "avatar + texto" reutilizable en cualquier pantalla */
    .ct-avatar-row {
        display: flex; align-items: center; gap: 14px; margin-bottom: 6px;
    }
    .ct-profile-name {
        color: #fdfbf7; font-weight: 700; font-size: 15px; margin-bottom: 4px;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .ct-role-badge {
        display: inline-block; font-size: 10.5px; font-weight: 700;
        letter-spacing: 0.5px; text-transform: uppercase;
        padding: 2px 10px; border-radius: 20px;
    }
    .ct-role-badge.role-dueno { background: rgba(244, 208, 111, 0.15); color: #f4d06f; border: 1px solid #f4d06f; }
    .ct-role-badge.role-administrador { background: rgba(52, 152, 219, 0.15); color: #3498db; border: 1px solid #3498db; }
    .ct-role-badge.role-conductor { background: rgba(46, 204, 113, 0.15); color: #2ecc71; border: 1px solid #2ecc71; }

    /* ============================================================
       ENLACES Y COMUNIDAD (chips con icono)
       ============================================================ */
    .ct-link-chip {
        display: flex; align-items: center; gap: 10px;
        padding: 7px 10px; border-radius: 8px; margin-bottom: 4px;
        text-decoration: none !important; color: #fdfbf7 !important;
        font-size: 13px; font-weight: 500;
        transition: background-color 0.15s ease, transform 0.15s ease;
    }
    .ct-link-chip:hover {
        background-color: #33241b; transform: translateX(2px);
    }
    .ct-link-chip .ct-link-icon {
        width: 26px; height: 26px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 13px; flex: 0 0 26px;
    }

    /* ============================================================
       MENÚ DE NAVEGACIÓN PRINCIPAL
       Construido con botones (no radios) para que se vea y se
       comporte como un menú tradicional de página web, igual que
       la lista de "Enlaces y Comunidad".
       ============================================================ */
    div[data-testid="stSidebar"] .ct-nav-title {
        color: #9c8f84; font-size: 11px; font-weight: 700;
        letter-spacing: 1.5px; text-transform: uppercase; margin: 4px 0 6px 4px;
    }
    .st-key-ct_menu_nav div[data-testid="stVerticalBlock"] {
        gap: 2px !important;
    }
    .st-key-ct_menu_nav .stButton {
        margin: 0 !important;
    }
    .st-key-ct_menu_nav .stButton > button {
        background-color: transparent !important;
        color: #d8cfc7 !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        border-radius: 8px !important;
        width: 100% !important;
        padding: 9px 10px !important;
        margin: 0 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        text-align: left !important;
        justify-content: flex-start !important;
        box-shadow: none !important;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }
    .st-key-ct_menu_nav .stButton > button p {
        text-align: left !important;
    }
    .st-key-ct_menu_nav .stButton > button:hover {
        background-color: #261c17 !important;
        color: #fdfbf7 !important;
        border-left: 3px solid transparent !important;
    }
    .st-key-ct_menu_nav .stButton > button:focus:not(:active) {
        box-shadow: none !important;
        border-left: 3px solid transparent !important;
    }
    .st-key-ct_menu_nav .stButton > button[kind="primary"] {
        background-color: #3a2a1e !important;
        border-left: 3px solid #d97736 !important;
        color: #f4d06f !important;
        font-weight: 700 !important;
    }
    .st-key-ct_menu_nav .stButton > button[kind="primary"]:hover {
        background-color: #3a2a1e !important;
        color: #f4d06f !important;
        border-left: 3px solid #d97736 !important;
    }
    .st-key-ct_menu_nav .stButton > button[kind="primary"]:focus:not(:active) {
        border-left: 3px solid #d97736 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


def cargar_csv_historico_local():
  """Lee el archivo histórico consolidado desde el disco local, si existe."""
  ruta_historico = "historico_trucksbook.csv"
  if os.path.exists(ruta_historico):
    try:
      return pd.read_csv(ruta_historico)
    except Exception:
      return None
  return None

def guardar_csv_local(uploaded_file):
    """Guarda una copia del CSV subido en una carpeta local del proyecto.

    Crea la carpeta (si no existe) y aloja allí el archivo con un
    nombre único basado en la fecha/hora de subida, para no
    sobrescribir cargas anteriores.
    """
    os.makedirs(CARPETA_CSV_SUBIDOS, exist_ok=True)

    marca_tiempo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"{marca_tiempo}_{uploaded_file.name}"
    ruta_destino = os.path.join(CARPETA_CSV_SUBIDOS, nombre_archivo)

    uploaded_file.seek(0)
    with open(ruta_destino, "wb") as f_destino:
        f_destino.write(uploaded_file.getbuffer())
    uploaded_file.seek(0)

    return ruta_destino


def guardar_respaldo_historico_local(df_consolidado):
    """Guarda una copia de respaldo del histórico consolidado en una carpeta local.

    Crea la carpeta (si no existe) dentro de la ruta donde se ejecuta
    app.py y aloja allí una copia con marca de tiempo. Reemplaza el
    respaldo que antes se subía a Google Drive.
    """
    os.makedirs(CARPETA_RESPALDO_HISTORICO, exist_ok=True)

    marca_tiempo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"historico_trucksbook_{marca_tiempo}.csv"
    ruta_destino = os.path.join(CARPETA_RESPALDO_HISTORICO, nombre_archivo)

    df_consolidado.to_csv(ruta_destino, index=False, encoding="utf-8-sig")

    return ruta_destino
def integrar_y_guardar_historico(df_nuevos):
    """Fusiona los nuevos datos con el histórico local sin perder nada ni duplicar."""
    ruta_historico = "historico_trucksbook.csv"
    
    if os.path.exists(ruta_historico):
        df_historico = pd.read_csv(ruta_historico)
        df_combinado = pd.concat([df_historico, df_nuevos], ignore_index=True)
        
        if "generar_firma_unica" in globals():
            df_combinado["firma"] = generar_firma_unica(df_combinado)
            df_combinado = df_combinado.drop_duplicates(subset=["firma"]).drop(columns=["firma"])
        else:
            df_combinado = df_combinado.drop_duplicates()
    else:
        df_combinado = df_nuevos.drop_duplicates()

    df_combinado.to_csv(ruta_historico, index=False, encoding="utf-8-sig")
    st.success(f"¡Proceso exitoso! Se actualizaron los datos correctamente.")
    return df_combinado        
def generar_firma_unica(df):
  """Clave primaria compuesta para impedir duplicar el mismo viaje."""
  return (
      df["Nombre"].astype(str).str.strip().str.upper() + "_" +
      df["Juego"].astype(str).str.strip().str.upper() + "_" +
      df["Fecha"].astype(str) + "_" +
      df["Desde"].astype(str).str.strip() + "_" +
      df["Hasta"].astype(str).str.strip() + "_" +
      df["Dist. Aceptada"].astype(str).str.strip()
  )


# =============================================================================
# MÓDULO RULETA (sorteo de DLC)
# =============================================================================

def cargar_historico_ruleta():
  """Lee el histórico de sorteos de la ruleta desde el disco local."""
  columnas = ["Fecha", "DLC", "Ganador", "Participantes", "Registrado por"]
  if os.path.exists(RUTA_HISTORICO_RULETA):
    try:
      df = pd.read_csv(RUTA_HISTORICO_RULETA)
      for col in columnas:
        if col not in df.columns:
          df[col] = ""
      return df[columnas]
    except Exception:
      return pd.DataFrame(columns=columnas)
  return pd.DataFrame(columns=columnas)


def guardar_ganador_ruleta(dlc, ganador, participantes, registrado_por):
  """Agrega un nuevo resultado de sorteo al histórico de la ruleta."""
  nueva_fila = pd.DataFrame([{
      "Fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "DLC": dlc,
      "Ganador": ganador,
      "Participantes": ", ".join(participantes),
      "Registrado por": registrado_por,
  }])
  historico = cargar_historico_ruleta()
  combinado = pd.concat([historico, nueva_fila], ignore_index=True)
  combinado.to_csv(RUTA_HISTORICO_RULETA, index=False, encoding="utf-8-sig")
  return combinado


# =============================================================================
# SISTEMA DE ALERTAS
# =============================================================================

def cargar_alertas():
  """Lee el histórico de alertas/notificaciones desde el disco local."""
  columnas = ["Fecha", "Categoria", "Icono", "Descripcion"]
  if os.path.exists(RUTA_HISTORICO_ALERTAS):
    try:
      df = pd.read_csv(RUTA_HISTORICO_ALERTAS)
      for col in columnas:
        if col not in df.columns:
          df[col] = ""
      return df[columnas]
    except Exception:
      return pd.DataFrame(columns=columnas)
  return pd.DataFrame(columns=columnas)


def registrar_alerta(categoria, descripcion, icono="🔔"):
  """Agrega una nueva notificación al histórico compartido de alertas.

  Categorías esperadas: "Estadísticas", "Podio", "Ruleta", "Chat".
  Al estar persistido en un CSV compartido, todos los usuarios (sin
  importar su sesión o rol) ven la misma bandeja de alertas.
  """
  nueva_fila = pd.DataFrame([{
      "Fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "Categoria": categoria,
      "Icono": icono,
      "Descripcion": descripcion,
  }])
  historico = cargar_alertas()
  combinado = pd.concat([historico, nueva_fila], ignore_index=True)
  combinado.to_csv(RUTA_HISTORICO_ALERTAS, index=False, encoding="utf-8-sig")
  return combinado


def mostrar_icono_alertas():
  """Muestra el ícono de campana con las notificaciones recientes.

  Visible para todos los usuarios (cualquier rol). El contador de
  "no leídas" se calcula comparando la marca de tiempo de la última
  vez que el usuario abrió el panel (guardada en la sesión) contra
  el histórico de alertas compartido.
  """
  alertas = cargar_alertas()
  if "alertas_vistas_en" not in st.session_state:
    # La primera vez que el usuario entra en la sesión, se marcan como
    # leídas las alertas ya existentes hasta ese momento.
    st.session_state.alertas_vistas_en = datetime.datetime.now()

  no_leidas = 0
  if not alertas.empty:
    fechas = pd.to_datetime(alertas["Fecha"], errors="coerce")
    no_leidas = int((fechas > st.session_state.alertas_vistas_en).sum())

  etiqueta = f"🔔 Alertas ({no_leidas})" if no_leidas > 0 else "🔔 Alertas"
  col_alerta, _col_relleno = st.columns([1, 5])
  with col_alerta:
    with st.popover(etiqueta, use_container_width=True):
      st.markdown("#### Notificaciones recientes")
      if alertas.empty:
        st.caption("Todavía no hay notificaciones registradas.")
      else:
        recientes = alertas.sort_values("Fecha", ascending=False).head(20)
        for _, fila in recientes.iterrows():
          st.markdown(
              f"""
              <div style="background-color: #261c17; border: 1px solid #4a3525;
                          border-radius: 8px; padding: 8px 12px; margin-bottom: 8px;">
                  <div style="font-size: 12px; color: #b0a8a0;">{fila['Fecha']} · {fila['Categoria']}</div>
                  <div style="font-size: 14px; color: #fdfbf7;">{fila['Icono']} {fila['Descripcion']}</div>
              </div>
              """,
              unsafe_allow_html=True,
          )
      if st.button("Marcar todo como leído", use_container_width=True):
        st.session_state.alertas_vistas_en = datetime.datetime.now()
        st.rerun()


# =============================================================================
# PERSISTENCIA DE USUARIOS (LOGIN) Y DIRECTORIO DE CONDUCTORES
# =============================================================================
# Antes, "users_db" y "drivers_db" solo vivían en st.session_state: al
# reiniciar el servidor (o desplegar un cambio de código) se perdían todos
# los usuarios/conductores creados manualmente. Ahora se guardan en CSV en
# disco, igual que el histórico de TrucksBook, la ruleta y las alertas.

_USUARIOS_DB_SEMILLA = [
    {"ID": 1, "Usuario": "Calderon", "Contraseña": "123", "Rol": "Dueño"},
    {"ID": 2, "Usuario": "Wajojk13", "Contraseña": "123", "Rol": "Administrador"},
    {"ID": 3, "Usuario": "MrGerzon", "Contraseña": "123", "Rol": "Conductor"},
]

# Esquema completo de la tabla de usuarios. Las columnas nuevas (Foto,
# Pregunta, Respuesta, Correo) se agregan automáticamente a los CSV viejos
# mediante normalizar_usuarios_df(), así que NO hay que borrar usuarios_db.csv.
COLUMNAS_USUARIOS = [
    "ID",          # identificador numérico
    "Usuario",     # nombre de login
    "Contraseña",  # hash pbkdf2 (o texto plano heredado, se migra al entrar)
    "Rol",         # Dueño / Administrador / Conductor
    "Foto",        # ruta relativa al archivo de imagen, o "" si no tiene
    "Pregunta",    # pregunta de seguridad para recuperar la contraseña
    "Respuesta",   # hash de la respuesta de seguridad
    "Correo",      # correo de contacto (opcional, para avisos manuales)
]

PREGUNTAS_SEGURIDAD = [
    "¿Cuál fue tu primer camión favorito en el juego?",
    "¿Cuál es el nombre de tu primera mascota?",
    "¿En qué ciudad naciste?",
    "¿Cuál es tu comida favorita?",
    "¿Cómo se llamaba tu mejor amigo de la infancia?",
]


# -----------------------------------------------------------------------------
# SEGURIDAD DE CONTRASEÑAS
# -----------------------------------------------------------------------------
# Hasta ahora las contraseñas se guardaban en texto plano dentro del CSV:
# cualquiera que abriera usuarios_db.csv las veía todas. Se pasa a PBKDF2 con
# sal aleatoria por usuario. Formato guardado:  pbkdf2$<iteraciones>$<sal>$<hash>
_ITERACIONES_PBKDF2 = 200_000


def hash_password(texto_plano):
  """Devuelve el hash seguro (con sal aleatoria) de una contraseña."""
  sal = secrets.token_hex(16)
  digest = hashlib.pbkdf2_hmac(
      "sha256", str(texto_plano).encode("utf-8"), sal.encode("utf-8"),
      _ITERACIONES_PBKDF2,
  ).hex()
  return f"pbkdf2${_ITERACIONES_PBKDF2}${sal}${digest}"


def es_hash(valor):
  """True si el valor guardado ya está hasheado (y no es texto plano viejo)."""
  return str(valor).startswith("pbkdf2$")


def verificar_password(texto_plano, valor_guardado):
  """Compara una contraseña escrita con lo que hay en el CSV.

  Acepta tanto hashes nuevos como contraseñas antiguas en texto plano, para
  que los usuarios que ya existían puedan seguir entrando sin cambios.
  """
  valor_guardado = str(valor_guardado)
  if not es_hash(valor_guardado):
    return hmac.compare_digest(str(texto_plano), valor_guardado)
  try:
    _, iteraciones, sal, digest = valor_guardado.split("$")
    calculado = hashlib.pbkdf2_hmac(
        "sha256", str(texto_plano).encode("utf-8"), sal.encode("utf-8"),
        int(iteraciones),
    ).hex()
    return hmac.compare_digest(calculado, digest)
  except Exception:
    return False


def normalizar_respuesta_seguridad(texto):
  """Normaliza la respuesta de seguridad (minúsculas, sin tildes ni espacios
  de más) para que 'Bogotá ' y 'bogota' se consideren iguales."""
  texto = str(texto).strip().lower()
  reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}
  for origen, destino in reemplazos.items():
    texto = texto.replace(origen, destino)
  return re.sub(r"\s+", " ", texto)


# -----------------------------------------------------------------------------
# FOTOS DE PERFIL
# -----------------------------------------------------------------------------


def guardar_foto_perfil(usuario, archivo_subido):
  """Guarda la foto de un usuario en disco y devuelve su ruta relativa.

  Si Pillow está instalado, la imagen se recorta en cuadrado y se reduce a
  TAMANO_AVATAR_PX para que el avatar pese poco y se vea bien redondeado.
  Devuelve "" si no se pudo guardar.
  """
  if archivo_subido is None:
    return ""
  os.makedirs(CARPETA_FOTOS_PERFIL, exist_ok=True)
  # Nombre de archivo seguro y estable a partir del usuario.
  slug = re.sub(r"[^a-zA-Z0-9_-]", "_", str(usuario)).strip("_") or "usuario"
  datos = archivo_subido.getvalue()

  if PIL_DISPONIBLE:
    try:
      img = Image.open(io.BytesIO(datos))
      img = img.convert("RGB")
      # Recorte centrado a cuadrado
      ancho, alto = img.size
      lado = min(ancho, alto)
      izq = (ancho - lado) // 2
      arr = (alto - lado) // 2
      img = img.crop((izq, arr, izq + lado, arr + lado))
      img = img.resize((TAMANO_AVATAR_PX, TAMANO_AVATAR_PX), Image.LANCZOS)
      ruta = os.path.join(CARPETA_FOTOS_PERFIL, f"{slug}.jpg")
      img.save(ruta, format="JPEG", quality=88)
      return ruta
    except Exception:
      pass

  # Sin Pillow (o si falló): se guarda el archivo tal cual.
  extension = os.path.splitext(archivo_subido.name)[1].lower() or ".png"
  ruta = os.path.join(CARPETA_FOTOS_PERFIL, f"{slug}{extension}")
  with open(ruta, "wb") as f:
    f.write(datos)
  return ruta


def eliminar_foto_perfil(ruta):
  """Borra del disco la foto de perfil indicada (si existe)."""
  try:
    if ruta and os.path.exists(ruta):
      os.remove(ruta)
  except Exception:
    pass


@st.cache_data(show_spinner=False)
def _foto_a_data_uri(ruta, marca_tiempo):
  """Convierte una imagen del disco en un data URI base64 para incrustarla
  dentro del HTML del avatar.

  'marca_tiempo' es la fecha de modificación del archivo: sirve solo para
  invalidar la caché cuando el usuario cambia su foto.
  """
  del marca_tiempo  # solo actúa como clave de caché
  try:
    tipo = mimetypes.guess_type(ruta)[0] or "image/png"
    with open(ruta, "rb") as f:
      b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{tipo};base64,{b64}"
  except Exception:
    return ""


def obtener_foto_data_uri(ruta):
  """Devuelve el data URI de la foto, o "" si el usuario no tiene foto."""
  ruta = str(ruta or "").strip()
  if not ruta or ruta.lower() == "nan" or not os.path.exists(ruta):
    return ""
  return _foto_a_data_uri(ruta, os.path.getmtime(ruta))


def buscar_usuario(nombre_usuario):
  """Devuelve la fila (Series) del usuario indicado, o None si no existe."""
  df = st.session_state.get("users_db")
  if df is None or df.empty:
    return None
  coincidencias = df[df["Usuario"].astype(str).str.lower()
                     == str(nombre_usuario).strip().lower()]
  if coincidencias.empty:
    return None
  return coincidencias.iloc[0]


def render_avatar_html(nombre_usuario, tamano=44, clase_extra=""):
  """Genera el HTML del avatar de un usuario: su foto si la tiene, o el
  círculo con la inicial (comportamiento anterior) si no la tiene.

  Se usa en el sidebar, en el saludo de Inicio, en el directorio, etc., para
  que la foto aparezca igual en toda la interfaz.
  """
  fila = buscar_usuario(nombre_usuario)
  data_uri = obtener_foto_data_uri(fila["Foto"]) if fila is not None else ""
  estilo = f"width:{tamano}px;height:{tamano}px;font-size:{max(12, int(tamano * 0.4))}px;"
  if data_uri:
    return (
        f"<img class='ct-avatar {clase_extra}' style='{estilo}' "
        f"src='{data_uri}' alt='{nombre_usuario}' />"
    )
  inicial = str(nombre_usuario or "?").strip()[:1].upper() or "?"
  return f"<div class='ct-avatar {clase_extra}' style='{estilo}'>{inicial}</div>"

_DRIVERS_DB_SEMILLA = [
    {
        "ID": 1,
        "Nombre / Tag": "El puma (CT)",
        "Ingreso": "2026-08-28",
        "Rol": "Administrador",
        "Juego": "Ambos",
        "Teléfono": "3147780213",
        "Lu": "20:00",
        "Ma": "-",
        "Mi": "20:00",
        "Ju": "20:00",
        "Vi": "08:00",
        "Sa": "-",
        "Do": "20:00",
    },
    {
        "ID": 2,
        "Nombre / Tag": "Wajojk13",
        "Ingreso": "2026-08-31",
        "Rol": "Conductor",
        "Juego": "ATS",
        "Teléfono": "3229042583",
        "Lu": "20:00",
        "Ma": "20:00",
        "Mi": "-",
        "Ju": "-",
        "Vi": "20:00",
        "Sa": "-",
        "Do": "-",
    },
    {
        "ID": 3,
        "Nombre / Tag": "MrGerzon",
        "Ingreso": "2026-09-01",
        "Rol": "Conductor",
        "Juego": "ETS2",
        "Teléfono": "3016008882",
        "Lu": "09:00",
        "Ma": "09:00",
        "Mi": "09:00",
        "Ju": "09:00",
        "Vi": "09:00",
        "Sa": "09:00",
        "Do": "09:00",
    },
]


COLUMNAS_DIRECTORIO = [
    "Nombre / Tag", "Ingreso", "Rol", "Juego", "Teléfono",
    "Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do",
]

MAPEO_COLUMNAS_DIRECTORIO_CSV = {
    "nombre": "Nombre / Tag",
    "fecha_ingreso": "Ingreso",
    "rol": "Rol",
    "juego": "Juego",
    "telefono": "Teléfono",
    "teléfono": "Teléfono",
    "lunes": "Lu",
    "martes": "Ma",
    "miercoles": "Mi",
    "miércoles": "Mi",
    "jueves": "Ju",
    "viernes": "Vi",
    "sabado": "Sa",
    "sábado": "Sa",
    "domingo": "Do",
}


def normalizar_drivers_df(df_raw):
  """Normaliza un DataFrame de conductores (venga de un CSV externo o de un
  directorio_conductores.csv con un esquema de columnas antiguo/distinto) al
  esquema interno esperado por la app: ID + COLUMNAS_DIRECTORIO.

  Esto evita KeyError: 'Nombre / Tag' cuando el CSV persistido en disco
  quedó guardado con encabezados como "Nombre", "Fecha_Ingreso",
  "Telefono", "Lunes", etc. en vez de los nombres internos."""
  renombres = {
      col: MAPEO_COLUMNAS_DIRECTORIO_CSV[col.strip().lower()]
      for col in df_raw.columns
      if col.strip().lower() in MAPEO_COLUMNAS_DIRECTORIO_CSV
  }
  df = df_raw.rename(columns=renombres)

  for col in COLUMNAS_DIRECTORIO:
    if col not in df.columns:
      df[col] = "-"

  if "ID" not in df.columns:
    df["ID"] = range(1, len(df) + 1)
  else:
    # El CSV se lee con dtype=str para blindar el resto de columnas, pero
    # "ID" debe ser numérico (se usa como int en otras partes de la app:
    # int(drivers_db["ID"].max() + 1)). Lo convertimos de vuelta aquí.
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
    if df["ID"].notna().any():
      siguiente_id = int(df["ID"].max()) + 1
    else:
      siguiente_id = 1
    for idx in df.index[df["ID"].isna()]:
      df.loc[idx, "ID"] = siguiente_id
      siguiente_id += 1
    df["ID"] = df["ID"].astype(int)

  df["Nombre / Tag"] = df["Nombre / Tag"].astype(str).str.strip()
  df = df[(df["Nombre / Tag"] != "") & (df["Nombre / Tag"].str.lower() != "nan")]

  for col in COLUMNAS_DIRECTORIO:
    if col != "Nombre / Tag":
      df[col] = df[col].fillna("-").astype(str).str.strip().replace("", "-")

  return df[["ID"] + COLUMNAS_DIRECTORIO].reset_index(drop=True)


def normalizar_usuarios_df(df_raw):
  """Lleva cualquier usuarios_db.csv (viejo o nuevo) al esquema actual.

  Agrega las columnas que falten (Foto, Pregunta, Respuesta, Correo) vacías,
  de forma que un CSV creado por la versión anterior de la app siga sirviendo
  sin que se pierda ningún usuario.
  """
  df = df_raw.copy()
  for col in COLUMNAS_USUARIOS:
    if col not in df.columns:
      df[col] = "" if col != "ID" else range(1, len(df) + 1)

  df["ID"] = pd.to_numeric(df["ID"], errors="coerce")
  if df["ID"].isna().any():
    siguiente = int(df["ID"].max()) + 1 if df["ID"].notna().any() else 1
    for idx in df.index[df["ID"].isna()]:
      df.loc[idx, "ID"] = siguiente
      siguiente += 1
  df["ID"] = df["ID"].astype(int)

  for col in ["Usuario", "Contraseña", "Rol", "Foto", "Pregunta", "Respuesta", "Correo"]:
    df[col] = df[col].fillna("").astype(str).str.strip()
    df[col] = df[col].replace("nan", "")

  df = df[df["Usuario"] != ""]
  return df[COLUMNAS_USUARIOS].reset_index(drop=True)


def cargar_usuarios_db():
  """Carga los usuarios (credenciales de login) desde el CSV local.

  Si el archivo no existe todavía (primera vez que corre la app), se crea
  con los usuarios semilla por defecto para no dejar el sistema sin acceso.
  """
  if os.path.exists(RUTA_USUARIOS_DB):
    try:
      df = pd.read_csv(RUTA_USUARIOS_DB, dtype=str)
      if not df.empty:
        df = normalizar_usuarios_df(df)
        if not df.empty:
          # Auto-repara el CSV en disco si venía con el esquema antiguo.
          guardar_usuarios_db(df)
          return df
    except Exception:
      pass
  df_semilla = normalizar_usuarios_df(pd.DataFrame(_USUARIOS_DB_SEMILLA))
  df_semilla.to_csv(RUTA_USUARIOS_DB, index=False, encoding="utf-8-sig")
  return df_semilla


def guardar_usuarios_db(df_usuarios):
  """Persiste en disco los usuarios de login. Debe llamarse cada vez que
  se crea, edita o elimina un usuario para que el cambio no se pierda."""
  df_usuarios.to_csv(RUTA_USUARIOS_DB, index=False, encoding="utf-8-sig")


def cargar_drivers_db():
  """Carga el directorio de conductores desde el CSV local.

  Si el archivo no existe todavía, se crea con el directorio semilla
  por defecto.
  """
  if os.path.exists(RUTA_DRIVERS_DB):
    try:
      df = pd.read_csv(RUTA_DRIVERS_DB, dtype=str)
      if not df.empty:
        df = normalizar_drivers_df(df)
        if not df.empty:
          # Auto-repara en disco el CSV si tenía un esquema de columnas
          # antiguo/distinto, para que este arreglo no se pierda al
          # reiniciar la app.
          guardar_drivers_db(df)
          return df
    except Exception:
      pass
  df_semilla = pd.DataFrame(_DRIVERS_DB_SEMILLA)
  df_semilla.to_csv(RUTA_DRIVERS_DB, index=False, encoding="utf-8-sig")
  return df_semilla


def guardar_drivers_db(df_drivers):
  """Persiste en disco el directorio de conductores. Debe llamarse cada
  vez que se agrega, edita o elimina un conductor."""
  df_drivers.to_csv(RUTA_DRIVERS_DB, index=False, encoding="utf-8-sig")


# =============================================================================
# CAPA DE RENDIMIENTO
# =============================================================================

FILAS_POR_PAGINA_OPCIONES = [50, 100, 200, 500]
FILAS_POR_PAGINA_DEFECTO = 100


def mostrar_cargando(placeholder, mensaje="Procesando información..."):
  """Pinta una animación de carga dentro de un placeholder de Streamlit."""
  placeholder.markdown(
      f"""
      <div class="ct-loader-box">
          <div class="ct-loader-ring"></div>
          <div class="ct-loader-text">{mensaje}</div>
      </div>
      """,
      unsafe_allow_html=True,
  )


def _a_numero(serie):
  """Convierte '1.243 km' / '1 106 km' / None a float sin lanzar excepciones."""
  limpio = (
      serie.astype(str)
      .str.replace(r"[^0-9]", "", regex=True)
      .replace("", None)
  )
  return pd.to_numeric(limpio, errors="coerce").fillna(0.0)


@st.cache_data(show_spinner=False)
def preparar_bitacora(df):
  """Normaliza la bitácora una sola vez: fecha datetime + distancia numérica."""
  df_prep = df.copy()

  if "Fecha" in df_prep.columns:
    df_prep["_Fecha_dt"] = pd.to_datetime(df_prep["Fecha"], errors="coerce")
  else:
    df_prep["_Fecha_dt"] = pd.NaT

  if "Distancia_Num" in df_prep.columns:
    df_prep["Distancia_Num"] = pd.to_numeric(
        df_prep["Distancia_Num"], errors="coerce"
    ).fillna(0.0)
  elif "Dist. Aceptada" in df_prep.columns:
    df_prep["Distancia_Num"] = _a_numero(df_prep["Dist. Aceptada"])
  elif "Dist. Estimada" in df_prep.columns:
    df_prep["Distancia_Num"] = _a_numero(df_prep["Dist. Estimada"])
  else:
    df_prep["Distancia_Num"] = 0.0

  if "Nombre" in df_prep.columns:
    df_prep["Nombre"] = df_prep["Nombre"].astype(str)
  if "Juego" in df_prep.columns:
    df_prep["Juego"] = df_prep["Juego"].astype(str)

  return df_prep


@st.cache_data(show_spinner=False)
def filtrar_bitacora(df, conductor, simulador, fecha_desde, fecha_hasta):
  """Filtrado vectorizado y cacheado. Devuelve solo el subconjunto pedido."""
  mascara = pd.Series(True, index=df.index)

  if conductor and conductor != "Todos los conductores":
    mascara &= df["Nombre"] == conductor

  if simulador and simulador != "Ambos" and "Juego" in df.columns:
    mascara &= df["Juego"].str.contains(simulador, case=False, na=False)

  if fecha_desde is not None:
    mascara &= df["_Fecha_dt"] >= pd.Timestamp(fecha_desde)
  if fecha_hasta is not None:
    mascara &= df["_Fecha_dt"] < pd.Timestamp(fecha_hasta) + pd.Timedelta(days=1)

  return df[mascara]


@st.cache_data(show_spinner=False)
def lista_conductores_bitacora(df):
  """Lista de conductores cacheada."""
  if "Nombre" not in df.columns or df.empty:
    return ["Todos los conductores"]
  return ["Todos los conductores"] + sorted(df["Nombre"].unique().tolist())


@st.cache_data(show_spinner=False)
def resumen_bitacora(df):
  """Métricas agregadas del resultado filtrado."""
  if df.empty:
    return {"registros": 0, "km": 0.0, "conductores": 0}
  return {
      "registros": int(len(df)),
      "km": float(df["Distancia_Num"].sum())
      if "Distancia_Num" in df.columns
      else 0.0,
      "conductores": int(df["Nombre"].nunique()) if "Nombre" in df.columns else 0,
  }


@st.cache_data(show_spinner=False)
def filtrar_periodo_simulador(df, simulador, anio, mes):
  """Filtra por simulador + año/mes usando la fecha ya convertida (cacheado)."""
  if df.empty or "Juego" not in df.columns:
    return df.iloc[0:0]
  
  patron = r"\bETS" if "ETS" in simulador.upper() else r"\bATS"
  mascara = df["Juego"].str.contains(patron, case=False, na=False, regex=True)
  
  if "_Fecha_dt" in df.columns:
    mascara &= (df["_Fecha_dt"].dt.year == anio) & (df["_Fecha_dt"].dt.month == mes)
  
  return df[mascara]


@st.cache_data(show_spinner=False)
def resumen_por_conductor(df):
  """Agregación por conductor en una sola pasada."""
  if df.empty or "Nombre" not in df.columns:
    return pd.DataFrame(
        columns=[
            "Conductor",
            "Total Registrado",
            "KM Real",
            "KM Carrera",
            "Promedio Diario",
        ]
    )

  base = df.copy()
  modalidad = base.get("Modalidad", pd.Series("", index=base.index)).astype(str)
  base["_km_real"] = base["Distancia_Num"].where(modalidad == "Real", 0.0)
  base["_km_carrera"] = base["Distancia_Num"].where(modalidad == "Carrera", 0.0)

  agrupado = (
      base.groupby("Nombre", sort=False)
      .agg(
          **{
              "Total Registrado": ("Distancia_Num", "sum"),
              "KM Real": ("_km_real", "sum"),
              "KM Carrera": ("_km_carrera", "sum"),
          }
      )
      .reset_index()
      .rename(columns={"Nombre": "Conductor"})
  )
  agrupado["Promedio Diario"] = agrupado["Total Registrado"] // 30
  return agrupado.sort_values(
      by="Total Registrado", ascending=False
  ).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def bitacora_a_csv(df):
  """CSV del resultado COMPLETO."""
  return df.drop(columns=["_Fecha_dt"], errors="ignore").to_csv(
      index=False
  ).encode("utf-8-sig")


def compactar_html(html):
  """Quita saltos de línea y sangría del HTML."""
  return "".join(linea.strip() for linea in str(html).splitlines())


def _fmt_juego(val):
  v = str(val).upper().strip()
  if "ATS" in v:
    return "<span style='color: #e74c3c; font-weight: bold;'>🔴 ATS</span>"
  if "ETS" in v:
    return "<span style='color: #3498db; font-weight: bold;'>🔵 ETS2</span>"
  return str(val)


def _fmt_entrega(val):
  v = str(val).lower().strip()
  if "real" in v:
    return "<span style='color: #2ecc71; font-weight: bold;'>🟢 Real</span>"
  if "wotr" in v:
    return "<span style='color: #e67e22; font-weight: bold;'>🟠 Wotr</span>"
  if "carrera" in v:
    return "<span style='color: #e74c3c; font-weight: bold;'>🔴 Carrera</span>"
  if "estándar" in v or "estandar" in v:
    return "<span style='color: #3498db; font-weight: bold;'>🔵 Estándar</span>"
  return str(val)


def _fmt_modalidad(val):
  v = str(val).lower().strip()
  if "real" in v:
    return "<span style='color: #2ecc71; font-weight: bold;'>🟢 Real</span>"
  if "wotr" in v:
    return "<span style='color: #e67e22; font-weight: bold;'>🟠 Wotr</span>"
  if "excluido" in v:
    return "<span style='color: #7f8c8d; font-weight: bold;'>⚪ Excluido (>180 km/h)</span>"
  if "carrera" in v:
    return "<span style='color: #e74c3c; font-weight: bold;'>🔴 Carrera</span>"
  return str(val)


def _fmt_tiempo(val):
  s = str(val).strip()
  try:
    total_segundos = int(float(s))
  except (ValueError, TypeError):
    return f"<span style='color: #9b59b6; font-weight: bold;'>{s}</span>"
  horas = total_segundos // 3600
  minutos = (total_segundos % 3600) // 60
  segundos = total_segundos % 60
  formateado = f"{horas}:{minutos:02d}:{segundos:02d}"
  return f"<span style='color: #9b59b6; font-weight: bold;'>{formateado}</span>"


def _fmt_multas(val):
  s = str(val).strip()
  digitos = re.sub(r"[^\d]", "", s)
  monto = int(digitos) if digitos else 0
  color = "#e74c3c" if monto > 0 else "#2ecc71"
  return f"<span style='color: {color}; font-weight: bold;'>{s}</span>"


_FORMATOS_BITACORA = {
    "Juego": _fmt_juego,
    "Entrega": _fmt_entrega,
    "Modalidad": _fmt_modalidad,
    "Tiempo Real": _fmt_tiempo,
    "Multas": _fmt_multas,
}


@st.cache_data(show_spinner=False)
def render_pagina_html(df_pagina):
  """Genera el HTML SOLO de la página visible."""
  df_display = df_pagina.drop(
      columns=["Distancia_Num", "Fecha", "_Fecha_dt"], errors="ignore"
  ).copy()

  for columna, formateador in _FORMATOS_BITACORA.items():
    if columna in df_display.columns:
      serie = df_display[columna]
      mapa = {v: formateador(v) for v in serie.astype(str).unique()}
      df_display[columna] = serie.astype(str).map(mapa)

  tabla = compactar_html(df_display.to_html(escape=False, index=False, border=0))
  return f"<div class='ct-table-wrap'>{tabla}</div>"


if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
if "user" not in st.session_state:
  st.session_state.user = None
if "role" not in st.session_state:
  st.session_state.role = None

if "meta_ats" not in st.session_state:
  st.session_state.meta_ats = 62000
if "meta_ets2" not in st.session_state:
  st.session_state.meta_ets2 = 10000

if "report_anio" not in st.session_state:
  st.session_state.report_anio = 2026
if "report_mes" not in st.session_state:
  st.session_state.report_mes = 9
if "report_tab" not in st.session_state:
  st.session_state.report_tab = "ATS"

if "convoys_db" not in st.session_state:
  st.session_state.convoys_db = [
      {
          "id": 1,
          "titulo": "Sem 36 - Lunes (Los Angeles)",
          "semana": "36",
          "dia": "Lunes",
          "origen": "Los Angeles",
      }
  ]
if "reuniones_db" not in st.session_state:
  st.session_state.reuniones_db = [
      {"id": 1, "titulo": "Día 15 - Quincenal", "tipo": "Quincenal", "dia": "15"},
      {"id": 2, "titulo": "Día 30 - Mensual", "tipo": "Mensual", "dia": "30"},
  ]
if "asistencias_registros" not in st.session_state:
  st.session_state.asistencias_registros = {}

if "users_db" not in st.session_state:
  st.session_state.users_db = cargar_usuarios_db()

if "drivers_db" not in st.session_state:
  st.session_state.drivers_db = cargar_drivers_db()


if "trucksbook_data" not in st.session_state:
  df_local = cargar_csv_historico_local()
  if df_local is not None and not df_local.empty:
    st.session_state.trucksbook_data = df_local
  else:
    # Dataset inicial mientras se crea el primer registro local
    st.session_state.trucksbook_data = pd.DataFrame([
        {
            "Nombre": "WAJOIK13",
            "Juego": "ATS",
            "Entrega": "Wotr",
            "Desde": "Camp Verde",
            "Hasta": "Oakland",
            "Dist. Estimada": "1.243 km",
            "Dist. Aceptada": "1.224 km",
            "Vel. Máx": "125 km/h",
            "Modalidad": "Real",
            "Beneficio": "161 546 $",
            "Multas": "27 920 $",
            "Daños": "0",
            "Tiempo Real": "7900",
            "Fecha": "2026-09-01",
        },
      {
          "Nombre": "profeta(CT)",
          "Juego": "ATS",
          "Entrega": "Estándar",
          "Desde": "Coastline Mining",
          "Hasta": "Waldens",
          "Dist. Estimada": "1 105 km",
          "Dist. Aceptada": "1 106 km",
          "Vel. Máx": "105 km/h",
          "Modalidad": "Real",
          "Beneficio": "110 933 $",
          "Multas": "0 $",
          "Daños": "0",
          "Tiempo Real": "3046",
          "Fecha": "2026-09-05",
      },
      {
          "Nombre": "CRAZY_GAMER_16",
          "Juego": "ETS2",
          "Entrega": "Estándar",
          "Desde": "BLT",
          "Hasta": "Norrfood",
          "Dist. Estimada": "128 km",
          "Dist. Aceptada": "130 km",
          "Vel. Máx": "100 km/h",
          "Modalidad": "Carrera",
          "Beneficio": "3 184 €",
          "Multas": "0 €",
          "Daños": "10",
          "Tiempo Real": "1455",
          "Fecha": "2026-09-02",
      },
  ])

meses_dict = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
nombres_meses_lista = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def obtener_anio_mes(texto):
  texto = texto.lower()
  m_val = 9
  a_val = 2026
  for nombre, num in meses_dict.items():
    if nombre in texto:
      m_val = num
      break
  for anio in [2024, 2025, 2026, 2027]:
    if str(anio) in texto:
      a_val = anio
      break
  return a_val, m_val


def procesar_datos_trucksbook(df):
  df = df.reset_index(drop=True)
  df.columns = [c.strip() for c in df.columns]
  col_nombre = next(
      (
          c
          for c in df.columns
          if "nombre" in c.lower()
          or "driver" in c.lower()
          or "user" in c.lower()
      ),
      df.columns[0],
  )
  col_juego = next(
      (c for c in df.columns if "juego" in c.lower() or "game" in c.lower()),
      df.columns[1] if len(df.columns) > 1 else col_nombre,
  )
  col_origen = next(
      (c for c in df.columns if "origen" in c.lower() or "origin" in c.lower()),
      None,
  )
  col_destino = next(
      (
          c
          for c in df.columns
          if "destino" in c.lower() or "destination" in c.lower()
      ),
      None,
  )
  col_dist_est = next(
      (
          c
          for c in df.columns
          if "estimada" in c.lower() or "dist. estimada" in c.lower()
      ),
      None,
  )
  col_dist_acp = next(
      (
          c
          for c in df.columns
          if "aceptada" in c.lower() or "dist. aceptada" in c.lower()
      ),
      None,
  )
  col_vel_max = next(
      (c for c in df.columns if "velocidad" in c.lower() or "vel" in c.lower()),
      None,
  )
  col_tipo_entrega = next(
      (
          c
          for c in df.columns
          if "tipo de entrega" in c.lower() or "delivery" in c.lower()
      ),
      None,
  )
  col_beneficio = next(
      (c for c in df.columns if "beneficio" in c.lower() or "profit" in c.lower()),
      None,
  )
  col_multas = next(
      (c for c in df.columns if "multa" in c.lower() or "fine" in c.lower()),
      None,
  )
  col_danos = next(
      (c for c in df.columns if "daño" in c.lower() or "damage" in c.lower()),
      None,
  )
  col_tiempo = next(
      (c for c in df.columns if "tiempo" in c.lower() or "time" in c.lower()),
      None,
  )
  col_fecha = next(
      (c for c in df.columns if "fecha" in c.lower() or "date" in c.lower()),
      None,
  )

  df_clean = pd.DataFrame()
  df_clean["Nombre"] = df[col_nombre] if col_nombre else "Desconocido"
  df_clean["Juego"] = df[col_juego] if col_juego else "ATS"

  if col_vel_max:
    vel_num = (
        df[col_vel_max].astype(str).str.replace(r"[^0-9]", "", regex=True)
    )
    vel_num = pd.to_numeric(vel_num, errors="coerce").fillna(0)
  else:
    vel_num = pd.Series([0] * len(df))

  if col_juego:
    juego_up = df[col_juego].astype(str).str.upper()
  else:
    juego_up = pd.Series(["ATS"] * len(df))

  if col_tipo_entrega:
    tipo_low = df[col_tipo_entrega].astype(str).str.lower()
  else:
    tipo_low = pd.Series([""] * len(df))

  is_wotr = tipo_low.str.contains(
      "contrato externo", na=False
  ) | tipo_low.str.contains("wotr", na=False)

  es_ats = juego_up.str.contains("ATS", na=False)
  es_ets = juego_up.str.contains("ETS", na=False)
  otros = (~es_ats) & (~es_ets)

  # Umbrales oficiales de TrucksBook (ver artículo "Estadísticas"):
  #   ETS2: > 100 km/h -> Carrera   |  ATS: > 130 km/h -> Carrera
  #   Cualquier juego: > 180 km/h -> el viaje NO cuenta en NINGUNA
  #   estadística (ni Real, ni Carrera, ni WoTr).
  LIMITE_ETS2 = 100
  LIMITE_ATS = 130
  LIMITE_EXCLUSION = 180

  limite_carrera = pd.Series(LIMITE_ATS, index=df.index)
  limite_carrera = limite_carrera.mask(es_ets & ~es_ats, LIMITE_ETS2)

  modalidad = pd.Series("Real", index=df.index)
  modalidad = modalidad.mask(otros & is_wotr, "Wotr")
  modalidad = modalidad.mask(vel_num > limite_carrera, "Carrera")
  # La exclusión por >180 km/h manda sobre cualquier otra clasificación.
  modalidad = modalidad.mask(vel_num > LIMITE_EXCLUSION, "Excluido")

  df_clean["Entrega"] = is_wotr.map({True: "Wotr", False: "Estándar"})
  df_clean["Desde"] = df[col_origen] if col_origen else "-"
  df_clean["Hasta"] = df[col_destino] if col_destino else "-"
  df_clean["Dist. Estimada"] = df[col_dist_est] if col_dist_est else "0 km"
  df_clean["Dist. Aceptada"] = df[col_dist_acp] if col_dist_acp else "0 km"
  df_clean["Vel. Máx"] = df[col_vel_max] if col_vel_max else "0 km/h"
  df_clean["Modalidad"] = modalidad
  df_clean["Beneficio"] = df[col_beneficio] if col_beneficio else "$0,00"
  df_clean["Multas"] = df[col_multas] if col_multas else "$0,00"
  df_clean["Daños"] = df[col_danos] if col_danos else "$0,00"
  df_clean["Tiempo Real"] = df[col_tiempo] if col_tiempo else "0h 0m"

  if col_fecha:
    df_clean["Fecha"] = (
        pd.to_datetime(df[col_fecha], errors="coerce")
        .dt.date.fillna(datetime.date.today())
    )
  else:
    df_clean["Fecha"] = datetime.date.today()

  if col_dist_acp:
    df_clean["Distancia_Num"] = _a_numero(df[col_dist_acp])
  elif col_dist_est:
    df_clean["Distancia_Num"] = _a_numero(df[col_dist_est])
  else:
    df_clean["Distancia_Num"] = 0.0

  return df_clean


def procesar_csv_directorio(df_raw):
  """Normaliza un CSV de conductores (formato Plantilla_Conductores) al
  esquema interno de drivers_db, sin asignar aún el ID."""
  renombres = {
      col: MAPEO_COLUMNAS_DIRECTORIO_CSV[col.strip().lower()]
      for col in df_raw.columns
      if col.strip().lower() in MAPEO_COLUMNAS_DIRECTORIO_CSV
  }
  df = df_raw.rename(columns=renombres)

  for col in COLUMNAS_DIRECTORIO:
    if col not in df.columns:
      df[col] = "-"

  df = df[COLUMNAS_DIRECTORIO].copy()
  df["Nombre / Tag"] = df["Nombre / Tag"].astype(str).str.strip()
  df = df[(df["Nombre / Tag"] != "") & (df["Nombre / Tag"].str.lower() != "nan")]

  for col in COLUMNAS_DIRECTORIO:
    if col != "Nombre / Tag":
      df[col] = df[col].fillna("-").astype(str).str.strip().replace("", "-")

  return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def generar_datos_podio(df_source, simulador, anio, mes, limite_restantes=10):
  """Podio + ranking. Cacheado y con agregación vectorizada."""
  columnas_necesarias = {"Juego", "Nombre", "Distancia_Num"}
  if not columnas_necesarias.issubset(df_source.columns):
    return "0 km", [], []

  mascara = df_source["Juego"].str.contains(simulador, case=False, na=False)
  if "Modalidad" in df_source.columns:
    mascara &= ~df_source["Modalidad"].isin(["Carrera", "Excluido"])

  if "_Fecha_dt" in df_source.columns:
    fechas = df_source["_Fecha_dt"]
  else:
    fechas = pd.to_datetime(df_source.get("Fecha"), errors="coerce")
  mascara &= (fechas.dt.year == anio) & (fechas.dt.month == mes)

  df_f = df_source[mascara]
  if df_f.empty:
    return "0 km", [], []

  total_km = df_f["Distancia_Num"].sum()
  group = (
      df_f.groupby("Nombre", sort=False)["Distancia_Num"]
      .sum()
      .sort_values(ascending=False)
      .head(3 + limite_restantes)
      .reset_index()
  )

  podio = []
  restantes = []
  medallas = {1: "👑 Oro", 2: "🥈 Plata", 3: "🥉 Bronce"}

  for idx, (nombre, km) in enumerate(
      zip(group["Nombre"].tolist(), group["Distancia_Num"].tolist()), start=1
  ):
    km_str = f"{km:,.0f} km"
    if idx <= 3:
      podio.append({
          "puesto": str(idx),
          "nombre": nombre,
          "km": km_str,
          "medalla": medallas[idx],
      })
    else:
      restantes.append({"pos": str(idx), "nombre": nombre, "km": km_str})

  while len(podio) < 3:
    p_num = len(podio) + 1
    podio.append({
        "puesto": str(p_num),
        "nombre": "Sin registros",
        "km": "0 km",
        "medalla": medallas[p_num],
    })

  return f"{total_km:,.0f} km", podio[:3], restantes


def show_login():
  col_left, col_center, col_right = st.columns([1, 1.2, 1])
  with col_center:
    # Se usa un <img> embebido en HTML (en vez de st.image) porque el
    # contenedor que genera st.image no siempre ocupa el ancho completo
    # de la columna, así que el CSS de centrado no tenía espacio donde
    # actuar. Con este div propio garantizamos que quede centrado.
    logo_data_uri = obtener_foto_data_uri("logo.png")
    if logo_data_uri:
      st.markdown(
          f"<div style='display:flex; justify-content:center;'>"
          f"<img src='{logo_data_uri}' width='140' "
          f"style='border-radius:8px;' /></div>",
          unsafe_allow_html=True,
      )
    else:
      st.markdown("<h1 style='text-align: center;'>☕</h1>", unsafe_allow_html=True)
    st.markdown(
        "<h1 style='text-align: center; color: #f4d06f;'>Coffee"
        " Transportees ERP</h1>",
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
      username = st.text_input("Usuario")
      password = st.text_input("Contraseña", type="password")
      if st.form_submit_button("Iniciar Sesión", use_container_width=True):
        candidatos = st.session_state.users_db[
            st.session_state.users_db["Usuario"].astype(str).str.lower()
            == username.strip().lower()
        ]
        fila_ok = None
        for idx, fila in candidatos.iterrows():
          if verificar_password(password, fila["Contraseña"]):
            fila_ok = fila
            # Migración transparente: si la contraseña estaba en texto plano,
            # se reemplaza por su hash la primera vez que el usuario entra.
            if not es_hash(fila["Contraseña"]):
              st.session_state.users_db.at[idx, "Contraseña"] = hash_password(password)
              guardar_usuarios_db(st.session_state.users_db)
            break

        if fila_ok is not None:
          st.session_state.logged_in = True
          st.session_state.user = fila_ok["Usuario"]
          st.session_state.role = fila_ok["Rol"]
          st.rerun()
        else:
          st.error("Usuario o contraseña incorrectos.")

    # ---- Recuperación de contraseña por pregunta de seguridad ----
    with st.expander("¿Olvidaste tu contraseña?"):
      st.caption(
          "Escribe tu usuario y responde tu pregunta de seguridad para"
          " definir una contraseña nueva. Si no configuraste una pregunta,"
          " pídele a un administrador que te la restablezca."
      )
      usuario_rec = st.text_input("Usuario", key="rec_usuario")
      fila_rec = buscar_usuario(usuario_rec) if usuario_rec.strip() else None

      if usuario_rec.strip() and fila_rec is None:
        st.warning("No encontramos ese usuario.")
      elif fila_rec is not None and not str(fila_rec["Pregunta"]).strip():
        st.warning(
            "Esta cuenta todavía no tiene pregunta de seguridad configurada."
            " Contacta a un administrador para restablecer el acceso."
        )
      elif fila_rec is not None:
        with st.form("form_recuperar_pass"):
          st.info(f"Pregunta de seguridad: **{fila_rec['Pregunta']}**")
          respuesta_rec = st.text_input("Tu respuesta", key="rec_respuesta")
          nueva_1 = st.text_input("Nueva contraseña", type="password", key="rec_p1")
          nueva_2 = st.text_input("Repite la nueva contraseña", type="password", key="rec_p2")

          if st.form_submit_button("Restablecer contraseña", use_container_width=True):
            intentos = st.session_state.get("intentos_recuperacion", 0)
            if intentos >= 5:
              st.error(
                  "Demasiados intentos fallidos. Contacta a un administrador."
              )
            elif not verificar_password(
                normalizar_respuesta_seguridad(respuesta_rec), fila_rec["Respuesta"]
            ):
              st.session_state.intentos_recuperacion = intentos + 1
              st.error("La respuesta no coincide.")
            elif len(nueva_1) < 4:
              st.error("La contraseña nueva debe tener al menos 4 caracteres.")
            elif nueva_1 != nueva_2:
              st.error("Las dos contraseñas no coinciden.")
            else:
              idx_rec = st.session_state.users_db[
                  st.session_state.users_db["Usuario"] == fila_rec["Usuario"]
              ].index[0]
              st.session_state.users_db.at[idx_rec, "Contraseña"] = hash_password(nueva_1)
              guardar_usuarios_db(st.session_state.users_db)
              st.session_state.intentos_recuperacion = 0
              st.success(
                  "¡Contraseña actualizada! Ya puedes iniciar sesión con ella."
              )


if not st.session_state.logged_in:
  show_login()
else:
  # Botón flotante (☰) para abrir/cerrar el menú lateral en móvil.
  # Se inyecta una sola vez en el documento padre (no en cada rerun)
  # y controla el menú alternando una clase CSS sobre el sidebar,
  # sin depender del control nativo de colapso de Streamlit.
  components.html(
      """
      <script>
      (function() {
        const doc = window.parent.document;
        if (doc.__ctMobileMenuInit) { return; }
        doc.__ctMobileMenuInit = true;

        const btn = doc.createElement('button');
        btn.id = 'ct-mobile-menu-btn';
        btn.className = 'ct-mobile-menu-btn';
        btn.type = 'button';
        btn.innerHTML = '&#9776;';
        btn.onclick = function(e) {
          e.stopPropagation();
          const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
          if (sidebar) { sidebar.classList.toggle('ct-sidebar-open'); }
        };
        doc.body.appendChild(btn);

        doc.addEventListener('click', function(e) {
          const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
          if (sidebar && sidebar.classList.contains('ct-sidebar-open')) {
            if (!sidebar.contains(e.target) && e.target.id !== 'ct-mobile-menu-btn') {
              sidebar.classList.remove('ct-sidebar-open');
            }
          }
        });
      })();
      </script>
      """,
      height=0,
      width=0,
  )
  with st.sidebar:
    _colores_rol = {
        "Dueño": "#f4d06f",
        "Administrador": "#3498db",
        "Conductor": "#2ecc71",
    }
    _slugs_rol = {
        "Dueño": "role-dueno",
        "Administrador": "role-administrador",
        "Conductor": "role-conductor",
    }
    _color_rol = _colores_rol.get(st.session_state.role, "#fdfbf7")
    _slug_rol = _slugs_rol.get(st.session_state.role, "role-conductor")
    _inicial_usuario = str(st.session_state.user or "?").strip()[:1].upper()

    # ---- Tarjeta de marca: logo + nombre de la VTC ----
    with st.container(border=True):
      col_logo_izq, col_logo_centro, col_logo_der = st.columns([1, 2, 1])
      with col_logo_centro:
        try:
          st.image("logo.png", use_container_width=True)
        except Exception:
          st.markdown(
              "<div style='text-align:center; font-size:34px;'>☕</div>",
              unsafe_allow_html=True,
          )
      st.markdown(
          "<div class='ct-brand-title'>Coffee Transportees</div>"
          "<div class='ct-brand-subtitle'>Virtual Trucking Company</div>",
          unsafe_allow_html=True,
      )

    # ---- Tarjeta de perfil: avatar + usuario + rol + cerrar sesión ----
    with st.container(border=True):
      col_avatar, col_info, col_salir = st.columns([1, 3, 1])
      with col_avatar:
        st.markdown(
            render_avatar_html(st.session_state.user, tamano=44),
            unsafe_allow_html=True,
        )
      with col_info:
        st.markdown(
            f"<div class='ct-profile-name'>{st.session_state.user}</div>"
            f"<span class='ct-role-badge {_slug_rol}'>{st.session_state.role}</span>",
            unsafe_allow_html=True,
        )
      with col_salir:
        if st.button(
            "",
            icon=":material/power_settings_new:",
            help="Cerrar Sesión",
            key="btn_logout",
        ):
          st.session_state.logged_in = False
          st.rerun()
    st.markdown(
        """
        <style>
        div[data-testid="stSidebar"] button[kind="secondary"]:has(span[data-testid="stIconMaterial"]) {
            border-radius: 50%;
            width: 40px;
            height: 40px;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid #d97736;
            background-color: #261c17;
        }
        div[data-testid="stSidebar"] button[kind="secondary"]:has(span[data-testid="stIconMaterial"]) span[data-testid="stIconMaterial"] {
            color: #d97736;
            font-size: 20px;
        }
        div[data-testid="stSidebar"] button[kind="secondary"]:has(span[data-testid="stIconMaterial"]):hover {
            border-color: #f4d06f;
            background-color: #4a3525;
        }
        div[data-testid="stSidebar"] button[kind="secondary"]:has(span[data-testid="stIconMaterial"]):hover span[data-testid="stIconMaterial"] {
            color: #f4d06f;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---- Tarjeta de menú de navegación ----
    menu_display_map = {
        "Inicio": "🏠 Inicio",
        "Directorio": "👥 Directorio",
        "Asistencia": "📋 Asistencia",
        "Reportes": "📊 Reportes",
        "Comparativa": "⚖️ Comparativa",
        "Kilómetros": "🛣️ Kilómetros",
        "Ruleta": "🎡 Ruleta",
        "Mi Perfil": "🙋 Mi Perfil",
        "Importar TrucksBook": "📂 Importar TrucksBook",
        "Configuración y Usuarios": "⚙️ Configuración y Usuarios"
    }

    menu_options_raw = [
        "Inicio",
        "Directorio",
        "Asistencia",
        "Reportes",
        "Comparativa",
        "Kilómetros",
        "Ruleta",
        "Mi Perfil",
    ]
    if st.session_state.role in ["Dueño", "Administrador"]:
      menu_options_raw.append("Importar TrucksBook")
      menu_options_raw.append("Configuración y Usuarios")

    if st.session_state.role == "Conductor":
      menu_options_raw = [
          m
          for m in menu_options_raw
          if m not in ["Importar TrucksBook", "Configuración y Usuarios"]
      ]

    # ---- Estado persistente de la página seleccionada ----
    if (
        "pagina_actual" not in st.session_state
        or st.session_state.pagina_actual not in menu_options_raw
    ):
      st.session_state.pagina_actual = menu_options_raw[0]

    with st.container(border=True, key="ct_menu_nav"):
      st.markdown("<div class='ct-nav-title'>📋 Menú</div>", unsafe_allow_html=True)
      for i, m in enumerate(menu_options_raw):
        es_activo = st.session_state.pagina_actual == m
        if st.button(
            menu_display_map[m],
            key=f"nav_item_{i}",
            use_container_width=True,
            type="primary" if es_activo else "secondary",
        ):
          st.session_state.pagina_actual = m
          st.rerun()

    choice = st.session_state.pagina_actual

    # ---- Tarjeta de enlaces y comunidad ----
    with st.container(border=True):
      st.markdown(
          "<div class='ct-nav-title'>🌐 Enlaces y Comunidad</div>",
          unsafe_allow_html=True,
      )
      st.markdown(
          """
          <a class="ct-link-chip" href="https://trucksbook.eu/company/209432" target="_blank">
              <span class="ct-link-icon" style="background:rgba(217,119,54,0.18); color:#d97736;">🚛</span> Trucksbook Empresa
          </a>
          <a class="ct-link-chip" href="https://truckersmp.com/vtc/80639" target="_blank">
              <span class="ct-link-icon" style="background:rgba(52,152,219,0.18); color:#3498db;">🌐</span> TruckersMP
          </a>
          <a class="ct-link-chip" href="https://lucky-sprinkles-2b51cb.netlify.app" target="_blank">
              <span class="ct-link-icon" style="background:rgba(46,204,113,0.18); color:#2ecc71;">🌍</span> Página Web
          </a>
          <a class="ct-link-chip" href="https://www.tiktok.com/@coffee.transportees" target="_blank">
              <span class="ct-link-icon" style="background:rgba(253,251,247,0.12); color:#fdfbf7;">📱</span> TikTok
          </a>
          <a class="ct-link-chip" href="https://kick.com/coffee-transportees" target="_blank">
              <span class="ct-link-icon" style="background:rgba(46,204,113,0.18); color:#2ecc71;">📺</span> Kick
          </a>
          <a class="ct-link-chip" href="https://discord.com/invite/Ukjxt7EqV" target="_blank">
              <span class="ct-link-icon" style="background:rgba(114,137,218,0.18); color:#7289da;">💬</span> Discord
          </a>
          """,
          unsafe_allow_html=True,
      )

  mostrar_icono_alertas()

  if choice == "Inicio":
    st.markdown(
        "<div class='ct-avatar-row'>"
        + render_avatar_html(st.session_state.user, tamano=72, clase_extra="ct-avatar-lg")
        + f"<h1 style='margin:0;'>¡Bienvenido a bordo, {st.session_state.user}!</h1>"
        "</div>",
        unsafe_allow_html=True,
    )
    bitacora_inicio = preparar_bitacora(st.session_state.trucksbook_data)
    
    # ----------------------------------------------------
    # CÁLCULOS DE KILÓMETROS Y VIAJES (Sin modalidad Carrera)
    # ----------------------------------------------------
    df_base_km = bitacora_inicio.copy()
    if "Modalidad" in df_base_km.columns:
      df_base_km = df_base_km[~df_base_km["Modalidad"].isin(["Carrera", "Excluido"])]
    
    hoy_actual = datetime.date.today()
    anio_actual = hoy_actual.year
    mes_actual = hoy_actual.month
    
    mes_anterior = mes_actual - 1 if mes_actual > 1 else 12
    anio_anterior = anio_actual if mes_actual > 1 else anio_actual - 1

    # 1. KM Año Actual
    df_anio = df_base_km[df_base_km["_Fecha_dt"].dt.year == anio_actual]
    km_anio = df_anio["Distancia_Num"].sum() if not df_anio.empty else 0.0

    # 2. KM Mes Actual
    df_mes_act = df_base_km[
      (df_base_km["_Fecha_dt"].dt.year == anio_actual) & 
      (df_base_km["_Fecha_dt"].dt.month == mes_actual)
    ]
    km_mes_act = df_mes_act["Distancia_Num"].sum() if not df_mes_act.empty else 0.0

    # 3. KM Mes Anterior
    df_mes_ant = df_base_km[
      (df_base_km["_Fecha_dt"].dt.year == anio_anterior) & 
      (df_base_km["_Fecha_dt"].dt.month == mes_anterior)
    ]
    km_mes_ant = df_mes_ant["Distancia_Num"].sum() if not df_mes_ant.empty else 0.0

    # 3b. KM Mes Actual / Mes Anterior separados por juego (ATS vs ETS2).
    # Se calculan aparte para poder comparar 1 a 1 contra las estadísticas
    # de TrucksBook, que siempre están separadas por juego.
    def _km_por_juego(df_periodo, patron):
      if df_periodo.empty or "Juego" not in df_periodo.columns:
        return 0.0
      filtro = df_periodo["Juego"].astype(str).str.contains(
          patron, case=False, na=False, regex=True
      )
      return df_periodo.loc[filtro, "Distancia_Num"].sum()

    km_mes_act_ats = _km_por_juego(df_mes_act, r"\bATS\b")
    km_mes_act_ets = _km_por_juego(df_mes_act, r"\bETS")
    km_mes_ant_ats = _km_por_juego(df_mes_ant, r"\bATS\b")
    km_mes_ant_ets = _km_por_juego(df_mes_ant, r"\bETS")

    # 4. Viajes registrados del mes en curso
    viajes_mes_act = df_mes_act.shape[0] if not df_mes_act.empty else 0

    # 5. Conductores activos: únicos que registraron viaje en el MES ACTUAL
    # (hereda de df_base_km, que ya excluye la modalidad "Carrera").
    conductores_activos = (
        df_mes_act["Nombre"].nunique()
        if not df_mes_act.empty and "Nombre" in df_mes_act.columns
        else 0
    )

    # ----------------------------------------------------
    # MÉTRICAS EN UI
    # ----------------------------------------------------
    c_ini1, c_ini2, c_ini3 = st.columns(3)
    c_ini1.metric("KM Año Actual", f"{km_anio:,.0f} km")
    c_ini2.metric("Viajes (Mes Actual)", f"{viajes_mes_act:,}")
    c_ini3.metric("Conductores activos", f"{conductores_activos:,}")

    st.markdown("#### 📅 KM Mes Actual — por juego")
    st.caption(
        "Separado por juego para poder comparar 1 a 1 contra las"
        " estadísticas oficiales de TrucksBook (que también están"
        " separadas por ATS y ETS2)."
    )
    c_act1, c_act2, c_act3 = st.columns(3)
    c_act1.metric("ATS", f"{km_mes_act_ats:,.0f} km")
    c_act2.metric("ETS2", f"{km_mes_act_ets:,.0f} km")
    c_act3.metric("Total", f"{km_mes_act:,.0f} km")

    st.markdown("#### 📆 KM Mes Anterior — por juego")
    c_ant1, c_ant2, c_ant3 = st.columns(3)
    c_ant1.metric("ATS", f"{km_mes_ant_ats:,.0f} km")
    c_ant2.metric("ETS2", f"{km_mes_ant_ets:,.0f} km")
    c_ant3.metric("Total", f"{km_mes_ant:,.0f} km")

    st.markdown("---")
    st.markdown("### 🚚 Próximo Convoy Programado")

    # Obtener el primer convoy disponible en la base de datos de sesión
    convoys_disponibles = st.session_state.get("convoys_db", [])
    
    if convoys_disponibles:
      convoy = convoys_disponibles[0]  # Tomamos el primero como informativo
      
      es_ats = "ATS" in str(convoy).upper() or "LOS ANGELES" in convoy.get("origen", "").upper()
      
      titulo_juego = "American Truck Simulator (ATS)" if es_ats else "Euro Truck Simulator 2 (ETS2)"
      color_juego = "#e74c3c" if es_ats else "#3498db"

      c_conv_img, c_conv_info = st.columns([1, 2.5])
      with c_conv_img:
        st.markdown(
            f"""
            <div style="background-color: #261c17; border: 1px solid #4a3525; border-radius: 8px; padding: 10px; text-align: center;">
                <span style="font-size: 12px; color: {color_juego}; font-weight: bold;">{titulo_juego}</span>
                <hr style="border-color: #4a3525; margin: 8px 0;">
                <p style="color: #fdfbf7; font-size: 13px; margin: 0;"><b>Semana:</b> {convoy.get('semana', 'N/A')}</p>
                <p style="color: #fdfbf7; font-size: 13px; margin: 0;"><b>Día:</b> {convoy.get('dia', 'N/A')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
      with c_conv_info:
        st.markdown(
            f"""
            <div style="background-color: #261c17; border: 1px solid #4a3525; border-radius: 8px; padding: 15px;">
                <h4 style="color: #f4d06f; margin-top: 0; margin-bottom: 10px;">{convoy.get('titulo', 'Convoy Oficial')}</h4>
                <p style="margin: 4px 0; font-size: 14px;">📍 <b>Origen / Ruta:</b> {convoy.get('origen', 'Por definir')}</p>
                <p style="margin: 4px 0; font-size: 14px;">📅 <b>Fecha y Hora:</b> Programado en agenda</p>
                <p style="margin: 4px 0; font-size: 14px;">🖥️ <b>Servidor:</b> Simulación Oficial</p>
                <p style="margin: 4px 0; font-size: 14px;">🎮 <b>Juego:</b> <span style="color: {color_juego}; font-weight: bold;">{titulo_juego}</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
      st.info("No hay convoyes programados en este momento.")
  elif choice == "Directorio":
    st.markdown("# Directorio de Conductores y Aspirantes")
    st.info(
        "Gestión de la plantilla de conductores, roles, juegos principales,"
        " teléfonos y horarios semanales."
    )

    es_admin_o_dueno = st.session_state.role in ["Dueño", "Administrador"]

    col_btn1, col_btn2, col_btn3, _ = st.columns([1.4, 1.6, 1.8, 1.7])
    with col_btn1:
      if st.button("📥 Descargar Plantilla", use_container_width=True):
        st.success("Plantilla descargada con éxito.")
    with col_btn2:
      if es_admin_o_dueno and st.button(
          "➕ Registrar Conductor", use_container_width=True
      ):
        st.session_state.show_add_driver = True
    with col_btn3:
      if es_admin_o_dueno and st.button(
          "📤 Subir Directorio (CSV)", use_container_width=True
      ):
        st.session_state.show_upload_directory = True

    st.markdown("<br>", unsafe_allow_html=True)

    if es_admin_o_dueno and st.session_state.get("show_upload_directory", False):
      st.markdown("### Subir Directorio desde CSV")
      st.caption(
          "Columnas esperadas: Nombre, Fecha_Ingreso, Rol, Juego, Telefono,"
          " Lunes, Martes, Miercoles, Jueves, Viernes, Sabado, Domingo."
          " Si un Nombre/Tag ya existe en el directorio, se actualiza; si no,"
          " se agrega como nuevo conductor."
      )
      archivo_directorio = st.file_uploader(
          "Selecciona el archivo CSV del directorio",
          type=["csv"],
          key="uploader_directorio_csv",
      )
      c_dir1, c_dir2 = st.columns(2)
      with c_dir1:
        procesar_dir_click = st.button(
            "Procesar e Integrar Directorio", use_container_width=True
        )
      with c_dir2:
        cancelar_dir_click = st.button(
            "Cancelar",
            use_container_width=True,
            key="cancelar_upload_directorio",
        )

      if cancelar_dir_click:
        st.session_state.show_upload_directory = False
        st.rerun()

      if procesar_dir_click:
        if archivo_directorio is None:
          st.warning("Primero selecciona un archivo CSV.")
        else:
          try:
            try:
              archivo_directorio.seek(0)
              df_raw_dir = pd.read_csv(archivo_directorio, sep=";")
              if df_raw_dir.shape[1] == 1:
                raise ValueError("separador incorrecto")
            except Exception:
              archivo_directorio.seek(0)
              df_raw_dir = pd.read_csv(archivo_directorio, sep=None, engine="python")

            df_nuevos_conductores = procesar_csv_directorio(df_raw_dir)

            if df_nuevos_conductores.empty:
              st.warning("El archivo no contiene registros válidos.")
            else:
              db_actual = st.session_state.drivers_db.copy()
              agregados, actualizados = 0, 0
              for _, fila in df_nuevos_conductores.iterrows():
                nombre = fila["Nombre / Tag"]
                coincide = (
                    db_actual["Nombre / Tag"].astype(str).str.strip().str.lower()
                    == nombre.lower()
                )
                if coincide.any():
                  idx = db_actual[coincide].index[0]
                  for col in COLUMNAS_DIRECTORIO:
                    db_actual.at[idx, col] = fila[col]
                  actualizados += 1
                else:
                  nuevo_id = (
                      int(db_actual["ID"].max()) + 1
                      if not db_actual.empty
                      else 1
                  )
                  fila_nueva = fila.to_dict()
                  fila_nueva["ID"] = nuevo_id
                  db_actual = pd.concat(
                      [db_actual, pd.DataFrame([fila_nueva])], ignore_index=True
                  )
                  agregados += 1

              st.session_state.drivers_db = db_actual
              guardar_drivers_db(st.session_state.drivers_db)
              st.session_state.show_upload_directory = False
              st.success(
                  f"¡Directorio actualizado! {agregados} conductores nuevos,"
                  f" {actualizados} actualizados."
              )
              st.rerun()
          except Exception as e:
            st.error(f"No se pudo procesar el archivo CSV: {e}")

      st.markdown("<br>", unsafe_allow_html=True)

    if es_admin_o_dueno and st.session_state.get("show_add_driver", False):
      with st.form("form_nuevo_driver"):
        st.markdown("### Agregar Nuevo Conductor")
        f_nombre = st.text_input("Nombre / Tag")
        f_ingreso = st.date_input(
            "Fecha de Ingreso", value=datetime.date.today()
        )
        f_rol = st.selectbox("Rol", ["Conductor", "Administrador"])
        f_juego = st.selectbox("Juego Principal", ["ATS", "ETS2", "Ambos"])
        f_tel = st.text_input("Teléfono")

        st.markdown("**Horario Semanal (Hora o '-' si no labora):**")
        col_d1, col_d2, col_d3, col_d4, col_d5, col_d6, col_d7 = st.columns(7)
        with col_d1:
          h_lu = st.text_input("Lu", value="-")
        with col_d2:
          h_ma = st.text_input("Ma", value="-")
        with col_d3:
          h_mi = st.text_input("Mi", value="-")
        with col_d4:
          h_ju = st.text_input("Ju", value="-")
        with col_d5:
          h_vi = st.text_input("Vi", value="-")
        with col_d6:
          h_sa = st.text_input("Sa", value="-")
        with col_d7:
          h_do = st.text_input("Do", value="-")

        c_sub1, c_sub2 = st.columns(2)
        with c_sub1:
          submitted = st.form_submit_button(
              "Guardar Conductor", use_container_width=True
          )
        with c_sub2:
          cancelled = st.form_submit_button("Cancelar", use_container_width=True)

        if submitted:
          if f_nombre:
            nuevo_id = (
                int(st.session_state.drivers_db["ID"].max() + 1)
                if not st.session_state.drivers_db.empty
                else 1
            )
            nuevo_registro = pd.DataFrame([{
                "ID": nuevo_id,
                "Nombre / Tag": f_nombre,
                "Ingreso": str(f_ingreso),
                "Rol": f_rol,
                "Juego": f_juego,
                "Teléfono": f_tel,
                "Lu": h_lu,
                "Ma": h_ma,
                "Mi": h_mi,
                "Ju": h_ju,
                "Vi": h_vi,
                "Sa": h_sa,
                "Do": h_do,
            }])
            st.session_state.drivers_db = pd.concat(
                [st.session_state.drivers_db, nuevo_registro], ignore_index=True
            )
            guardar_drivers_db(st.session_state.drivers_db)
            st.session_state.show_add_driver = False
            st.success("¡Conductor agregado con éxito!")
            st.rerun()
          else:
            st.error("El nombre o tag es obligatorio.")
        if cancelled:
          st.session_state.show_add_driver = False
          st.rerun()

    f_busq, f_dia = st.columns([2, 2])
    with f_busq:
      busqueda_txt = st.text_input(
          "Buscar por Nombre / Tag...",
          label_visibility="collapsed",
          placeholder="Buscar por Nombre / Tag...",
      )
    with f_dia:
      dia_sel = st.selectbox(
          "Filtrar por Día",
          ["Todos", "Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"],
          label_visibility="collapsed",
      )

    df_dir = st.session_state.drivers_db.copy()
    if busqueda_txt:
      df_dir = df_dir[
          df_dir["Nombre / Tag"].str.contains(busqueda_txt, case=False, na=False)
      ]
    if dia_sel != "Todos":
      df_dir = df_dir[df_dir[dia_sel] != "-"]

    # ---- Privacidad de teléfonos ----
    # Un Conductor solo puede ver el teléfono de los Administradores y el
    # Dueño; los teléfonos de los demás conductores se ocultan por
    # privacidad. Los Administradores y el Dueño sí ven todos los
    # teléfonos tal cual están registrados.
    df_dir_mostrar = df_dir.copy()
    if (
        not es_admin_o_dueno
        and "Teléfono" in df_dir_mostrar.columns
        and "Rol" in df_dir_mostrar.columns
    ):
      rol_con_telefono_visible = df_dir_mostrar["Rol"].isin(
          ["Administrador", "Dueño"]
      )
      df_dir_mostrar.loc[~rol_con_telefono_visible, "Teléfono"] = "••••••••"

    st.dataframe(df_dir_mostrar, use_container_width=True)

    if es_admin_o_dueno:
      st.markdown("### Gestión de Directorio")
      c_del1, c_del2 = st.columns([2, 2])
      with c_del1:
        nombre_a_borrar = st.selectbox(
            "Selecciona Nombre / Tag de Conductor a Eliminar",
            options=["Seleccione..."] + list(df_dir["Nombre / Tag"]),
        )
      with c_del2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(
            "🗑️ Eliminar Conductor Seleccionado", use_container_width=True
        ):
          if nombre_a_borrar != "Seleccione...":
            st.session_state.drivers_db = st.session_state.drivers_db[
                st.session_state.drivers_db["Nombre / Tag"] != nombre_a_borrar
            ]
            guardar_drivers_db(st.session_state.drivers_db)
            st.success("Conductor eliminado correctamente.")
            st.rerun()
          else:
            st.warning("Selecciona un Nombre / Tag válido.")

  elif choice == "Kilómetros":
    st.markdown("# Bitácora de Viajes (TrucksBook)")

    bitacora = preparar_bitacora(st.session_state.trucksbook_data)

    lista_conductores = lista_conductores_bitacora(bitacora)

    f_col1, f_col2, f_col3, f_col4, f_btn1, f_btn_hoy, f_btn_sem, f_btn_mes = (
        st.columns([1.2, 1.2, 1.5, 1.2, 0.7, 0.5, 0.6, 0.5])
    )

    with f_col1:
      fecha_desde = st.date_input("Desde", value=None, key="km_desde")
    with f_col2:
      fecha_hasta = st.date_input("Hasta", value=None, key="km_hasta")
    with f_col3:
      conductor_sel = st.selectbox("Conductor", lista_conductores, key="km_conductor")
    with f_col4:
      simulador_sel = st.selectbox("Simulador", ["Ambos", "ATS", "ETS2"], key="km_sim")

    if "filtro_fecha_inicio" not in st.session_state:
      st.session_state.filtro_fecha_inicio = None
    if "filtro_fecha_fin" not in st.session_state:
      st.session_state.filtro_fecha_fin = None
    if "km_pagina" not in st.session_state:
      st.session_state.km_pagina = 1

    with f_btn_hoy:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.button("Hoy"):
        hoy = datetime.date.today()
        st.session_state.filtro_fecha_inicio = hoy
        st.session_state.filtro_fecha_fin = hoy
        st.session_state.km_pagina = 1
        st.rerun()

    with f_btn_sem:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.button("Semana"):
        hoy = datetime.date.today()
        inicio_sem = hoy - datetime.timedelta(days=hoy.weekday())
        st.session_state.filtro_fecha_inicio = inicio_sem
        st.session_state.filtro_fecha_fin = hoy
        st.session_state.km_pagina = 1
        st.rerun()

    with f_btn_mes:
      st.markdown("<br>", unsafe_allow_html=True)
      if st.button("Mes"):
        hoy = datetime.date.today()
        inicio_mes = hoy.replace(day=1)
        st.session_state.filtro_fecha_inicio = inicio_mes
        st.session_state.filtro_fecha_fin = hoy
        st.session_state.km_pagina = 1
        st.rerun()

    with f_btn1:
      st.markdown("<br>", unsafe_allow_html=True)
      filtrar_btn = st.button("Filtrar", type="primary")

    if filtrar_btn:
      st.session_state.filtro_fecha_inicio = fecha_desde
      st.session_state.filtro_fecha_fin = fecha_hasta
      st.session_state.km_pagina = 1

    if st.session_state.filtro_fecha_inicio:
      fecha_desde = st.session_state.filtro_fecha_inicio
    if st.session_state.filtro_fecha_fin:
      fecha_hasta = st.session_state.filtro_fecha_fin

    firma_filtros = (conductor_sel, simulador_sel, str(fecha_desde), str(fecha_hasta))
    if st.session_state.get("km_firma_filtros") != firma_filtros:
      st.session_state.km_firma_filtros = firma_filtros
      st.session_state.km_pagina = 1

    loader = st.empty()
    mostrar_cargando(loader, "Cargando y filtrando bitácora de viajes...")

    df_filtered = filtrar_bitacora(
        bitacora, conductor_sel, simulador_sel, fecha_desde, fecha_hasta
    )
    resumen = resumen_bitacora(df_filtered)

    loader.empty()

    total_registros = resumen["registros"]

    rango_txt = (
        f"{fecha_desde or 'inicio'} → {fecha_hasta or 'hoy'}"
        if (fecha_desde or fecha_hasta)
        else "todo el histórico"
    )
    st.caption(
        f"Rango activo: {rango_txt} · Conductor: {conductor_sel} · Simulador:"
        f" {simulador_sel}"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registros encontrados", f"{total_registros:,}")
    m2.metric("Kilómetros del filtro", f"{resumen['km']:,.0f} km")
    m3.metric("Conductores", f"{resumen['conductores']:,}")
    with m4:
      st.markdown("<br>", unsafe_allow_html=True)
      st.download_button(
          "⬇️ Descargar CSV completo",
          data=bitacora_a_csv(df_filtered),
          file_name="bitacora_filtrada.csv",
          mime="text/csv",
          use_container_width=True,
          disabled=df_filtered.empty,
      )

    if df_filtered.empty:
      st.warning("No hay registros que coincidan con los filtros seleccionados.")
    else:
      c_pg1, c_pg2, c_pg3, c_pg4, c_pg5 = st.columns([1.2, 0.6, 1.4, 0.6, 3])

      with c_pg1:
        filas_pagina = st.selectbox(
            "Filas por página",
            FILAS_POR_PAGINA_OPCIONES,
            index=FILAS_POR_PAGINA_OPCIONES.index(FILAS_POR_PAGINA_DEFECTO),
            key="km_filas_pagina",
        )

      total_paginas = max(1, -(-total_registros // filas_pagina))
      if st.session_state.km_pagina > total_paginas:
        st.session_state.km_pagina = total_paginas

      with c_pg2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("◀", use_container_width=True, disabled=st.session_state.km_pagina <= 1):
          st.session_state.km_pagina -= 1
          st.rerun()

      with c_pg3:
        pagina_sel = st.number_input(
            "Página",
            min_value=1,
            max_value=total_paginas,
            value=int(st.session_state.km_pagina),
            step=1,
            key="km_pagina_input",
        )
        if pagina_sel != st.session_state.km_pagina:
          st.session_state.km_pagina = int(pagina_sel)

      with c_pg4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶", use_container_width=True, disabled=st.session_state.km_pagina >= total_paginas):
          st.session_state.km_pagina += 1
          st.rerun()

      pagina_actual = int(st.session_state.km_pagina)
      inicio = (pagina_actual - 1) * filas_pagina
      fin = min(inicio + filas_pagina, total_registros)

      with c_pg5:
        st.markdown(
            f"<br><span style='color:#b0a8a0;'>Mostrando <b style='color:#f4d06f;'>"
            f"{inicio + 1:,} - {fin:,}</b> de <b style='color:#f4d06f;'>"
            f"{total_registros:,}</b> registros · Página {pagina_actual} de "
            f"{total_paginas}</span>",
            unsafe_allow_html=True,
        )

      loader_tabla = st.empty()
      mostrar_cargando(loader_tabla, "Renderizando página de resultados...")

      df_pagina = df_filtered.iloc[inicio:fin]
      html_tabla = render_pagina_html(df_pagina)

      loader_tabla.empty()
      st.markdown(html_tabla, unsafe_allow_html=True)

  elif choice == "Asistencia":
    st.markdown("# Control de Asistencia")
    es_admin_o_dueno = st.session_state.role in ["Dueño", "Administrador"]

    # Si en la corrida anterior se pidió limpiar un filtro (caso Conductor),
    # se resetea el selectbox ANTES de crearlo para no chocar con la
    # restricción de Streamlit de modificar un widget ya instanciado.
    if st.session_state.pop("_reset_sel_convoy", False):
      st.session_state.sel_convoy_box = "Seleccione..."
    if st.session_state.pop("_reset_sel_reunion", False):
      st.session_state.sel_reunion_box = "Seleccione..."

    c_convoy_izq, c_convoy_der = st.columns(2)

    with c_convoy_izq:
      st.markdown(
          """
            <div style="background-color: #261c17; padding: 20px; border-radius: 10px; border: 1px solid #4a3525; margin-bottom: 20px;">
                <h4 style="color: #f4d06f; margin-top: 0;">Convoy Activo</h4>
            """,
          unsafe_allow_html=True,
      )

      nombres_convoys = [c["titulo"] for c in st.session_state.convoys_db]
      opciones_convoy = ["Seleccione..."] + nombres_convoys
      sel_convoy_val = st.selectbox(
          "Seleccionar convoy", opciones_convoy, key="sel_convoy_box"
      )

      col_b1, col_b2 = st.columns([1, 1])
      with col_b1:
        cargar_convoy = st.button(
            "Cargar", use_container_width=True, key="btn_cargar_convoy"
        )
      with col_b2:
        eliminar_convoy = st.button(
            "Eliminar", use_container_width=True, key="btn_eliminar_convoy"
        )

      if eliminar_convoy and sel_convoy_val != "Seleccione...":
        if es_admin_o_dueno:
          st.session_state.convoys_db = [
              c
              for c in st.session_state.convoys_db
              if c["titulo"] != sel_convoy_val
          ]
          st.success(f"Convoy '{sel_convoy_val}' eliminado.")
        else:
          # Los conductores no pueden borrar convoys del sistema:
          # el botón solo limpia su filtro/selección local.
          st.session_state["_reset_sel_convoy"] = True
          st.info("Filtro de convoy limpiado.")
        st.rerun()

      st.markdown("</div>", unsafe_allow_html=True)

    with c_convoy_der:
      if es_admin_o_dueno:
        st.markdown(
            """
                <div style="background-color: #261c17; padding: 20px; border-radius: 10px; border: 1px solid #4a3525; margin-bottom: 20px;">
                    <h4 style="color: #f4d06f; margin-top: 0;">— ó crear nuevo convoy —</h4>
                """,
            unsafe_allow_html=True,
        )

        with st.form("form_nuevo_convoy"):
          f_sem = st.text_input("Semana", placeholder="Ej: 42")
          f_dia = st.selectbox(
              "Día",
              [
                  "Lunes",
                  "Martes",
                  "Miércoles",
                  "Jueves",
                  "Viernes",
                  "Sábado",
                  "Domingo",
              ],
          )
          f_orig = st.text_input("Origen", placeholder="Ej: Los Angeles")
          submit_convoy = st.form_submit_button(
              "Crear Convoy", use_container_width=True
          )

          if submit_convoy:
            if f_sem and f_orig:
              nuevo_titulo = f"Sem {f_sem} - {f_dia} ({f_orig})"
              nuevo_obj = {
                  "id": len(st.session_state.convoys_db) + 1,
                  "titulo": nuevo_titulo,
                  "semana": f_sem,
                  "dia": f_dia,
                  "origen": f_orig,
              }
              st.session_state.convoys_db.append(nuevo_obj)
              st.success("¡Convoy creado con éxito!")
              st.rerun()
            else:
              st.error("Por favor completa todos los campos.")
        st.markdown("</div>", unsafe_allow_html=True)
      else:
        st.info("🔒 Los conductores solo pueden visualizar los registros.")

    c_reun_izq, c_reun_der = st.columns(2)

    with c_reun_izq:
      st.markdown(
          """
            <div style="background-color: #261c17; padding: 20px; border-radius: 10px; border: 1px solid #4a3525;">
                <h4 style="color: #f4d06f; margin-top: 0;">Reunión Activa</h4>
            """,
          unsafe_allow_html=True,
      )

      nombres_reuniones = [r["titulo"] for r in st.session_state.reuniones_db]
      opciones_reunion = ["Seleccione..."] + nombres_reuniones
      sel_reunion_val = st.selectbox(
          "Seleccionar reunión", opciones_reunion, key="sel_reunion_box"
      )

      col_rb1, col_rb2 = st.columns([1, 1])
      with col_rb1:
        cargar_reunion = st.button(
            "Cargar", use_container_width=True, key="btn_cargar_reunion"
        )
      with col_rb2:
        eliminar_reunion = st.button(
            "Eliminar", use_container_width=True, key="btn_eliminar_reunion"
        )

      if eliminar_reunion and sel_reunion_val != "Seleccione...":
        if es_admin_o_dueno:
          st.session_state.reuniones_db = [
              r
              for r in st.session_state.reuniones_db
              if r["titulo"] != sel_reunion_val
          ]
          st.success(f"Reunión '{sel_reunion_val}' eliminada.")
        else:
          # Los conductores no pueden borrar reuniones del sistema:
          # el botón solo limpia su filtro/selección local.
          st.session_state["_reset_sel_reunion"] = True
          st.info("Filtro de reunión limpiado.")
        st.rerun()

      st.markdown("</div>", unsafe_allow_html=True)

    with c_reun_der:
      if es_admin_o_dueno:
        st.markdown(
            """
                <div style="background-color: #261c17; padding: 20px; border-radius: 10px; border: 1px solid #4a3525;">
                    <h4 style="color: #f4d06f; margin-top: 0;">— ó crear nueva reunión —</h4>
                """,
            unsafe_allow_html=True,
        )

        with st.form("form_nueva_reunion"):
          r_num = st.text_input("Día (Número)", placeholder="Ej: 15")
          r_nom = st.text_input(
              "Nombre de Reunión", placeholder="Ej: Reunión Mensual"
          )
          submit_reunion = st.form_submit_button("Crear", use_container_width=True)

          if submit_reunion:
            if r_num and r_nom:
              nuevo_titulo_r = f"Día {r_num} - {r_nom}"
              tipo_r = (
                  "Quincenal" if "quincen" in r_nom.lower() else "Mensual"
              )
              nuevo_obj_r = {
                  "id": len(st.session_state.reuniones_db) + 1,
                  "titulo": nuevo_titulo_r,
                  "tipo": tipo_r,
                  "dia": r_num,
              }
              st.session_state.reuniones_db.append(nuevo_obj_r)
              st.success("¡Reunión creada con éxito!")
              st.rerun()
            else:
              st.error("Completa todos los campos.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    item_activo = None
    if sel_convoy_val != "Seleccione..." and cargar_convoy:
      item_activo = sel_convoy_val
    elif sel_reunion_val != "Seleccione..." and cargar_reunion:
      item_activo = sel_reunion_val

    if item_activo:
      st.markdown(
          f"### 📋 Control de Asistencia para: <span style='color:"
          f" #f4d06f;'>{item_activo}</span>",
          unsafe_allow_html=True,
      )

      lista_trabajadores = st.session_state.drivers_db[
          "Nombre / Tag"
      ].tolist()

      if item_activo not in st.session_state.asistencias_registros:
        st.session_state.asistencias_registros[item_activo] = {
            t: False for t in lista_trabajadores
        }

      if es_admin_o_dueno:
        with st.form(f"form_asistencia_{item_activo}"):
          asistencia_actualizada = {}
          for trabajador in lista_trabajadores:
            estado_previo = (
                st.session_state.asistencias_registros[item_activo].get(
                    trabajador, False
                )
            )
            asistencia_actualizada[trabajador] = st.checkbox(
                f"Asistió: {trabajador}", value=estado_previo
            )

          if st.form_submit_button("Guardar Asistencia", type="primary"):
            st.session_state.asistencias_registros[
                item_activo
            ] = asistencia_actualizada
            st.success("¡Asistencia guardada correctamente!")
      else:
        for trabajador in lista_trabajadores:
          asistio = st.session_state.asistencias_registros[item_activo].get(
              trabajador, False
          )
          badge = "✅ Asistió" if asistio else "❌ Ausente"
          color_badge = "#2ecc71" if asistio else "#e74c3c"
          st.markdown(
              f"- **{trabajador}:** <span style='color: {color_badge};"
              f" font-weight: bold;'>{badge}</span>",
              unsafe_allow_html=True,
          )

    st.markdown("---")
    st.markdown("### 📊 Estadísticas y Visión Histórica de Asistencia")

    def _calcular_stats_asistencia(eventos_dict, trabajadores):
      total_eventos = len(eventos_dict)
      filas = []
      for t in trabajadores:
        asistencias_totales = sum(
            1 for registros in eventos_dict.values() if registros.get(t, False)
        )
        porcentaje_asist = (
            int((asistencias_totales / total_eventos) * 100)
            if total_eventos > 0
            else 0
        )
        filas.append({
            "Trabajador": t,
            "Asistencias": f"{asistencias_totales} / {total_eventos}",
            "Cumplimiento": f"{porcentaje_asist}%",
        })
      return filas

    trabajadores = st.session_state.drivers_db["Nombre / Tag"].tolist()

    registros_reuniones = {
        ev: reg
        for ev, reg in st.session_state.asistencias_registros.items()
        if ev in nombres_reuniones
    }
    registros_convoyes = {
        ev: reg
        for ev, reg in st.session_state.asistencias_registros.items()
        if ev in nombres_convoys
    }

    col_stats_reun, col_stats_convoy = st.columns(2)

    with col_stats_reun:
      st.markdown("#### 📋 Asistencia a Reuniones")
      if registros_reuniones:
        st.dataframe(
            pd.DataFrame(
                _calcular_stats_asistencia(registros_reuniones, trabajadores)
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.warning("No hay reuniones con asistencia registrada todavía.")

    with col_stats_convoy:
      st.markdown("#### 🚚 Asistencia a Convoyes")
      if registros_convoyes:
        st.dataframe(
            pd.DataFrame(
                _calcular_stats_asistencia(registros_convoyes, trabajadores)
            ),
            use_container_width=True,
            hide_index=True,
        )
      else:
        st.warning("No hay convoyes con asistencia registrada todavía.")

  elif choice == "Reportes":
    st.markdown("# Reportes y Estadísticas Mensuales")
    st.info(
        "Progreso detallado con indicador tipo semáforo según el cumplimiento de"
        " la meta."
    )

    c_nav1, c_nav2, c_nav3 = st.columns([1, 3, 1])
    with c_nav1:
      if st.button("◀ Mes Anterior", use_container_width=True):
        if st.session_state.report_mes == 1:
          st.session_state.report_mes = 12
          st.session_state.report_anio -= 1
        else:
          st.session_state.report_mes -= 1
        st.rerun()
    with c_nav2:
      mes_actual_nombre = nombres_meses_lista[st.session_state.report_mes]
      st.markdown(
          f"<h3 style='text-align: center; color: #f4d06f; margin: 0;'>📅"
          f" {mes_actual_nombre} {st.session_state.report_anio}</h3>",
          unsafe_allow_html=True,
      )
    with c_nav3:
      if st.button("Mes Siguiente ▶", use_container_width=True):
        if st.session_state.report_mes == 12:
          st.session_state.report_mes = 1
          st.session_state.report_anio += 1
        else:
          st.session_state.report_mes += 1
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    col_tab_ats, col_tab_ets2, _ = st.columns([1.5, 1.5, 4])
    with col_tab_ats:
      if st.button("🔴 ATS (American Truck Simulator)", use_container_width=True):
        st.session_state.report_tab = "ATS"
        st.rerun()
    with col_tab_ets2:
      if st.button("🔵 ETS2 (Euro Truck Simulator 2)", use_container_width=True):
        st.session_state.report_tab = "ETS2"
        st.rerun()

    st.markdown("---")
    current_border = (
        "#e74c3c" if st.session_state.report_tab == "ATS" else "#3498db"
    )
    st.markdown(
        f'<div style="height:4px; border-radius:3px; background-color:'
        f'{current_border}; margin-bottom:12px;"></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.report_tab == "ATS":
      meta_actual = st.number_input(
          "Meta Mensual ATS (km)",
          min_value=0,
          max_value=10000000,
          value=int(st.session_state.meta_ats),
          step=1000,
          key="meta_input_ats"
      )
      st.session_state.meta_ats = meta_actual
      simulador_actual = "ATS"
    else:
      meta_actual = st.number_input(
          "Meta Mensual ETS2 (km)",
          min_value=0,
          max_value=10000000,
          value=int(st.session_state.meta_ets2),
          step=1000,
          key="meta_input_ets2"
      )
      st.session_state.meta_ets2 = meta_actual
      simulador_actual = "ETS2"

    loader_rep = st.empty()
    mostrar_cargando(loader_rep, "Calculando reporte mensual...")

    bitacora_rep = preparar_bitacora(st.session_state.trucksbook_data)
    df_source = filtrar_periodo_simulador(
        bitacora_rep,
        simulador_actual,
        st.session_state.report_anio,
        st.session_state.report_mes,
    )
    df_res = resumen_por_conductor(df_source)

    loader_rep.empty()

    if df_res.empty:
      st.warning(f"No hay registros para {simulador_actual} en este periodo.")
    else:
      total_conductores = len(df_res)
      
      # Garantizar límites coherentes para Streamlit
      min_top = min(5, total_conductores)
      max_top = max(5, total_conductores)
      default_top = min(25, max_top)

      c_top, c_info = st.columns([1.2, 4])
      with c_top:
        top_n = st.number_input(
            "Conductores a mostrar",
            min_value=int(min_top),
            max_value=int(max_top),
            value=int(default_top),
            step=1 if max_top < 5 else 5,
            key=f"rep_top_n_{simulador_actual}"  # Key dinámica para evitar colisiones entre ATS y ETS2
        )
      with c_info:
        st.markdown(
            f"<br><span style='color:#b0a8a0;'>Ranking sobre "
            f"<b style='color:#f4d06f;'>{total_conductores:,}</b> conductores "
            f"con actividad en el periodo.</span>",
            unsafe_allow_html=True,
        )

      df_top = df_res.head(int(top_n))

      filas_html = []
      datos_top = zip(
          df_top["Conductor"].tolist(),
          df_top["Total Registrado"].tolist(),
          df_top["KM Real"].tolist(),
          df_top["KM Carrera"].tolist(),
          df_top["Promedio Diario"].tolist(),
      )
      for idx, (conductor, total, km_real, km_carrera, promedio) in enumerate(
          datos_top, start=1
      ):
        porcentaje = (
            min(int((total / meta_actual) * 100), 100) if meta_actual > 0 else 0
        )
        color_barra = (
            "#e74c3c"
            if porcentaje < 40
            else ("#f1c40f" if porcentaje < 80 else "#2ecc71")
        )
        filas_html.append(
            f'<tr>'
            f'<td style="font-weight:bold;">{idx}</td>'
            f'<td style="font-weight:bold;">{conductor}</td>'
            f'<td>{total:,.0f}</td>'
            f'<td style="color:#2ecc71;">{km_real:,.0f}</td>'
            f'<td style="color:#e74c3c;">{km_carrera:,.0f}</td>'
            f'<td>{promedio:,.0f}</td>'
            f'<td style="min-width:180px;">'
            f'<div style="background-color:#261c17; border-radius:4px;'
            f' width:100%; height:16px; border:1px solid #4a3525;">'
            f'<div style="background-color:{color_barra}; width:{porcentaje}%;'
            f' height:100%; border-radius:3px;"></div></div>'
            f'<span style="font-size:11px; color:#b0a8a0;">{porcentaje}%'
            f' completado</span>'
            f'</td>'
            f'</tr>'
        )

      st.markdown(
          compactar_html(
              "<div class='ct-table-wrap'><table><thead><tr>"
              "<th>#</th><th>Conductor</th><th>Total Registrado</th>"
              "<th>KM Real</th><th>KM Carrera</th><th>Promedio Diario</th>"
              "<th>Avance vs Meta</th></tr></thead><tbody>"
              + "".join(filas_html)
              + "</tbody></table></div>"
          ),
          unsafe_allow_html=True,
      )

      st.download_button(
          "⬇️ Descargar reporte completo (CSV)",
          data=bitacora_a_csv(df_res),
          file_name=f"reporte_{simulador_actual}_{st.session_state.report_anio}_"
          f"{st.session_state.report_mes:02d}.csv",
          mime="text/csv",
      )

    st.markdown("</div>", unsafe_allow_html=True)

  elif choice == "Comparativa":
    st.markdown("# ⚖️ Comparativa Mensual")
    st.info(
        "Compara los kilómetros y el rendimiento de los conductores entre dos"
        " meses distintos."
    )

      # 1. Obtener la lista de meses disponibles en la base de datos de TrucksBook
    if not st.session_state.trucksbook_data.empty:
        df_tb = st.session_state.trucksbook_data.copy()
        df_tb['Fecha_dt'] = pd.to_datetime(df_tb['Fecha'], errors='coerce')
        df_tb['Periodo'] = df_tb['Fecha_dt'].dt.strftime('%Y-%m')

        meses_es = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }

        periodos_unicos = sorted(df_tb['Fecha_dt'].dt.to_period('M').dropna().unique())
        if len(periodos_unicos) > 0:
            opciones_meses = [
                f"{meses_es[p.month]} de {p.year}"
                for p in periodos_unicos
                if pd.notnull(p)
            ]
        else:
            opciones_meses = ['agosto de 2026', 'septiembre de 2026']

        idx_base = max(0, len(opciones_meses) - 2) if len(opciones_meses) >= 2 else 0
        idx_comp = len(opciones_meses) - 1 if len(opciones_meses) >= 1 else 0

        col_sim, col_m1, col_m2, col_btn = st.columns([1.2, 2, 2, 1])

        with col_sim:
            simulador_comp = st.selectbox(
                'Simulador',
                options=["ATS", "ETS2"],
                key='select_sim_comp',
            )

        with col_m1:
            mes_base = st.selectbox(
                'Mes Base (Anterior)',
                options=opciones_meses,
                index=idx_base,
                key='select_mes_base',
            )

        with col_m2:
            mes_a_comparar = st.selectbox(
                'Mes a Comparar (Actual)',
                options=opciones_meses,
                index=idx_comp,
                key='select_mes_comp',
            )

        with col_btn:
            st.write("##")
            btn_comparar = st.button("Comparar", use_container_width=True, type="primary")

        loader_comp = st.empty()

        if btn_comparar:
            mostrar_cargando(loader_comp, "Calculando comparativa y estadísticas...")

        # Cálculo por defecto (o al presionar el botón) para que las variables siempre existan
        a_base, m_base_num = obtener_anio_mes(mes_base)
        a_comp, m_comp_num = obtener_anio_mes(mes_a_comparar)

        tb_df = preparar_bitacora(st.session_state.trucksbook_data)
        tot_base, podio_base, rest_base = generar_datos_podio(
            tb_df, simulador_comp, a_base, m_base_num, 7
        )
        tot_comp, podio_comp, rest_comp = generar_datos_podio(
            tb_df, simulador_comp, a_comp, m_comp_num, 7
        )

        if btn_comparar:
            loader_comp.empty()
    if not podio_base:
          podio_base = [
              {"puesto": "1", "nombre": "Sin registros", "km": "0 km", "medalla": "👑 Oro"},
              {"puesto": "2", "nombre": "Sin registros", "km": "0 km", "medalla": "🥈 Plata"},
              {"puesto": "3", "nombre": "Sin registros", "km": "0 km", "medalla": "🥉 Bronce"},
          ]
    if not podio_comp:
          podio_comp = [
              {"puesto": "1", "nombre": "Sin registros", "km": "0 km", "medalla": "👑 Oro"},
              {"puesto": "2", "nombre": "Sin registros", "km": "0 km", "medalla": "🥈 Plata"},
            {"puesto": "3", "nombre": "Sin registros", "km": "0 km", "medalla": "🥉 Bronce"},
        ]

    st.markdown("---")
    col_met1, col_met2 = st.columns(2)
    with col_met1:
        st.markdown(
            f"""
                <div style="background-color: #261c17; padding: 20px; border-radius: 10px; border: 1px solid #4a3525; text-align: center;">
                    <h4 style="color: #f4d06f; margin-bottom: 15px;">TOTAL KILÓMETROS ({simulador_comp} - Sin Carrera)</h4>
                    <div style="display: flex; justify-content: space-around; align-items: center;">
                        <div>
                            <span style="font-size: 12px; color: #b0a8a0; text-transform: uppercase;">{mes_base}</span><br>
                            <span style="font-size: 20px; font-weight: bold; color: #fdfbf7;">{tot_base}</span>
                        </div>
                        <div style="background-color: #4a3525; color: #fdfbf7; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: bold;">VS</div>
                        <div>
                            <span style="font-size: 12px; color: #b0a8a0; text-transform: uppercase;">{mes_a_comparar}</span><br>
                            <span style="font-size: 20px; font-weight: bold; color: #3498db;">{tot_comp}</span>
                        </div>
                    </div>
                </div>
                """,
              unsafe_allow_html=True,
          )

    with col_met2:
      st.markdown(
          f"""
            <div style="background-color: #261c17; padding: 20px; border-radius: 10px; border: 1px solid #4a3525; text-align: center;">
                <h4 style="color: #f4d06f; margin-bottom: 15px;">ASISTENCIA PROMEDIO</h4>
                <div style="display: flex; justify-content: space-around; align-items: center;">
                    <div>
                        <span style="font-size: 12px; color: #b0a8a0; text-transform: uppercase;">{mes_base}</span><br>
                        <span style="font-size: 20px; font-weight: bold; color: #fdfbf7;">0%</span>
                    </div>
                    <div style="background-color: #4a3525; color: #fdfbf7; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: bold;">VS</div>
                    <div>
                        <span style="font-size: 12px; color: #b0a8a0; text-transform: uppercase;">{mes_a_comparar}</span><br>
                        <span style="font-size: 20px; font-weight: bold; color: #f1c40f;">0%</span>
                    </div>
                </div>
            </div>
            """,
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)
    col_izq, col_der = st.columns(2)

    with col_izq:
      st.markdown(f"### 🏆 Top 10 - {simulador_comp} ({mes_base})")
      item_oro_b = next(
          (x for x in podio_base if "Oro" in x["medalla"]), podio_base[0]
      )
      item_plata_b = next(
          (x for x in podio_base if "Plata" in x["medalla"]), podio_base[1]
      )
      item_bronce_b = next(
          (x for x in podio_base if "Bronce" in x["medalla"]), podio_base[2]
      )

      pb2, pb1, pb3 = st.columns(3)
      with pb2:
        st.markdown(
            f"""
                <div style="background-color: #120d0b; border: 1px solid #4a3525; padding: 10px; border-radius: 8px; text-align: center; margin-top: 15px;">
                    <div style="font-size: 18px;">🥈</div>
                    <div style="font-size: 9px; color: #b0a8a0; text-transform: uppercase; font-weight: bold;">Plata (#2)</div>
                    <div style="font-size: 13px; font-weight: bold; color: #fdfbf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item_plata_b['nombre']}</div>
                    <div style="font-size: 11px; color: #3498db; font-family: monospace; font-weight: bold;">{item_plata_b['km']}</div>
                </div>
                """,
            unsafe_allow_html=True,
        )
      with pb1:
        st.markdown(
            f"""
                <div style="background-color: #261c17; border: 2px solid #f4d06f; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 22px;">👑</div>
                    <div style="font-size: 10px; color: #f4d06f; text-transform: uppercase; font-weight: bold;">Oro (#1)</div>
                    <div style="font-size: 14px; font-weight: bold; color: #fdfbf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item_oro_b['nombre']}</div>
                    <div style="font-size: 12px; color: #f4d06f; font-family: monospace; font-weight: bold;">{item_oro_b['km']}</div>
                </div>
                """,
            unsafe_allow_html=True,
        )
      with pb3:
        st.markdown(
            f"""
                <div style="background-color: #120d0b; border: 1px solid #4a3525; padding: 10px; border-radius: 8px; text-align: center; margin-top: 25px;">
                    <div style="font-size: 18px;">🥉</div>
                    <div style="font-size: 9px; color: #b0a8a0; text-transform: uppercase; font-weight: bold;">Bronce (#3)</div>
                    <div style="font-size: 13px; font-weight: bold; color: #fdfbf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item_bronce_b['nombre']}</div>
                    <div style="font-size: 11px; color: #3498db; font-family: monospace; font-weight: bold;">{item_bronce_b['km']}</div>
                </div>
                """,
            unsafe_allow_html=True,
        )

      if rest_base:
        st.markdown("<br>", unsafe_allow_html=True)
        for driver in rest_base:
          st.markdown(
              f"""
                    <div style="background-color: #261c17; padding: 8px 12px; border-radius: 6px; border: 1px solid #4a3525; display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 13px;">
                        <span style="font-weight: bold; color: #fdfbf7;">#{driver['pos']} {driver['nombre']}</span>
                        <span style="color: #3498db; font-family: monospace; font-weight: bold;">{driver['km']}</span>
                    </div>
                    """,
              unsafe_allow_html=True,
          )

    with col_der:
      st.markdown(f"### 🏆 Top 10 - {simulador_comp} ({mes_a_comparar})")
      item_oro = next(
          (x for x in podio_comp if "Oro" in x["medalla"]), podio_comp[0]
      )
      item_plata = next(
          (x for x in podio_comp if "Plata" in x["medalla"]), podio_comp[1]
      )
      item_bronce = next(
          (x for x in podio_comp if "Bronce" in x["medalla"]), podio_comp[2]
      )

      p2, p1, p3 = st.columns(3)
      with p2:
        st.markdown(
            f"""
                <div style="background-color: #120d0b; border: 1px solid #4a3525; padding: 10px; border-radius: 8px; text-align: center; margin-top: 15px;">
                    <div style="font-size: 18px;">🥈</div>
                    <div style="font-size: 9px; color: #b0a8a0; text-transform: uppercase; font-weight: bold;">Plata (#2)</div>
                    <div style="font-size: 13px; font-weight: bold; color: #fdfbf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item_plata['nombre']}</div>
                    <div style="font-size: 11px; color: #3498db; font-family: monospace; font-weight: bold;">{item_plata['km']}</div>
                </div>
                """,
            unsafe_allow_html=True,
        )
      with p1:
        st.markdown(
            f"""
                <div style="background-color: #261c17; border: 2px solid #f4d06f; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 22px;">👑</div>
                    <div style="font-size: 10px; color: #f4d06f; text-transform: uppercase; font-weight: bold;">Oro (#1)</div>
                    <div style="font-size: 14px; font-weight: bold; color: #fdfbf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item_oro['nombre']}</div>
                    <div style="font-size: 12px; color: #f4d06f; font-family: monospace; font-weight: bold;">{item_oro['km']}</div>
                </div>
                """,
            unsafe_allow_html=True,
        )
      with p3:
        st.markdown(
            f"""
                <div style="background-color: #120d0b; border: 1px solid #4a3525; padding: 10px; border-radius: 8px; text-align: center; margin-top: 25px;">
                    <div style="font-size: 18px;">🥉</div>
                    <div style="font-size: 9px; color: #b0a8a0; text-transform: uppercase; font-weight: bold;">Bronce (#3)</div>
                    <div style="font-size: 13px; font-weight: bold; color: #fdfbf7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item_bronce['nombre']}</div>
                    <div style="font-size: 11px; color: #3498db; font-family: monospace; font-weight: bold;">{item_bronce['km']}</div>
                </div>
                """,
            unsafe_allow_html=True,
        )

      if rest_comp:
        st.markdown("<br>", unsafe_allow_html=True)
        for driver in rest_comp:
          st.markdown(
              f"""
                    <div style="background-color: #261c17; padding: 8px 12px; border-radius: 6px; border: 1px solid #4a3525; display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 13px;">
                        <span style="font-weight: bold; color: #fdfbf7;">#{driver['pos']} {driver['nombre']}</span>
                        <span style="color: #3498db; font-family: monospace; font-weight: bold;">{driver['km']}</span>
                    </div>
                    """,
              unsafe_allow_html=True,
          )


  elif choice == "Ruleta":
    st.markdown("# 🎡 Ruleta de Sorteos (DLC)")
    st.caption(
        "Sortea DLCs entre los participantes de la VTC. Administradores y"
        " dueños pueden realizar el sorteo; el historial de ganadores es"
        " visible para todos los usuarios."
    )

    es_admin_ruleta = st.session_state.role in ["Dueño", "Administrador"]

    if es_admin_ruleta:
      st.session_state.setdefault("ruleta_participantes", [])
      st.session_state.setdefault("ruleta_ganador_actual", None)

      st.markdown("### 🎁 Nuevo sorteo")
      nombre_dlc = st.text_input(
          "Nombre del DLC / premio a sortear", key="ruleta_dlc_nombre"
      )

      if st.session_state.get("_ruleta_limpiar_input"):
        st.session_state.ruleta_input_participante = ""
        st.session_state._ruleta_limpiar_input = False

      col_add1, col_add2 = st.columns([3, 1])
      with col_add1:
        nuevo_participante = st.text_input(
            "Nombre del participante", key="ruleta_input_participante"
        )
      with col_add2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("➕ Agregar", use_container_width=True):
          nombre_limpio = nuevo_participante.strip()
          if not nombre_limpio:
            st.warning("Escribe un nombre antes de agregarlo.")
          elif nombre_limpio in st.session_state.ruleta_participantes:
            st.warning("Ese participante ya está en la lista.")
          else:
            st.session_state.ruleta_participantes.append(nombre_limpio)
            st.session_state._ruleta_limpiar_input = True
            st.rerun()

      if st.session_state.ruleta_participantes:
        st.markdown(
            f"**Participantes ({len(st.session_state.ruleta_participantes)}):**"
        )
        for i, nombre_p in enumerate(st.session_state.ruleta_participantes):
          col_p1, col_p2 = st.columns([5, 1])
          with col_p1:
            st.markdown(
                f"""<div style="background-color: #261c17; border: 1px solid #4a3525;
                border-radius: 6px; padding: 6px 12px; margin-bottom: 4px;">{nombre_p}</div>""",
                unsafe_allow_html=True,
            )
          with col_p2:
            if st.button("🗑️", key=f"del_participante_{i}"):
              st.session_state.ruleta_participantes.pop(i)
              st.rerun()

        col_clear, col_spin = st.columns([1, 2])
        with col_clear:
          if st.button("Limpiar lista", use_container_width=True):
            st.session_state.ruleta_participantes = []
            st.session_state.ruleta_ganador_actual = None
            st.rerun()
        with col_spin:
          girar_disabled = len(st.session_state.ruleta_participantes) < 2
          if st.button(
              "🎡 Girar la ruleta",
              type="primary",
              use_container_width=True,
              disabled=girar_disabled,
          ):
            if not nombre_dlc.strip():
              st.warning("Escribe el nombre del DLC antes de girar.")
            else:
              placeholder_ruleta = st.empty()
              participantes_actuales = list(st.session_state.ruleta_participantes)
              ganador = random.choice(participantes_actuales)
              vueltas = 18
              for i in range(vueltas):
                nombre_visible = random.choice(participantes_actuales)
                demora = 0.03 + (i / vueltas) * 0.12
                placeholder_ruleta.markdown(
                    f"""
                    <div style="background-color: #261c17; border: 2px solid #d97736;
                    border-radius: 10px; padding: 20px; text-align: center;">
                        <div style="font-size: 13px; color: #f4d06f;">Girando la ruleta...</div>
                        <div style="font-size: 26px; font-weight: bold; color: #fdfbf7;">{nombre_visible}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                time.sleep(demora)
              placeholder_ruleta.markdown(
                  f"""
                  <div style="background-color: #261c17; border: 2px solid #f4d06f;
                  border-radius: 10px; padding: 20px; text-align: center;">
                      <div style="font-size: 13px; color: #f4d06f;">🏆 ¡GANADOR!</div>
                      <div style="font-size: 28px; font-weight: bold; color: #f4d06f;">{ganador}</div>
                  </div>
                  """,
                  unsafe_allow_html=True,
              )
              st.balloons()
              st.session_state.ruleta_ganador_actual = {
                  "dlc": nombre_dlc.strip(),
                  "ganador": ganador,
                  "participantes": participantes_actuales,
              }
      else:
        st.info("Agrega al menos 2 participantes para poder girar la ruleta.")

      if st.session_state.get("ruleta_ganador_actual"):
        resultado = st.session_state.ruleta_ganador_actual
        st.success(f"Ganador de '{resultado['dlc']}': **{resultado['ganador']}**")
        if st.button("✅ Confirmar y guardar en el historial", type="primary"):
          guardar_ganador_ruleta(
              resultado["dlc"],
              resultado["ganador"],
              resultado["participantes"],
              st.session_state.user,
          )
          registrar_alerta(
              "Ruleta",
              f"Se sorteó '{resultado['dlc']}' y el ganador fue"
              f" {resultado['ganador']}.",
              "🎡",
          )
          st.session_state.ruleta_participantes = []
          st.session_state.ruleta_ganador_actual = None
          st.success("¡Resultado guardado en el historial de ganadores!")
          st.rerun()

      st.divider()
    else:
      st.info(
          "Solo los administradores y el dueño pueden realizar sorteos."
          " Aquí puedes ver el historial de ganadores."
      )

    st.markdown("### 🏆 Historial de Ganadores")
    historico_ruleta = cargar_historico_ruleta()
    if historico_ruleta.empty:
      st.caption("Todavía no se ha registrado ningún sorteo.")
    else:
      st.dataframe(
          historico_ruleta.sort_values("Fecha", ascending=False),
          use_container_width=True,
          hide_index=True,
      )
  elif choice == "Importar TrucksBook":
    if st.session_state.role == "Conductor":
      st.error("⚠️ Acceso exclusivo para administradores y dueños.")
    else:
      st.markdown("# 📂 Importar Reporte CSV de TrucksBook")
      uploaded_file = st.file_uploader("Selecciona el archivo CSV", type=["csv"])
      if uploaded_file is not None:
        ruta_local_csv = guardar_csv_local(uploaded_file)
        loader_imp = st.empty()
        mostrar_cargando(loader_imp, "Leyendo y procesando el archivo CSV...")
        try:
          try:
            uploaded_file.seek(0)
            df_raw = pd.read_csv(uploaded_file, sep=";")
            if df_raw.shape[1] == 1:
              raise ValueError("separador incorrecto")
          except Exception:
            uploaded_file.seek(0)
            try:
              df_raw = pd.read_csv(uploaded_file, sep=",")
              if df_raw.shape[1] == 1:
                raise ValueError("separador incorrecto")
            except Exception:
              uploaded_file.seek(0)
              df_raw = pd.read_csv(uploaded_file, sep=None, engine="python")

          df_processed = procesar_datos_trucksbook(df_raw)
          loader_imp.empty()
          st.success(
              f"¡Datos procesados correctamente! {len(df_processed):,} registros"
              " listos para integrar."
          )
          st.caption(f"Copia local guardada en: {ruta_local_csv}")
          st.caption("Vista previa (primeras 10 filas):")
          st.dataframe(
              df_processed.head(10), use_container_width=True, hide_index=True
          )

          if st.button("Confirma e integra al ERP"):
            df_final = integrar_y_guardar_historico(df_processed)
            st.session_state.trucksbook_data = df_final
            st.cache_data.clear()
            registrar_alerta(
                "Estadísticas",
                f"Se integraron {len(df_processed):,} nuevos registros de "
                "TrucksBook. Las estadísticas y el podio de conductores"
                " fueron actualizados.",
                "📊",
            )
            try:
              ruta_respaldo = guardar_respaldo_historico_local(df_final)
              st.success(f"¡Se integraron los nuevos registros y se respaldó en: {ruta_respaldo}!")
            except Exception as e:
              st.warning(f"Se integraron los registros, pero no se logró crear el respaldo local: {e}")
        except Exception as e:
          loader_imp.empty()
          st.error(f"No se pudo procesar el archivo CSV: {e}")
  elif choice == "Mi Perfil":
    # Página propia de cada usuario (cualquier rol): puede cambiar su foto,
    # su contraseña y su pregunta de seguridad sin pedirle nada a un admin.
    st.markdown("# 🙋 Mi Perfil")
    fila_yo = buscar_usuario(st.session_state.user)
    if fila_yo is None:
      st.error("No se encontró tu usuario en la base de datos.")
    else:
      idx_yo = st.session_state.users_db[
          st.session_state.users_db["Usuario"] == fila_yo["Usuario"]
      ].index[0]

      col_foto, col_datos = st.columns([1, 2])
      with col_foto:
        st.markdown(
            render_avatar_html(st.session_state.user, tamano=140, clase_extra="ct-avatar-lg"),
            unsafe_allow_html=True,
        )
      with col_datos:
        st.markdown(
            f"<div class='ct-profile-name' style='font-size:22px;'>{fila_yo['Usuario']}</div>"
            f"<span class='ct-role-badge {_slugs_rol.get(fila_yo['Rol'], 'role-conductor')}'>"
            f"{fila_yo['Rol']}</span>",
            unsafe_allow_html=True,
        )

      st.divider()
      tab_mi_foto, tab_mi_pass, tab_mi_seg = st.tabs(
          ["📷 Foto de perfil", "🔑 Cambiar contraseña", "🔐 Pregunta de seguridad"]
      )

      with tab_mi_foto:
        with st.form("form_mi_foto"):
          mi_foto = st.file_uploader(
              "Elige tu nueva foto",
              type=EXTENSIONES_FOTO_PERMITIDAS,
              key="foto_mi_perfil",
          )
          mi_quitar = st.checkbox("Quitar mi foto actual", key="quitar_foto_mi_perfil")
          if st.form_submit_button("Guardar foto", type="primary"):
            if mi_foto is not None and mi_foto.size > MAX_PESO_FOTO_MB * 1024 * 1024:
              st.error(f"La foto supera los {MAX_PESO_FOTO_MB} MB.")
            elif mi_quitar:
              eliminar_foto_perfil(str(fila_yo["Foto"]))
              st.session_state.users_db.at[idx_yo, "Foto"] = ""
              guardar_usuarios_db(st.session_state.users_db)
              st.success("Foto eliminada.")
              st.rerun()
            elif mi_foto is not None:
              eliminar_foto_perfil(str(fila_yo["Foto"]))
              st.session_state.users_db.at[idx_yo, "Foto"] = guardar_foto_perfil(
                  fila_yo["Usuario"], mi_foto
              )
              guardar_usuarios_db(st.session_state.users_db)
              st.success("¡Foto actualizada! Ya aparece en todo el ERP.")
              st.rerun()
            else:
              st.warning("Selecciona una imagen primero.")

      with tab_mi_pass:
        with st.form("form_mi_pass"):
          pass_actual = st.text_input("Contraseña actual", type="password")
          pass_nueva_1 = st.text_input("Contraseña nueva", type="password")
          pass_nueva_2 = st.text_input("Repite la contraseña nueva", type="password")
          if st.form_submit_button("Cambiar contraseña", type="primary"):
            if not verificar_password(pass_actual, fila_yo["Contraseña"]):
              st.error("La contraseña actual no es correcta.")
            elif len(pass_nueva_1) < 4:
              st.error("La contraseña nueva debe tener al menos 4 caracteres.")
            elif pass_nueva_1 != pass_nueva_2:
              st.error("Las dos contraseñas nuevas no coinciden.")
            else:
              st.session_state.users_db.at[idx_yo, "Contraseña"] = hash_password(pass_nueva_1)
              guardar_usuarios_db(st.session_state.users_db)
              st.success("¡Contraseña actualizada!")

      with tab_mi_seg:
        if not str(fila_yo["Pregunta"]).strip():
          st.warning(
              "Aún no tienes pregunta de seguridad. Configúrala para poder"
              " recuperar tu contraseña desde la pantalla de login."
          )
        with st.form("form_mi_seguridad"):
          mi_pregunta = st.selectbox("Pregunta", PREGUNTAS_SEGURIDAD, key="preg_mi_perfil")
          mi_respuesta = st.text_input("Respuesta", type="password", key="resp_mi_perfil")
          mi_correo = st.text_input(
              "Correo de contacto (opcional)", value=str(fila_yo["Correo"])
          )
          if st.form_submit_button("Guardar", type="primary"):
            if not mi_respuesta.strip():
              st.error("Escribe una respuesta.")
            else:
              st.session_state.users_db.at[idx_yo, "Pregunta"] = mi_pregunta
              st.session_state.users_db.at[idx_yo, "Respuesta"] = hash_password(
                  normalizar_respuesta_seguridad(mi_respuesta)
              )
              st.session_state.users_db.at[idx_yo, "Correo"] = mi_correo.strip()
              guardar_usuarios_db(st.session_state.users_db)
              st.success("Pregunta de seguridad guardada.")
              st.rerun()

  elif choice == "Configuración y Usuarios":
    if st.session_state.role == "Conductor":
      st.error("⚠️ Acceso exclusivo para administradores y dueños.")
    else:
          st.markdown("# ⚙️ Configuración y Credenciales de Usuarios")
          st.info(
              "Administra las cuentas de acceso, credenciales y el rol asignado"
              " para controlar los permisos de visualización del ERP."
          )

          tab_users_list, tab_users_edit, tab_users_new = st.tabs(
              ["Lista de Usuarios", "Modificar / Eliminar Usuario", "Crear Nuevo Usuario"]
          )

          with tab_users_list:
              # Se muestra la foto como columna de imagen y se ocultan los
              # campos sensibles (hash de contraseña y de respuesta secreta).
              df_vista = st.session_state.users_db.copy()
              df_vista["Foto"] = df_vista["Foto"].apply(obtener_foto_data_uri)
              df_vista["Contraseña"] = df_vista["Contraseña"].apply(
                  lambda v: "🔒 protegida" if es_hash(v) else "⚠️ sin cifrar"
              )
              df_vista["Pregunta de seguridad"] = df_vista["Pregunta"].apply(
                  lambda v: "✅ configurada" if str(v).strip() else "— sin configurar"
              )
              st.dataframe(
                  df_vista[["ID", "Foto", "Usuario", "Rol", "Contraseña",
                            "Pregunta de seguridad", "Correo"]],
                  use_container_width=True,
                  hide_index=True,
                  column_config={
                      "Foto": st.column_config.ImageColumn("Foto", width="small"),
                  },
              )

          with tab_users_edit:
              st.markdown("### Modificar o Eliminar Usuario Existente")
              if st.session_state.users_db.empty:
                  st.warning("No hay usuarios registrados.")
              else:
                  user_options = st.session_state.users_db["Usuario"].tolist()
                  selected_user_to_edit = st.selectbox("Seleccionar Usuario", user_options, key="sel_user_edit")

                  user_row = st.session_state.users_db[st.session_state.users_db["Usuario"] == selected_user_to_edit].iloc[0]

                  # Vista previa de la foto actual, fuera del formulario
                  st.markdown(
                      "<div class='ct-avatar-row'>"
                      + render_avatar_html(selected_user_to_edit, tamano=80, clase_extra="ct-avatar-lg")
                      + f"<div class='ct-profile-name'>{selected_user_to_edit}</div></div>",
                      unsafe_allow_html=True,
                  )

                  with st.form("form_edit_user_cred"):
                      edit_user_name = st.text_input("Nombre de Usuario (Login)", value=str(user_row["Usuario"]))
                      edit_user_pass = st.text_input(
                          "Nueva contraseña (deja vacío para no cambiarla)",
                          value="", type="password",
                          help="Las contraseñas se guardan cifradas, por eso ya no se muestran.",
                      )

                      roles_disponibles = ["Dueño", "Administrador", "Conductor"]
                      current_role_idx = roles_disponibles.index(user_row["Rol"]) if user_row["Rol"] in roles_disponibles else 0
                      edit_user_role = st.selectbox("Rol en el Sistema", roles_disponibles, index=current_role_idx)

                      edit_user_correo = st.text_input(
                          "Correo de contacto (opcional)", value=str(user_row["Correo"])
                      )

                      # ---- Foto de perfil ----
                      st.markdown("#### 📷 Foto de perfil")
                      edit_user_foto = st.file_uploader(
                          "Subir o reemplazar foto",
                          type=EXTENSIONES_FOTO_PERMITIDAS,
                          key="foto_edit_user",
                          help=f"Formatos: {', '.join(EXTENSIONES_FOTO_PERMITIDAS)}. Máx {MAX_PESO_FOTO_MB} MB.",
                      )
                      quitar_foto = st.checkbox("Quitar la foto actual", key="quitar_foto_edit")

                      # ---- Pregunta de seguridad (recuperación de contraseña) ----
                      st.markdown("#### 🔐 Pregunta de seguridad")
                      pregunta_actual = str(user_row["Pregunta"]).strip()
                      opciones_preg = ["(sin cambios)"] + PREGUNTAS_SEGURIDAD
                      idx_preg = opciones_preg.index(pregunta_actual) if pregunta_actual in opciones_preg else 0
                      edit_pregunta = st.selectbox(
                          "Pregunta", opciones_preg, index=idx_preg, key="preg_edit_user"
                      )
                      edit_respuesta = st.text_input(
                          "Respuesta (deja vacío para no cambiarla)", type="password",
                          key="resp_edit_user",
                      )

                      col_e1, col_e2 = st.columns(2)
                      with col_e1:
                          submit_update = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
                      with col_e2:
                          submit_delete = st.form_submit_button("🗑️ Eliminar Usuario", use_container_width=True)

                      if submit_update:
                          nombre_repetido = (
                              edit_user_name.strip().lower() != selected_user_to_edit.lower()
                              and buscar_usuario(edit_user_name) is not None
                          )
                          foto_muy_pesada = (
                              edit_user_foto is not None
                              and edit_user_foto.size > MAX_PESO_FOTO_MB * 1024 * 1024
                          )
                          if not edit_user_name.strip():
                              st.error("Por favor completa el nombre de usuario.")
                          elif nombre_repetido:
                              st.error("Ya existe otro usuario con ese nombre.")
                          elif foto_muy_pesada:
                              st.error(f"La foto supera los {MAX_PESO_FOTO_MB} MB.")
                          else:
                              idx_match = st.session_state.users_db[st.session_state.users_db["Usuario"] == selected_user_to_edit].index[0]
                              st.session_state.users_db.at[idx_match, "Usuario"] = edit_user_name.strip()
                              st.session_state.users_db.at[idx_match, "Rol"] = edit_user_role
                              st.session_state.users_db.at[idx_match, "Correo"] = edit_user_correo.strip()

                              # Contraseña: solo se toca si escribieron una nueva
                              if edit_user_pass:
                                  st.session_state.users_db.at[idx_match, "Contraseña"] = hash_password(edit_user_pass)

                              # Foto
                              foto_previa = str(user_row["Foto"])
                              if quitar_foto:
                                  eliminar_foto_perfil(foto_previa)
                                  st.session_state.users_db.at[idx_match, "Foto"] = ""
                              elif edit_user_foto is not None:
                                  eliminar_foto_perfil(foto_previa)
                                  nueva_ruta = guardar_foto_perfil(edit_user_name.strip(), edit_user_foto)
                                  st.session_state.users_db.at[idx_match, "Foto"] = nueva_ruta

                              # Pregunta / respuesta de seguridad
                              if edit_pregunta != "(sin cambios)":
                                  st.session_state.users_db.at[idx_match, "Pregunta"] = edit_pregunta
                              if edit_respuesta:
                                  st.session_state.users_db.at[idx_match, "Respuesta"] = hash_password(
                                      normalizar_respuesta_seguridad(edit_respuesta)
                                  )

                              guardar_usuarios_db(st.session_state.users_db)
                              # Si el usuario editado es el que está en sesión,
                              # se actualiza la sesión para que el sidebar
                              # refleje el nombre/rol/foto al instante.
                              if st.session_state.user == selected_user_to_edit:
                                  st.session_state.user = edit_user_name.strip()
                                  st.session_state.role = edit_user_role
                              st.success(f"¡Usuario '{edit_user_name}' actualizado con éxito!")
                              st.rerun()

                      if submit_delete:
                          if len(st.session_state.users_db) <= 1:
                              st.error("No puedes eliminar al último usuario del sistema.")
                          elif selected_user_to_edit == st.session_state.user:
                              st.error("No puedes eliminar la cuenta con la que estás conectado.")
                          else:
                              eliminar_foto_perfil(str(user_row["Foto"]))
                              st.session_state.users_db = st.session_state.users_db[
                                  st.session_state.users_db["Usuario"] != selected_user_to_edit
                              ].reset_index(drop=True)
                              guardar_usuarios_db(st.session_state.users_db)
                              st.success(f"¡Usuario '{selected_user_to_edit}' eliminado correctamente!")
                              st.rerun()

          with tab_users_new:
              with st.form("form_nuevo_usuario_cred"):
                  nuevo_user_name = st.text_input("Nombre de Usuario (Login)")
                  nuevo_user_pass = st.text_input("Contraseña", type="password")
                  nuevo_user_role = st.selectbox(
                      "Rol en el Sistema", ["Dueño", "Administrador", "Conductor"]
                  )
                  nuevo_user_correo = st.text_input("Correo de contacto (opcional)")

                  st.markdown("#### 📷 Foto de perfil")
                  nuevo_user_foto = st.file_uploader(
                      "Foto de perfil (opcional)",
                      type=EXTENSIONES_FOTO_PERMITIDAS,
                      key="foto_nuevo_user",
                      help=f"Formatos: {', '.join(EXTENSIONES_FOTO_PERMITIDAS)}. Máx {MAX_PESO_FOTO_MB} MB.",
                  )

                  st.markdown("#### 🔐 Pregunta de seguridad")
                  st.caption(
                      "Permite que el usuario recupere su contraseña solo desde"
                      " la pantalla de login, sin depender de un administrador."
                  )
                  nueva_pregunta = st.selectbox(
                      "Pregunta", PREGUNTAS_SEGURIDAD, key="preg_nuevo_user"
                  )
                  nueva_respuesta = st.text_input(
                      "Respuesta", type="password", key="resp_nuevo_user"
                  )

                  if st.form_submit_button("Crear Credencial de Acceso", type="primary"):
                      if buscar_usuario(nuevo_user_name) is not None:
                          st.error("Ya existe un usuario con ese nombre.")
                      elif (
                          nuevo_user_foto is not None
                          and nuevo_user_foto.size > MAX_PESO_FOTO_MB * 1024 * 1024
                      ):
                          st.error(f"La foto supera los {MAX_PESO_FOTO_MB} MB.")
                      elif nuevo_user_name and nuevo_user_pass:
                          ruta_foto = guardar_foto_perfil(nuevo_user_name.strip(), nuevo_user_foto)
                          nuevo_u_row = pd.DataFrame([{
                              "ID": int(st.session_state.users_db["ID"].max() + 1) if not st.session_state.users_db.empty else 1,
                              "Usuario": nuevo_user_name.strip(),
                              "Contraseña": hash_password(nuevo_user_pass),
                              "Rol": nuevo_user_role,
                              "Foto": ruta_foto,
                              "Pregunta": nueva_pregunta if nueva_respuesta else "",
                              "Respuesta": hash_password(
                                  normalizar_respuesta_seguridad(nueva_respuesta)
                              ) if nueva_respuesta else "",
                              "Correo": nuevo_user_correo.strip(),
                          }])
                          st.session_state.users_db = pd.concat(
                              [st.session_state.users_db, nuevo_u_row], ignore_index=True
                          )
                          guardar_usuarios_db(st.session_state.users_db)
                          st.success(
                              f"¡Usuario '{nuevo_user_name}' creado con éxito con rol de"
                              f" {nuevo_user_role}!"
                          )
                          st.rerun()
                      else:
                          st.error("Por favor completa el usuario y la contraseña.")