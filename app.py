import requests
import time

# Telegram Configuration (REPLACE WITH YOUR VALUES)
TELEGRAM_BOT_TOKEN = "7936691138:AAEPaIh1vApmAegWFV3qT8e_1dGCmXmH5G4"
TELEGRAM_CHAT_ID = "5549286576"

# Binance timeframes (excluding 1m, 3m, 5m)
ALL_TIMEFRAMES = [
    "15m", "30m",
    "1h", "2h", "4h", "8h", "1d", "1w"
]

# --------------------- CORE FUNCTIONS ---------------------
def get_usdt_pairs():
    """Fetch all active USDT trading pairs."""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    try:
        response = requests.get(url)
        data = response.json()
        return [
            symbol['symbol']
            for symbol in data['symbols']
            if symbol['symbol'].endswith('USDT')
            and symbol['status'] == 'TRADING'
            and symbol['quoteAsset'] == 'USDT'
        ]
    except Exception as e:
        print(f"Error fetching pairs: {e}")
        return []

def parse_candle_value(value, default=0.0):
    """Safely parse candle data."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def find_reference_group(candles):
    """Find 1-3 green candles with ascending highs."""
    groups = []
    for i in range(len(candles)):
        for size in [1, 2, 3]:
            if i + size > len(candles):
                continue
            # Check green candles
            is_green = True
            for j in range(i, i + size):
                if len(candles[j]) < 5:
                    is_green = False
                    break
                open_price = parse_candle_value(candles[j][1])
                close_price = parse_candle_value(candles[j][4])
                if close_price <= open_price:
                    is_green = False
                    break
            if not is_green:
                continue
            # Check ascending highs
            ascending = True
            if size > 1:
                for j in range(i, i + size - 1):
                    current_high = parse_candle_value(candles[j][2])
                    next_high = parse_candle_value(candles[j+1][2])
                    if next_high <= current_high:
                        ascending = False
                        break
            if not ascending:
                continue
            # Calculate group metrics
            highs = [parse_candle_value(candles[j][2]) for j in range(i, i + size)]
            lows = [parse_candle_value(candles[j][3]) for j in range(i, i + size)]
            groups.append({
                "start": i,
                "size": size,
                "max_high": max(highs),
                "min_low": min(lows)
            })
    return max(groups, key=lambda x: x["max_high"]) if groups else None

def validate_conditions(reference, candles):
    """Check all validation rules."""
    if not reference:
        return False
    subsequent_start = reference["start"] + reference["size"]
    if subsequent_start + 3 > len(candles):
        return False
    
    midpoint = (reference["max_high"] + reference["min_low"]) / 2
    for i in range(subsequent_start, len(candles)):
        candle_high = parse_candle_value(candles[i][2])
        candle_low = parse_candle_value(candles[i][3])
        if candle_high > reference["max_high"] or candle_low < midpoint:
            return False
    
    last_high = parse_candle_value(candles[-1][2])
    return last_high >= reference["max_high"] * 0.90

def analyze_pair(pair, timeframe):
    """Analyze a single pair in a specific timeframe."""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": pair, "interval": timeframe, "limit": 15}
        )
        if response.status_code != 200:
            return False
        candles = response.json()
        if len(candles) < 15 or not isinstance(candles, list):
            return False
        
        reference = find_reference_group(candles)
        return validate_conditions(reference, candles)
    except Exception as e:
        print(f"Error analyzing {pair} ({timeframe}): {str(e)}")
        return False

# --------------------- TELEGRAM INTEGRATION ---------------------
def send_to_telegram(message):
    """Send message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

# --------------------- MAIN EXECUTION ---------------------
if __name__ == "__main__":
    all_pairs = get_usdt_pairs()  # Now properly defined
    if not all_pairs:
        exit("No USDT pairs found.")
    
    results = {}
    
    print(f"\nAnalyzing {len(all_pairs)} pairs across all timeframes...")
    send_to_telegram(f"🚀 Starting analysis of {len(all_pairs)} pairs...")
    
    for idx, pair in enumerate(all_pairs, 1):
        pair_results = []
        for timeframe in ALL_TIMEFRAMES:
            if analyze_pair(pair, timeframe):
                pair_results.append(timeframe)
            time.sleep(1)
        
        if pair_results:
            results[pair] = pair_results
            message = f"✅ *{pair}* valid in:\n" + "\n".join(pair_results)
            send_to_telegram(message)
        
        if idx % 100 == 0:
            send_to_telegram(f"📊 Progress: {idx}/{len(all_pairs)} pairs checked")
    
    final_message = "🔥 *Final Results* 🔥\n\n"
    for pair, timeframes in results.items():
        final_message += f"*{pair}*:\n" + "\n".join(timeframes) + "\n\n"
    
    if not results:
        final_message = "❌ No valid pairs found."
    
    send_to_telegram(final_message)
    print("\n✅ Analysis complete. Results sent to Telegram.")
