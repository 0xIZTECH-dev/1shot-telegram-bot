require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');

const bot = new TelegramBot(process.env.TELEGRAM_BOT_TOKEN, { polling: true });

console.log("🤖 Bot çalışıyor, Telegram'dan /start komutunu bekliyor...");

bot.onText(/\/start/, (msg) => {
  console.log("📩 /start komutu alındı.");
  bot.sendMessage(msg.chat.id, "Bot başarıyla çalışıyor 🎉");
});
