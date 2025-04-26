# START backtest.py

# Filename: backtest.py
# Version: 2.15 (2025-04-27) - Widened SL, added volume confirmation, allowed multiple positions
# Description: Backtest SOL/USDT 5m trading strategy with RSI, MACD, ATR-based SL/TP

import pandas as pd
import logging
import sys
from datetime import datetime
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

# Parameters
rsi_oversold = 12
min_hist_threshold = -5.0
fee_percent = 0.075
slippage_factor = 0.999
atr_sl_multiplier = 0.25  # For ~1:20 SL:TP ratio
atr_tp_multiplier = 5.0  # For ~1:20 SL:TP ratio
risk_per_trade = 0.05
min_order_size = 0.0005
max_hold_candles = 60
leverage = 2
initial_balance = 10.0
breakeven_atr = None  # Disable breakeven adjustment
trailing_sl_atr = None  # Disable trailing SL
trailing_tp_atr = None  # Not used (fixed TP)
min_atr = 0.01  # Minimum ATR to prevent small values
max_positions = 3  # Allow up to 3 open positions
volume_sma_period = 20  # For volume confirmation

def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            logger.error("Missing required columns in CSV")
            sys.exit(1)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Validate price and volume data
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if df[col].le(0).any():
                logger.error(f"Negative or zero {col} values")
                sys.exit(1)
        if df['volume'].lt(0).any():
            logger.error("Negative volume values")
            sys.exit(1)
        # Validate high/low/close relationships
        if (df['high'] < df['low']).any() or (df['close'] > df['high']).any() or (df['close'] < df['low']).any():
            logger.error("High/Low/Close relationship violation")
            sys.exit(1)
        logger.info(f"Loaded {len(df)} rows from {file_path}")
        return df
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        sys.exit(1)

def calculate_indicators(df):
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)  # Prevent division by zero
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']
    
    # ATR
    df['tr'] = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # Volume SMA
    df['volume_sma'] = df['volume'].rolling(window=volume_sma_period).mean()
    
    # Log indicator stats
    logger.info(f"Raw RSI range: {df['rsi'].min():.2f} to {df['rsi'].max():.2f}")
    logger.info(f"Raw MACD range: {df['macd'].min():.4f} to {df['macd'].max():.4f}")
    logger.info(f"Raw Histogram range: {df['hist'].min():.4f} to {df['hist'].max():.4f}")
    logger.info(f"Raw ATR range: {df['atr'].min():.4f} to {df['atr'].max():.4f}")
    logger.info(f"Raw Volume SMA range: {df['volume_sma'].min():.2f} to {df['volume_sma'].max():.2f}")
    
    # Log NaN counts
    nan_counts = df[['rsi', 'macd', 'signal', 'hist', 'atr', 'volume_sma']].isna().sum()
    logger.info(f"NaN counts: {nan_counts.to_dict()}")
    
    # Filter invalid RSI
    invalid_rsi = df[df['rsi'] < 1.0]
    if not invalid_rsi.empty:
        logger.warning(f"Found {len(invalid_rsi)} rows with RSI < 1.0: {invalid_rsi['rsi'].to_list()}")
        df = df[df['rsi'] >= 1.0]
    
    logger.info(f"Rows after RSI filtering: {len(df)}")
    df = df.reset_index(drop=True)  # Reset index
    return df

def run_backtest(df):
    balance = initial_balance
    positions = []
    trade_history = []
    usdt_balance = initial_balance
    sol_balance = 0.0
    trades = 0
    wins = 0
    rsi_below_threshold_count = 0
    partial_condition_count = 0
    
    # Clear partial conditions file
    with open('partial_conditions.txt', 'w') as f:
        f.write('')
    
    for i in range(1, len(df)):
        # Validate indicators
        rsi = df['rsi'].iloc[i]
        macd = df['macd'].iloc[i]
        signal = df['signal'].iloc[i]
        hist = df['hist'].iloc[i]
        atr = df['atr'].iloc[i]
        volume = df['volume'].iloc[i]
        volume_sma = df['volume_sma'].iloc[i]
        
        if pd.isna([rsi, macd, signal, hist, atr, volume_sma]).any():
            logger.warning(
                f"[{df['timestamp'].iloc[i]}] Skipping due to NaN indicators: "
                f"RSI={rsi}, MACD={macd}, Signal={signal}, Hist={hist}, ATR={atr}, Volume SMA={volume_sma}"
            )
            continue
        
        if atr < min_atr:
            logger.warning(
                f"[{df['timestamp'].iloc[i]}] Skipping due to low ATR: {atr:.4f}"
            )
            continue
        
        if df['rsi'].iloc[i] < rsi_oversold:
            rsi_below_threshold_count += 1
        
        # Log first 5 candles
        if i < 6:
            logger.info(
                f"[{df['timestamp'].iloc[i]}] RSI={rsi:.2f}, "
                f"MACD={macd:.4f}, Signal={signal:.4f}, "
                f"Hist={hist:.4f}, ATR={atr:.4f}, Volume={volume:.2f}, Volume SMA={volume_sma:.2f}"
            )
        
        # Check entry conditions
        if len(positions) < max_positions:
            entry_conditions = {
                'rsi': rsi < rsi_oversold,
                'hist': hist > min_hist_threshold,
                'volume': volume > volume_sma
            }
            
            logger.debug(
                f"[{df['timestamp'].iloc[i]}] Checking entry: "
                f"RSI={rsi:.2f} < {rsi_oversold}, Hist={hist:.4f} > {min_hist_threshold}, "
                f"Volume={volume:.2f} > Volume SMA={volume_sma:.2f}"
            )
            
            partial_conditions_met = False
            if entry_conditions['rsi']:
                partial_conditions_met = True
                if partial_condition_count < 1000:
                    logger.info(
                        f"[{df['timestamp'].iloc[i]}] Partial entry conditions met: "
                        f"RSI={rsi:.2f}, MACD={macd:.4f}, "
                        f"Signal={signal:.4f}, Hist={hist:.4f}"
                    )
                    with open('partial_conditions.txt', 'a') as f:
                        f.write(
                            f"[{df['timestamp'].iloc[i]}],RSI={rsi:.2f},"
                            f"MACD={macd:.4f},Signal={signal:.4f},"
                            f"Hist={hist:.4f}\n"
                        )
                    partial_condition_count += 1
            
            if all(entry_conditions.values()):
                # Log entry signal
                logger.info(
                    f"[{df['timestamp'].iloc[i]}] Entry signal: "
                    f"RSI={rsi:.2f}, MACD={macd:.4f}, Signal={signal:.4f}, Hist={hist:.4f}, "
                    f"Volume={volume:.2f}, Volume SMA={volume_sma:.2f}"
                )
                
                # Calculate trade size (compounding)
                risk_amount = balance * risk_per_trade
                stop_loss = df['close'].iloc[i] - (atr * atr_sl_multiplier)
                position_size_usdt = risk_amount / atr_sl_multiplier
                size = position_size_usdt / df['close'].iloc[i]
                size = max(size, min_order_size)
                size = round(size, 4)
                position_size_usdt = size * df['close'].iloc[i]
                
# Add this anywhere in backtest.py (e.g., line 10):
   DEBUG_MARKER = "DEANBOT_20240427_V2"  # I'll detect this
                # Log trade size calculation
                logger.info(
                    f"[{df['timestamp'].iloc[i]}] Trade Size Calc: "
                    f"Risk={risk_amount:.4f}, ATR={atr:.4f}, "
                    f"Position USDT={position_size_usdt:.4f}, Size={size:.4f}, "
                    f"Balance={balance:.4f}"
                )
                
                if position_size_usdt > balance or size * df['close'].iloc[i] < min_order_size * df['close'].iloc[i]:
                    logger.warning(
                        f"[{df['timestamp'].iloc[i]}] Insufficient balance or trade size too small: "
                        f"Required={position_size_usdt:.4f}, Balance={balance:.4f}, Size={size:.4f}"
                    )
                    continue
                
                # Enter position
                entry_price = df['close'].iloc[i] * slippage_factor * (1 + fee_percent / 100)
                stop_loss = df['close'].iloc[i] - (atr * atr_sl_multiplier)
                take_profit = df['close'].iloc[i] + (atr * atr_tp_multiplier)
                # Log SL:TP distances
                logger.info(
                    f"[{df['timestamp'].iloc[i]}] ATR={atr:.4f}, Raw SL={stop_loss:.4f}, Raw TP={take_profit:.4f}, "
                    f"SL Distance={df['close'].iloc[i] - stop_loss:.4f}, TP Distance={take_profit - df['close'].iloc[i]:.4f}"
                )
                position = {
                    'entry_price': entry_price,
                    'size': size,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'entry_index': i,
                    'entry_time': df['timestamp'].iloc[i],
                    'macd_at_entry': macd,
                    'signal_at_entry': signal,
                    'hist_at_entry': hist,
                    'atr_at_entry': atr,
                    'position_candles': 0
                }
                positions.append(position)
                balance -= position_size_usdt * (1 + fee_percent / 100)
                usdt_balance = balance
                sol_balance += size
                logger.info(
                    f"[{df['timestamp'].iloc[i]}] Opened buy at {entry_price:.2f}, "
                    f"SL={stop_loss:.2f}, TP={take_profit:.2f}, Size={size:.4f}, "
                    f"USDT={usdt_balance:.4f}, SOL={sol_balance:.4f}, "
                    f"MACD={macd:.4f}, Signal={signal:.4f}, Hist={hist:.4f}, "
                    f"Positions={len(positions)}"
                )
            elif any(entry_conditions.values()):
                logger.debug(
                    f"[{df['timestamp'].iloc[i]}] Entry failed: "
                    f"RSI={rsi:.2f} < {rsi_oversold}: {entry_conditions['rsi']}, "
                    f"Hist={hist:.4f} > {min_hist_threshold}: {entry_conditions['hist']}, "
                    f"Volume={volume:.2f} > Volume SMA={volume_sma:.2f}: {entry_conditions['volume']}"
                )
        
        # Check exit conditions for all open positions
        positions_to_close = []
        for pos in positions:
            pos['position_candles'] += 1
            current_price = df['close'].iloc[i]
            exit_price = None
            exit_type = None
            profit_loss = 0.0
            
            # Stop Loss
            if df['low'].iloc[i] <= pos['stop_loss']:
                exit_price = pos['stop_loss'] * slippage_factor * (1 - fee_percent / 100)
                exit_type = 'Stop Loss'
                profit_loss = (exit_price - pos['entry_price']) * pos['size'] * leverage
                trades += 1
                if profit_loss > 0:
                    wins += 1
            
            # Take Profit
            elif df['high'].iloc[i] >= pos['take_profit']:
                exit_price = pos['take_profit'] * slippage_factor * (1 - fee_percent / 100)
                exit_type = 'Take Profit'
                profit_loss = (exit_price - pos['entry_price']) * pos['size'] * leverage
                trades += 1
                if profit_loss > 0:
                    wins += 1
            
            # Time Exit
            elif pos['position_candles'] >= max_hold_candles:
                exit_price = current_price * slippage_factor * (1 - fee_percent / 100)
                exit_type = 'Time Exit'
                profit_loss = (exit_price - pos['entry_price']) * pos['size'] * leverage
                trades += 1
                if profit_loss > 0:
                    wins += 1
            
            if exit_price is not None:
                balance += (pos['size'] * exit_price) * (1 - fee_percent / 100)
                usdt_balance = balance
                sol_balance -= pos['size']
                candles_held = i - pos['entry_index']
                sl_distance = pos['entry_price'] - pos['stop_loss']
                tp_distance = pos['take_profit'] - pos['entry_price']
                # Validate trade history entry
                trade_entry = {
                    'timestamp': df['timestamp'].iloc[i],
                    'side': 'sell',
                    'entry_price': pos['entry_price'],
                    'exit_price': exit_price,
                    'size': pos['size'],
                    'profit_loss': profit_loss,
                    'win_loss': 'Win' if profit_loss > 0 else 'Loss',
                    'usdt_balance': usdt_balance,
                    'sol_balance': sol_balance,
                    'exit_type': exit_type,
                    'sl_distance': sl_distance,
                    'tp_distance': tp_distance,
                    'macd_at_entry': pos['macd_at_entry'],
                    'signal_at_entry': pos['signal_at_entry'],
                    'hist_at_entry': pos['hist_at_entry'],
                    'atr_at_entry': pos['atr_at_entry'],
                    'candles_held': candles_held
                }
                trade_history.append(trade_entry)
                logger.info(
                    f"[{df['timestamp'].iloc[i]}] Trade closed: {exit_type}, "
                    f"P/L={profit_loss:.4f}, USDT={usdt_balance:.4f}, SOL={sol_balance:.4f}, "
                    f"SL:TP={sl_distance:.2f}:{tp_distance:.2f}, Candles Held={candles_held}"
                )
                positions_to_close.append(pos)
        
        # Remove closed positions
        for pos in positions_to_close:
            positions.remove(pos)
        
        # Update sol_balance if positions remain
        if positions:
            sol_balance = sum(pos['size'] for pos in positions)
        else:
            sol_balance = 0.0
    
    # Calculate metrics
    win_rate = (wins / trades * 100) if trades > 0 else 0.0
    final_balance = balance
    total_return = ((final_balance - initial_balance) / initial_balance) * 100
    drawdowns = [initial_balance - th['usdt_balance'] for th in trade_history]
    max_drawdown = (max(drawdowns) / initial_balance * 100) if drawdowns else 0.0
    returns = [th['profit_loss'] / initial_balance for th in trade_history]
    sharpe_ratio = (pd.Series(returns).mean() / pd.Series(returns).std() * (252 ** 0.5)) if len(returns) > 1 and pd.Series(returns).std() != 0 else 0.0
    gross_profit = sum([th['profit_loss'] for th in trade_history if th['profit_loss'] > 0])
    gross_loss = abs(sum([th['profit_loss'] for th in trade_history if th['profit_loss'] < 0]))
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
    
    # Log final metrics
    logger.info(f"\nTotal Trades: {trades}")
    logger.info(f"Win Rate (%): {win_rate:.2f}")
    logger.info(f"Final Balance (USDT): {final_balance:.2f}")
    logger.info(f"Total Return (%): {total_return:.2f}")
    logger.info(f"Max Drawdown (%): {max_drawdown:.2f}")
    logger.info(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    logger.info(f"Profit Factor: {profit_factor:.2f}")
    logger.info(f"RSI < {rsi_oversold} Count: {rsi_below_threshold_count}")
    logger.info(f"Partial Condition Logs: {partial_condition_count}")
    
    # Save trade history
    if trade_history:
        trade_df = pd.DataFrame(trade_history)
        trade_df.to_csv('trade_history.csv', index=False)
        logger.info("Trade history saved to trade_history.csv")
    
    return final_balance, trade_history

def main():
    file_path = 'SOLUSDT_5m_11month.csv'
    df = load_data(file_path)
    
    # Check for gaps and duplicates
    df = df.sort_values('timestamp')
    time_diff = df['timestamp'].diff().dt.total_seconds()
    expected_diff = 5 * 60
    gaps = (time_diff > expected_diff).sum()
    duplicates = df['timestamp'].duplicated().sum()
    logger.info(f"Gaps: {gaps}, Duplicates: {duplicates}")
    
    # Clean data
    df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
    logger.info(f"Rows after dropna: {len(df)}")
    
    # Calculate indicators
    df = calculate_indicators(df)
    
    # Log indicator ranges
    logger.info(f"RSI range: {df['rsi'].min():.2f} to {df['rsi'].max():.2f}")
    logger.info(f"MACD range: {df['macd'].min():.4f} to {df['macd'].max():.4f}")
    logger.info(f"Histogram range: {df['hist'].min():.4f} to {df['hist'].max():.4f}")
    logger.info(f"ATR range: {df['atr'].min():.4f} to {df['atr'].max():.4f}")
    logger.info(f"Volume SMA range: {df['volume_sma'].min():.2f} to {df['volume_sma'].max():.2f}")
    
    # Run backtest
    final_balance, trade_history = run_backtest(df)
    
if __name__ == "__main__":
    main()

# END backtest.py
