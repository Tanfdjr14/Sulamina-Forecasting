from statsmodels.tsa.statespace.sarimax import SARIMAX
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

def train_sarima(df):
    # Parameter default (1,1,1) x (1,1,1,12)
    # Jika data sangat sedikit, s_order disederhanakan otomatis
    s_order = (1, 1, 1, 12) if len(df) >= 24 else (1, 0, 0, 12)
    
    model = SARIMAX(
        df['penjualan'],
        order=(1, 1, 1),
        seasonal_order=s_order,
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    return model.fit(disp=False)

def forecast_sarima(model, df, steps=12):
    # Prediksi masa depan
    forecast_res = model.get_forecast(steps=steps)
    forecast_values = forecast_res.predicted_mean
    
    # Buat range tanggal masa depan
    last_date = df.index[-1]
    future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=steps, freq='MS')
    forecast_values.index = future_dates
    return forecast_values

def evaluate_model(model, df):
    pred = model.get_prediction(start=0).predicted_mean
    actual = df['penjualan']
    mae = mean_absolute_error(actual, pred)
    rmse = np.sqrt(mean_squared_error(actual, pred))
    return mae, rmse

def generate_recommendation(df, forecast):
    avg_now = df['penjualan'].tail(3).mean()
    avg_f = forecast.mean()
    
    if avg_f > avg_now:
        return [
            "⚠️ Stok: Prediksi naik! Tambah stok cokelat 15-20% untuk bulan depan.",
            "📢 Marketing: Fokuskan iklan pada produk best-seller.",
            "📦 Logistik: Pastikan ketersediaan kemasan/box mencukupi."
        ]
    else:
        return [
            "📉 Penjualan melambat: Hindari penumpukan stok berlebih.",
            "🎁 Promo: Lakukan diskon bundling untuk menjaga perputaran kas.",
            "🔍 Evaluasi: Cek kembali strategi pemasaran bulan lalu."
        ]