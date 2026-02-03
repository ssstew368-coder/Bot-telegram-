import json
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ────────────────────────────────────────────────
# HEALTH CHECK SERVER (pour tromper les plateformes PaaS)
# ────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Bot running")

def start_health_server():
    try:
        server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
        logging.info("Health check server démarré sur port 8080")
        server.serve_forever()
    except Exception as e:
        logging.error(f"Erreur health server: {e}")

# Lance le health server en thread daemon
threading.Thread(target=start_health_server, daemon=True).start()

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))  # Mets 0 par défaut pour sécurité

if not TOKEN or ADMIN_ID == 0:
    raise ValueError("TELEGRAM_TOKEN et ADMIN_ID doivent être définis dans les variables d'environnement !")

LICENSE_FILE = 'licenses.json'
TON_ADDRESS = 'UQD6Px7DIkcRoI9zRyGumPXEPxh7-fc7G7tBv5I10Zso5OWE'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

PLANS = {
    '2jours': {'ariary': 1000, 'usdt': 0.25, 'days': 2, 'label': '🌟 2 jours'},
    '5jours': {'ariary': 2500, 'usdt': 0.60, 'days': 5, 'label': '🚀 5 jours'},
    '15jours': {'ariary': 5000, 'usdt': 1.25, 'days': 15, 'label': '💎 15 jours'}
}

# ────────────────────────────────────────────────
# GESTION FICHIER LICENCES (attention : non persistant sur la plupart des PaaS !)
# ────────────────────────────────────────────────
def load_licenses():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lecture JSON: {e}")
            return {}
    return {}

def save_licenses(data):
    try:
        with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Erreur sauvegarde JSON: {e}")

# ────────────────────────────────────────────────
# CLAVIERS
# ────────────────────────────────────────────────
def get_bottom_keyboard():
    kb = [
        [KeyboardButton("🛒 Acheter licence"), KeyboardButton("🔑 Vérifier clé")],
        [KeyboardButton("❓ Aide"), KeyboardButton("📩 Contact admin")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=False)

def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 2 jours - 1.000 Ar", callback_data='plan_2jours')],
        [InlineKeyboardButton("🚀 5 jours - 2.500 Ar", callback_data='plan_5jours')],
        [InlineKeyboardButton("💎 15 jours - 5.000 Ar", callback_data='plan_15jours')],
        [InlineKeyboardButton("❓ Aide", callback_data='help')]
    ])

# ────────────────────────────────────────────────
# HANDLERS
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bienvenue sur SmmKey_bot ! 😊",
        reply_markup=get_bottom_keyboard()
    )
    await update.message.reply_text("Choisis ton abonnement :", reply_markup=get_main_menu_keyboard())

async def show_main_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.callback_query.message.edit_text(
        "Choisis ton abonnement :",
        reply_markup=get_main_menu_keyboard()
    )

async def navigation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'back_menu':
        await show_main_menu_cb(update, context)
        return

    if data == 'help':
        text = "📖 Aide :\n1. Choisis un plan\n2. Paie par MVola ou Crypto\n3. Envoie la photo du paiement ici\n4. Attends la validation"
        kb = [[InlineKeyboardButton("🔙 Retour", callback_data='back_menu')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith('plan_'):
        plan_code = data.split('_')[1]
        context.user_data['plan'] = plan_code
        details = PLANS[plan_code]
        
        kb = [
            [InlineKeyboardButton("💸 MVola", callback_data='pay_mvola')],
            [InlineKeyboardButton("🔗 Binance (TON)", callback_data='pay_usdt')],
            [InlineKeyboardButton("🔙 Retour", callback_data='back_menu')]
        ]
        await query.edit_message_text(
            f"✅ Plan : {details['label']}\nPrix : {details['ariary']} Ar ou {details['usdt']} USDT\nChoisis le moyen de paiement :",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if data.startswith('pay_'):
        plan = context.user_data.get('plan')
        if not plan:
            await query.edit_message_text("Session expirée. Recommencez.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]]))
            return

        if data == 'pay_mvola':
            msg = f"Envoyez {PLANS[plan]['ariary']} Ar par MVola au :\n038 51 103 48 (Haritina Steven)\n\n📸 Envoyez ensuite la capture d'écran ici."
        else:
            msg = f"Envoyez {PLANS[plan]['usdt']} USDT (Réseau TON) à :\n`{TON_ADDRESS}`\n\n📸 Envoyez ensuite la capture d'écran ici."

        kb = [[InlineKeyboardButton("🔙 Retour", callback_data=f'plan_{plan}')]]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['proof_id'] = update.message.message_id
        
        kb = [
            [InlineKeyboardButton("✅ Envoyer à l'admin", callback_data='confirm_proof')],
            [InlineKeyboardButton("❌ Annuler", callback_data='cancel_proof')]
        ]
        await update.message.reply_text(
            "Capture reçue. Envoyer à l'admin pour validation ?",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def proof_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'cancel_proof':
        await query.edit_message_text("Annulé.")
        await show_main_menu_cb(update, context)
        return

    if data == 'confirm_proof':
        user = query.from_user
        plan = context.user_data.get('plan', 'Inconnu')
        proof_id = context.user_data.get('proof_id')

        if not proof_id:
            await query.edit_message_text("Erreur : Image introuvable.")
            return

        try:
            await context.bot.forward_message(chat_id=ADMIN_ID, from_chat_id=user.id, message_id=proof_id)
            
            kb_admin = [
                [InlineKeyboardButton("✅ Valider", callback_data=f'val_{user.id}_{plan}')],
                [InlineKeyboardButton("❌ Refuser", callback_data=f'ref_{user.id}_{plan}')]
            ]
            
            user_info = f"@{user.username}" if user.username else f"ID: {user.id}"
            
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 NOUVELLE PREUVE !\n👤 User: {user_info}\n📦 Plan: {plan}\nValider ou Refuser ci-dessous :",
                reply_markup=InlineKeyboardMarkup(kb_admin)
            )
            
            await query.edit_message_text("✅ Envoyé ! L'admin va vérifier. Vous recevrez la clé ici.")
            
        except Exception as e:
            logger.error(f"Erreur envoi preuve admin: {e}")
            await query.edit_message_text(f"Erreur technique: {str(e)}")

async def admin_decision_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return

    data = query.data
    parts = data.split('_')
    action = parts[0]
    uid = int(parts[1])
    plan = parts[2]

    if action == 'ref':
        try:
            await context.bot.send_message(uid, "❌ Paiement refusé. Contactez l'admin.")
            await query.edit_message_text(f"Refusé pour {uid}.")
        except:
            await query.edit_message_text(f"Refusé (impossible de notifier l'user).")

    if action == 'val':
        days = PLANS.get(plan, {'days': 2})['days']
        key = f"KEY-{uid}-{datetime.now().strftime('%d%H%M')}"
        exp = datetime.now() + timedelta(days=days)
        
        licenses = load_licenses()
        licenses[str(uid)] = {'key': key, 'expiration': exp.isoformat(), 'plan': plan}
        save_licenses(licenses)

        try:
            await context.bot.send_message(uid, f"🎉 Paiement validé !\nVotre clé expire le {exp.strftime('%d/%m/%Y')}")
            kb_copy = [[InlineKeyboardButton("Vérifier", callback_data=f'check_this_{key}')]]
            await context.bot.send_message(uid, f"`{key}`", parse_mode='MarkdownV2', reply_markup=InlineKeyboardMarkup(kb_copy))
            
            await query.edit_message_text(f"✅ Validé pour {uid}.\nClé : {key}")
        except Exception as e:
            logger.error(f"Erreur envoi clé user: {e}")
            await query.edit_message_text(f"Erreur envoi user: {str(e)}")

async def check_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace('check_this_', '')
    licenses = load_licenses()
    user_id = str(query.from_user.id)
    
    user_license = licenses.get(user_id, {})
    if user_license.get('key') == key:
        exp = datetime.fromisoformat(user_license['expiration'])
        status = "✅ Valide" if exp > datetime.now() else "❌ Expirée"
        await query.message.reply_text(f"État : {status} (Jusqu'au {exp.strftime('%d/%m/%Y')})")
    else:
        await query.message.reply_text("❌ Clé invalide ou n'appartient pas à cet utilisateur.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🛒 Acheter licence":
        await start(update, context)
    elif text == "📩 Contact admin":
        await update.message.reply_text("@haritina08")
    elif text == "❓ Aide":
        await update.message.reply_text("Utilisez les boutons pour acheter.")
    elif text == "🔑 Vérifier clé":
        await update.message.reply_text("Utilisez le bouton 'Vérifier' reçu avec votre clé.")

# ────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(navigation_handler, pattern='^(plan_|pay_|help|back_menu)'))
    app.add_handler(CallbackQueryHandler(proof_action_handler, pattern='^(confirm_proof|cancel_proof)'))
    app.add_handler(CallbackQueryHandler(admin_decision_handler, pattern='^(val_|ref_)'))
    app.add_handler(CallbackQueryHandler(check_key_handler, pattern='^check_this_'))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot démarré...")
    logging.info("Bot polling lancé")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # Évite les conflits polling au redémarrage
    )

if __name__ == '__main__':
    main()
