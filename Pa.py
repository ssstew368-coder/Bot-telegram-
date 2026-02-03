import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters

# Configuration
TOKEN = '8308177711:AAGTg7xj0pnZYAJHOKBv3rFthZooeWiIvKQ'
ADMIN_ID = 8101911097  # Ton ID admin
ADMIN_USERNAME = '@haritina08'

# Prix et durées
PLANS = {
    '2jours': {'ariary': 1000, 'usdt': 0.25, 'days': 2},
    '5jours': {'ariary': 2500, 'usdt': 0.60, 'days': 5},
    '15jours': {'ariary': 5000, 'usdt': 1.25, 'days': 15}
}

# Fichier pour stocker les licences (persistant sur Pella)
LICENSE_FILE = 'licenses.json'

# Adresse TON pour USDT (remplace par ta vraie adresse TON pour USDT)
TON_ADDRESS = 'EQXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'  # À CHANGER PAR TA VRAIE ADRESSE TON

# Fonctions utilitaires
def load_licenses():
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_licenses(licenses):
    with open(LICENSE_FILE, 'w') as f:
        json.dump(licenses, f)

# Handler pour /start
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("2 jours - 1.000 Ar / 0.25 USDT", callback_data='plan_2jours')],
        [InlineKeyboardButton("5 jours - 2.500 Ar / 0.60 USDT", callback_data='plan_5jours')],
        [InlineKeyboardButton("15 jours - 5.000 Ar / 1.25 USDT", callback_data='plan_15jours')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Bienvenue sur SmmKey_bot ! Choisis ton abonnement pour grr.py :",
        reply_markup=reply_markup
    )

# Handler pour choix du plan
async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('plan_'):
        plan = data.split('_')[1]
        context.user_data['plan'] = plan
        keyboard = [
            [InlineKeyboardButton("Payer via MVola", callback_data='pay_mvola')],
            [InlineKeyboardButton("Payer via Binance USDT (TON)", callback_data='pay_usdt')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Tu as choisi {plan}. Choisis la méthode de paiement :",
            reply_markup=reply_markup
        )
    elif data == 'pay_mvola':
        plan = context.user_data['plan']
        amount = PLANS[plan]['ariary']
        await query.edit_message_text(
            f"Pour {plan} :\n"
            f"Envoye {amount} Ar sur MVola : 038 51 103 48 (Haritina Steven)\n\n"
            "Ensuite, envoie-moi la preuve de paiement (photo du reçu) ici.\n"
            "Inclue ton username Telegram dans le message."
        )
        context.user_data['payment_method'] = 'mvola'
    elif data == 'pay_usdt':
        plan = context.user_data['plan']
        amount = PLANS[plan]['usdt']
        user_id = query.from_user.id
        memo = f"Commande_{user_id}_{plan}"  # Memo unique pour traçabilité
        await query.edit_message_text(
            f"Pour {plan} :\n"
            f"Envoye {amount} USDT sur TON à : {TON_ADDRESS}\n"
            f"Utilise ce memo/TXID : {memo}\n\n"
            "Ensuite, envoie-moi la preuve de paiement (screenshot Binance/TON) ici.\n"
            "Inclue ton username Telegram dans le message."
        )
        context.user_data['payment_method'] = 'usdt'

# Handler pour recevoir les preuves de paiement (photos ou textes)
async def handle_proof(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"
    plan = context.user_data.get('plan', 'inconnu')
    method = context.user_data.get('payment_method', 'inconnu')

    # Forward le message entier à l'admin
    await update.message.forward(chat_id=ADMIN_ID)
    # Envoie un message supplémentaire à l'admin avec infos
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Nouvelle preuve de {username} (ID: {user_id}) pour {plan} via {method}.\n"
             f"Utilise /confirmer {user_id} {plan} pour valider\n"
             f"Ou /refuser {user_id} raison pour refuser"
    )
    await update.message.reply_text("Preuve envoyée à l'admin. Attends la confirmation !")

# Commande /confirmer (seulement pour admin)
async def confirmer(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /confirmer user_id plan (ex: /confirmer 123456789 15jours)")
        return
    user_id = int(args[0])
    plan = args[1]
    if plan not in PLANS:
        await update.message.reply_text("Plan invalide.")
        return

    # Génère une clé simple (tu pourras la rendre plus secure plus tard)
    key = f"KEY_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    expiration = datetime.now() + timedelta(days=PLANS[plan]['days'])

    licenses = load_licenses()
    licenses[str(user_id)] = {'key': key, 'expiration': expiration.isoformat()}
    save_licenses(licenses)

    await context.bot.send_message(
        chat_id=user_id,
        text=f"Paiement validé ! Voici ta clé pour {plan} : {key}\n"
             f"Expire le : {expiration.strftime('%d/%m/%Y')}\n"
             f"Utilise-la dans grr.py."
    )
    await update.message.reply_text(f"Clé envoyée à l'utilisateur {user_id}.")

# Commande /refuser (seulement pour admin)
async def refuser(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /refuser user_id raison (ex: /refuser 123456789 Paiement invalide)")
        return
    user_id = int(args[0])
    raison = ' '.join(args[1:])
    await context.bot.send_message(
        chat_id=user_id,
        text=f"Paiement refusé : {raison}\nContacte l'admin si erreur."
    )
    await update.message.reply_text(f"Refus envoyé à l'utilisateur {user_id}.")

# Commande /check pour vérifier une clé (optionnel, pour les users)
async def check(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Usage: /check ta_clé")
        return
    key = args[0]
    user_id = update.message.from_user.id
    licenses = load_licenses()
    if str(user_id) in licenses and licenses[str(user_id)]['key'] == key:
        exp = datetime.fromisoformat(licenses[str(user_id)]['expiration'])
        if exp > datetime.now():
            await update.message.reply_text(f"Clé valide jusqu'au {exp.strftime('%d/%m/%Y')}.")
        else:
            await update.message.reply_text("Clé expirée.")
    else:
        await update.message.reply_text("Clé invalide.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_proof))  # Capture preuves
    app.add_handler(CommandHandler("confirmer", confirmer))
    app.add_handler(CommandHandler("refuser", refuser))
    app.add_handler(CommandHandler("check", check))

    app.run_polling()

if __name__ == '__main__':
    main()