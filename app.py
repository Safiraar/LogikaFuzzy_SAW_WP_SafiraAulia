import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import time

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Fuzzy MADM – SAW & WP", layout="wide")
st.title("Sistem Pendukung Keputusan – SAW & WP (Single File Version)")

# DATA AWAL (sesuai perhitungan manual Anda)
DEFAULT_DATA = pd.DataFrame({
    "kode":["A1","A2","A3","A4","A5"],
    "nama":["Bluehost","Dreamhost","Siteground","Inmotion","HostGator"],
    "C1":[2,2,4,1,2],
    "C2":[2,4,1,2,2],
    "C3":[1,2,1,4,1],
    "C4":[2,2,1,4,2],
    "C5":[4,4,4,4,4]
})

CRITERIA = {
    "C1":{"name":"Harga", "type":"cost",    "weight":0.30},
    "C2":{"name":"Website", "type":"benefit","weight":0.25},
    "C3":{"name":"Storage", "type":"benefit","weight":0.15},
    "C4":{"name":"Pengunjung", "type":"benefit","weight":0.20},
    "C5":{"name":"Domain", "type":"benefit","weight":0.10},
}

CRIT_KEYS = list(CRITERIA.keys())

# ---------------------------------------------------------
# Set session state
# ---------------------------------------------------------
if "df" not in st.session_state:
    st.session_state.df = DEFAULT_DATA.copy()

if "weights" not in st.session_state:
    st.session_state.weights = {c:CRITERIA[c]["weight"] for c in CRITERIA}

# ---------------------------------------------------------
# Sidebar Menu
# ---------------------------------------------------------
st.sidebar.header("Menu")
page = st.sidebar.radio("Pilih Halaman", 
    ["Home","Input Data","SAW","WP","Perbandingan","Tentang"])

# EDIT BOBOT DI SIDEBAR
st.sidebar.markdown("### Bobot Kriteria")

new_weights = {}
for c in CRITERIA:
    new_weights[c] = st.sidebar.slider(
        f"{c} – {CRITERIA[c]['name']}", 
        0.0, 1.0, st.session_state.weights[c], 0.01
    )

# Normalisasi bobot
total_w = sum(new_weights.values())
if total_w == 0:
    st.sidebar.error("Total bobot = 0, menggunakan bobot default.")
    st.session_state.weights = {c:CRITERIA[c]["weight"] for c in CRITERIA}
else:
    st.session_state.weights = {c:(new_weights[c]/total_w) for c in new_weights}


# ---------------------------------------------------------
# FUNGSI SAW
# ---------------------------------------------------------
def calc_saw(df, criteria):
    dfX = df[CRIT_KEYS].astype(float)
    norm = dfX.copy()

    # normalisasi
    for c in CRIT_KEYS:
        if criteria[c]["type"] == "benefit":
            norm[c] = dfX[c] / dfX[c].max()
        else: # cost
            norm[c] = dfX[c].min() / dfX[c]

    # bobot
    W = pd.Series(st.session_state.weights)

    weighted = norm * W

    score = weighted.sum(axis=1)
    rank = score.rank(ascending=False, method="min")

    result = pd.DataFrame({
        "kode": df["kode"],
        "nama": df["nama"],
        "score": score,
        "rank": rank
    })

    return dfX, norm, weighted, result


# ---------------------------------------------------------
# FUNGSI WP
# ---------------------------------------------------------
def calc_wp(df, criteria):
    dfX = df[CRIT_KEYS].astype(float)
    W = np.array([st.session_state.weights[c] for c in CRIT_KEYS])

    # exponent: cost → negative
    W_exp = W.copy()
    for i,c in enumerate(CRIT_KEYS):
        if criteria[c]["type"] == "cost":
            W_exp[i] *= -1

    # hitung S
    S = []
    for _, row in dfX.iterrows():
        val = np.prod(row.values ** W_exp)
        S.append(val)

    S = np.array(S)
    V = S / S.sum()

    result = pd.DataFrame({
        "kode": df["kode"],
        "nama": df["nama"],
        "S": S,
        "V": V,
        "rank": pd.Series(V).rank(ascending=False, method="min")
    })

    return dfX, W_exp, result


# ---------------------------------------------------------
# PAGE 1 – HOME
# ---------------------------------------------------------
if page == "Home":
    st.header("Informasi Sistem")
    st.write("""
    Sistem ini menggunakan metode **SAW** dan **Weighted Product (WP)**  
    untuk menentukan peringkat alternatif berdasarkan beberapa kriteria.
    """)

    st.subheader("Kriteria yang digunakan")
    crit_table = pd.DataFrame({
        c:[CRITERIA[c]["name"], CRITERIA[c]["type"], CRITERIA[c]["weight"]]
        for c in CRITERIA
    }, index=["Nama","Tipe","Bobot Default"])
    st.table(crit_table.T)

    st.subheader("Data Awal")
    st.dataframe(DEFAULT_DATA)


# ---------------------------------------------------------
# PAGE 2 – INPUT DATA
# ---------------------------------------------------------
elif page == "Input Data":
    st.header("Edit / Tambah Alternatif")
    st.info("Anda dapat menambah atau mengedit alternatif di tabel berikut.")

    edited = st.data_editor(st.session_state.df, num_rows="dynamic")
    st.session_state.df = edited

    st.download_button(
        "Download data (.csv)", 
        edited.to_csv(index=False).encode('utf-8'),
        file_name="data_alternatif.csv"
    )


# ---------------------------------------------------------
# PAGE 3 – SAW
# ---------------------------------------------------------
elif page == "SAW":
    st.header("Perhitungan Metode SAW")

    df = st.session_state.df.copy()

    with st.spinner("Menghitung SAW..."):
        time.sleep(0.3)
        raw, norm, weighted, result = calc_saw(df, CRITERIA)

    st.subheader("1. Matriks Awal (X)")
    st.dataframe(raw)

    st.subheader("2. Normalisasi")
    st.dataframe(norm.style.format("{:.6f}"))

    st.subheader("3. Perkalian Bobot")
    st.dataframe(weighted.style.format("{:.6f}"))

    st.subheader("4. Hasil SAW (Score & Rank)")
    st.dataframe(result.sort_values("rank"))

    buf = BytesIO()
    result.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button("Download Hasil SAW (.xlsx)", buf, "hasil_saw.xlsx")


# ---------------------------------------------------------
# PAGE 4 – WP
# ---------------------------------------------------------
elif page == "WP":
    st.header("Perhitungan Metode Weighted Product (WP)")

    df = st.session_state.df.copy()

    with st.spinner("Menghitung WP..."):
        time.sleep(0.3)
        raw, W_exp, result = calc_wp(df, CRITERIA)

    st.subheader("1. Matriks Awal (X)")
    st.dataframe(raw)

    st.subheader("2. Bobot Berpangkat (cost → negatif)")
    Wexp_df = pd.DataFrame([W_exp], columns=CRIT_KEYS)
    st.dataframe(Wexp_df)

    st.subheader("3. Hasil WP (S, V, Rank)")
    st.dataframe(result.sort_values("rank"))

    buf = BytesIO()
    result.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button("Download Hasil WP (.xlsx)", buf, "hasil_wp.xlsx")


# ---------------------------------------------------------
# PAGE 5 – PERBANDINGAN
# ---------------------------------------------------------
elif page == "Perbandingan":
    st.header("Perbandingan SAW vs WP")

    df = st.session_state.df.copy()

    raw_saw, norm, weighted, res_saw = calc_saw(df, CRITERIA)
    raw_wp, Wexp, res_wp = calc_wp(df, CRITERIA)

    comp = pd.DataFrame({
        "Alternatif": df["nama"],
        "SAW Score": res_saw["score"].values,
        "WP Score": res_wp["V"].values,
    })

    st.dataframe(comp)

    top_saw = res_saw.loc[res_saw["rank"].idxmin(), "nama"]
    top_wp = res_wp.loc[res_wp["rank"].idxmin(), "nama"]

    st.subheader("Kesimpulan")

    if top_saw == top_wp:
        st.success(f"Kedua metode memilih **{top_saw}** sebagai alternatif terbaik.")
    else:
        st.info(f"SAW memilih **{top_saw}**, sedangkan WP memilih **{top_wp}**.")


# ---------------------------------------------------------
# PAGE 6 – TENTANG
# ---------------------------------------------------------
elif page == "Tentang":
    st.header("Tentang Sistem")
    st.write("""
    Sistem ini dibangun menggunakan:
    - **Metode SAW (Simple Additive Weighting)**
    - **Metode WP (Weighted Product)**
    - **Streamlit** sebagai antarmuka interaktif.
    """)

