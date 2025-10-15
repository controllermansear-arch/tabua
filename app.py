import streamlit as st
import sqlite3
import re
import PyPDF2
import pandas as pd
import io
from datetime import datetime, time

st.set_page_config(page_title="🌊 Tábua de Maré", page_icon="🌊", layout="wide")

class TabuaMareConverter:
    def __init__(self, db_path="tabua_mare.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mare (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data DATE NOT NULL,
                hora TEXT NOT NULL,
                altura REAL NOT NULL,
                tipo TEXT CHECK(tipo IN ('BAIXA', 'ALTA')) NOT NULL,
                local TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def extract_text_from_pdf(self, pdf_file):
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            # Corrige hora colada
            text = re.sub(r'(\d{2})(\d{4})(?=\s*[-]?\d)', r'\1 \2', text)
            return text
        except Exception as e:
            st.error(f"Erro ao ler PDF: {e}")
            return None

    def parse_tide_data_dual_day_lines(self, text, year, local="Porto de Cabedelo"):
        months_pt = {
            'Janeiro': '01', 'Fevereiro': '02', 'Março': '03', 'Abril': '04',
            'Maio': '05', 'Junho': '06', 'Julho': '07', 'Agosto': '08',
            'Setembro': '09', 'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
        }
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        tide_data, buffer, current_month = [], [], None

        def flush_buffer():
            if buffer:
                block_text = " ".join(buffer)
                tide_data.extend(self._process_day_pair_block(block_text, current_month, year, local))
                buffer.clear()

        for line in lines:
            for m in months_pt.keys():
                if m in line:
                    current_month = m
                    break
            if not current_month:
                continue

            if re.match(r'^\s*(\d{1,2})\b', line):
                day = int(re.match(r'^\s*(\d{1,2})\b', line).group(1))
                if 1 <= day <= 16:
                    flush_buffer()
            buffer.append(line)
        flush_buffer()
        return tide_data

    def _process_day_pair_block(self, block_text, current_month, year, local):
        months_pt = {
            'Janeiro': '01', 'Fevereiro': '02', 'Março': '03', 'Abril': '04',
            'Maio': '05', 'Junho': '06', 'Julho': '07', 'Agosto': '08',
            'Setembro': '09', 'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
        }
        month_num = months_pt[current_month]
        tide_data = []

        # Detecta dois dias (1–16 e 17–31)
        match_days = re.findall(r'\b(\d{1,2})\b', block_text)
        if len(match_days) < 2:
            return []
        d1, d2 = match_days[0].zfill(2), None
        for d in match_days[1:]:
            if int(d) >= 17:
                d2 = d.zfill(2)
                break
        if not d2:
            return []

        # Divide por espaço grande entre colunas (duas ou mais)
        split_pos = re.search(rf'\b{int(d2)}\b', block_text)
        if not split_pos:
            return []
        left, right = block_text[:split_pos.start()], block_text[split_pos.start():]

        # Extrai pares hora-altura
        left_pairs = self.extract_tide_pairs_from_line(left)
        right_pairs = self.extract_tide_pairs_from_line(right)

        for h, a in left_pairs:
            e = self.create_tide_entry(f"{year}-{month_num}-{d1}", h, a, local)
            if e: tide_data.append(e)
        for h, a in right_pairs:
            e = self.create_tide_entry(f"{year}-{month_num}-{d2}", h, a, local)
            if e: tide_data.append(e)

        return tide_data

    def extract_tide_pairs_from_line(self, line):
        # Corrige espaçamentos e mantém sinais negativos
        line = re.sub(r'(\d{2})(\d{4})', r'\1 \2', line)
        pattern = r'(\d{3,4})\s*([-]?\d+[.,]?\d*)'
        matches = re.findall(pattern, line)
        pairs = []
        for h, a in matches:
            if self.is_valid_time(h):
                a = self.clean_altura(a)
                pairs.append((h, a))
        return pairs

    def clean_altura(self, altura_str):
        altura = altura_str.replace(',', '.')
        return re.sub(r'[^0-9.\-]', '', altura)

    def is_valid_time(self, t):
        if not t.isdigit(): return False
        if len(t) == 3: t = '0' + t
        h, m = int(t[:2]), int(t[2:])
        return 0 <= h <= 23 and 0 <= m <= 59

    def create_tide_entry(self, date, hora, altura, local):
        try:
            if len(hora) == 3: hora = '0' + hora
            hora_fmt = f"{hora[:2]}:{hora[2:]}"
            altura = float(altura)
            tipo = 'BAIXA' if altura < 1.0 else 'ALTA'
            return {'data': date, 'hora': hora_fmt, 'altura': altura, 'tipo': tipo, 'local': local}
        except:
            return None

    def save_to_database(self, dados):
        if not dados: return 0
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        for d in dados:
            try:
                cur.execute("INSERT INTO mare (data, hora, altura, tipo, local) VALUES (?, ?, ?, ?, ?)",
                            (d['data'], d['hora'], d['altura'], d['tipo'], d['local']))
            except: continue
        conn.commit(); c = cur.rowcount; conn.close(); return c

    def convert_pdf_to_db(self, pdf, local):
        st.info(f"📄 Processando {pdf.name}...")
        text = self.extract_text_from_pdf(pdf)
        if not text:
            st.error("Falha ao extrair texto."); return False, 0
        all_pairs = re.findall(r'(\d{3,4})\s*([-]?\d+[.,]?\d*)', text)
        tide = self.parse_tide_data_dual_day_lines(text, 2025, local)
        c = self.save_to_database(tide)
        st.success(f"✅ {c} registros salvos ({len(all_pairs)} detectados)")
        return True, c

    def get_filtered_data(self, data_inicio=None, data_fim=None, altura_min=None, altura_max=None,
                          hora_inicio=None, hora_fim=None):
        conn = sqlite3.connect(self.db_path)
        q, p = "SELECT * FROM mare WHERE 1=1", []
        if data_inicio: q += " AND data >= ?"; p.append(data_inicio)
        if data_fim: q += " AND data <= ?"; p.append(data_fim)
        if altura_min is not None: q += " AND altura >= ?"; p.append(altura_min)
        if altura_max is not None: q += " AND altura <= ?"; p.append(altura_max)
        if hora_inicio:
            q += " AND CAST(strftime('%H', hora)||strftime(':%M', hora) AS TIME) >= ?"; p.append(hora_inicio)
        if hora_fim:
            q += " AND CAST(strftime('%H', hora)||strftime(':%M', hora) AS TIME) <= ?"; p.append(hora_fim)
        q += " ORDER BY data, hora"
        df = pd.read_sql_query(q, conn, params=p)
        conn.close(); return df


# ==================== INTERFACE STREAMLIT ====================

def main():
    st.markdown("<h1 style='color:#b22222;'>🌊 Conversor e Filtro de Tábuas de Maré</h1>", unsafe_allow_html=True)

    if 'converter' not in st.session_state:
        st.session_state.converter = TabuaMareConverter()
    c = st.session_state.converter

    with st.sidebar:
        st.markdown("<h2 style='color:#b22222;'>📤 Upload de PDFs</h2>", unsafe_allow_html=True)
        files = st.file_uploader("Selecione os arquivos", type="pdf", accept_multiple_files=True)
        local = st.text_input("📍 Local", "Porto de Cabedelo - PB")
        if files and st.button("Processar PDFs", type="primary"):
            total = 0
            for f in files:
                ok, cnt = c.convert_pdf_to_db(f, local)
                if ok: total += cnt
            st.success(f"🎉 Total de {total} registros processados!")

    st.header("🔍 Filtros")
    col1, col2, col3 = st.columns(3)
    with col1:
        d1 = st.date_input("Data inicial")
        d2 = st.date_input("Data final")
    with col2:
        a_min = st.number_input("Altura mínima", value=None, step=0.1, format="%.2f")
        a_max = st.number_input("Altura máxima", value=None, step=0.1, format="%.2f")
    with col3:
        h1 = st.time_input("Horário inicial", time(7, 0))
        h2 = st.time_input("Horário final", time(14, 0))

    if st.button("🔍 Aplicar Filtros", type="primary"):
        df = c.get_filtered_data(
            d1.strftime("%Y-%m-%d") if d1 else None,
            d2.strftime("%Y-%m-%d") if d2 else None,
            a_min, a_max,
            h1.strftime("%H:%M"), h2.strftime("%H:%M")
        )
        if not df.empty:
            st.metric("Total", len(df))
            st.dataframe(df, use_container_width=True)
            st.line_chart(df.assign(data_hora=pd.to_datetime(df["data"] + " " + df["hora"]))
                          .set_index("data_hora")["altura"])
        else:
            st.warning("Nenhum registro encontrado.")

if __name__ == "__main__":
    main()
