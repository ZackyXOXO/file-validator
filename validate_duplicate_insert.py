import os
import logging
import pandas as pd

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)


# ======================================
# 1. LOGGING
# ======================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# ======================================
# 2. TELEGRAM TOKEN
# ======================================

TOKEN = "7057320849:AAGQuC1RErEwjlmDTnOfHNP4b4X8Mlh2dq4"


# ======================================
# 3. VALIDATION FUNCTION
# ======================================

def process_and_validate_file(
        file_path,
        mode
):


    # ==========================
    # READ CSV
    # ==========================

    try:

        df = pd.read_csv(
            file_path
        )

    except Exception as e:

        return None, (
            f"❌ Gagal membaca file\n\n{str(e)}"
        )



    # ==========================
    # NORMALIZE HEADER
    # ==========================

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
    )


    expected_columns = [
        "polygon",
        "polygon_type",
        "label"
    ]


    missing_column = [
        col for col in expected_columns
        if col not in df.columns
    ]



    if missing_column:

        return None, (
            "❌ Header tidak sesuai\n\n"
            f"Kolom kurang:\n{missing_column}\n\n"
            f"Header ditemukan:\n{list(df.columns)}"
        )



    df = df[expected_columns]



    # ==========================
    # CLEANING DATA
    # ==========================


    for col in expected_columns:

        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
        )



    df["polygon_type"] = (
        df["polygon_type"]
        .str.title()
    )



    # ==========================
    # TOTAL DATA
    # ==========================

    total_rows = len(df)



    # ==========================
    # REMOVE DUPLICATE
    # ==========================


    df_unique = (
        df
        .drop_duplicates()
        .reset_index(drop=True)
    )


    duplicate_count = (
        total_rows -
        len(df_unique)
    )



    # ==========================
    # CHECK LABEL CONFLICT
    # ==========================


    polygon_label_check = (
        df_unique
        .groupby("polygon")
        ["label"]
        .nunique()
    )


    conflict_polygon = (
        polygon_label_check[
            polygon_label_check > 1
        ]
        .index
        .tolist()
    )



    # ==========================
    # CHECK BAD CHARACTER
    # ==========================


    bad_character = (
        df_unique["polygon"]
        .str
        .contains(
            r"[,;|]",
            regex=True
        )
    )


    bad_polygon = (
        df_unique.loc[
            bad_character,
            "polygon"
        ]
        .tolist()
    )



    # ==========================
    # REPORT
    # ==========================

    report = ""

    report += (
        "📊 *SIFA VALIDATION REPORT*\n\n"
    )


    report += (
        f"MODE : {mode.upper()}\n\n"
    )


    report += (
        f"📌 Total Input : {total_rows}\n"
    )


    report += (
        f"✨ Unique Data : {len(df_unique)}\n"
    )


    report += (
        f"🗑 Duplicate   : {duplicate_count}\n\n"
    )

    label_count = (
    df_unique["label"]
    .value_counts()
)


    report += (
    "📋 LIST UNIQUE LABELS & TOTAL :\n"
)


    for label, count in label_count.items():

     report += (
        f"▫️ {label}: {count} baris\n"
    )


    report += "\n"



    if conflict_polygon:

        report += (
            "⚠️ POLYGON CONFLICT\n"
        )

        report += (
            f"{len(conflict_polygon)} polygon "
            "memiliki lebih dari satu label\n\n"
        )



    if bad_polygon:

        report += (
            "⚠️ Hati Hati !! ada format polygon yang bisa menyebabkan anomaly struktur data ketika create temp table\n"
        )

        for item in bad_polygon:

            report += (
                f"- {item}\n"
            )

        report += "\n"



    if (
        not conflict_polygon
        and not bad_polygon
    ):

        report += (
            "✅ DATA AMAN\n\n"
        )



    # ==========================
    # EXPORT
    # ==========================


    folder = os.path.dirname(
        file_path
    )


    filename = os.path.splitext(
        os.path.basename(file_path)
    )[0]



    if mode == "delete":


        output_file = os.path.join(
            folder,
            f"clean_delete_{filename}.txt"
        )


        df_unique.to_csv(
            output_file,
            sep="|",
            index=False
        )


        report += (
            "📤 Output : DELETE\n"
            "Separator : |\n"
        )



    else:


        output_file = os.path.join(
            folder,
            f"clean_insert_{filename}.txt"
        )


        df_unique.to_csv(
            output_file,
            sep=",",
            index=False
        )


        report += (
            "📤 Output : INSERT\n"
            "Separator : ,\n"
        )



    return output_file, report





# ======================================
# 4. START COMMAND
# ======================================


async def start_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 SIFA Validator Bot\n\n"
        "Cara penggunaan:\n\n"
        "/val_sifa insert\n"
        "/val_sifa delete\n\n"
        "Upload CSV dengan caption command.\n\n"
        "file CSV harus berisi column polygon,polygon_type,label"
    )





# ======================================
# 5. FILE HANDLER
# ======================================


async def handle_document(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):


    caption = update.message.caption



    if not caption:

        return



    command = (
        caption
        .lower()
        .split()
    )



    if len(command) != 2:

        await update.message.reply_text(
            "❌ Format salah\n\n"
            "Gunakan:\n"
            "/val_sifa insert\n"
            "/val_sifa delete"
        )

        return



    if command[0] != "/val_sifa":

        return



    mode = command[1]



    if mode not in [
        "insert",
        "delete"
    ]:

        await update.message.reply_text(
            "❌ Mode tidak tersedia"
        )

        return



    document = (
        update.message.document
    )


    filename = (
        document.file_name
    )



    await update.message.reply_text(
        f"⏳ Processing {filename}"
    )



    temp_folder = "tmp_files"


    os.makedirs(
        temp_folder,
        exist_ok=True
    )



    local_file = os.path.join(
        temp_folder,
        filename
    )



    try:


        telegram_file = (
            await context.bot.get_file(
                document.file_id
            )
        )


        await telegram_file.download_to_drive(
            local_file
        )



        output, report = (
            process_and_validate_file(
                local_file,
                mode
            )
        )



        await update.message.reply_text(
            report,
        )



        if output:


            with open(
                output,
                "rb"
            ) as file:


                await update.message.reply_document(
                    document=file,
                    filename=os.path.basename(output),
                    caption="✅ File hasil validasi yang bisa digunakan untuk inputan"
                )



            os.remove(output)



    except Exception as e:


        await update.message.reply_text(
            f"❌ Error sistem:\n{str(e)}"
        )



    finally:


        if os.path.exists(local_file):

            os.remove(local_file)





# ======================================
# 6. MAIN
# ======================================


def main():


    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )



    app.add_handler(
        CommandHandler(
            "sifa",
            start_command
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            handle_document
        )
    )



    print(
        "🤖 SIFA Validator Bot Running..."
    )


    app.run_polling()



if __name__ == "__main__":

    main()