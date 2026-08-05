import streamlit as st
from database import verify_user, register_user
from model import train_sarima, forecast_sarima, evaluate_model, generate_recommendation
from utils import (
    load_data, prepare_timeseries, plot_data, plot_forecast,
    plot_timeseries_plotly, plot_heatmap_plotly, plot_distribution_plotly,
    plot_product_ranking_plotly, get_inventory_data, generate_notifications
)

# ─────────────────────────────────────────────
# 1. Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Sulamina – Predictive Confectionery",
    page_icon="🍫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# 2. Load CSS Stylesheet
# ─────────────────────────────────────────────
try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception:
    pass

# ─────────────────────────────────────────────
# 3. Session State Initialization
# ─────────────────────────────────────────────
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ''
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'
if 'show_notifications' not in st.session_state:
    st.session_state.show_notifications = False
if 'forecast_steps' not in st.session_state:
    st.session_state.forecast_steps = 12


# ─────────────────────────────────────────────
# 4. Mandatory Login & Sign Up Gate (NoSQL Auth)
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    st.markdown("""
    <div class="login-screen-wrapper">
        <div class="login-header-icon">🍫</div>
        <div class="login-header-title">Sulamina Predictive Confectionery</div>
        <div class="login-header-subtitle">
            Akses dibatasi. Silakan login atau daftarkan Akun Google resmi Anda untuk melanjutkan ke platform analitik.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        tab_login, tab_signup = st.tabs(["🔑 LOGIN AKUN", "📝 DAFTAR AKUN BARU"])

        with tab_login:
            with st.form("login_form"):
                email_input = st.text_input("📧 Email Google", placeholder="nama@gmail.com")
                password_input = st.text_input("🔒 Password", type="password", placeholder="Masukkan password...")
                submit_login = st.form_submit_button("🚀 LOGIN SEKARANG", use_container_width=True)

                if submit_login:
                    if not email_input or not password_input:
                        st.error("⚠️ Email dan password harus diisi!")
                    else:
                        if verify_user(email_input, password_input):
                            st.session_state.logged_in = True
                            st.session_state.username = email_input.strip().lower()
                            st.success("✅ Login berhasil! Mengalihkan...")
                            st.rerun()
                        else:
                            st.error("❌ Email atau password salah! Silakan coba lagi.")

        with tab_signup:
            with st.form("signup_form"):
                st.caption("🌐 Hanya menerima Akun Google resmi (@gmail.com)")
                new_email = st.text_input("📧 Email Google Resmi", placeholder="contoh: akun@gmail.com")
                new_password = st.text_input("🔒 Buat Password", type="password", placeholder="Minimal 6 karakter...")
                confirm_password = st.text_input("🔒 Konfirmasi Password", type="password", placeholder="Ulangi password...")
                submit_signup = st.form_submit_button("✨ DAFTAR AKUN GOOGLE", use_container_width=True)

                if submit_signup:
                    if not new_email or not new_password or not confirm_password:
                        st.error("⚠️ Semua kolom pendaftaran harus diisi!")
                    elif new_password != confirm_password:
                        st.error("⚠️ Password dan Konfirmasi Password tidak cocok!")
                    else:
                        success, msg = register_user(new_email, new_password)
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")

    st.stop()


# ─────────────────────────────────────────────
# 5. Custom Top Toolbar (Substitution for Default Streamlit Toolbar)
# ─────────────────────────────────────────────
def nav_to(page_name):
    st.session_state.page = page_name

nav_pages = ['Dashboard', 'Analytics', 'Inventory']
current_page = st.session_state.page

tb_cols = st.columns([2.5, 1.8, 4.5, 2.5])

with tb_cols[0]:
    st.markdown('<div class="brand-text">🍫 Sulamina</div>', unsafe_allow_html=True)

with tb_cols[1]:
    if st.button("📂 Data Panel", key="btn_panel_toggle", help="Buka/Tutup Panel Upload Data"):
        st.components.v1.html("""
            <script>
                var btn = window.parent.document.querySelector('[data-testid="collapsedControl"] button') ||
                          window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"] button');
                if (btn) { btn.click(); }
            </script>
        """, height=0)

with tb_cols[2]:
    btn_cols = st.columns(len(nav_pages))
    for i, page in enumerate(nav_pages):
        with btn_cols[i]:
            btn_label = f"▸ {page}" if current_page == page else page
            st.button(btn_label, key=f"nav_{page}", on_click=nav_to, args=(page,), use_container_width=True)

with tb_cols[3]:
    icon_cols = st.columns([1, 2])
    with icon_cols[0]:
        if st.button("🔔", key="btn_notif", help="Notifikasi"):
            st.session_state.show_notifications = not st.session_state.show_notifications
    with icon_cols[1]:
        if st.button(f"🚪 Logout ({st.session_state.username.split('@')[0]})", key="btn_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ''
            st.rerun()

st.divider()


# ─────────────────────────────────────────────
# 6. Sidebar (Data Upload & Notifications)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand-wrapper">
        <div class="brand-sidebar">Sulamina</div>
        <div class="brand-subtext">Predictive Analytics</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.header("📂 Upload Data")
    files = st.file_uploader(
        "Pilih file CSV atau Excel (.xlsx)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True
    )

    if st.session_state.show_notifications:
        st.divider()
        st.subheader("🔔 Notifikasi")
        cached_df = st.session_state.get('cached_df_all', None)
        notifs = generate_notifications(df_all=cached_df)
        for n in notifs:
            st.markdown(f"""
            <div class="notif-card">
                <span class="notif-icon">{n['icon']}</span>
                <span class="notif-msg">{n['msg']}</span>
                <div class="notif-time">🕐 {n['time']}</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 7. Load & Process Data
# ─────────────────────────────────────────────
df_all = None
products = []
df = None
product = 'Semua Produk (Total)'

if files:
    df_all, products = load_data(files)
    st.session_state.cached_df_all = df_all

    if df_all is not None and len(df_all) > 0:
        with st.sidebar:
            st.divider()
            pilihan = ['Semua Produk (Total)'] + products
            product = st.selectbox("🏷️ Pilih Produk untuk Prediksi", pilihan)

        df = prepare_timeseries(df_all, product)
else:
    st.session_state.cached_df_all = None


# ═════════════════════════════════════════════
#  PAGE ROUTING
# ═════════════════════════════════════════════

# ─────────────────────────────────────────────
# PAGE 1: DASHBOARD
# ─────────────────────────────────────────────
if current_page == 'Dashboard':

    st.markdown("""
    <section class="hero-wrapper">
        <div class="hero-content">
            <h1 class="hero-title">
                Prediksi Penjualan<br/>Cokelat Sulamina
            </h1>
            <p class="hero-description">
                Manfaatkan kekuatan analitik prediktif. Platform analitik kami memperkirakan permintaan,
                mengoptimalkan inventaris, dan memvisualisasikan data rantai pasokan secara real-time
                untuk produksi confectionery premium.
            </p>
        </div>
        <div class="hero-card">
            <div class="hero-card-icon">🍫</div>
            <div class="hero-card-title">Sulamina</div>
            <div class="hero-card-subtitle">Predictive Confectionery</div>
            <hr class="hero-card-divider"/>
            <div class="hero-stat-container">
                <div>
                    <div class="hero-stat-num">STAT</div>
                    <div class="hero-stat-label">Model</div>
                </div>
                <div class="hero-stat-line"></div>
                <div>
                    <div class="hero-stat-num">SARIMA</div>
                    <div class="hero-stat-label">Engine</div>
                </div>
            </div>
        </div>
    </section>
    """, unsafe_allow_html=True)

    cta1, cta2, cta3 = st.columns([1, 1, 2])
    with cta1:
        if st.button("📊 Akses Dashboard Analytics", use_container_width=True):
            nav_to('Analytics')
            st.rerun()

    st.divider()

    if files and df is not None:
        tab1, tab2 = st.tabs(["📈 Analisis Data", "🔮 Prediksi SARIMA"])

        with tab1:
            st.subheader("📋 Data Bulanan")
            st.dataframe(df, use_container_width=True)
            st.divider()
            st.subheader("📈 Grafik Penjualan")
            plot_data(df, df_all, product)

        with tab2:
            if st.button("🚀 Hitung Prediksi Sekarang"):
                with st.spinner('Model sedang belajar pola data...'):
                    model_fit = train_sarima(df)
                    forecast = forecast_sarima(model_fit, df, steps=st.session_state.forecast_steps)
                    mae, rmse = evaluate_model(model_fit, df)

                    st.divider()
                    st.subheader("🎯 Hasil Forecast & Evaluasi Model")

                    m1, m2, m3 = st.columns(3)
                    m1.metric(
                        label="Prediksi Bulan Depan",
                        value=f"{forecast.iloc[0]:,.0f}",
                        help="Estimasi penjualan bulan pertama setelah data historis berakhir."
                    )
                    m2.metric(
                        label="Akurasi (MAE)",
                        value=f"{mae:,.0f}",
                        help="Mean Absolute Error: Semakin kecil, semakin akurat."
                    )
                    m3.metric(
                        label="Margin Error (RMSE)",
                        value=f"{rmse:,.0f}",
                        help="Root Mean Squared Error: Sensitif terhadap outlier."
                    )

                    with st.expander("📖 Apa arti dari angka-angka evaluasi di atas?"):
                        st.markdown(f"""
                        **1. Prediksi Jumlah Penjualan ({forecast.iloc[0]:,.0f})**
                        Proyeksi jumlah penjualan Cokelat Sulamina. Dihitung dari pola tren dan efek musiman.

                        **2. Akurasi / MAE ({mae:,.0f})**
                        Rata-rata "melesetnya" tebakan. Secara rata-rata, prediksi bisa meleset sebesar **{mae:,.0f}**.

                        **3. Margin Error / RMSE ({rmse:,.0f})**
                        Sama seperti MAE, namun memberi penalti lebih berat pada kesalahan ekstrem.
                        Jika RMSE ≈ MAE, maka model sangat **stabil**.
                        """)

                    st.divider()
                    st.subheader("📈 Visualisasi Forecast")
                    plot_forecast(df, forecast)

                    st.subheader("💡 Rekomendasi Pengambilan Keputusan")
                    recs = generate_recommendation(df, forecast)
                    for r in recs:
                        st.info(r)
    else:
        st.markdown("""
        <div class="empty-state-card">
            <div class="empty-icon">🍫</div>
            <div class="empty-title">Selamat Datang di Sulamina!</div>
            <div class="empty-text">
                Silakan <strong class="empty-highlight">upload data penjualan</strong> terlebih dahulu
                melalui panel sidebar di sebelah kiri untuk memulai analisis prediktif.
            </div>
            <div class="empty-badge-wrapper">
                <div class="empty-feature-badge">
                    <div class="empty-badge-icon">📁</div>
                    <div class="empty-badge-label">CSV / Excel</div>
                </div>
                <div class="empty-feature-badge">
                    <div class="empty-badge-icon">🤖</div>
                    <div class="empty-badge-label">SARIMA</div>
                </div>
                <div class="empty-feature-badge">
                    <div class="empty-badge-icon">📊</div>
                    <div class="empty-badge-label">Forecast</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE 2: ANALYTICS
# ─────────────────────────────────────────────
elif current_page == 'Analytics':
    st.markdown("""
    <h1 class="page-title">📊 Analytics Dashboard</h1>
    <p class="page-subtitle">
        Grafik interaktif — hover, zoom, dan pan untuk eksplorasi data mendalam.
    </p>
    """, unsafe_allow_html=True)

    if files and df is not None and df_all is not None:
        s1, s2, s3, s4 = st.columns(4)
        total_sales = df_all['penjualan'].sum()
        avg_monthly = df['penjualan'].mean()
        n_products = len(products)
        n_months = len(df)

        s1.metric("📦 Total Penjualan", f"{total_sales:,.0f}")
        s2.metric("📊 Rata-rata Bulanan", f"{avg_monthly:,.0f}")
        s3.metric("🏷️ Jumlah Produk", f"{n_products}")
        s4.metric("📅 Periode Data", f"{n_months} bulan")

        st.divider()

        atab1, atab2, atab3, atab4 = st.tabs([
            "📈 Time Series", "🗓️ Heatmap", "📊 Distribusi", "🏆 Ranking Produk"
        ])

        with atab1:
            plot_timeseries_plotly(df, df_all, product)
        with atab2:
            plot_heatmap_plotly(df_all, product)
        with atab3:
            plot_distribution_plotly(df)
        with atab4:
            plot_product_ranking_plotly(df_all)
    else:
        st.warning("📂 Upload data penjualan terlebih dahulu di sidebar untuk melihat analytics.")


# ─────────────────────────────────────────────
# PAGE 3: INVENTORY
# ─────────────────────────────────────────────
elif current_page == 'Inventory':
    st.markdown("""
    <h1 class="page-title">📦 Inventory Management</h1>
    <p class="page-subtitle">
        Monitor status stok dan dapatkan rekomendasi berdasarkan tren penjualan terkini.
    </p>
    """, unsafe_allow_html=True)

    if files and df_all is not None and len(products) > 0:
        inv_df = get_inventory_data(df_all, products)

        if len(inv_df) > 0:
            naik = len(inv_df[inv_df['Status'].str.contains('Naik')])
            stabil = len(inv_df[inv_df['Status'].str.contains('Stabil')])
            turun = len(inv_df[inv_df['Status'].str.contains('Turun')])

            c1, c2, c3 = st.columns(3)
            c1.metric("🟢 Tren Naik", f"{naik} produk")
            c2.metric("🟡 Stabil", f"{stabil} produk")
            c3.metric("🔴 Tren Turun", f"{turun} produk")

            st.divider()

            st.subheader("📋 Status Inventaris Per Produk")
            st.dataframe(inv_df, use_container_width=True)

            st.divider()

            critical = inv_df[inv_df['Status'].str.contains('Turun')]
            if len(critical) > 0:
                st.subheader("⚠️ Produk yang Perlu Perhatian")
                for _, row in critical.iterrows():
                    st.warning(f"**{row['Produk']}** — Tren {row['Tren (%)']} | Rekomendasi: {row['Rekomendasi Stok']}")

            rising = inv_df[inv_df['Status'].str.contains('Naik')]
            if len(rising) > 0:
                st.subheader("📈 Produk dengan Tren Positif")
                for _, row in rising.iterrows():
                    st.success(f"**{row['Produk']}** — Tren {row['Tren (%)']} | Rekomendasi: {row['Rekomendasi Stok']}")
        else:
            st.info("Data tidak mencukupi untuk analisis inventaris.")
    else:
        st.warning("📂 Upload data penjualan terlebih dahulu di sidebar.")


# ─────────────────────────────────────────────
# 8. Footer (All Logged-In Pages)
# ─────────────────────────────────────────────
st.markdown("""
<footer class="sulamina-footer">
    <div class="brand-text">Sulamina</div>
    <div class="footer-links-wrapper">
        <span class="footer-link">Privacy Policy</span>
        <span class="footer-link">Terms of Service</span>
        <span class="footer-link">Supply Chain Transparency</span>
        <span class="footer-link">Contact Support</span>
    </div>
    <div class="footer-copy">
        © 2024 Sulamina Predictive Confectionery. All rights reserved.
    </div>
</footer>
""", unsafe_allow_html=True)
