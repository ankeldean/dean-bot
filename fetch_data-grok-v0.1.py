import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import logging
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fetch_data.log'),
        logging.StreamHandler()
    ]
)

# Initialize exchange
exchange = ccxt.mexc()

# Settings
symbol = 'SOL/USDT'
timeframe = '5m'
months = 11
output_filename = f"{symbol.replace('/', '')}_{timeframe}_{months}month.csv"
checkpoint_filename = f"{symbol.replace('/', '')}_{timeframe}_checkpoint.csv"

# Define the time range
end_time_ms = exchange.milliseconds()
start_time_ms = end_time_ms - months * 30 * 24 * 60 * 60 * 1000  # Approx 11 months

all_ohlcv = []
chunk_duration = timedelta(days=30)  # Fetch in 30-day chunks
current_fetch_start_dt = datetime.utcfromtimestamp(start_time_ms / 1000)
end_dt = datetime.utcfromtimestamp(end_time_ms / 1000)

logging.info(f"Fetching {timeframe} candles for {months} months for {symbol} from {current_fetch_start_dt} to {end_dt}")

while current_fetch_start_dt < end_dt:
    fetch_end_dt = min(current_fetch_start_dt + chunk_duration, end_dt)
    fetch_start_ms = int(current_fetch_start_dt.timestamp() * 1000)
    fetch_end_ms = int(fetch_end_dt.timestamp() * 1000)

    logging.info(f"Fetching period: {current_fetch_start_dt.strftime('%Y-%m-%d')} to {fetch_end_dt.strftime('%Y-%m-%d')}")

    try:
        ohlcv_chunk = exchange.fetch_ohlcv(symbol, timeframe, since=fetch_start_ms, limit=1000)
        if ohlcv_chunk:
            logging.info(f"Fetched {len(ohlcv_chunk)} candles.")
            all_ohlcv.extend(ohlcv_chunk)
            
            # Check for more data in the chunk
            last_timestamp = ohlcv_chunk[-1][0]
            while last_timestamp < fetch_end_ms - 300_000:  # 5-minute candles
                time.sleep(1)
                logging.info(f"Fetching more data from: {pd.to_datetime(last_timestamp, unit='ms')}")
                additional_ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=last_timestamp + 300_000, limit=1000)
                if additional_ohlcv:
                    all_ohlcv.extend(additional_ohlcv)
                    last_timestamp = additional_ohlcv[-1][0]
                    logging.info(f"Fetched {len(additional_ohlcv)} more candles. Total: {len(all_ohlcv)}.")
                else:
                    logging.info("No more data in this sub-chunk.")
                    break

            # Save checkpoint
            if all_ohlcv:
                df_temp = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], unit='ms')
                df_temp.to_csv(checkpoint_filename, index=False)
                logging.info(f"Saved checkpoint to {checkpoint_filename}")

        else:
            logging.warning(f"No data received for period {current_fetch_start_dt.strftime('%Y-%m-%d')}.")

    except ccxt.RateLimitExceeded as e:
        logging.error(f"Rate Limit Exceeded: {e}. Sleeping for 60 seconds...")
        time.sleep(60)
    except ccxt.NetworkError as e:
        logging.error(f"Network Error: {e}. Sleeping for 30 seconds...")
        time.sleep(30)
    except ccxt.ExchangeError as e:
        logging.error(f"Exchange Error: {e}. Skipping period.")
        current_fetch_start_dt += chunk_duration
        continue
    except Exception as e:
        logging.error(f"Unexpected error: {e}. Skipping period.")
        current_fetch_start_dt += chunk_duration
        continue

    time.sleep(1)  # Respect rate limits
    current_fetch_start_dt += chunk_duration

# Convert to DataFrame and validate
if all_ohlcv:
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Validate data
    df = df.drop_duplicates(subset=['timestamp'], keep='last')
    df = df.sort_values('timestamp')
    expected_interval = timedelta(minutes=5)
    time_diffs = df['timestamp'].diff().dropna()
    gaps = time_diffs[time_diffs > expected_interval]
    if not gaps.empty:
        logging.warning(f"Found {len(gaps)} gaps in data larger than {expected_interval}.")
    
    # Save final data
    df.to_csv(output_filename, index=False)
    logging.info(f"Data saved to {output_filename}. Total candles: {len(df)}")
else:
    logging.error("No data fetched.")
