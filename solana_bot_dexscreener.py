import requests
import time
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from datetime import datetime
import json
import os

# ============= YAPILANDIRMA =============
# GÜVENLIK: Token'lar environment variable'dan alınır
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Eğer environment variable yoksa hata ver
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID environment variables tanımlanmalı!")

# Normal Kriterler
MIN_VOLUME_5M = 100000         # 100K USD
MIN_MARKET_CAP = 50000         # 50K USD
MAX_MARKET_CAP = 10000000      # 10M USD
MIN_LIQUIDITY = 20000          # 20K USD

# Yaş Filtreleri
MAX_TOKEN_AGE_HOURS = 48       # 48 saat (2 gün)
ENABLE_AGE_FILTER = True       # Yaş filtresini aktif et

# Özel Alarm
HIGH_VOLUME_ALERT = True
HIGH_VOLUME_THRESHOLD = 500000 # 500K USD (5 dakikalık hacim)
MAX_AGE_FOR_HIGH_VOLUME = 24   # 24 saat

# Tarama
SCAN_INTERVAL = 60             # 60 saniye

# JSON kayıt
SAVE_TO_JSON = True
JSON_FILE = "scanned_tokens.json"

# Bildirilen tokenlar
notified_tokens = set()

# Büyük coinler
EXCLUDED_SYMBOLS = {'SOL', 'USDC', 'USDT', 'BONK', 'JTO', 'PYTH', 'WIF', 'JUP', 'ORCA', 'RAY', 'MSOL', 'WSOL', 'BAGS'}

# ============= DEXSCREENER FUNCTIONS =============

def get_dexscreener_profiles():
    """DexScreener Token Profiles"""
    try:
        print("🔍 DexScreener Profiles...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        response = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
            headers=headers,
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            solana_tokens = [t for t in data if t.get('chainId') == 'solana']
            
            if not solana_tokens:
                print(f"  ⚠️ Profiles: Solana token yok")
                return []
            
            print(f"  ✅ Profiles: {len(solana_tokens)} token")
            
            standardized = []
            for token in solana_tokens[:20]:
                try:
                    token_addr = token.get('tokenAddress', '')
                    if not token_addr:
                        continue
                    
                    pair_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}"
                    pair_resp = requests.get(pair_url, headers=headers, timeout=10)
                    
                    if pair_resp.status_code != 200:
                        time.sleep(0.3)
                        continue
                    
                    pairs = pair_resp.json().get('pairs', [])
                    if not pairs:
                        time.sleep(0.3)
                        continue
                    
                    pair = pairs[0]
                    base_token = pair.get('baseToken', {})
                    volume_data = pair.get('volume', {})
                    liquidity_data = pair.get('liquidity', {})
                    
                    created_at = pair.get('pairCreatedAt', 0)
                    age_hours = None
                    if created_at:
                        age_hours = (datetime.now().timestamp() * 1000 - created_at) / (1000 * 3600)
                    
                    standardized.append({
                        'address': token_addr,
                        'symbol': base_token.get('symbol', 'UNKNOWN'),
                        'name': base_token.get('name', 'Unknown'),
                        'market_cap': pair.get('marketCap', pair.get('fdv', 0)),
                        'volume_5m': volume_data.get('m5', 0) or 0,
                        'liquidity': liquidity_data.get('usd', 0) or 0,
                        'created_timestamp': created_at,
                        'age_hours': age_hours,
                        'price_usd': pair.get('priceUsd', 0) or 0,
                        'platform': 'dexscreener',
                        'url': f"https://dexscreener.com/solana/{token_addr}",
                        'dexscreener_url': f"https://dexscreener.com/solana/{token_addr}"
                    })
                    
                    time.sleep(0.3)
                    
                except:
                    continue
            
            return standardized
        else:
            print(f"  ⚠️ Profiles: HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"  ❌ Profiles hatası: {e}")
        return []


def get_dexscreener_sol_pairs():
    """DexScreener SOL Pairs"""
    try:
        print("🔍 DexScreener SOL Pairs...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        response = requests.get(
            "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112",
            headers=headers,
            timeout=20
        )
        
        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])
            solana_pairs = [p for p in pairs if p.get('chainId') == 'solana']
            
            print(f"  ✅ SOL Pairs: {len(solana_pairs)} pair")
            
            standardized = []
            for pair in solana_pairs:
                try:
                    base_token = pair.get('baseToken', {})
                    volume_data = pair.get('volume', {})
                    liquidity_data = pair.get('liquidity', {})
                    
                    created_at = pair.get('pairCreatedAt', 0)
                    age_hours = None
                    if created_at:
                        age_hours = (datetime.now().timestamp() * 1000 - created_at) / (1000 * 3600)
                    
                    standardized.append({
                        'address': base_token.get('address', ''),
                        'symbol': base_token.get('symbol', 'UNKNOWN'),
                        'name': base_token.get('name', 'Unknown'),
                        'market_cap': pair.get('marketCap', pair.get('fdv', 0)),
                        'volume_5m': volume_data.get('m5', 0) or 0,
                        'liquidity': liquidity_data.get('usd', 0) or 0,
                        'created_timestamp': created_at,
                        'age_hours': age_hours,
                        'price_usd': pair.get('priceUsd', 0) or 0,
                        'platform': 'dexscreener',
                        'url': f"https://dexscreener.com/solana/{base_token.get('address', '')}",
                        'dexscreener_url': f"https://dexscreener.com/solana/{base_token.get('address', '')}"
                    })
                except:
                    continue
            
            return standardized
        else:
            print(f"  ⚠️ SOL Pairs: HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"  ❌ SOL Pairs hatası: {e}")
        return []


# ============= UTILITY FUNCTIONS =============

def save_tokens_to_json(tokens, scan_number):
    """Token listesini JSON dosyasına kaydet"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
        json_path = os.path.join(script_dir, JSON_FILE)
        
        data = {
            "scan_info": {
                "scan_number": scan_number,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_tokens": len(tokens)
            },
            "tokens": tokens
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  💾 {len(tokens)} token JSON'a kaydedildi")
        
    except Exception as e:
        print(f"  ❌ JSON kayıt hatası: {e}")


def filter_tokens(tokens):
    """Kriterlere göre tokenları filtrele"""
    filtered = []
    
    for token in tokens:
        try:
            address = token.get('address', '')
            symbol = token.get('symbol', 'UNKNOWN')
            market_cap = token.get('market_cap', 0)
            volume_5m = token.get('volume_5m', 0)
            liquidity = token.get('liquidity', 0)
            age_hours = token.get('age_hours')
            
            if not address or address == '':
                continue
            
            if address in notified_tokens:
                continue
            
            if symbol in EXCLUDED_SYMBOLS:
                continue
            
            if ENABLE_AGE_FILTER and age_hours is not None:
                if age_hours > MAX_TOKEN_AGE_HOURS:
                    continue
            
            # ÖZEL ALARM: Yüksek hacim + genç token
            if HIGH_VOLUME_ALERT:
                if age_hours is not None and age_hours <= MAX_AGE_FOR_HIGH_VOLUME:
                    if volume_5m >= HIGH_VOLUME_THRESHOLD:
                        if market_cap >= MIN_MARKET_CAP and market_cap <= MAX_MARKET_CAP:
                            if liquidity >= MIN_LIQUIDITY:
                                filtered.append({
                                    'token': token,
                                    'type': 'high_volume'
                                })
                                notified_tokens.add(address)
                                continue
            
            # Normal kriterler
            if market_cap >= MIN_MARKET_CAP and market_cap <= MAX_MARKET_CAP:
                if volume_5m >= MIN_VOLUME_5M:
                    if liquidity >= MIN_LIQUIDITY:
                        filtered.append({
                            'token': token,
                            'type': 'normal'
                        })
                        notified_tokens.add(address)
                        
        except Exception as e:
            continue
    
    return filtered


def format_message(token_data, msg_type='normal'):
    """Telegram mesajı formatla"""
    try:
        token = token_data['token']
        
        address = token.get('address', 'N/A')
        symbol = token.get('symbol', 'UNKNOWN')
        name = token.get('name', 'Unknown')
        
        # Fiyat
        price = token.get('price_usd', 0)
        try:
            price_float = float(price)
            if price_float < 0.000001:
                price_str = f"${price_float:.10f}"
            elif price_float < 0.01:
                price_str = f"${price_float:.8f}"
            else:
                price_str = f"${price_float:.6f}"
        except:
            price_str = 'N/A'
        
        market_cap = token.get('market_cap', 0)
        volume_5m = token.get('volume_5m', 0)
        liquidity = token.get('liquidity', 0)
        
        # Yaş
        age_hours = token.get('age_hours')
        if age_hours is not None:
            if age_hours < 1:
                age_text = f"⚡ {int(age_hours * 60)} dakika"
            elif age_hours < 24:
                age_text = f"🔥 {int(age_hours)} saat"
            else:
                age_text = f"📅 {int(age_hours / 24)} gün"
        else:
            age_text = "Bilinmiyor"
        
        dexscreener_url = token.get('dexscreener_url', '')
        
        # Mesaj tipi
        if msg_type == 'high_volume':
            header = "🚨🔥 YÜKSEK HACİM ALARMI! 🔥🚨"
            alert_text = f"\n⚠️ *24 SAAT İÇİNDE ÇIKTI VE 5DK HACİM 500K$+!*\n"
        else:
            if volume_5m >= 500000:
                volume_emoji = "🔥"
            elif volume_5m >= 250000:
                volume_emoji = "🚀"
            else:
                volume_emoji = "💎"
            header = f"{volume_emoji} *YENİ SOLANA COIN!*"
            alert_text = ""
        
        message = f"""
{dexscreener_url}

{header}
{alert_text}
🏷️ *{name}* (${symbol})
💎 *Kaynak:* DexScreener
📍 `{address}`

💰 *Fiyat:* {price_str}
📊 *Market Cap:* ${market_cap:,.0f}
📈 *5dk Hacim:* ${volume_5m:,.0f}
💧 *Likidite:* ${liquidity:,.0f}

⏰ *Yaş:* {age_text}

🔗 [DexScreener]({dexscreener_url})

_{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}_
        """
        
        return message.strip()
        
    except Exception as e:
        print(f"❌ Mesaj hatası: {e}")
        return f"Token: {token_data['token'].get('symbol', 'N/A')}"


async def send_telegram_message(bot, chat_id, message):
    """Telegram mesaj gönder"""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
        return True
    except TelegramError as e:
        print(f"  ❌ Telegram: {e}")
        return False


# ============= MAIN =============

async def main():
    """Ana fonksiyon"""
    print("="*70)
    print("🚀 SOLANA BOT - DEXSCREENER ONLY")
    print("="*70)
    print(f"📡 Kaynak: DexScreener")
    print(f"\n📊 Kriterler:")
    print(f"   • 5dk Hacim: ${MIN_VOLUME_5M:,}+")
    print(f"   • Market Cap: ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,}")
    print(f"   • Likidite: ${MIN_LIQUIDITY:,}+")
    if ENABLE_AGE_FILTER:
        print(f"   • Max Yaş: {MAX_TOKEN_AGE_HOURS} saat")
    if HIGH_VOLUME_ALERT:
        print(f"\n🔥 Özel: {MAX_AGE_FOR_HIGH_VOLUME}s yaş / ${HIGH_VOLUME_THRESHOLD:,}+ hacim")
    print(f"\n⏰ Tarama: {SCAN_INTERVAL} saniye")
    if SAVE_TO_JSON:
        print(f"💾 JSON Kayıt: {JSON_FILE}")
    print("="*70)
    print()
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot_info = await bot.get_me()
        print(f"✅ Bot: @{bot_info.username}\n")
        
        startup_message = f"""
🤖 *SOLANA BOT AKTİF!*

✅ Bot başarıyla başlatıldı
📡 Kaynak: DexScreener
⏰ Tarama Aralığı: {SCAN_INTERVAL} saniye

📊 *Filtreleme Kriterleri:*
• 5dk Hacim: ${MIN_VOLUME_5M:,}+
• Market Cap: ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,}
• Likidite: ${MIN_LIQUIDITY:,}+
• Max Token Yaşı: {MAX_TOKEN_AGE_HOURS} saat

🔥 *Yüksek Hacim Özel Alert:*
• Token Yaşı: {MAX_AGE_FOR_HIGH_VOLUME} saat altı
• 5dk Hacim: ${HIGH_VOLUME_THRESHOLD:,}+

💎 Kriterlere uyan tokenlar otomatik olarak bu kanala gönderilecek!

_{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}_
        """
        
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=startup_message.strip(),
            parse_mode='Markdown'
        )
        print("📤 Başlangıç mesajı kanala gönderildi\n")
        
    except Exception as e:
        print(f"❌ Bot hatası: {e}")
        return
    
    scan_count = 0
    
    while True:
        try:
            scan_count += 1
            print(f"🔄 Tarama #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            all_tokens = []
            
            # 1. DexScreener Profiles
            profiles = get_dexscreener_profiles()
            if profiles:
                all_tokens.extend(profiles)
            time.sleep(2)
            
            # 2. DexScreener SOL Pairs
            sol_pairs = get_dexscreener_sol_pairs()
            if sol_pairs:
                all_tokens.extend(sol_pairs)
            
            if not all_tokens:
                print("⚠️ Hiç token bulunamadı")
                print(f"⏳ {SCAN_INTERVAL} saniye bekleniyor...\n")
                await asyncio.sleep(SCAN_INTERVAL)
                continue
            
            print(f"\n📊 Toplam {len(all_tokens)} token toplanıyor...")
            
            if SAVE_TO_JSON and all_tokens:
                save_tokens_to_json(all_tokens, scan_count)
            
            filtered = filter_tokens(all_tokens)
            
            if filtered:
                print(f"\n✅ {len(filtered)} token kriterleri karşılıyor!\n")
                
                for item in filtered:
                    msg_type = item['type']
                    message = format_message(item, msg_type)
                    
                    success = await send_telegram_message(bot, TELEGRAM_CHAT_ID, message)
                    if success:
                        token = item['token']
                        symbol = token.get('symbol', 'N/A')
                        
                        if msg_type == 'high_volume':
                            print(f"  🔥🔥 {symbol} - YÜKSEK HACİM gönderildi")
                        else:
                            print(f"  ✅ {symbol} gönderildi")
                    
                    await asyncio.sleep(2)
                
                print()
            else:
                print("\nℹ️ Kriterlere uygun token yok")
            
            print(f"\n⏳ {SCAN_INTERVAL} saniye bekleniyor...")
            print("-"*70)
            print()
            await asyncio.sleep(SCAN_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n🛑 Bot durduruldu")
            break
        except Exception as e:
            print(f"❌ Hata: {e}")
            print("⏳ 60 saniye bekleniyor...\n")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
