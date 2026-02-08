import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from functools import partial

from dotenv import load_dotenv
from supabase import create_client
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# -------------------------
# Configuration & Logging
# -------------------------

def get_brasilia_time():
    """Get current time in Brasília timezone (UTC-3)."""
    return datetime.now(timezone(timedelta(hours=-3)))
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

# Sync database functions
def _get_pending_now_sync():
    """Fetch pending medications for current time window."""
    now = get_brasilia_time()
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
    """Mark medication as sent."""
    try:
        supabase.table("medication_history") \
            .update({"status": "sent"}) \
            .eq("id", item_id) \
            .execute()
    except Exception as e:
        logger.error(f"Error marking med {item_id} as sent: {e}")

def _update_final_status_sync(unique_id, status):
    """Update final status of medication (taken/missed)."""
    try:
        supabase.table("medication_history") \
            .update({"status": status}) \
            .eq("unique_id", unique_id) \
            .eq("status", "sent") \
            .execute()
    except Exception as e:
        logger.error(f"Error updating status for {unique_id}: {e}")

def _get_active_meds_sync():
    """Fetch all active medications."""
    return supabase.table("medications").select("*").eq("active", True).execute()

def _get_history_for_med_sync(med_id, today):
    """Get medication history for a specific medication and date."""
    return supabase.table("medication_history") \
        .select("*") \
        .eq("medication_id", med_id) \
        .eq("date", today) \
        .execute()

def _insert_records_sync(records):
    """Insert medication history records."""
    return supabase.table("medication_history").insert(records).execute()

# Async wrappers
async def get_pending_now():
    """Async wrapper for getting pending medications."""
    return await run_db(_get_pending_now_sync)

async def mark_sent(item_id):
    """Async wrapper for marking medication as sent."""
    await run_db(_mark_sent_sync, item_id)

async def update_final_status(unique_id, status):
    """Async wrapper for updating final status."""
    await run_db(_update_final_status_sync, unique_id, status)

async def get_active_meds():
    """Async wrapper for getting active medications."""
    return await run_db(_get_active_meds_sync)

async def get_history_for_med(med_id, today):
    """Async wrapper for getting medication history."""
    return await run_db(_get_history_for_med_sync, med_id, today)

async def insert_records(records):
    """Async wrapper for inserting records."""
    return await run_db(_insert_records_sync, records)

def _get_patient_by_telegram_id_sync(telegram_id):
    """Get patient by telegram_id."""
    try:
        res = supabase.table("patients").select("*").eq("telegram_id", str(telegram_id)).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error fetching patient: {e}")
        return None

def _create_pending_patient_sync(telegram_id, first_name, username):
    """Create a new pending patient."""
    try:
        res = supabase.table("patients").insert({
            "telegram_id": str(telegram_id),
            "name": first_name or username or "Paciente",
            "status": "pending",
            "created_at": get_brasilia_time().isoformat()
        }).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"Error creating pending patient: {e}")
        return None

# Async wrappers for patient operations
async def get_patient_by_telegram_id(telegram_id):
    """Async wrapper for getting patient by telegram_id."""
    return await run_db(_get_patient_by_telegram_id_sync, telegram_id)

async def create_pending_patient(telegram_id, first_name, username):
    """Async wrapper for creating pending patient."""
    return await run_db(_create_pending_patient_sync, telegram_id, first_name, username)

# -------------------------
# Schedule Generators
# -------------------------
async def generate_daily_schedule():
    """Generates medication history entries for the current day."""
    today = get_brasilia_time().date().isoformat()

    try:
        # 1. Fetch active medications
        meds_res = await get_active_meds()
        meds = meds_res.data or []

        if not meds:
            return

        for med in meds:
            # 2. Check existing history for this medication today
            history_res = await get_history_for_med(med["id"], today)
            existing_times = {h["scheduled_time"] for h in (history_res.data or [])}

            # 3. Insert new records only for missing time slots
            new_records = []
            times = med.get("times", [])
            minutes = med.get("times_minutes", [])

            for t_str in times:
                try:
                    h, m = map(int, t_str.split(':'))
                    t_min = h * 60 + m
                except ValueError:
                    continue  # Invalid time format
                if t_str in existing_times:
                    continue  # Already exists, skip

                # Create deterministic ID to prevent duplicates
                unique_str = f"{med['id']}_{today}_{t_str}"
                uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_str))
                
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
                await insert_records(new_records)
                logger.info(f"Generated {len(new_records)} entries for {med['name']}")

    except Exception as e:
        logger.error(f"Error generating daily schedule: {e}")

# -------------------------
# Telegram Helpers
# -------------------------
def get_keyboard(unique_id):
    """Create inline keyboard for medication confirmation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tomei", callback_data=f"taken:{unique_id}"),
            InlineKeyboardButton("❌ Não Tomei", callback_data=f"missed:{unique_id}")
        ]
    ])

async def send_alert(bot, item):
    """Send medication alert to patient via Telegram."""
    try:
        telegram_id = item.get("patients", {}).get("telegram_id")
        if not telegram_id:
            logger.warning(f"No telegram_id for patient in item {item['id']}")
            return False

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
        return True
    except Exception as e:
        logger.error(f"Failed to send alert for item {item['id']}: {e}")
        return False

# -------------------------
# Message Handlers
# -------------------------
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - register or welcome patient."""
    user = update.effective_user
    telegram_id = user.id
    first_name = user.first_name
    username = user.username
    
    try:
        # Check if patient already exists
        patient = await get_patient_by_telegram_id(telegram_id)
        
        if patient:
            if patient.get("status") == "active":
                await update.message.reply_text(
                    f"👋 Olá, {patient['name']}!\n\n"
                    f"✅ Você já está cadastrado no sistema.\n"
                    f"💊 Você receberá alertas quando for hora de tomar seus remédios."
                )
            else:
                await update.message.reply_text(
                    f"👋 Olá, {first_name}!\n\n"
                    f"⏳ Seu cadastro está pendente de aprovação.\n"
                    f"📋 Entre em contato com o administrador para ativar sua conta."
                )
        else:
            # Create new pending patient
            new_patient = await create_pending_patient(telegram_id, first_name, username)
            
            if new_patient:
                await update.message.reply_text(
                    f"👋 Bem-vindo, {first_name}!\n\n"
                    f"✅ Seu Telegram foi registrado no sistema.\n"
                    f"⏳ Seu cadastro está pendente de aprovação.\n\n"
                    f"📋 O administrador precisa:\n"
                    f"1. Acessar o painel web\n"
                    f"2. Ativar seu cadastro\n"
                    f"3. Cadastrar seus medicamentos\n\n"
                    f"💊 Após a ativação, você receberá alertas dos seus remédios!"
                )
                logger.info(f"New pending patient registered: {telegram_id} ({first_name})")
            else:
                await update.message.reply_text(
                    "❌ Erro ao registrar. Tente novamente mais tarde."
                )
    except Exception as e:
        logger.error(f"Error in handle_start: {e}")
        await update.message.reply_text(
            "❌ Ocorreu um erro. Por favor, tente novamente."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any message - automatically register new patients."""
    user = update.effective_user
    telegram_id = user.id
    
    try:
        # Check if patient already exists
        patient = await get_patient_by_telegram_id(telegram_id)
        
        if not patient:
            # Auto-register as pending
            new_patient = await create_pending_patient(
                telegram_id, 
                user.first_name, 
                user.username
            )
            
            if new_patient:
                await update.message.reply_text(
                    f"👋 Olá, {user.first_name}!\n\n"
                    f"✅ Seu Telegram foi registrado automaticamente.\n"
                    f"⏳ Aguardando aprovação do administrador.\n\n"
                    f"📱 Seu ID: `{telegram_id}`\n\n"
                    f"💊 Após a ativação no painel web, você receberá os alertas!",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Auto-registered patient: {telegram_id} ({user.first_name})")
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")

# -------------------------
# Callback Handler
# -------------------------
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user response to medication alert."""
    query = update.callback_query
    await query.answer()

    try:
        action, unique_id = query.data.split(":")
        status = "taken" if action == "taken" else "missed"

        await update_final_status(unique_id, status)

        msg_status = "✅ Tomado" if status == "taken" else "❌ Não tomado"
        await query.edit_message_text(
            f"{msg_status}\n\nStatus registrado com sucesso!"
        )
        logger.info(f"Status updated to {status} for {unique_id}")

    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        await query.edit_message_text("❌ Erro ao registrar status. Tente novamente.")

# -------------------------
# Scheduler
# -------------------------
async def scheduler(app: Application, stop_event: asyncio.Event):
    """Main scheduler loop for checking and sending medication alerts."""
    logger.info("Scheduler started.")

    # Run once at startup
    await generate_daily_schedule()
    last_schedule_check = get_brasilia_time()

    while not stop_event.is_set():
        try:
            now = get_brasilia_time()

            # Periodically sync schedules (every 5 minutes)
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
                # Send alert first, then mark as sent only if successful
                success = await send_alert(app.bot, m)
                if success:
                    await mark_sent(m["id"])

        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        # Wait for the next minute boundary OR stop signal
        now = get_brasilia_time()
        seconds_to_sleep = 60 - now.second
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds_to_sleep)
            break  # Stop signal received
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue loop

    logger.info("Scheduler stopped.")

# -------------------------
# Main
# -------------------------
async def main():
    """Main application entry point."""
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Initialize and start bot
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("Bot started via polling.")

    # Create stop event for graceful shutdown
    stop_signal = asyncio.Event()

    # Start scheduler in background
    scheduler_task = asyncio.create_task(scheduler(app, stop_signal))

    # Keep the main loop running until interrupt
    try:
        await stop_signal.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Received shutdown signal.")
        stop_signal.set()
    finally:
        logger.info("Stopping bot...")
        
        # Wait for scheduler to finish gracefully
        try:
            await asyncio.wait_for(scheduler_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Scheduler did not stop gracefully, cancelling...")
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Stop bot components
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Bot stopped successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user.")