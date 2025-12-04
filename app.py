import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# ==============================================
# CONFIGURASI AWAL
# ==============================================

st.set_page_config(page_title="Sistem Keputusan Fuzzy SAW & WP", layout="wide")
st.title("Sistem Keputusan – Fuzzy + SAW & WP")

# ==============================================
# DATA AWAL (Diambil dari PDF Penghitungan Manual)
# ==============================================

@st.cache_data
def load_default_data():
    df = pd.DataFrame({
        "kode": ["A1","A2","A3","A4","A5"],
        "nama": ["Bluehost","Dreamhost","Siteground","Inmotion","HostGator"],
        "C1": [2,2,4,1,2],   # Harga
        "C2": [2,4,1,2,2],   # Website
        "C3": [1,2,1,4,1],   # Storage
        "C4": [2,2,1,4,2],   # Pengunjung
        "C5": [4,4,4,4,4],   # Domain
    })
    return df

CRITERIA = {
    "C1": {"name": "Harga",       "type": "cost",    "weight": 0.30},
    "C2": {"name": "Website",     "type": "benefit", "weight": 0.25},
    "C3": {"name": "Storage",     "type": "benefit", "weight": 0.15},
    "C4": {"name": "Pengunjung",  "type": "benefit", "weight": 0.20},
    "C5": {"name": "Domain",      "type": "benefit", "weight": 0.10},
}

CRIT_KEYS = list(CRITERIA.keys())

# ==============================================
# SESSION STATE
# ==============================================

if "df" not in st.session_state:
    st.session_state.df = load_default_data().copy()

if "weights" not in st.session_state:
    st.session_state.weights = {c: CRITERIA[c]["weight"] for c in CRITERIA}

if "last_results" not in st.session_state:
    st.session_state.last_results = None


# ==============================================
# FUZZY (TRIANGULAR FUZZY + CENTROID)
# ==============================================

TFN = {
    1: (0, 0, 1),
    2: (0, 1, 2),
    3: (1, 2, 3),
    4: (2, 3, 4),
    5: (3, 4, 4),
}

def fuzzify_value(v):
    v = int(v)
    return TFN[v]

def fuzzify_dataframe(df):
    cols = CRIT_KEYS
    fuzzy_parts = []
    for c in cols:
        fuzzy_col = df[c].apply(lambda x: fuzzify_value(x))
        fuzzy_df = pd.DataFrame(fuzzy_col.tolist(), columns=[f"{c}_l", f"{c}_m", f"{c}_u"])
        fuzzy_parts.append(fuzzy_df)
    return pd.concat(fuzzy_parts, axis=1)

def defuzzify(fuzzy_df):
    vals = {}
    for c in CRIT_KEYS:
        l = fuzzy_df[f"{c}_l"]
        m = fuzzy_df[f"{c}_m"]
        u = fuzzy_df[f"{c}_u"]
        centroid = (l + m + u) / 3.0
        vals[c] = centroid
    return pd.DataFrame(vals)


# ==============================================
# SAW CALC
# ==============================================

def saw_normalize(X):
    norm = X.copy().astype(float)
    maxv = X.max()
    minv = X.min()

    for c in CRIT_KEYS:
        if CRITERIA[c]["type"] == "benefit":
            norm[c] = X[c] / maxv[c]
        else:
            norm[c] = minv[c] / X[c]

    return norm

def saw_full(X, weights):
    norm = saw_normalize(X)
    w = pd.Series(weights)
    weighted = norm * w
    score = weighted.sum(axis=1)
    rank = score.rank(ascending=False, method="min").astype(int)

    result = pd.DataFrame({"score": score, "rank": rank})
    return {
        "normalized": norm,
        "weighted": weighted,
        "result": result
    }


# ==============================================
# WP CALC
# ==============================================

def wp_full(X, weights):
    w = pd.Series(weights)
    exp = w.copy()

    for c in CRIT_KEYS:
        if CRITERIA[c]["type"] == "cost":
            exp[c] = -abs(w[c])

    eps = 1e-9
    X_safe = X.clip(lower=eps)
    S = X_safe.pow(exp).prod(axis=1)
    V = S / S.sum()
    rank = V.rank(ascending=False, method="min").astype(int)

    result = pd.DataFrame({"S": S, "V": V, "rank": rank})
    return {"exp": exp, "result": result}


# ==============================================
# SIDEBAR NAVIGATION
# ==============================================

st.sidebar.header("Menu")
page = st.sidebar.radio("Pilih halaman", [
    "Home", "Perhitungan", "SAW", "WP", "Pembanding", "Tentang"
])

use_fuzzy = st.sidebar.checkbox("Gunakan Fuzzy", value=False)



# ==============================================
# PAGE: HOME
# ==============================================

if page == "Home":
    st.header("Home – Informasi Sistem")
    st.write("Aplikasi mendukung Fuzzy → SAW → WP → Pembanding")

    st.subheader("Data Awal Alternatif")
    st.dataframe(st.session_state.df)

    st.subheader("Kriteria & Bobot Default")
    st.table(pd.DataFrame({
        c: {"Nama": CRITERIA[c]["name"],
            "Tipe": CRITERIA[c]["type"],
            "Bobot": CRITERIA[c]["weight"]}
    }).T)


# ==============================================
# PAGE: PERHITUNGAN (EDIT DATA + RUN)
# ==============================================

elif page == "Perhitungan":
    st.header("Perhitungan – Edit Data & Jalankan")

    st.write("Ubah nilai alternatif:")
    edited = st.experimental_data_editor(st.session_state.df, num_rows="dynamic")
    st.session_state.df = edited

    # EDIT BOBOT
    st.subheader("Edit Bobot Kriteria")
    new_weights = {}
    for c in CRITERIA:
        new_weights[c] = st.number_input(
            f"{c} - {CRITERIA[c]['name']}",
            0.0, 1.0,
            st.session_state.weights[c]
        )

    if st.button("Simpan Bobot"):
        s = sum(new_weights.values())
        st.session_state.weights = {k: v/s for k,v in new_weights.items()}
        st.success("Bobot berhasil dinormalisasi & disimpan!")

    if st.button("Hitung SAW & WP"):
        df_used = st.session_state.df.copy()

        # FUZZY?
        if use_fuzzy:
            fuzzy_df = fuzzify_dataframe(df_used)
            df_defuzz = defuzzify(fuzzy_df)
            for c in CRIT_KEYS:
                df_used[c] = df_defuzz[c]

        saw_res = saw_full(df_used[CRIT_KEYS], st.session_state.weights)
        wp_res = wp_full(df_used[CRIT_KEYS], st.session_state.weights)

        st.session_state.last_results = {
            "df_used": df_used.copy(),
            "saw": saw_res,
            "wp": wp_res
        }

        st.success("Perhitungan selesai! Lihat menu SAW, WP atau Pembanding.")


# ==============================================
# PAGE: SAW DETAIL
# ==============================================

elif page == "SAW":
    if not st.session_state.last_results:
        st.warning("Belum ada hasil. Jalankan Perhitungan dulu.")
    else:
        st.header("Detail Perhitungan SAW")
        saw = st.session_state.last_results["saw"]
        df_used = st.session_state.last_results["df_used"]

        st.subheader("Normalisasi")
        st.dataframe(saw["normalized"].style.format("{:.6f}"))

        st.subheader("Bobot × Normalisasi")
        st.dataframe(saw["weighted"].style.format("{:.6f}"))

        st.subheader("Skor & Ranking")
        st.dataframe(saw["result"].sort_values("rank"))


# ==============================================
# PAGE: WP DETAIL
# ==============================================

elif page == "WP":
    if not st.session_state.last_results:
        st.warning("Belum ada hasil. Jalankan Perhitungan dulu.")
    else:
        st.header("Detail Perhitungan WP")
        wp = st.session_state.last_results["wp"]
        df_used = st.session_state.last_results["df_used"]

        st.subheader("Bobot Berpangkat")
        st.dataframe(wp["exp"].to_frame("exponent"))

        st.subheader("S, V, Rank")
        st.dataframe(wp["result"].sort_values("rank"))


# ==============================================
# PAGE: PEMBANDING
# ==============================================

elif page == "Pembanding":
    if not st.session_state.last_results:
        st.warning("Belum ada hasil!")
    else:
        st.header("Pembanding SAW vs WP")

        saw = st.session_state.last_results["saw"]["result"]
        wp = st.session_state.last_results["wp"]["result"]
        df_used = st.session_state.last_results["df_used"]

        comp = pd.DataFrame({
            "nama": df_used["nama"],
            "score_saw": saw["score"].values,
            "rank_saw": saw["rank"].values,
            "score_wp": wp["V"].values,
            "rank_wp": wp["rank"].values,
        })

        st.dataframe(comp)

        best_saw = comp.loc[comp["rank_saw"].idxmin(), "nama"]
        best_wp = comp.loc[comp["rank_wp"].idxmin(), "nama"]

        if best_saw == best_wp:
            st.success(f"Kedua metode sepakat: **{best_saw}**")
        else:
            st.error(f"Metode berbeda → SAW memilih **{best_saw}**, WP memilih **{best_wp}**")


# ==============================================
# PAGE: TENTANG
# ==============================================

elif page == "Tentang":
    st.header("Tentang Sistem")
    st.write("""
        Sistem keputusan ini menggabungkan:
        - Logika Fuzzy (Triangular → Centroid)
        - SAW (Simple Additive Weighting)
        - WP (Weighted Product)

        Semua perhitungan dapat ditampilkan lengkap:
        - Normalisasi SAW
        - Weighted Matrix
        - Ranking
        - Exponent WP
        - Skor S & V
        - Pembandingan hasil SAW & WP
    """)

