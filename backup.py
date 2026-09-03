import os
import logging
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Konfigurasi Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 2. Masukkan Token Telegram Anda disini
TOKEN = '7057320849:AAGQuC1RErEwjlmDTnOfHNP4b4X8Mlh2dq4'

# 3. Fungsi Inti Validasi & Transformasi Data
def process_and_validate_file(file_path):
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(file_path)
    elif ext == ".txt":
        df = pd.read_csv(file_path, sep=r"\s+|\t", engine="python")
    else:
        return None, "❌ Format file tidak didukung. Kirim .csv, .xlsx, atau .txt."

    df.columns = df.columns.str.strip().str.lower()
    expected_cols = ["polygon", "polygon_type", "label"]

    if not all(col in df.columns for col in expected_cols):
        return None, f"❌ Header tidak sesuai. Kolom ditemukan: {list(df.columns)}\nDiharapkan: {expected_cols}"

    df = df[expected_cols]

    for col in expected_cols:
        df[col] = df[col].astype(str).str.strip()

    df["polygon_type"] = df["polygon_type"].str.title()

    total_rows_all = len(df)
    df_unique = df.drop_duplicates().reset_index(drop=True)
    total_rows_unique = len(df_unique)
    total_duplicate_rows = total_rows_all - total_rows_unique

    label_counts_series = df_unique["label"].value_counts()
    total_unique_labels_count = len(label_counts_series)

    label_polygon_counts = df_unique.groupby("label")["polygon"].nunique()
    invalid_labels = label_polygon_counts[label_polygon_counts > 1].index.tolist()
    total_invalid_labels = len(invalid_labels)

    bad_char_mask = df_unique["polygon"].str.contains(r"[,;|]", regex=True)
    has_bad_structure = bad_char_mask.any()

    log_msg = f"📊 *Total Rows (All Input)* : {total_rows_all} baris\n"
    log_msg += f"✨ *Total Rows (Unique Out)*: {total_rows_unique} baris\n"
    log_msg += f"👥 *Duplikat Dibuang*       : {total_duplicate_rows} baris\n"
    log_msg += f"🗺️ *Unique Polygons*        : {df_unique['polygon'].nunique()} data\n"
    log_msg += f"🏷️ *Total Unique Labels*     : {total_unique_labels_count} data\n\n"
    
    log_msg += "📋 *LIST UNIQUE LABELS & KEMUNCULAN*:\n"
    for label_name, count in label_counts_series.items():
        log_msg += f" ▫️ `{label_name}`: {count} baris\n"
    log_msg += "\n"

    if has_bad_structure:
        log_msg += "⚠️ *WARN!! ada file yang menyebabkan data polygon rusak secara struktur*\n"
        bad_polygons = df_unique[bad_char_mask]["polygon"].unique()
        for poly in bad_polygons:
            log_msg += f"  - `{poly}`\n"
        log_msg += "\n"

    if total_invalid_labels > 0:
        log_msg += f"⚠️ *PERINGATAN LOGIKA DATA*: Ditemukan {total_invalid_labels} label terikat pada beberapa polygon berbeda.\n\n"
    
    if not has_bad_structure and total_invalid_labels == 0:
        log_msg += "✅ *DATA AMAN*: Struktur & logika data 100% sempurna.\n\n"

    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    file_title, _ = os.path.splitext(base_name)
    output_path = os.path.join(dir_name, f"clean_{file_title}.csv")
    
    df_unique.to_csv(output_path, index=False)

    return output_path, log_msg

# 4. Handler untuk Perintah /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya adalah Bot Validator Polygon.\n\n"
        "💡 *Cara Penggunaan*:\n"
        "Silakan unggah file (.csv, .xlsx, atau .txt) Anda dan berikan pesan/caption: `/val_sifa_insert` saat mengirim agar saya proses.",
        parse_mode="Markdown"
    )

# 5. Handler untuk Menerima Dokumen berdasarkan Caption khusus
async def handle_document_with_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Mengambil teks/caption dari file yang dikirim
    caption = update.message.caption
    
    # 🔒 Kunci logika: Cek apakah caption persis /val_sifa_insert
    if not caption or caption.strip() != "/val_sifa_insert":
        # Jika file dikirim tanpa command tersebut, bot akan diam / mengabaikan file.
        return

    document = update.message.document
    file_name = document.file_name
    
    await update.message.reply_text(f"⏳ Oncheck Sedang memproses file `{file_name}`...")

    tmp_dir = "tmp_files"
    os.makedirs(tmp_dir, exist_ok=True)
    local_file_path = os.path.join(tmp_dir, file_name)

    try:
        tg_file = await context.bot.get_file(document.file_id)
        await tg_file.download_to_drive(local_file_path)

        output_file, report_message = process_and_validate_file(local_file_path)

        if output_file and os.path.exists(output_file):
            await update.message.reply_text(f"=== *STATISTIK DATA: {file_name}* ===\n\n{report_message}", parse_mode="Markdown")
            
            with open(output_file, 'rb') as f:
                await update.message.reply_document(document=f, filename=os.path.basename(output_file), caption="💾 Ini file unik yang sudah dibersihkan.")
            
            os.remove(output_file)
        else:
            await update.message.reply_text(report_message)

    except Exception as e:
        await update.message.reply_text(f"❌ Terjadi kesalahan sistem saat memproses file: {str(e)}")
    
    finally:
        if os.path.exists(local_file_path):
            os.remove(local_file_path)

# 6. Fungsi Utama Menjalankan Bot
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    
    # Handler diubah agar mendengarkan dokumen dengan lampiran teks/caption
    app.add_handler(MessageHandler(filters.Document.ALL & filters.Caption(None), handle_document_with_command))

    print("🤖 Bot Telegram Validator sedang berjalan dengan filter command... Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == '__main__':
    main()