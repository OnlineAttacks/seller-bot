import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from config import BOT_TOKEN, ADMIN_ID
from database import *
import logging

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# ================= USER UI =================

def user_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Buy PDF", callback_data="buy")],
        [InlineKeyboardButton(text="My Order Status", callback_data="status")],
        [InlineKeyboardButton(text="Contact Admin", url=f"https://t.me/{ADMIN_ID}")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Full Stats", callback_data="stats")],
        [InlineKeyboardButton(text="👥 Export Users", callback_data="export")],
        [InlineKeyboardButton(text="💰 Pending Payments", callback_data="pending")],
        [InlineKeyboardButton(text="📤 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton(text="⚙ Set Price", callback_data="setprice")],
        [InlineKeyboardButton(text="🖼 Set QR", callback_data="setqr")],
        [InlineKeyboardButton(text="📁 Set PDF", callback_data="setpdf")]
    ])

# ================= START =================

@dp.message(Command("start"))
async def start(msg: Message):
    await add_user(msg.from_user.id, msg.from_user.username)
    await msg.answer(
        "<b>Welcome!</b>\nSecurely purchase PDF below.",
        reply_markup=user_keyboard()
    )

# ================= BUY =================

@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):
    if await user_pending(call.from_user.id):
        await call.message.answer("⚠️ You already have pending request.")
        return

    price, upi_id, qr, _ = await get_settings()

    await call.message.answer_photo(
        qr,
        caption=f"<b>Price:</b> ₹{price}\n<b>UPI ID:</b> {upi_id}\n\nSend 12 digit UTR:",
    )

# ================= UTR VALIDATION =================

@dp.message(F.text.regexp(r"^\d{12}$"))
async def handle_utr(msg: Message):
    if await payment_exists(msg.text):
        await msg.answer("❌ UTR already used.")
        return

    if await user_pending(msg.from_user.id):
        await msg.answer("⚠️ You already submitted.")
        return

    await add_payment(msg.from_user.id, msg.text)

    await msg.answer("✅ Submitted. Waiting for admin approval.")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Approve", callback_data=f"approve_{msg.text}"),
            InlineKeyboardButton(text="Reject", callback_data=f"reject_{msg.text}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"New Payment Request\n\nUser: @{msg.from_user.username}\nUser ID: {msg.from_user.id}\nUTR: {msg.text}",
        reply_markup=kb
    )

# ================= APPROVAL =================

@dp.callback_query(F.data.startswith("approve_"))
async def approve(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    utr = call.data.split("_")[1]
    await update_payment(utr, "approved")

    settings = await get_settings()
    pdf = settings[3]

    await call.message.answer("✅ Approved")

    user_id = int(call.message.text.split("User ID: ")[1].split("\n")[0])
    await bot.send_document(user_id, pdf)
    await bot.send_message(user_id, "🎉 Payment Approved! Here is your PDF.")

# ================= REJECT =================

@dp.callback_query(F.data.startswith("reject_"))
async def reject(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    utr = call.data.split("_")[1]
    await update_payment(utr, "rejected")

    user_id = int(call.message.text.split("User ID: ")[1].split("\n")[0])
    await bot.send_message(user_id, "❌ Payment Rejected.")

    await call.message.answer("Rejected")

# ================= ADMIN PANEL =================

@dp.message(Command("admin"))
async def admin_panel_cmd(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("Admin Panel", reply_markup=admin_keyboard())

# ================= STATS =================

@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    s = await get_stats()
    price = (await get_settings())[0]
    revenue = s["approved"] * price

    await call.message.answer(
        f"""📊 <b>Stats</b>

Users: {s["total_users"]}
Payments: {s["total_payments"]}
Approved: {s["approved"]}
Rejected: {s["rejected"]}
Pending: {s["pending"]}
Revenue: ₹{revenue}
"""
    )

# ================= EXPORT USERS =================

@dp.callback_query(F.data == "export")
async def export_users(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    users = await get_all_users()

    text = ""
    for u in users:
        text += f"{u[0]} | {u[1]} | {u[2]}\n"

    with open("users.txt", "w") as f:
        f.write(text)

    await call.message.answer_document(FSInputFile("users.txt"))

# ================= BROADCAST =================

broadcast_data = {}

@dp.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    broadcast_data["waiting"] = True
    await call.message.answer("Send message or media to broadcast.")

@dp.message()
async def handle_broadcast(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    if not broadcast_data.get("waiting"):
        return

    broadcast_data["waiting"] = False

    users = await get_all_users()

    sent = 0
    failed = 0

    status_msg = await msg.answer("Broadcasting...")

    for u in users:
        try:
            await msg.copy_to(u[0])
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            continue
        except TelegramForbiddenError:
            failed += 1
        except:
            failed += 1

        await status_msg.edit_text(
            f"Broadcasting...\nSent: {sent}\nFailed: {failed}\nRemaining: {len(users)-sent-failed}"
        )

    await status_msg.edit_text(
        f"✅ Done\nSent: {sent}\nFailed: {failed}"
    )

# ================= RUN =================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())