import discord
from discord.ext import commands, tasks
import ollama
import json
import os
import asyncio
from collections import deque
from datetime import datetime
import time

# Discord bot tokenini buraya ekleyin
DISCORD_TOKEN = 'Write Your Token Here'

# Ollama modelini çalıştırmak için gerekli ayarları yapın
OLLAMA_MODEL = 'tinydolphin:latest'  # Yerel olarak çalışan modelin adı

# JSON dosyalarının yolları
DATA_FILE = 'responses.json'
CHANNELS_FILE = 'channels.json'

# Discord istemcisi oluşturma
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Model promptu için ek talimat
PROMPT_INSTRUCTION = "Please provide a brief response, no longer than a sentence."

# Soru kuyruğu ve kilit
question_queue = deque()
processing = asyncio.Event()

def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {}

def save_data(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

data = load_data(DATA_FILE)
channels = load_data(CHANNELS_FILE)

async def process_queue():
    while True:
        if not question_queue:
            await asyncio.sleep(1)
            continue

        processing.set()
        user_input, message = question_queue.popleft()
        
        # Eğer mesajın geldiği kanal aktifse
        if str(message.channel.id) in channels:
            # Eğer daha önce bu soru sorulmuşsa, saklanan cevabı gönder
            if user_input in data:
                await message.channel.send(f"{message.author.mention} {data[user_input]}")
            else:
                # Ollama modeline kullanıcı girdisini gönderme
                try:
                    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": f"{PROMPT_INSTRUCTION} {user_input}"}])
                    if 'message' in response and 'content' in response['message']:
                        answer = response['message']['content']
                        await message.channel.send(f"{message.author.mention} {answer}")

                        # Soruyu ve cevabı JSON dosyasına kaydet
                        data[user_input] = answer
                        save_data(data, DATA_FILE)
                    else:
                        await message.channel.send(f"{message.author.mention} Yanıtta bir sorun var veya modelden beklenen cevap alınamadı.")
                except Exception as e:
                    print(f"Ollama ile bağlantıda bir hata oluştu: {e}")
                    await message.channel.send(f"{message.author.mention} Bunu bilmiyorum.")
        
        processing.clear()
        await asyncio.sleep(1)  # Küçük bir bekleme, yoğun işlemler için

status_index = 0  # Durumlar arasında geçiş yapacak indeks

@tasks.loop(seconds=10)
async def status_update():
    global status_index
    toplam_kullanici = sum(guild.member_count for guild in client.guilds)
    toplam_sunucu = len(client.guilds)
    
    statuses = [
        f"Bot açık: {format_timedelta(datetime.now() - start_time)}",
        f"Toplam Kullanıcı: {toplam_kullanici}",
        f"Toplam Sunucu: {toplam_sunucu}",
        "Version Alpha",
        "Made by Gökhan Özen",
        "Beni etiketle ve sorunu sor!",
        "Anderson Hosting güvencesiyle!",
        "Llama3.1 my beloved <3",
        "Geliştirilmiş 'NonAI' sistemi.",
        "!openchat ile beni başlatın.",
    ]
    current_status = statuses[status_index]
    await client.change_presence(activity=discord.Game(name=current_status))
    status_index = (status_index + 1) % len(statuses)  # İndeksi döngüye al

def format_timedelta(td):
    """Verilen timedelta objesini gün/saat/dakika/saniye formatında döndürür."""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}g {hours}s {minutes}d {seconds}s"

@client.event
async def on_ready():
    global start_time
    print(f'{client.user} olarak giriş yapıldı.')
    # Kuyruk işleyiciyi başlat
    client.loop.create_task(process_queue())
    status_update.start()
    start_time = datetime.now()  # Botun başlama zamanı

@client.event
async def on_message(message):
    # Botun kendisiyle konuşmasını önlemek için
    if message.author == client.user:
        return

    # Komutları kontrol et
    if message.content.startswith('!ping'):
        start_time = time.time()
        msg = await message.channel.send("Ping...")
        end_time = time.time()

        latency = client.latency * 1000  # ms cinsinden
        response_time = (end_time - start_time) * 1000  # ms cinsinden
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        await msg.edit(content=f"""
**Botun Yanıt Süresi:**
- Bot Yanıt Süresi: {latency:.2f} ms
- API Yanıt Süresi: {response_time:.2f} ms
- Güncel Zaman: {current_time}
- Sunucu Ping Değeri: {int(latency)} ms
""")
        return

    if message.content.startswith('!openchat'):
        channels[str(message.channel.id)] = 'active'
        save_data(channels, CHANNELS_FILE)
        await message.channel.send("Bu kanalda sohbet açıldı. Beni etiketleyerek istediğinizi sorun!")
        return

    if message.content.startswith('!closechat'):
        channels.pop(str(message.channel.id), None)
        save_data(channels, CHANNELS_FILE)
        await message.channel.send("Bu kanalda sohbet kapatıldı.")
        return

    # Bot etiketlendiğinde tepki vermesi için
    if client.user.mentioned_in(message):
        user_input = message.content.replace(f'<@{client.user.id}>', '').strip()

        # Eğer mesajın geldiği kanal aktifse
        if str(message.channel.id) in channels:
            # Soruyu kuyruğa ekle
            question_queue.append((user_input, message))

            # Eğer işlem zaten devam ediyorsa, kuyruğa eklemeye devam et
            if not processing.is_set():
                processing.set()
                await process_queue()

client.run(DISCORD_TOKEN)
