import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import re


def load_data(files):
    """
    Membaca dan menggabungkan file penjualan Sulamina.
    Mendukung:
      - .xlsx / .xls : Membaca SEMUA sheet. Tahun diambil dari nama sheet (misal 'Tahun 2022').
      - .csv          : Tahun diambil dari nama file (misal '... Tahun 2022.csv').
    Setiap sheet/CSV harus memiliki 2 baris judul di atas (skiprows=2).
    Return: (df_gabungan, list_produk) atau (None, []) jika gagal.
    """
    all_dfs = []

    for file in files:
        try:
            nama = file.name.lower()

            if nama.endswith(('.xlsx', '.xls')):
                # --- FILE EXCEL: baca semua sheet ---
                xl = pd.ExcelFile(file)
                for sheet_name in xl.sheet_names:
                    match = re.search(r'(\d{4})', sheet_name)
                    if not match:
                        st.warning(f"⚠️ Tahun tidak terdeteksi dari sheet '{sheet_name}', di-skip.")
                        continue
                    tahun = int(match.group(1))
                    df = pd.read_excel(xl, sheet_name, skiprows=2)
                    result = _process_sheet(df, tahun)
                    if result is not None:
                        all_dfs.append(result)

            elif nama.endswith('.csv'):
                # --- FILE CSV: tahun dari nama file ---
                match = re.search(r'(\d{4})', file.name)
                if not match:
                    st.warning(f"⚠️ Tahun tidak terdeteksi dari: {file.name}, file di-skip.")
                    continue
                tahun = int(match.group(1))

                df = pd.read_csv(file, skiprows=2)
                # Fallback: jika semua data masuk 1 kolom (separator bukan koma)
                if len(df.columns) <= 2:
                    file.seek(0)
                    df = pd.read_csv(file, skiprows=2, sep=';')

                result = _process_sheet(df, tahun)
                if result is not None:
                    all_dfs.append(result)
            else:
                st.warning(f"⚠️ Format file tidak didukung: {file.name}")

        except Exception as e:
            st.error(f"❌ Gagal membaca {file.name}: {e}")

    if not all_dfs:
        return None, []

    df_all = pd.concat(all_dfs, ignore_index=True)
    products = sorted(df_all['Nama Barang'].unique().tolist())

    return df_all, products


def _process_sheet(df, tahun):
    """
    Memproses satu sheet/CSV: bersihkan, melt wide→long, buat tanggal.
    Return DataFrame atau None jika gagal.
    """
    bulan_map = {
        'Januari': 1, 'Februari': 2, 'Maret': 3, 'April': 4,
        'Mei': 5, 'Juni': 6, 'Juli': 7, 'Agustus': 8,
        'September': 9, 'Oktober': 10, 'November': 11, 'Desember': 12
    }

    # Bersihkan spasi di nama kolom
    df.columns = df.columns.str.strip()

    # Kolom pertama = nama produk
    nama_col = df.columns[0]

    # Buang baris kosong & baris TOTAL KESELURUHAN
    df = df[df[nama_col].notna()]
    df = df[~df[nama_col].astype(str).str.upper().str.contains('TOTAL')]

    # Buang kolom 'Total Tahunan' (atau kolom apapun bertuliskan 'total')
    total_cols = [c for c in df.columns if 'total' in c.lower()]
    df = df.drop(columns=total_cols, errors='ignore')

    # Deteksi kolom bulan yang ada di file
    bulan_cols = [c for c in df.columns if c in bulan_map]
    if not bulan_cols:
        return None

    # Melt: ubah dari wide (bulan sebagai kolom) → long (bulan sebagai baris)
    df_long = df.melt(
        id_vars=[nama_col],
        value_vars=bulan_cols,
        var_name='Bulan',
        value_name='penjualan'
    )

    # Buat kolom tanggal dari tahun + bulan
    df_long['bulan_num'] = df_long['Bulan'].map(bulan_map)
    df_long['tanggal'] = pd.to_datetime(
        df_long['bulan_num'].apply(lambda m: f"{tahun}-{m:02d}-01")
    )
    df_long['Tahun'] = tahun
    df_long = df_long.rename(columns={nama_col: 'Nama Barang'})

    # Pastikan penjualan numerik
    df_long['penjualan'] = pd.to_numeric(df_long['penjualan'], errors='coerce')
    df_long = df_long.dropna(subset=['penjualan'])

    return df_long[['tanggal', 'Tahun', 'Nama Barang', 'Bulan', 'penjualan']]


def prepare_timeseries(df_all, product='Semua Produk (Total)'):
    """
    Mengagregasi data gabungan menjadi time-series bulanan
    yang siap dipakai oleh model SARIMA.
    Output: DataFrame dengan DatetimeIndex (freq='MS') dan kolom 'penjualan'.
    """
    if product == 'Semua Produk (Total)':
        df_ts = df_all.groupby('tanggal')['penjualan'].sum()
    else:
        df_ts = df_all[df_all['Nama Barang'] == product].groupby('tanggal')['penjualan'].sum()

    df_ts = df_ts.sort_index().to_frame()
    df_ts.index.freq = 'MS'

    return df_ts

def plot_data(df, df_all=None, product='Semua Produk (Total)'):
    """
    Menampilkan 3 grafik analisis penjualan:
    1. Time-series keseluruhan (garis per tahun beda warna)
    2. Perbandingan pola bulanan antar tahun (overlay)
    3. Total penjualan tahunan (bar chart)
    
    Parameter:
    - df      : DataFrame time-series (DatetimeIndex + kolom 'penjualan') untuk grafik utama
    - df_all  : DataFrame gabungan mentah (opsional, untuk grafik per-tahun)
    - product : Nama produk yang dipilih
    """
    import numpy as np

    # Palet warna untuk tiap tahun
    year_colors = ['#c084fc', '#38bdf8', '#34d399', '#fbbf24', '#fb7185',
                   '#a78bfa', '#22d3ee', '#4ade80', '#f59e0b', '#f43f5e']

    bulan_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                    'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']

    # --- Siapkan data per tahun ---
    if df_all is not None:
        if product == 'Semua Produk (Total)':
            df_yearly = df_all.groupby(['Tahun', 'tanggal'])['penjualan'].sum().reset_index()
        else:
            df_yearly = df_all[df_all['Nama Barang'] == product] \
                .groupby(['Tahun', 'tanggal'])['penjualan'].sum().reset_index()
        tahun_list = sorted(df_yearly['Tahun'].unique())
    else:
        df_yearly = None
        tahun_list = sorted(df.index.year.unique())

    # =============================================
    # GRAFIK 1: Time-Series Keseluruhan (per tahun beda warna)
    # =============================================
    fig1, ax1 = plt.subplots(figsize=(12, 4.5), facecolor='#1e293b')
    ax1.set_facecolor('#1e293b')

    if df_yearly is not None:
        for i, tahun in enumerate(tahun_list):
            data_tahun = df_yearly[df_yearly['Tahun'] == tahun].sort_values('tanggal')
            color = year_colors[i % len(year_colors)]
            ax1.plot(data_tahun['tanggal'], data_tahun['penjualan'],
                     color=color, marker='o', linewidth=2, markersize=5,
                     label=str(tahun))
    else:
        ax1.plot(df.index, df['penjualan'], color='#c084fc', marker='o', linewidth=2)

    ax1.set_title("📈 Data Penjualan Historis (Per Tahun)", color='white', fontsize=14, fontweight='bold', pad=12)
    ax1.set_xlabel("Tanggal", color='#94a3b8', fontsize=10)
    ax1.set_ylabel("Jumlah Penjualan", color='#94a3b8', fontsize=10)
    ax1.tick_params(colors='#cbd5e1', labelsize=9)
    ax1.grid(axis='y', color='#334155', linewidth=0.5, alpha=0.7)
    ax1.legend(facecolor='#334155', edgecolor='#475569', labelcolor='white', fontsize=9)

    for spine in ax1.spines.values():
        spine.set_color('#334155')

    fig1.tight_layout()
    st.pyplot(fig1)

    # =============================================
    # GRAFIK 2: Perbandingan Pola Bulanan Antar Tahun (Overlay)
    # =============================================
    if df_yearly is not None and len(tahun_list) > 1:
        fig2, ax2 = plt.subplots(figsize=(12, 4.5), facecolor='#1e293b')
        ax2.set_facecolor('#1e293b')

        for i, tahun in enumerate(tahun_list):
            data_tahun = df_yearly[df_yearly['Tahun'] == tahun].sort_values('tanggal')
            data_tahun = data_tahun.copy()
            data_tahun['bulan_num'] = data_tahun['tanggal'].dt.month
            data_bulan = data_tahun.groupby('bulan_num')['penjualan'].sum().reindex(range(1, 13))

            color = year_colors[i % len(year_colors)]
            ax2.plot(range(1, 13), data_bulan.values,
                     color=color, marker='s', linewidth=2.5, markersize=6,
                     label=str(tahun), alpha=0.9)

        ax2.set_xticks(range(1, 13))
        ax2.set_xticklabels(bulan_labels)
        ax2.set_title("📊 Perbandingan Pola Bulanan Antar Tahun", color='white', fontsize=14, fontweight='bold', pad=12)
        ax2.set_xlabel("Bulan", color='#94a3b8', fontsize=10)
        ax2.set_ylabel("Jumlah Penjualan", color='#94a3b8', fontsize=10)
        ax2.tick_params(colors='#cbd5e1', labelsize=9)
        ax2.grid(axis='y', color='#334155', linewidth=0.5, alpha=0.7)
        ax2.legend(facecolor='#334155', edgecolor='#475569', labelcolor='white', fontsize=9)

        for spine in ax2.spines.values():
            spine.set_color('#334155')

        fig2.tight_layout()
        st.pyplot(fig2)

    # =============================================
    # GRAFIK 3: Total Penjualan Tahunan (Bar Chart)
    # =============================================
    if df_yearly is not None:
        fig3, ax3 = plt.subplots(figsize=(8, 4), facecolor='#1e293b')
        ax3.set_facecolor('#1e293b')

        total_per_tahun = df_yearly.groupby('Tahun')['penjualan'].sum()
        bars = ax3.bar(
            [str(t) for t in total_per_tahun.index],
            total_per_tahun.values,
            color=[year_colors[i % len(year_colors)] for i in range(len(total_per_tahun))],
            edgecolor='#1e293b', linewidth=1.5, width=0.6
        )

        # Tambah label angka di atas bar
        for bar, val in zip(bars, total_per_tahun.values):
            ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(total_per_tahun.values) * 0.01,
                     f'{val:,.0f}', ha='center', va='bottom', color='white', fontsize=10, fontweight='bold')

        ax3.set_title("📦 Total Penjualan Per Tahun", color='white', fontsize=14, fontweight='bold', pad=12)
        ax3.set_xlabel("Tahun", color='#94a3b8', fontsize=10)
        ax3.set_ylabel("Total Penjualan", color='#94a3b8', fontsize=10)
        ax3.tick_params(colors='#cbd5e1', labelsize=10)
        ax3.grid(axis='y', color='#334155', linewidth=0.5, alpha=0.7)

        for spine in ax3.spines.values():
            spine.set_color('#334155')

        fig3.tight_layout()
        st.pyplot(fig3)

def plot_forecast(df, forecast):
    fig, ax = plt.subplots(figsize=(10, 4), facecolor='#1e293b')
    ax.set_facecolor('#1e293b')
    ax.plot(df.index, df['penjualan'], color='white', label="Data Asli", marker='o')
    ax.plot(forecast.index, forecast, color='#7c3aed', linestyle='--', label="Prediksi", marker='s')
    ax.tick_params(colors='white')
    ax.legend()
    st.pyplot(fig)


# =============================================
# PLOTLY INTERACTIVE CHARTS
# =============================================
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# -- Shared Plotly theme colors --
_PLOTLY_BG = '#1c1110'
_PLOTLY_PAPER = '#1c1110'
_PLOTLY_GRID = 'rgba(80,68,66,0.4)'
_PLOTLY_TEXT = '#d3c3c0'
_PLOTLY_GOLD = '#ffba38'
_PLOTLY_PALETTE = ['#ffba38', '#e3beb8', '#e5beb5', '#ffd799', '#feb300',
                   '#c084fc', '#38bdf8', '#34d399', '#fb7185', '#a78bfa']

def _plotly_layout(fig, title='', xaxis_title='', yaxis_title='', height=420):
    """Apply consistent Sulamina dark theme to any Plotly figure."""
    fig.update_layout(
        title=dict(text=title, font=dict(family='Montserrat', size=16, color=_PLOTLY_GOLD)),
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        height=height,
        plot_bgcolor=_PLOTLY_BG,
        paper_bgcolor=_PLOTLY_PAPER,
        font=dict(family='Inter', color=_PLOTLY_TEXT, size=12),
        xaxis=dict(gridcolor=_PLOTLY_GRID, zerolinecolor=_PLOTLY_GRID),
        yaxis=dict(gridcolor=_PLOTLY_GRID, zerolinecolor=_PLOTLY_GRID),
        legend=dict(bgcolor='rgba(62,39,35,0.6)', bordercolor='rgba(255,215,153,0.2)',
                    font=dict(color=_PLOTLY_TEXT)),
        margin=dict(l=40, r=20, t=50, b=40),
        hovermode='x unified',
    )
    return fig


def plot_timeseries_plotly(df, df_all=None, product='Semua Produk (Total)'):
    """Interactive time-series line chart with Plotly."""
    bulan_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                    'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']

    if df_all is not None:
        if product == 'Semua Produk (Total)':
            df_yearly = df_all.groupby(['Tahun', 'tanggal'])['penjualan'].sum().reset_index()
        else:
            df_yearly = df_all[df_all['Nama Barang'] == product] \
                .groupby(['Tahun', 'tanggal'])['penjualan'].sum().reset_index()
        tahun_list = sorted(df_yearly['Tahun'].unique())
    else:
        df_yearly = None
        tahun_list = sorted(df.index.year.unique())

    # --- Chart 1: Historical time-series ---
    fig1 = go.Figure()
    if df_yearly is not None:
        for i, tahun in enumerate(tahun_list):
            data_tahun = df_yearly[df_yearly['Tahun'] == tahun].sort_values('tanggal')
            fig1.add_trace(go.Scatter(
                x=data_tahun['tanggal'], y=data_tahun['penjualan'],
                mode='lines+markers', name=str(tahun),
                line=dict(color=_PLOTLY_PALETTE[i % len(_PLOTLY_PALETTE)], width=2.5),
                marker=dict(size=6),
                hovertemplate='%{x|%b %Y}<br>Penjualan: %{y:,.0f}<extra>' + str(tahun) + '</extra>'
            ))
    else:
        fig1.add_trace(go.Scatter(
            x=df.index, y=df['penjualan'],
            mode='lines+markers', name='Penjualan',
            line=dict(color=_PLOTLY_GOLD, width=2.5),
            hovertemplate='%{x|%b %Y}<br>Penjualan: %{y:,.0f}<extra></extra>'
        ))
    _plotly_layout(fig1, '📈 Data Penjualan Historis (Per Tahun)', 'Tanggal', 'Jumlah Penjualan')
    st.plotly_chart(fig1, use_container_width=True)

    # --- Chart 2: Monthly pattern overlay ---
    if df_yearly is not None and len(tahun_list) > 1:
        fig2 = go.Figure()
        for i, tahun in enumerate(tahun_list):
            data_tahun = df_yearly[df_yearly['Tahun'] == tahun].sort_values('tanggal').copy()
            data_tahun['bulan_num'] = data_tahun['tanggal'].dt.month
            data_bulan = data_tahun.groupby('bulan_num')['penjualan'].sum().reindex(range(1, 13))
            fig2.add_trace(go.Scatter(
                x=bulan_labels, y=data_bulan.values,
                mode='lines+markers', name=str(tahun),
                line=dict(color=_PLOTLY_PALETTE[i % len(_PLOTLY_PALETTE)], width=2.5),
                marker=dict(size=7, symbol='square'),
                hovertemplate='%{x}<br>Penjualan: %{y:,.0f}<extra>' + str(tahun) + '</extra>'
            ))
        _plotly_layout(fig2, '📊 Perbandingan Pola Bulanan Antar Tahun', 'Bulan', 'Jumlah Penjualan')
        st.plotly_chart(fig2, use_container_width=True)

    # --- Chart 3: Annual bar chart ---
    if df_yearly is not None:
        total_per_tahun = df_yearly.groupby('Tahun')['penjualan'].sum().reset_index()
        fig3 = go.Figure(go.Bar(
            x=total_per_tahun['Tahun'].astype(str),
            y=total_per_tahun['penjualan'],
            marker_color=[_PLOTLY_PALETTE[i % len(_PLOTLY_PALETTE)] for i in range(len(total_per_tahun))],
            text=total_per_tahun['penjualan'].apply(lambda v: f'{v:,.0f}'),
            textposition='outside',
            textfont=dict(color=_PLOTLY_TEXT, size=11),
            hovertemplate='Tahun %{x}<br>Total: %{y:,.0f}<extra></extra>'
        ))
        _plotly_layout(fig3, '📦 Total Penjualan Per Tahun', 'Tahun', 'Total Penjualan', height=380)
        st.plotly_chart(fig3, use_container_width=True)


def plot_forecast_plotly(df, forecast):
    """Interactive forecast line chart with Plotly."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df['penjualan'],
        mode='lines+markers', name='Data Asli',
        line=dict(color='#f4dddb', width=2),
        marker=dict(size=5),
        hovertemplate='%{x|%b %Y}<br>Aktual: %{y:,.0f}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=forecast.index, y=forecast,
        mode='lines+markers', name='Prediksi',
        line=dict(color=_PLOTLY_GOLD, width=2.5, dash='dash'),
        marker=dict(size=7, symbol='diamond'),
        hovertemplate='%{x|%b %Y}<br>Prediksi: %{y:,.0f}<extra></extra>'
    ))
    _plotly_layout(fig, '🔮 Forecast vs Data Asli', 'Tanggal', 'Jumlah Penjualan')
    st.plotly_chart(fig, use_container_width=True)


def plot_heatmap_plotly(df_all, product='Semua Produk (Total)'):
    """Heatmap bulan × tahun."""
    if product == 'Semua Produk (Total)':
        df_grp = df_all.groupby(['Tahun', 'tanggal'])['penjualan'].sum().reset_index()
    else:
        df_grp = df_all[df_all['Nama Barang'] == product] \
            .groupby(['Tahun', 'tanggal'])['penjualan'].sum().reset_index()

    df_grp['Bulan'] = df_grp['tanggal'].dt.month
    pivot = df_grp.pivot_table(index='Tahun', columns='Bulan', values='penjualan', aggfunc='sum')

    bulan_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                    'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
    pivot.columns = [bulan_labels[c - 1] for c in pivot.columns]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=[str(y) for y in pivot.index],
        colorscale=[[0, '#1c1110'], [0.5, '#5b403c'], [1, '#ffba38']],
        hovertemplate='%{y} – %{x}<br>Penjualan: %{z:,.0f}<extra></extra>',
        colorbar=dict(title='Penjualan', tickfont=dict(color=_PLOTLY_TEXT)),
    ))
    _plotly_layout(fig, '🗓️ Heatmap Penjualan (Bulan × Tahun)', '', '', height=320)
    st.plotly_chart(fig, use_container_width=True)


def plot_distribution_plotly(df):
    """Histogram distribusi penjualan bulanan."""
    fig = go.Figure(go.Histogram(
        x=df['penjualan'],
        nbinsx=20,
        marker_color=_PLOTLY_GOLD,
        marker_line=dict(color='#1c1110', width=1),
        opacity=0.85,
        hovertemplate='Range: %{x}<br>Frekuensi: %{y}<extra></extra>'
    ))
    _plotly_layout(fig, '📊 Distribusi Penjualan Bulanan', 'Jumlah Penjualan', 'Frekuensi', height=350)
    st.plotly_chart(fig, use_container_width=True)


def plot_product_ranking_plotly(df_all):
    """Bar chart top produk."""
    ranking = df_all.groupby('Nama Barang')['penjualan'].sum().sort_values(ascending=True).tail(15)
    fig = go.Figure(go.Bar(
        x=ranking.values,
        y=ranking.index,
        orientation='h',
        marker_color=_PLOTLY_GOLD,
        marker_line=dict(color='rgba(255,215,153,0.3)', width=1),
        text=ranking.values,
        texttemplate='%{text:,.0f}',
        textposition='outside',
        textfont=dict(color=_PLOTLY_TEXT, size=10),
        hovertemplate='%{y}<br>Total: %{x:,.0f}<extra></extra>'
    ))
    _plotly_layout(fig, '🏆 Ranking Produk (Total Penjualan)', 'Total Penjualan', '', height=max(350, len(ranking) * 28))
    fig.update_layout(yaxis=dict(tickfont=dict(size=10)))
    st.plotly_chart(fig, use_container_width=True)


def get_inventory_data(df_all, products, forecast_func=None, train_func=None, prepare_func=None):
    """Generate inventory status table based on recent sales trends."""
    import numpy as np
    rows = []
    for prod in products:
        df_prod = df_all[df_all['Nama Barang'] == prod].groupby('tanggal')['penjualan'].sum().sort_index()
        if len(df_prod) < 3:
            continue
        avg_3m = df_prod.tail(3).mean()
        avg_all = df_prod.mean()
        trend = ((df_prod.tail(3).mean() - df_prod.head(3).mean()) / max(df_prod.head(3).mean(), 1)) * 100

        if trend > 10:
            status = '🟢 Naik'
            rekomendasi = f'Tambah stok {int(avg_3m * 1.2):,}'
        elif trend < -10:
            status = '🔴 Turun'
            rekomendasi = f'Kurangi stok ke {int(avg_3m * 0.8):,}'
        else:
            status = '🟡 Stabil'
            rekomendasi = f'Pertahankan stok {int(avg_3m):,}'

        rows.append({
            'Produk': prod,
            'Rata-rata 3 Bulan': int(avg_3m),
            'Rata-rata Semua': int(avg_all),
            'Tren (%)': f'{trend:+.1f}%',
            'Status': status,
            'Rekomendasi Stok': rekomendasi,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def generate_notifications(df_all=None, df_ts=None, forecast=None):
    """Auto-generate smart notifications based on data analysis."""
    notifs = []
    import datetime
    now = datetime.datetime.now().strftime('%H:%M')

    if df_all is not None and len(df_all) > 0:
        # Check for declining trend
        total_by_year = df_all.groupby('Tahun')['penjualan'].sum()
        if len(total_by_year) >= 2:
            last_two = total_by_year.sort_index().tail(2)
            if last_two.iloc[-1] < last_two.iloc[-2]:
                notifs.append({
                    'icon': '📉', 'time': now, 'type': 'warning',
                    'msg': f'Penjualan tahun {int(last_two.index[-1])} turun dibanding {int(last_two.index[-2])}.'
                })
            else:
                notifs.append({
                    'icon': '📈', 'time': now, 'type': 'success',
                    'msg': f'Penjualan tahun {int(last_two.index[-1])} naik! Trend positif.'
                })

        # Product with lowest sales
        bottom = df_all.groupby('Nama Barang')['penjualan'].sum().sort_values().head(1)
        if len(bottom) > 0:
            notifs.append({
                'icon': '⚠️', 'time': now, 'type': 'info',
                'msg': f'Produk penjualan terendah: {bottom.index[0]} ({int(bottom.values[0]):,} unit).'
            })

    if forecast is not None:
        notifs.append({
            'icon': '🔮', 'time': now, 'type': 'info',
            'msg': f'Forecast selesai. Prediksi bulan depan: {forecast.iloc[0]:,.0f} unit.'
        })

    if not notifs:
        notifs.append({
            'icon': '✅', 'time': now, 'type': 'info',
            'msg': 'Tidak ada notifikasi baru. Upload data untuk memulai analisis.'
        })

    return notifs