# START analysetradehistory.py

# Filename: analysetradehistory.py
# Version: 2.6 (2025-04-27) - Fixed duplicate partial conditions output
# Description: Analyze trade_history.csv and partial_conditions.txt from backtest.py

import pandas as pd
import re
import os

def load_trade_history(file_path='trade_history.csv'):
    if not os.path.exists(file_path):
        print(f"Error loading trade history: {file_path} not found")
        return None
    try:
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        print(f"Error loading trade history: {e}")
        return None

def load_partial_conditions(file_path='partial_conditions.txt'):
    conditions = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                match = re.match(r'\[(.*?)\],RSI=([\d.]+),MACD=([-.\d]+),Signal=([-.\d]+),Hist=([-.\d]+)', line)
                if match:
                    timestamp = pd.to_datetime(match.group(1))
                    rsi = float(match.group(2))
                    macd = float(match.group(3))
                    signal = float(match.group(4))
                    hist = float(match.group(5))
                    conditions.append({
                        'timestamp': timestamp,
                        'rsi': rsi,
                        'macd': macd,
                        'signal': signal,
                        'hist': hist
                    })
        return pd.DataFrame(conditions)
    except Exception as e:
        print(f"Error loading partial conditions: {e}")
        return pd.DataFrame()

def analyze_trades(trade_df):
    if trade_df is None or trade_df.empty:
        print("No trade data to analyze")
        return
    
    total_trades = len(trade_df)
    wins = len(trade_df[trade_df['win_loss'] == 'Win'])
    losses = total_trades - wins
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    print("Trade Summary:")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win Rate (%): {win_rate:.2f}")
    
    # Mean profit/loss by exit type
    exit_types = trade_df['exit_type'].unique()
    print("\nMean Profit/Loss by Exit Type (USDT):")
    for exit_type in exit_types:
        subset = trade_df[trade_df['exit_type'] == exit_type]
        mean_pl = subset['profit_loss'].mean()
        print(f"{exit_type}: {mean_pl:.6f} (Trades: {len(subset)})")
    
    # Average trade duration
    avg_duration = trade_df['candles_held'].mean()
    avg_duration_wins = trade_df[trade_df['win_loss'] == 'Win']['candles_held'].mean()
    avg_duration_losses = trade_df[trade_df['win_loss'] == 'Loss']['candles_held'].mean()
    print("\nAverage Trade Duration (Candles):")
    print(f"Overall: {avg_duration:.2f}")
    print(f"Wins: {avg_duration_wins:.2f}")
    print(f"Losses: {avg_duration_losses:.2f}")
    print(f"Average Trade Duration (Minutes): {avg_duration * 5:.2f}")
    
    # Candles held by exit type
    print("\nCandles Held by Exit Type:")
    for exit_type in exit_types:
        mean_candles = trade_df[trade_df['exit_type'] == exit_type]['candles_held'].mean()
        print(f"{exit_type}: {mean_candles:.2f} candles")
    
    # Trades by hour
    trade_df['entry_hour'] = trade_df['timestamp'].dt.hour
    trades_by_hour = trade_df['entry_hour'].value_counts().sort_index()
    print("\nTrades by Hour:")
    print(trades_by_hour)
    
    # Mean ATR at entry
    mean_atr = trade_df['atr_at_entry'].mean()
    mean_atr_wins = trade_df[trade_df['win_loss'] == 'Win']['atr_at_entry'].mean()
    mean_atr_losses = trade_df[trade_df['win_loss'] == 'Loss']['atr_at_entry'].mean()
    print("\nMean ATR at Entry:")
    print(f"  Overall: {mean_atr:.4f}")
    print(f"  Wins: {mean_atr_wins:.4f}")
    print(f"  Losses: {mean_atr_losses:.4f}")
    
    # Mean indicator values at entry
    indicators = ['macd_at_entry', 'signal_at_entry', 'hist_at_entry']
    for indicator in indicators:
        mean_val = trade_df[indicator].mean()
        mean_val_wins = trade_df[trade_df['win_loss'] == 'Win'][indicator].mean()
        mean_val_losses = trade_df[trade_df['win_loss'] == 'Loss'][indicator].mean()
        print(f"\n{indicator}:")
        print(f"  Overall: {mean_val:.6f}")
        print(f"  Wins: {mean_val_wins:.6f}")
        print(f"  Losses: {mean_val_losses:.6f}")
    
    # Mean SL/TP distances
    mean_sl_distance = trade_df['sl_distance'].mean()
    mean_tp_distance = trade_df['tp_distance'].mean()
    sl_tp_ratio = mean_sl_distance / mean_tp_distance if mean_tp_distance != 0 else float('inf')
    print("\nMean SL/TP Distances (USDT):")
    print(f"Stop Loss Distance: {mean_sl_distance:.4f}")
    print(f"Take Profit Distance: {mean_tp_distance:.4f}")
    print(f"SL:TP Ratio: {sl_tp_ratio:.2f}:1")
    
    # Additional metrics
    total_pl = trade_df['profit_loss'].sum()
    profit_factor = trade_df[trade_df['profit_loss'] > 0]['profit_loss'].sum() / abs(trade_df[trade_df['profit_loss'] < 0]['profit_loss'].sum()) if trade_df[trade_df['profit_loss'] < 0]['profit_loss'].sum() != 0 else float('inf')
    avg_trade_size = trade_df['size'].mean()
    print("\nAdditional Metrics:")
    print(f"Total Profit/Loss (USDT): {total_pl:.4f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Average Trade Size (SOL): {avg_trade_size:.4f}")

def analyze_partial_conditions(conditions_df):
    if conditions_df.empty:
        print("No partial conditions data to analyze")
        return
    
    print("\nPartial Conditions Summary:")
    print(f"Total Partial Conditions: {len(conditions_df)}")
    
    # RSI statistics
    rsi_stats = conditions_df['rsi'].describe()
    rsi_below_25 = len(conditions_df[conditions_df['rsi'] < 25])
    print("\nRSI Statistics:")
    print(f"  Count: {int(rsi_stats['count'])}")
    print(f"  Mean: {rsi_stats['mean']:.5f}")
    print(f"  Min: {rsi_stats['min']:.2f}")
    print(f"  Max: {rsi_stats['max']:.2f}")
    print(f"  RSI < 25 Count: {rsi_below_25}")
    
    # MACD > Signal statistics
    macd_above_signal = len(conditions_df[conditions_df['hist'] > 0])
    macd_above_signal_pct = (macd_above_signal / len(conditions_df) * 100) if len(conditions_df) > 0 else 0.0
    print("\nMACD > Signal Statistics:")
    print(f"  MACD > Signal Count: {macd_above_signal}")
    print(f"  Percentage: {macd_above_signal_pct:.4f}")
    
    # Hist statistics
    hist_stats = conditions_df['hist'].describe()
    negative_hist = len(conditions_df[conditions_df['hist'] < 0])
    hist_above_0_001 = len(conditions_df[conditions_df['hist'] > 0.001])
    print("\nHist Statistics:")
    print(f"  Count: {int(hist_stats['count'])}")
    print(f"  Mean: {hist_stats['mean']:.6f}")
    print(f"  Min: {hist_stats['min']:.4f}")
    print(f"  Max: {hist_stats['max']:.4f}")
    print(f"  Negative Hist Count: {negative_hist}")
    print(f"  Hist > 0.001 Count: {hist_above_0_001}")
    
    # Sample partial conditions
    print("\nSample Partial Conditions (First 5):")
    for _, row in conditions_df.head().iterrows():
        print(f"[{row['timestamp']}],RSI={row['rsi']:.2f},MACD={row['macd']:.4f},Signal={row['signal']:.4f},Hist={row['hist']:.4f}")

def main():
    trade_df = load_trade_history()
    conditions_df = load_partial_conditions()
    analyze_trades(trade_df)
    analyze_partial_conditions(conditions_df)

if __name__ == "__main__":
    main()

# END analysetradehistory.py
