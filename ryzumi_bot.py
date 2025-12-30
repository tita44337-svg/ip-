import os
import telebot
import requests
import json
import re
import time
import logging
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

# ==============================================
# CONFIGURATION
# ==============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "0")

# API URLs
RYZUMI_API = "https://api.ryzumi.vip/api/tool/iplocation?ip="
IP_API = "http://ip-api.com/json/{ip}"

# Flask app for Railway
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ==============================================
# LOGGING
# ==============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================
# IP LOOKUP FUNCTION
# ==============================================
def lookup_ip(ip_address):
    """Lookup IP address"""
    try:
        # Try Ryzumi API
        response = requests.get(f"{RYZUMI_API}{ip_address}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'ipInfo' in data:
                info = data['ipInfo']
                return {
                    'success': True,
                    'ip': info.get('ip', ip_address),
                    'city': info.get('city', 'N/A'),
                    'region': info.get('region', 'N/A'),
                    'country': info.get('country', 'N/A'),
                    'location': info.get('loc', 'N/A'),
                    'org': info.get('org', 'N/A'),
                    'timezone': info.get('timezone', 'N/A')
                }
        
        # Fallback to ip-api.com
        response = requests.get(IP_API.format(ip=ip_address), timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'success': True,
                    'ip': data.get('query', ip_address),
                    'city': data.get('city', 'N/A'),
                    'region': data.get('regionName', 'N/A'),
                    'country': data.get('countryCode', 'N/A'),
                    'location': f"{data.get('lat', 'N/A')},{data.get('lon', 'N/A')}",
                    'org': data.get('org', 'N/A'),
                    'timezone': data.get('timezone', 'N/A')
                }
        
        return {'success': False, 'ip': ip_address, 'error': 'Lookup failed'}
    except Exception as e:
        return {'success': False, 'ip': ip_address, 'error': str(e)}

# ==============================================
# BOT COMMAND HANDLERS
# ==============================================
@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    user = message.from_user
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔍 Check IP", callback_data="check_ip"),
        InlineKeyboardButton("🌐 My IP", callback_data="my_ip"),
        InlineKeyboardButton("📊 Bulk Check", callback_data="bulk"),
        InlineKeyboardButton("⚡ Speed", callback_data="speed")
    )
    
    bot.send_message(
        message.chat.id,
        f"🤖 <b>RYZUMI IP LOCATOR BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👋 Hello {user.first_name}!\n\n"
        f"<b>Quick Usage:</b>\n"
        f"• Send any IP address\n"
        f"• <code>/ip 8.8.8.8</code>\n"
        f"• <code>/myip</code> - Your public IP\n"
        f"• <code>/bulk ip1 ip2 ip3</code>\n\n"
        f"<i>Powered by Ryzumi API • Hosted on Railway</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@bot.message_handler(commands=['ip'])
def ip_cmd(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "❌ <b>Usage:</b> <code>/ip [address]</code>")
            return
        
        ip = args[1].strip()
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            bot.reply_to(message, f"❌ Invalid IP: <code>{ip}</code>")
            return
        
        msg = bot.reply_to(message, f"🔍 Checking <code>{ip}</code>...")
        result = lookup_ip(ip)
        
        if result['success']:
            response = f"""
✅ <b>IP LOCATION FOUND</b>
━━━━━━━━━━━━━━━━━━
<b>IP Address:</b> <code>{result['ip']}</code>
<b>Location:</b> {result['city']}, {result['region']}
<b>Country:</b> {result['country']}
<b>ISP/Org:</b> {result['org']}
<b>Timezone:</b> {result['timezone']}
            """
            
            if result['location'] != 'N/A' and ',' in result['location']:
                lat, lon = result['location'].split(',')
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(
                    "🗺️ Google Maps", 
                    url=f"https://maps.google.com/?q={lat},{lon}"
                ))
                bot.edit_message_text(response, message.chat.id, msg.message_id, 
                                    parse_mode="HTML", reply_markup=keyboard)
            else:
                bot.edit_message_text(response, message.chat.id, msg.message_id, parse_mode="HTML")
        else:
            bot.edit_message_text(
                f"❌ Failed: <code>{ip}</code>\nError: {result['error']}",
                message.chat.id, msg.message_id, parse_mode="HTML"
            )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['myip'])
def myip_cmd(message):
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        user_ip = response.json()['ip']
        result = lookup_ip(user_ip)
        
        if result['success']:
            bot.reply_to(message,
                f"🌐 <b>Your Public IP:</b> <code>{user_ip}</code>\n"
                f"📍 Location: {result['city']}, {result['country']}\n"
                f"🔧 ISP: {result['org']}",
                parse_mode="HTML"
            )
        else:
            bot.reply_to(message, f"🌐 <b>Your IP:</b> <code>{user_ip}</code>")
    except:
        bot.reply_to(message, "❌ Cannot get IP")

@bot.message_handler(commands=['bulk'])
def bulk_cmd(message):
    try:
        ips = message.text.split()[1:5]  # Max 4 IPs
        if not ips:
            bot.reply_to(message, "❌ <b>Usage:</b> <code>/bulk ip1 ip2 ip3</code>")
            return
        
        msg = bot.reply_to(message, f"🔍 Processing {len(ips)} IPs...")
        results = []
        
        for ip in ips:
            if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
                results.append(lookup_ip(ip))
                time.sleep(0.3)
        
        response = "📊 <b>Bulk Results:</b>\n━━━━━━━━━━━━━━━━━━\n"
        for i, (ip, res) in enumerate(zip(ips, results), 1):
            if res['success']:
                response += f"{i}. ✅ {ip} - {res['city']}, {res['country']}\n"
            else:
                response += f"{i}. ❌ {ip} - Failed\n"
        
        bot.edit_message_text(response, message.chat.id, msg.message_id, parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    text = message.text.strip()
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
        msg = bot.reply_to(message, f"🔍 Checking <code>{text}</code>...")
        result = lookup_ip(text)
        
        if result['success']:
            bot.edit_message_text(
                f"📍 <b>{text}</b> → {result['city']}, {result['country']}\n"
                f"🔧 {result['org']}",
                message.chat.id, msg.message_id, parse_mode="HTML"
            )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "check_ip":
        bot.answer_callback_query(call.id, "Send me an IP address!")
    elif call.data == "my_ip":
        myip_cmd(call.message)
    elif call.data == "speed":
        start = time.time()
        lookup_ip("8.8.8.8")
        speed = (time.time() - start) * 1000
        bot.answer_callback_query(call.id, f"⚡ Speed: {speed:.0f}ms")

# ==============================================
# FLASK ROUTES FOR WEBHOOK
# ==============================================
@app.route('/')
def home():
    return "🤖 Ryzumi IP Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return ''
    return 'Bad Request', 400

@app.route('/health')
def health():
    return {'status': 'ok', 'time': datetime.now().isoformat()}

# ==============================================
# SETUP WEBHOOK
# ==============================================
def setup_webhook():
    webhook_url = os.environ.get('RAILWAY_STATIC_URL', '')
    if webhook_url:
        webhook_url += '/webhook'
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook set: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")

# ==============================================
# MAIN
# ==============================================
if __name__ == '__main__':
    # Check token
    if not BOT_TOKEN:
        print("\n" + "="*50)
        print("❌ ERROR: BOT_TOKEN not set!")
        print("\nSet environment variables:")
        print("BOT_TOKEN=your_bot_token_here")
        print("ADMIN_ID=your_telegram_id")
        print("\nGet token from @BotFather on Telegram")
        print("="*50)
        exit(1)
    
    # Setup webhook
    setup_webhook()
    
    # Start Flask
    port = int(os.environ.get('PORT', 8080))
    print(f"\n🚀 Bot starting on port {port}")
    print(f"🤖 Token: {BOT_TOKEN[:10]}...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("="*50)
    
    app.run(host='0.0.0.0', port=port)
