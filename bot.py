import logging
import os
import sqlite3
from datetime import datetime, time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

DB_NAME = "quan_ly_no.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            person_name TEXT,
            principal REAL,
            interest REAL,
            total_amount REAL,
            debt_form TEXT,
            due_date TEXT,
            note TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'CHUA_XONG'
        )
    """
    )
    conn.commit()
    conn.close()


def parse_args(args):
    if len(args) < 3:
        return None, 0, 0, "Đứng", "Chưa rõ", "Không có"

    numbers = []
    num_indices = []
    for i, arg in enumerate(args):
        clean_arg = arg.replace(".", "").replace(",", "")
        try:
            val = float(clean_arg)
            numbers.append(val)
            num_indices.append(i)
        except ValueError:
            continue

    if len(numbers) < 2:
        return None, 0, 0, "Đứng", "Chưa rõ", "Không có"

    principal = numbers[0]
    interest = numbers[1]
    p_idx = num_indices[0]
    i_idx = num_indices[1]

    person_name = " ".join(args[:p_idx]).strip()

    remaining = args[i_idx + 1 :]
    debt_form = "Đứng"
    due_date = "Chưa rõ"

    if remaining:
        if remaining[0].lower() in ["đứng", "dung"]:
            debt_form = "Đứng"
            remaining = remaining[1:]
        elif remaining[0].lower() in ["góp", "gop"]:
            debt_form = "Góp"
            remaining = remaining[1:]

    if remaining:
        due_date = remaining[0]
        remaining = remaining[1:]

    note = " ".join(remaining) if remaining else "Không có"
    return person_name, principal, interest, debt_form, due_date, note


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<blockquote>🤖 <b>BOT QUẢN LÝ CHO VAY</b>\n\n"
        "📌 <b>Cú pháp cho vay:</b> <code>/thu</code>\n"
        "<code>/thu [Tên] [Gốc] [Lãi] [Đứng/Góp] [Hẹn_trả] [Ghi_chú]</code>\n\n"
        "👉 <b>Ví dụ:</b> <code>/thu Nguyễn Văn A 10.000.000 1.000.000 Đứng/Góp 17/10/2020 Công việc</code>\n\n"
        "📋 <b>Các lệnh khác:</b>\n"
        "• <code>/ds</code> - Xem danh sách nợ chưa xong\n"
        "• <code>/nhac</code> - Kiểm tra nợ đến hạn hôm nay\n"
        "• <code>/xong [Mã]</code> - Đánh dấu đã trả xong\n"
        "• <code>/xoa [Mã]</code> - Xóa khoản vay\n"
        "• <code>/baocao</code> - Xem tổng tiền gốc & lãi\n\n"
        "⏰ <i>Tự động nhắc nợ lúc 08:00 sáng hằng ngày!</i></blockquote>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def add_thu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        person_name, principal, interest, debt_form, due_date, note = parse_args(context.args)

        if not person_name or principal <= 0:
            await update.message.reply_text(
                "<blockquote>❌ <b>CÚ PHÁP CHƯA ĐÚNG!</b>\n\n"
                "💡 <b>Mẫu chuẩn:</b> <code>/thu Nguyễn Văn A 10.000.000 1.000.000 Đứng 17/10/2020 Công việc</code></blockquote>",
                parse_mode="HTML",
            )
            return

        total_amount = principal + interest
        created_at = datetime.now().strftime("%d/%m/%Y")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO debts (user_id, person_name, principal, interest, total_amount, debt_form, due_date, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                person_name,
                principal,
                interest,
                total_amount,
                debt_form,
                due_date,
                note,
                created_at,
            ),
        )
        debt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        msg = (
            f"<blockquote>✅ <b>ĐÃ GHI NHẬN KHOẢN VAY (Mã #{debt_id})</b>\n\n"
            f"👤 Người vay: <b>{person_name}</b>\n"
            f"💵 Tiền gốc: <code>{principal:,.0f} VNĐ</code>\n"
            f"📈 Tiền lời: <code>{interest:,.0f} VNĐ</code>\n"
            f"💰 <b>TỔNG THU: <code>{total_amount:,.0f} VNĐ</code></b>\n"
            f"🔄 Hình thức: <b>{debt_form}</b>\n"
            f"📅 Hẹn trả: <b>{due_date}</b>\n"
            f"📝 Ghi chú: {note}</blockquote>"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi xử lý: {str(e)}")


async def list_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, person_name, principal, interest, total_amount, debt_form, due_date, note, created_at 
        FROM debts 
        WHERE user_id = ? AND status = 'CHUA_XONG'
        ORDER BY id DESC
    """,
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("🎉 Hiện tại không có khoản vay nào chưa hoàn tất!")
        return

    msg = "📋 <b>DANH SÁCH CÁC KHOẢN CHO VAY CHƯA XONG:</b>\n\n"
    for r in rows:
        debt_id, name, principal, interest, total, form, due, note, date = r
        msg += (
            f"<blockquote>🔹 <b>Mã #{debt_id}</b> | Người vay: <b>{name}</b>\n"
            f"💵 Gốc: <code>{principal:,.0f}</code> | Lãi: <code>{interest:,.0f}</code>\n"
            f"💰 <b>Tổng thu: <code>{total:,.0f} VNĐ</code></b>\n"
            f"🔄 Dạng: <b>{form}</b> | 📅 Hẹn: <b>{due}</b>\n"
            f"📝 Ghi chú: {note} (<i>{date}</i>)</blockquote>\n"
        )

    msg += "💡 Gửi <code>/xong [Mã_Số]</code> khi người vay đã trả tiền xong."
    await update.message.reply_text(msg, parse_mode="HTML")


async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: <code>/xong [Mã_Số]</code>", parse_mode="HTML")
        return
    try:
        debt_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Mã khoản vay phải là số!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT person_name, total_amount FROM debts WHERE id = ? AND user_id = ? AND status = 'CHUA_XONG'",
        (debt_id, user_id),
    )
    row = cursor.fetchone()

    if row:
        person_name, total_amount = row
        cursor.execute(
            "UPDATE debts SET status = 'DA_XONG' WHERE id = ? AND user_id = ?",
            (debt_id, user_id),
        )
        conn.commit()
        conn.close()

        done_msg = (
            f"<blockquote>🎉 <b>HOÀN THÀNH KHOẢN VAY</b>\n\n"
            f"👤 <b>{person_name}</b> đã trả xong toàn bộ số tiền vay!\n"
            f"🗑️ Hồ sơ nợ Mã #{debt_id} của <b>{person_name}</b> đã được tự động đóng và xóa khỏi danh sách.</blockquote>"
        )
        await update.message.reply_text(done_msg, parse_mode="HTML")
    else:
        conn.close()
        await update.message.reply_text(f"❌ Không tìm thấy khoản vay chưa xong có mã #{debt_id}!")


async def daily_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data.get("chat_id")
    user_id = job_data.get("user_id")

    today_str = datetime.now().strftime("%d/%m/%Y")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, person_name, total_amount, due_date FROM debts WHERE user_id = ? AND status = 'CHUA_XONG'",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        debt_id, name, total, due_date = r
        if due_date == today_str or "hôm nay" in due_date.lower():
            alert_msg = (
                f"<blockquote>⚠️ <b>CẢNH BÁO SẮP ĐẾN HẠN TRẢ NỢ</b>\n\n"
                f"👤 Người vay: <b>{name}</b> (Mã #{debt_id})\n"
                f"💰 Tổng số tiền: <code>{total:,.0f} VNĐ</code>\n"
                f"⏰ Hạn trả: Hôm nay đến ngày trả (<b>{due_date}</b>)!</blockquote>"
            )
            await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode="HTML")


async def check_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today_str = datetime.now().strftime("%d/%m/%Y")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, person_name, total_amount, due_date FROM debts WHERE user_id = ? AND status = 'CHUA_XONG'",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    count = 0
    for r in rows:
        debt_id, name, total, due_date = r
        if due_date == today_str or "hôm nay" in due_date.lower() or due_date == "Chưa rõ":
            alert_msg = (
                f"<blockquote>⚠️ <b>CẢNH BÁO SẮP ĐẾN HẠN TRẢ NỢ</b>\n\n"
                f"👤 Người vay: <b>{name}</b> (Mã #{debt_id})\n"
                f"💰 Tổng số tiền: <code>{total:,.0f} VNĐ</code>\n"
                f"⏰ Hạn trả: Hôm nay đến ngày trả (<b>{due_date}</b>)!</blockquote>"
            )
            await update.message.reply_text(alert_msg, parse_mode="HTML")
            count += 1

    if count == 0:
        await update.message.reply_text("✅ Không có khoản vay nào đến hạn trả hôm nay!")


async def delete_debt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: <code>/xoa [Mã_Số]</code>", parse_mode="HTML")
        return
    try:
        debt_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Mã số phải là số!")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM debts WHERE id = ? AND user_id = ?", (debt_id, user_id))
    if cursor.rowcount > 0:
        conn.commit()
        await update.message.reply_text(f"🗑️ Đã xóa khoản vay mã <b>#{debt_id}</b>!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Không tìm thấy mã #{debt_id}!")
    conn.close()


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT SUM(total_amount), SUM(principal), SUM(interest) FROM debts WHERE user_id = ? AND status = 'CHUA_XONG'",
        (user_id,),
    )
    total, principal, interest = cursor.fetchone()
    conn.close()

    total = total or 0
    principal = principal or 0
    interest = interest or 0

    msg = (
        "<blockquote>📊 <b>BÁO CÁO TỔNG QUAN CHO VAY</b>\n\n"
        f"💵 Tổng gốc đã cho vay: <code>{principal:,.0f} VNĐ</code>\n"
        f"📈 Tổng tiền lời dự thu: <code>{interest:,.0f} VNĐ</code>\n\n"
        f"💰 <b>TỔNG THU VỀ: <code>{total:,.0f} VNĐ</code></b></blockquote>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


if __name__ == "__main__":
    init_db()
    TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN", "8892361273:AAEZxPhyRRQvHM6iXMxCj6jylMy-gyb3KIQ"
    )
    app = ApplicationBuilder().token(TOKEN).build()

    job_queue = app.job_queue
    job_queue.run_daily(
        daily_reminder_job,
        time=time(8, 0, 0),
        data={"chat_id": 0, "user_id": 0},
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("thu", add_thu))
    app.add_handler(CommandHandler("ds", list_debts))
    app.add_handler(CommandHandler("danhsach", list_debts))
    app.add_handler(CommandHandler("nhac", check_reminders))
    app.add_handler(CommandHandler("xong", mark_done))
    app.add_handler(CommandHandler("xoa", delete_debt))
    app.add_handler(CommandHandler("baocao", report))

    print("🤖 Bot cho vay đã sẵn sàng với giao diện chuẩn HTML...")
    app.run_polling()
