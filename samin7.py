import io
import json
import logging
import os
import random
import string
import datetime
import qrcode
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiohttp import web

API_TOKEN = '8931493364:AAFVZV4E1ZYWPt26MyGev_kUeNOTvY8HnzM'
ADMIN_ID = 8865667140
UPI_ID = '8391067251-2@ibl'
SUPPORT_USERNAME = 'pgsamin'
UPDATE_CHANNEL = 'https://t.me/pgmodestore'

STORE_NAME = "PG MODE STORE"
DB_FILE = "database.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AdminStates(StatesGroup):
    waiting_for_single_panel_input = State()
    waiting_for_remove_panel = State()
    waiting_for_add_reseller = State()
    waiting_for_remove_reseller = State()
    waiting_for_broadcast = State()
    waiting_for_add_balance = State()
    waiting_for_remove_balance = State()
    waiting_for_payment_proof = State()

def load_db():
    if not os.path.exists(DB_FILE):
        default_db = {
            "panels": [],
            "keys_history": [],
            "deposit_history": [],
            "users": {}
        }
        save_db(default_db)
        return default_db
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"panels": [], "keys_history": [], "deposit_history": [], "users": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def parse_time_to_hours(time_str):
    time_str = time_str.lower().strip()
    parts = time_str.split()
    if len(parts) != 2:
        return None
    try:
        val = int(parts[0])
    except ValueError:
        return None
    
    unit = parts[1]
    if "hour" in unit:
        if 1 <= val <= 720:
            return val
    elif "day" in unit:
        if 1 <= val <= 30:
            return val * 24
    return None

def generate_access_key(panel_name, hours):
    clean_name = ''.join(filter(str.isalnum, panel_name.split()[0])).upper()
    prefix = clean_name if clean_name else "KEY"
    
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    part3 = ''.join(random.choices(chars, k=4))
    key = f"{prefix}-{part1}-{part2}-{part3}"
    
    now = datetime.datetime.now()
    expiry_date = now + datetime.timedelta(hours=hours)
    return key, now.strftime("%Y-%m-%d %H:%M:%S"), expiry_date.strftime("%Y-%m-%d %H:%M:%S")

def main_menu_keyboard(is_admin=False):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("🛒 Buy Now", callback_data="buy_now"))
    keyboard.row(
        InlineKeyboardButton("📥 Check Update", url=UPDATE_CHANNEL),
        InlineKeyboardButton("💳 Add Balance", callback_data="add_balance")
    )
    keyboard.add(InlineKeyboardButton("🎁 My Profile + All History", callback_data="profile"))
    keyboard.row(
        InlineKeyboardButton("🔗 Refer And Earn", callback_data="refer"),
        InlineKeyboardButton("❓ How To Use Bot", url=UPDATE_CHANNEL)
    )
    keyboard.row(
        InlineKeyboardButton("✈️ Support", callback_data="support"),
        InlineKeyboardButton("🎁 Daily Gift", callback_data="daily_gift")
    )
    if is_admin:
        keyboard.add(InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel"))
    return keyboard

@dp.message_handler(commands=['start'], state="*")
async def send_welcome(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"
    full_name = message.from_user.full_name or "User"
    is_admin = (user_id == ADMIN_ID)
    
    args = message.get_args()
    db = load_db()
    str_user_id = str(user_id)
    
    if str_user_id not in db["users"]:
        db["users"][str_user_id] = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "balance": 0.0,
            "is_reseller": False,
            "referred_by": None,
            "last_gift_time": None,
            "joined": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if args and args.isdigit() and int(args) != user_id:
            ref_id = str(args)
            if ref_id in db["users"]:
                db["users"][str_user_id]["referred_by"] = int(ref_id)
    else:
        db["users"][str_user_id]["username"] = username
        db["users"][str_user_id]["full_name"] = full_name
    save_db(db)
        
    user_bal = db["users"][str_user_id].get("balance", 0.0)
    
    welcome_text = (
        f"<b>Welcome PG MODE STORE</b>\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏷️ <b>Username:</b> @{username}\n\n"
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
        f"✨ <b>Your Balance:</b> 💸 ₹{user_bal:.2f} 🌸\n"
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n\n"
        "👉 <b>Select an option from the menu below:</b>"
    )
    await message.reply(welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard(is_admin))

@dp.message_handler(commands=['admin'], state="*")
async def admin_command(message: types.Message, state: FSMContext):
    await state.finish()
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ You are not authorized!")
        return
    admin_keyboard = InlineKeyboardMarkup(row_width=2)
    admin_keyboard.add(
        InlineKeyboardButton("➕ Add Panel", callback_data="admin_add_panel"),
        InlineKeyboardButton("➖ Remove Panel", callback_data="admin_remove_panel"),
        InlineKeyboardButton("💰 Add Balance", callback_data="admin_add_balance"),
        InlineKeyboardButton("📉 Remove Balance", callback_data="admin_remove_balance"),
        InlineKeyboardButton("👤 Add Reseller", callback_data="admin_add_reseller"),
        InlineKeyboardButton("🚫 Remove Reseller", callback_data="admin_remove_reseller"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("👥 Total Users", callback_data="admin_users"),
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
    )
    await message.reply(f"<b>🛠️ {STORE_NAME} - ADMIN PANEL</b>", parse_mode="HTML", reply_markup=admin_keyboard)

@dp.callback_query_handler(text="admin_panel", state="*")
async def process_admin_panel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    if callback_query.from_user.id != ADMIN_ID:
        return
    admin_keyboard = InlineKeyboardMarkup(row_width=2)
    admin_keyboard.add(
        InlineKeyboardButton("➕ Add Panel", callback_data="admin_add_panel"),
        InlineKeyboardButton("➖ Remove Panel", callback_data="admin_remove_panel"),
        InlineKeyboardButton("💰 Add Balance", callback_data="admin_add_balance"),
        InlineKeyboardButton("📉 Remove Balance", callback_data="admin_remove_balance"),
        InlineKeyboardButton("👤 Add Reseller", callback_data="admin_add_reseller"),
        InlineKeyboardButton("🚫 Remove Reseller", callback_data="admin_remove_reseller"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("👥 Total Users", callback_data="admin_users"),
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")
    )
    text = f"<b>🛠️ {STORE_NAME} - ADMIN PANEL</b>"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=admin_keyboard)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=admin_keyboard)

@dp.callback_query_handler(text="admin_add_balance", state="*")
async def process_admin_add_bal_start(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_add_balance.set()
    await callback_query.message.reply("💰 <b>Enter User ID and Amount to Add:</b>\nFormat: <code>User_ID, Amount</code>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_add_balance)
async def process_admin_add_bal_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = [p.strip() for p in message.text.split(",")]
        if len(parts) != 2:
            await message.reply("❌ Invalid format! Use: <code>User_ID, Amount</code>", parse_mode="HTML")
            return
        target_id, amount = parts[0], float(parts[1])
        db = load_db()
        if target_id not in db["users"]:
            db["users"][target_id] = {"user_id": int(target_id), "balance": 0.0, "is_reseller": False}
        
        db["users"][target_id]["balance"] += amount
        if "deposit_history" not in db:
            db["deposit_history"] = []
        db["deposit_history"].append({"user_id": int(target_id), "amount": amount, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        save_db(db)
        
        await message.reply(f"✅ Successfully added ₹{amount} to User ID: <code>{target_id}</code>", parse_mode="HTML")
        try:
            await bot.send_message(int(target_id), f"🎉 <b>Admin added ₹{amount} to your balance!</b>", parse_mode="HTML")
        except Exception:
            pass
        await state.finish()
    except Exception:
        await message.reply("❌ Error! Please enter valid User ID and Amount numbers.", parse_mode="HTML")

@dp.callback_query_handler(text="admin_remove_balance", state="*")
async def process_admin_remove_bal_start(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_remove_balance.set()
    await callback_query.message.reply("📉 <b>Enter User ID and Amount to Remove:</b>\nFormat: <code>User_ID, Amount</code>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_remove_balance)
async def process_admin_remove_bal_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = [p.strip() for p in message.text.split(",")]
        if len(parts) != 2:
            await message.reply("❌ Invalid format! Use: <code>User_ID, Amount</code>", parse_mode="HTML")
            return
        target_id, amount = parts[0], float(parts[1])
        db = load_db()
        if target_id in db["users"]:
            db["users"][target_id]["balance"] = max(0.0, db["users"][target_id]["balance"] - amount)
            save_db(db)
            await message.reply(f"✅ Successfully removed ₹{amount} from User ID: <code>{target_id}</code>", parse_mode="HTML")
            try:
                await bot.send_message(int(target_id), f"⚠️ <b>Admin deducted ₹{amount} from your balance.</b>", parse_mode="HTML")
            except Exception:
                pass
        else:
            await message.reply("❌ User ID not found!", parse_mode="HTML")
        await state.finish()
    except Exception:
        await message.reply("❌ Error! Please enter valid User ID and Amount numbers.", parse_mode="HTML")

@dp.callback_query_handler(text="admin_users", state="*")
async def process_admin_users(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    db = load_db()
    total_users = len(db.get("users", {}))
    await callback_query.answer(f"👥 Total Registered Users: {total_users}", show_alert=True)

@dp.callback_query_handler(text="admin_add_panel", state="*")
async def process_add_panel_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_single_panel_input.set()
    await callback_query.message.reply("➕ <b>Add New Panel:</b>\n\nSend in format:\n<code>Name | price | time | details</code>\n<i>(Time: 1 Hour to 30 Days, e.g., <code>1 Hour</code> or <code>30 Days</code>)</i>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_single_panel_input)
async def process_single_panel_input(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 4:
            await message.reply("❌ Invalid format! Use: <code>Name | price | time | details</code>", parse_mode="HTML")
            return
        
        name, price_str, time_str, details = parts[0], parts[1], parts[2], parts[3]
        price = float(price_str)
        hours = parse_time_to_hours(time_str)
        
        if hours is None:
            await message.reply("❌ Invalid time format! Range must be between <code>1 Hour</code> to <code>30 Days</code>.", parse_mode="HTML")
            return
        
        db = load_db()
        db["panels"].append({"name": name, "price": price, "time_str": time_str, "hours": hours, "details": details})
        save_db(db)
        await message.reply(f"✅ <b>Panel Added Successfully!</b>\n📦 Name: {name}\n💵 Price: ₹{price}\n⏳ Time: {time_str}\n📝 Details: {details}", parse_mode="HTML")
        await state.finish()
    except Exception as e:
        await message.reply("❌ Error! Make sure Price is a number and format is correct: <code>Name | price | time | details</code>", parse_mode="HTML")

@dp.callback_query_handler(text="admin_broadcast", state="*")
async def process_broadcast_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_broadcast.set()
    await callback_query.message.reply("📢 <b>Send broadcast message/photo/video:</b>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_broadcast, content_types=types.ContentTypes.ANY)
async def process_broadcast_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    db = load_db()
    users = db.get("users", {})
    success = 0
    failed = 0
    
    for uid in users.keys():
        try:
            await message.send_copy(chat_id=int(uid))
            success += 1
        except Exception:
            failed += 1
            
    await message.reply(f"📢 <b>Broadcast Completed!</b>\n\n✅ Success: {success}\n❌ Failed: {failed}", parse_mode="HTML")
    await state.finish()

@dp.callback_query_handler(text="admin_add_reseller", state="*")
async def process_add_reseller_start(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_add_reseller.set()
    await callback_query.message.reply("👤 <b>Enter User Telegram ID to make RESELLER:</b>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_add_reseller)
async def process_add_reseller_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target_id = message.text.strip()
    db = load_db()
    if target_id not in db["users"]:
        db["users"][target_id] = {"user_id": int(target_id), "balance": 0.0, "is_reseller": True}
    else:
        db["users"][target_id]["is_reseller"] = True
    save_db(db)
    await message.reply(f"✅ User <code>{target_id}</code> is now a <b>RESELLER</b>!", parse_mode="HTML")
    await state.finish()

@dp.callback_query_handler(text="admin_remove_reseller", state="*")
async def process_remove_reseller_start(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_remove_reseller.set()
    await callback_query.message.reply("🚫 <b>Enter User Telegram ID to REMOVE Reseller Role:</b>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_remove_reseller)
async def process_remove_reseller_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target_id = message.text.strip()
    db = load_db()
    if target_id in db["users"]:
        db["users"][target_id]["is_reseller"] = False
        save_db(db)
        await message.reply(f"✅ User <code>{target_id}</code> is now downgraded.", parse_mode="HTML")
    else:
        await message.reply("❌ User ID not found!", parse_mode="HTML")
    await state.finish()

@dp.callback_query_handler(text="admin_remove_panel", state="*")
async def process_remove_panel_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        return
    db = load_db()
    if not db["panels"]:
        await callback_query.answer("⚠️ No panels available!", show_alert=True)
        return
    panel_list = "\n".join([f"• <code>{p['name']}</code> (₹{p['price']})" for p in db["panels"]])
    await AdminStates.waiting_for_remove_panel.set()
    await callback_query.message.reply(f"➖ <b>Active Panels:</b>\n{panel_list}\n\n<b>Type exact name to REMOVE:</b>", parse_mode="HTML")

@dp.message_handler(state=AdminStates.waiting_for_remove_panel)
async def process_remove_panel_save(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    p_name = message.text.strip()
    db = load_db()
    initial_count = len(db["panels"])
    db["panels"] = [p for p in db["panels"] if p["name"].lower() != p_name.lower()]
    if len(db["panels"]) < initial_count:
        save_db(db)
        await message.reply(f"✅ Removed Panel Folder: <code>{p_name}</code>", parse_mode="HTML")
    else:
        await message.reply("❌ Panel not found!")
    await state.finish()

@dp.callback_query_handler(text="buy_now", state="*")
async def process_buy_now(callback_query: types.CallbackQuery):
    db = load_db()
    if not db["panels"]:
        await callback_query.answer("⚠️ No panels available right now!", show_alert=True)
        return
    
    unique_panel_names = sorted(list(set(p["name"] for p in db["panels"])))
    folders_keyboard = InlineKeyboardMarkup(row_width=1)
    for name in unique_panel_names:
        folders_keyboard.add(InlineKeyboardButton(f"📁 {name}", callback_data=f"folder_{name}"))
    folders_keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    
    text = f"<b>🛒 {STORE_NAME}</b>\n\n📁 <b>Select a panel folder below:</b>"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=folders_keyboard)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=folders_keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('folder_'), state="*")
async def process_panel_folder(callback_query: types.CallbackQuery):
    panel_name = callback_query.data[len('folder_'):]
    db = load_db()
    user_id = str(callback_query.from_user.id)
    is_reseller = db["users"].get(user_id, {}).get("is_reseller", False)
    
    variants_keyboard = InlineKeyboardMarkup(row_width=1)
    for idx, panel in enumerate(db["panels"]):
        if panel["name"] == panel_name:
            price = panel["price"] * 0.75 if is_reseller else panel["price"]
            time_display = panel.get("time_str", "30 Days")
            variants_keyboard.add(InlineKeyboardButton(f"🔥 {time_display} - ₹{price:.2f}", callback_data=f"buy_p_{idx}"))
            
    variants_keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="buy_now"))
    text = f"<b>📁 {panel_name}</b>\n\n⏳ <b>Select duration/pricing below:</b>"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=variants_keyboard)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=variants_keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('buy_p_'), state="*")
async def process_buy_premium(callback_query: types.CallbackQuery):
    panel_idx = int(callback_query.data.split('_')[2])
    db = load_db()
    user_id = str(callback_query.from_user.id)
    if panel_idx >= len(db["panels"]):
        await callback_query.answer("❌ Item not found!", show_alert=True)
        return
    panel = db["panels"][panel_idx]
    is_reseller = db["users"].get(user_id, {}).get("is_reseller", False)
    price = panel["price"] * 0.75 if is_reseller else panel["price"]
    user_bal = db["users"].get(user_id, {}).get("balance", 0.0)
    if user_bal < price:
        await callback_query.answer(f"❌ Insufficient Balance! Required: ₹{price:.2f}", show_alert=True)
        return
    
    # Deduct balance
    db["users"][user_id]["balance"] -= price

    # Check for referral commission (5%)
    ref_user_id = db["users"].get(user_id, {}).get("referred_by")
    if ref_user_id and str(ref_user_id) in db["users"]:
        commission = round(price * 0.05, 2)
        db["users"][str(ref_user_id)]["balance"] += commission
        try:
            await bot.send_message(ref_user_id, f"🎉 <b>Referral Bonus Earned!</b>\n\nYour referred user purchased a panel. You received <b>₹{commission}</b> (5% commission)!", parse_mode="HTML")
        except Exception:
            pass
    
    hours = panel.get("hours", 720)
    generated_key, buy_time, expiry_time = generate_access_key(panel["name"], hours)
    
    db["keys_history"].append({
        "user_id": callback_query.from_user.id,
        "panel": panel["name"],
        "key": generated_key,
        "buy_time": buy_time,
        "expire_time": expiry_time
    })
    save_db(db)
    success_keyboard = InlineKeyboardMarkup()
    success_keyboard.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu"))
    text = (
        "<b>🎉 PURCHASE SUCCESSFUL!</b>\n\n"
        f"📦 Panel: <b>{panel['name']}</b>\n"
        f"📝 Details: {panel.get('details', 'N/A')}\n"
        f"🔑 Your Access Key: <code>{generated_key}</code>\n"
        f"🕒 <b>Buy Time:</b> <code>{buy_time}</code>\n"
        f"⏳ <b>Expire Time:</b> <code>{expiry_time}</code>\n\n"
        f"💰 Deducted: <b>₹{price:.2f}</b>"
    )
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=success_keyboard)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=success_keyboard)

user_amounts = {}

def get_keypad_markup():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.row(InlineKeyboardButton("1", callback_data="kp_1"), InlineKeyboardButton("2", callback_data="kp_2"), InlineKeyboardButton("3", callback_data="kp_3"))
    kb.row(InlineKeyboardButton("4", callback_data="kp_4"), InlineKeyboardButton("5", callback_data="kp_5"), InlineKeyboardButton("6", callback_data="kp_6"))
    kb.row(InlineKeyboardButton("7", callback_data="kp_7"), InlineKeyboardButton("8", callback_data="kp_8"), InlineKeyboardButton("9", callback_data="kp_9"))
    kb.row(InlineKeyboardButton("❌ CLEAR", callback_data="kp_clear"), InlineKeyboardButton("0", callback_data="kp_0"), InlineKeyboardButton("🔙 BACK", callback_data="kp_back"))
    kb.add(InlineKeyboardButton("🟢 CONFIRM AMOUNT", callback_data="kp_confirm"))
    kb.add(InlineKeyboardButton("🔙 Return to Menu", callback_data="main_menu"))
    return kb

@dp.callback_query_handler(text="add_balance", state="*")
async def process_add_balance(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_amounts[user_id] = "0"
    text = "<b>💰 ENTER CUSTOM AMOUNT</b>\nAmount: <b>₹0</b>\n\n<i>Use keypad below (Min: ₹1 | Max: ₹50,000):</i>"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=get_keypad_markup())
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=get_keypad_markup())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('kp_'), state="*")
async def process_keypad_action(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    action = callback_query.data.split('_')[1]
    current = user_amounts.get(user_id, "0")
    
    if action == "clear":
        current = "0"
    elif action == "back":
        current = current[:-1] if len(current) > 1 else "0"
    elif action == "confirm":
        amt = float(current)
        if amt < 1.0 or amt > 50000.0:
            await callback_query.answer("❌ Amount must be between ₹1 and ₹50,000!", show_alert=True)
            return
        
        upi_string = f"upi://pay?pa={UPI_ID}&pn=PG%20MODE%20STORE&am={current}&cu=INR"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(upi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = io.BytesIO()
        bio.name = 'qr.png'
        img.save(bio, 'PNG')
        bio.seek(0)
        
        qr_keyboard = InlineKeyboardMarkup(row_width=1)
        qr_keyboard.add(
            InlineKeyboardButton("🟢 Verify Payment", callback_data=f"verify_pay_{current}"),
            InlineKeyboardButton("🔙 Back", callback_data="add_balance")
        )
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        await bot.send_photo(chat_id=callback_query.message.chat.id, photo=InputFile(bio), caption=f"<b>🟢 UPI QR ACTIVE</b>\nScan & pay <b>₹{current}</b>\n\n👤 User ID: <code>{user_id}</code>", parse_mode="HTML", reply_markup=qr_keyboard)
        return
    else:
        current = action if current == "0" else (current + action if len(current) < 6 else current)
                
    user_amounts[user_id] = current
    text = f"<b>💰 ENTER CUSTOM AMOUNT</b>\nAmount: <b>₹{current}</b>\n\n<i>Use keypad below (Min: ₹1 | Max: ₹50,000):</i>"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=get_keypad_markup())
    except Exception:
        pass

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('verify_pay_'), state="*")
async def process_verify_payment(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    amt = callback_query.data.split('_')[2]
    
    await AdminStates.waiting_for_payment_proof.set()
    await state.update_data(verify_amount=amt)
    
    text = (
        "<b>📤 PAYMENT VERIFICATION</b>\n\n"
        "Please provide your **UTR ID** or **Payment Screenshot**."
    )
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu"))
    try:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)

@dp.message_handler(state=AdminStates.waiting_for_payment_proof, content_types=types.ContentTypes.ANY)
async def process_payment_proof_receive(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"
    full_name = message.from_user.full_name or "User"
    data = await state.get_data()
    amt = data.get("verify_amount", "0")
    
    proof_content = message.text or message.caption or "Payment Screenshot (Photo)"
    
    await message.reply("✅ <b>Payment Successful!</b>\n\nYour payment request has been successfully submitted and verified. Go to the profile option to check your balance.", parse_mode="HTML")
    
    try:
        admin_text = (
            f"🔔 <b>NEW PAYMENT PROOF RECEIVED!</b>\n\n"
            f"👤 <b>Name:</b> {full_name}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🏷️ <b>Username:</b> @{username}\n"
            f"💳 <b>UTR ID / Proof:</b> {proof_content}\n"
            f"💵 <b>Balance Adding Amount:</b> ₹{amt}"
        )
        if message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, parse_mode="HTML")
        else:
            await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception:
        pass
        
    await state.finish()
    
    db = load_db()
    is_admin = (user_id == ADMIN_ID)
    user_data = db["users"].get(str(user_id), {})
    user_bal = user_data.get("balance", 0.0)
    
    welcome_text = (
        f"<b>Welcome PG MODE STORE</b>\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏷️ <b>Username:</b> @{username}\n\n"
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
        f"✨ <b>Your Balance:</b> 💸 ₹{user_bal:.2f} 🌸\n"
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n\n"
        "👉 <b>Select an option from the menu below:</b>"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard(is_admin))

@dp.callback_query_handler(text="profile", state="*")
async def process_profile(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    db = load_db()
    user_data = db["users"].get(user_id, {})
    user_bal = user_data.get("balance", 0.0)
    user_tier = "RESELLER" if user_data.get("is_reseller", False) else "USER"
    profile_keyboard = InlineKeyboardMarkup(row_width=2)
    profile_keyboard.add(
        InlineKeyboardButton("🔑 Key History", callback_data="key_history"),
        InlineKeyboardButton("📥 Deposit History", callback_data="dep_history")
    )
    profile_keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    text = f"<b>🔥 YOUR PROFILE</b>\n\nID: {user_id}\nTier: {user_tier}\nBalance: ₹{user_bal:.2f}"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=profile_keyboard)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=profile_keyboard)

@dp.callback_query_handler(text="key_history", state="*")
async def process_key_history(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    db = load_db()
    user_keys = [k for k in db["keys_history"] if k["user_id"] == user_id]
    text = "<b>🔑 KEY HISTORY</b>\n\n" + ("No keys yet." if not user_keys else "\n".join([f"• {k['panel']}: <code>{k['key']}</code>" for k in user_keys[-5:]]))
    back_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="profile"))
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=back_kb)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=back_kb)

@dp.callback_query_handler(text="dep_history", state="*")
async def process_dep_history(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    db = load_db()
    user_deps = [d for d in db.get("deposit_history", []) if d.get("user_id") == user_id]
    text = "<b>📥 DEPOSIT HISTORY</b>\n\n" + ("No deposit records." if not user_deps else "\n".join([f"• ₹{d['amount']}" for d in user_deps[-5:]]))
    back_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="profile"))
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=back_kb)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=back_kb)

@dp.callback_query_handler(text="refer", state="*")
async def process_referral(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    text = (
        "<b>🔗 REFER AND EARN</b>\n\n"
        "Invite your friends using your unique referral link below. When they purchase any panel, you will instantly receive **5% commission** on their purchase amount added to your balance!\n\n"
        f"🔗 Your Referral Link:\n<code>{referral_link}</code>"
    )
    back_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=back_kb)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=back_kb)

@dp.callback_query_handler(text="daily_gift", state="*")
async def process_daily_gift(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    db = load_db()
    
    if user_id not in db["users"]:
        db["users"][user_id] = {"balance": 0.0, "last_gift_time": None}
    
    user_data = db["users"][user_id]
    last_gift_time_str = user_data.get("last_gift_time")
    now = datetime.datetime.now()
    
    if last_gift_time_str:
        last_gift_time = datetime.datetime.strptime(last_gift_time_str, "%Y-%m-%d %H:%M:%S")
        diff = now - last_gift_time
        if diff.total_seconds() < 86400:
            remaining_seconds = int(86400 - diff.total_seconds())
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            seconds = remaining_seconds % 60
            
            await callback_query.answer(
                f"⏳ Daily gift already claimed! Please wait {hours}h {minutes}m {seconds}s before claiming again.",
                show_alert=True
            )
            return

    gift_amount = round(random.uniform(0.01, 1.00), 2)
    db["users"][user_id]["balance"] += gift_amount
    db["users"][user_id]["last_gift_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
    save_db(db)
    
    gift_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    text = f"<b>🎁 DAILY GIFT CLAIMED!</b>\n\nYou won <b>₹{gift_amount}</b>!"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=gift_kb)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=gift_kb)

@dp.callback_query_handler(text="support", state="*")
async def process_support(callback_query: types.CallbackQuery):
    support_keyboard = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}"), InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    text = f"<b>🛠️ SUPPORT</b>\nContact: @{SUPPORT_USERNAME}"
    try:
        await bot.edit_message_text(text, chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, parse_mode="HTML", reply_markup=support_keyboard)
    except Exception:
        await callback_query.message.answer(text, parse_mode="HTML", reply_markup=support_keyboard)

@dp.callback_query_handler(text="main_menu", state="*")
async def back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    user_id = callback_query.from_user.id
    is_admin = (user_id == ADMIN_ID)
    db = load_db()
    user_data = db["users"].get(str(user_id), {})
    user_bal = user_data.get("balance", 0.0)
    full_name = user_data.get("full_name", "User")
    username = user_data.get("username", "N/A")
    
    welcome_text = (
        f"<b>Welcome PG MODE STORE</b>\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏷️ <b>Username:</b> @{username}\n\n"
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
        f"✨ <b>Your Balance:</b> 💸 ₹{user_bal:.2f} 🌸\n"
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n\n"
        "👉 <b>Select an option from the menu below:</b>"
    )
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    await bot.send_message(chat_id=callback_query.message.chat.id, text=welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard(is_admin))

if __name__ == '__main__':
    from aiogram import executor

    async def handle(request):
        return web.Response(text="PG MODE STORE Bot is active!")

    async def on_startup(dp):
        app = web.Application()
        app.router.add_get('/', handle)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

    print("Bot is running...")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)