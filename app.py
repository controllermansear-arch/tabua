import streamlit as st
import pandas as pd
import json
from datetime import datetime, time
import os

st.set_page_config(page_title="🌊 Conversor de Tábuas de Maré", page_icon="🌊", layout="wide")

JSON_PATH = "tabua.json"
LOCAL_PADRAO = "Porto de Cabedelo - PB"

@st.cache_data
def carregar_tabua_completa():
    if not os.path.exists(JSON_PATH):
        st.error(f"❌ Arquivo '{JSON_PATH}' não encontrado.")
        return pd.DataFrame()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try:
            json_data = json.load(f)
        except Exception as e:
            st.error(f"Erro ao ler JSON: {e}")
            return pd.DataFrame()

    registros = []
    for item in json_data:
        ano = item.get("ano")
        dia_str = item.get("dia", "").strip()
        try:
            dia, mes = dia_str.split("/")
            data_formatada = f"{ano}-{int(mes):02d}-{int(dia):02d}"
        except Exception:
            continue

        for mare in item.get("marés", []):
            hora = mare.get("hora")
            altura = mare.get("altura_m")

            if not hora or altura is None:
                continue

            try:
                altura_float = float(altura)
            except:
                continue

            tipo = "ALTA" if altura_float >= 1.0 else "BAIXA"
            registros.append({
                "data": data_formatada,
                "hora": hora,
                "altura": altura_float,
                "tipo": tipo,
                "local": LOCAL_PADRAO
            })

    df = pd.DataFrame(registros)
    if not df.empty:
        df["data_hora"] = pd.to_datetime(df["data"] + " " + df["hora"], errors="coerce")
        df = df.sort_values("data_hora").reset_index(drop=True)
        df["dia_semana"] = df["data_hora"].dt.strftime("%A")
        traduz = {
            "Monday": "Segunda", "Tuesday": "Terça", "Wednesday": "Quarta",
            "Thursday": "Quinta", "Friday": "Sexta", "Saturday": "Sábado", "Sunday": "Domingo"
        }
        df["dia_semana"] = df["dia_semana"].map(traduz).fillna(df["dia_semana"])
    return df

def main():
    st.sidebar.markdown("<h1 style='color:#b22222;'>🌊 Conversor de Tábuas de Maré</h1>", unsafe_allow_html=True)
    st.sidebar.write("---")

    df = carregar_tabua_completa()

    if df.empty:
        st.warning("Nenhum dado encontrado no JSON.")
        return

    st.header("🔍 Filtros e Visualização")

    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input("Data inicial", value=None)
        data_fim = st.date_input("Data final", value=None)
    with col2:
        altura_min = st.number_input("Altura mínima (m)", value=-2.0, step=0.01, format="%.2f")
        altura_max = st.number_input("Altura máxima (m)", value=0.7, step=0.01, format="%.2f")
    with col3:
        hora_inicio = st.time_input("Horário inicial", value=time(7, 0))
        hora_fim = st.time_input("Horário final", value=time(14, 0))

    st.markdown("---")

    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    dias_selecionados = st.multiselect("🗓️ Selecione os dias da semana", options=dias_semana)

    df_filtrado = df.copy()

    if data_inicio:
        df_filtrado = df_filtrado[df_filtrado["data"] >= data_inicio.strftime("%Y-%m-%d")]
    if data_fim:
        df_filtrado = df_filtrado[df_filtrado["data"] <= data_fim.strftime("%Y-%m-%d")]
    if altura_min is not None:
        df_filtrado = df_filtrado[df_filtrado["altura"] >= altura_min]
    if altura_max is not None:
        df_filtrado = df_filtrado[df_filtrado["altura"] <= altura_max]
    if hora_inicio and hora_fim:
        df_filtrado = df_filtrado[
            (df_filtrado["hora"] >= hora_inicio.strftime("%H:%M")) &
            (df_filtrado["hora"] <= hora_fim.strftime("%H:%M"))
        ]
    if dias_selecionados:
        df_filtrado = df_filtrado[df_filtrado["dia_semana"].isin(dias_selecionados)]

    st.markdown("---")

    if df_filtrado.empty:
        st.warning("⚠️ Nenhum registro encontrado com os filtros aplicados.")
    else:
        st.success(f"✅ {len(df_filtrado)} registros encontrados")
        st.dataframe(df_filtrado, width='stretch')

        st.subheader("📈 Gráfico das Alturas das Marés")
        chart_df = df_filtrado.set_index("data_hora")[["altura"]]
        st.line_chart(chart_df)

        anos_csv = sorted(set(pd.to_datetime(df_filtrado["data"]).dt.year))
        nome_csv = f"mare_{'-'.join(map(str, anos_csv))}.csv"
        csv = df_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Baixar CSV", csv, nome_csv, "text/csv")

if __name__ == "__main__":
    main()