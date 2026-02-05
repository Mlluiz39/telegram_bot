import os
import asyncio
import logging
import uuid
from datetime import datetime
from functools import partial

from dotenv import load_dotenv
from supabase import create_client
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
)

# -------------------------
# Configuration & Logging
# -------------------------
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not all([SUPABASE_URL, SUPABASE_KEY, TELEGRAM_TOKEN]):
    logger.error("Missing environment variables. Check .env file.")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# Async Database Wrappers
# -------------------------
async def run_db(func, *args, **kwargs):
    """Run blocking DB calls in a separate thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))

def _get_pending_now_sync():
    now = datetime.now()
    minutes = now.hour * 60 + now.minute
    today = now.date().isoformat()

    # Define a window to catch missed alerts (e.g. last 30 minutes)
    start_window = minutes - 30

    try:
        res = (
            supabase.table("medication_history")
            .select(
                "id,unique_id,scheduled_time,"
                "patients(name,telegram_id),"
                "medications(name,dosage)"
            )
            .eq("status", "pending")
            .eq("date", today)
            .lte("scheduled_minutes", minutes)
            .gte("scheduled_minutes", start_window)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching pending meds: {e}")
        return []

def _mark_sent_sync(item_id):
    try:
        supabase.table("medication_history") \
            .update({"status": "sent"}) \
            .eq("id", item_id) \
            .execute()
    except Exception as e:
        logger.error(f"Error marking med {item_id} as sent: {e}")

def _update_final_status_sync(unique_id, status):
    try:
        supabase.table("medication_history") \
            .update({"status": status}) \
            .eq("unique_id", unique_id) \
            .eq("status", "sent") \
            .execute()
    except Exception as e:
        logger.error(f"Error updating status for {unique_id}: {e}")

async def get_pending_now():
    return await run_db(_get_pending_now_sync)

async def mark_sent(item_id):
    await run_db(_mark_sent_sync, item_id)

async def update_final_status(unique_id, status):
    await run_db(_update_final_status_sync, unique_id, status)

# -------------------------
# Schedule Generators
# -------------------------
async def generate_daily_schedule():
    """Generates medication history entries for the current day."""
    today = datetime.now().date().isoformat()
    # logger.info(f"Checking schedules for {today}...") # Reduced log spam

    try:
        # 1. Fetch active medications
        meds_res = await run_db(
            lambda: supabase.table("medications").select("*").eq("active", True).execute()
        )
        meds = meds_res.data or []

        if not meds:
            return

        for med in meds:
            # 2. Check if history already exists for this med today
            history_res = await run_db(
                lambda: supabase.table("medication_history")
                .select("id")
                .eq("medication_id", med["id"])
                .eq("date", today)
                .execute()
            )
            
            if history_res.data:
                # Basic check: if count matches schedule count? 
                # For now, if ANY history exists, we assume it's done. 
                # Ideally we check per time slot, but that's heavier.
                # Assuming "if data exists, we already processed this med" handles basic case.
                # To handle "history deleted": if query returns empty, we recreate.
                continue

            # 3. Insert new records
            new_records = []
            
            times = med.get("times", [])
            minutes = med.get("times_minutes", [])
            
            for t_str, t_min in zip(times, minutes):
                uid = str(uuid.uuid4())
                record = {
                    "unique_id": uid,
                    "short_id": uid[:8],
                    "medication_id": med["id"],
                    "patient_id": med["patient_id"],
                    "date": today,
                    "scheduled_time": t_str,
                    "scheduled_minutes": t_min,
                    "status": "pending"
                }
                new_records.append(record)

            if new_records:
                await run_db(
                    lambda: supabase.table("medication_history").insert(new_records).execute()
                )
                logger.info(f"Generated {len(new_records)} entries for {med['name']}")

    except Exception as e:
        logger.error(f"Error generating daily schedule: {e}")

# -------------------------
# Telegram Helpers
# -------------------------
def get_keyboard(unique_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tomei", callback_data=f"taken:{unique_id}"),
            InlineKeyboardButton("❌ Não Tomei", callback_data=f"missed:{unique_id}")
        ]
    ])

async def send_alert(bot, item):
    try:
        telegram_id = item.get("patients", {}).get("telegram_id")
        if not telegram_id:
            logger.warning(f"No telegram_id for patient in item {item['id']}")
            return

        text = (
            "⏰ <b>Hora do seu remédio!</b>\n\n"
            f"👤 <b>{item['patients']['name']}</b>\n"
            f"💊 <b>{item['medications']['name']}</b>\n"
            f"📌 Dose: {item['medications']['dosage']}\n"
            f"🕒 Horário: {item['scheduled_time']}"
        )
        
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_keyboard(item["unique_id"])
        )
        logger.info(f"Alert sent to {telegram_id} for medication {item['medications']['name']}")
    except Exception as e:
        logger.error(f"Failed to send alert for item {item['id']}: {e}")

# -------------------------
# Callback Handler
# -------------------------
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        action, unique_id = query.data.split(":")
        status = "taken" if action == "taken" else "missed"

        await update_final_status(unique_id, status)

        msg_status = "Tomado" if status == "taken" else "Não tomado"
        await query.edit_message_text(
            f"✅ Status registrado: {msg_status}"
        )
        logger.info(f"Status updated to {status} for {unique_id}")

    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        await query.edit_message_text("❌ Erro ao registrar status via callback.")

# -------------------------
# Scheduler
# -------------------------
async def scheduler(app: Application):
    logger.info("Scheduler started.")
    
    # Run once at startup
    await generate_daily_schedule()
    last_schedule_check = datetime.now()

    while True:
        try:
            now = datetime.now()
            
            # Periodically sync schedules (e.g., every 5 minutes)
            # This handles deletions or new additions dynamically
            if (now - last_schedule_check).total_seconds() > 300: 
                 logger.info("Running periodic schedule sync...")
                 await generate_daily_schedule()
                 last_schedule_check = now

            # Check for pending medications
            meds = await get_pending_now()
            
            if meds:
                logger.info(f"Found {len(meds)} pending medications.")

            for m in meds:
                await mark_sent(m["id"])
                await send_alert(app.bot, m)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        # Wait for the next minute boundary
        now = datetime.now()
        seconds_to_sleep = 60 - now.second
        await asyncio.sleep(seconds_to_sleep)

# -------------------------
# Main
# -------------------------
async def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CallbackQueryHandler(handle_callback))

    # Initialize and start bot without blocking loop
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    logger.info("Bot started via polling.")

    # Start scheduler in background
    scheduler_task = asyncio.create_task(scheduler(app))

    # Keep the main loop running until interrupt
    stop_signal = asyncio.Event()

    try:
        await stop_signal.wait()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping bot...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
