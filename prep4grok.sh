# START prep4grok.sh

#!/bin/bash
# Filename: prep4grok.sh
# Version: 1.2 (2025-04-26) - Fixed histogram max parsing logic
# Description: Combines backtest.log, trade_history.csv, analysis.txt, partial_conditions.txt

output_file="4grok.txt"

# Initialize output file
> "$output_file"

# Backtest Summary from backtest.log
echo "Backtest Summary:" >> "$output_file"
grep -E "Total Trades|Win Rate|Final Balance|Total Return|Max Drawdown|Sharpe Ratio|Profit Factor|RSI < [0-9]+ Count|Partial Condition Logs|Trade history saved" backtest.log >> "$output_file"
echo "" >> "$output_file"

# Trade History (first 5 and last 5 trades)
echo "Trade History (First 5 and Last 5):" >> "$output_file"
head -n 1 trade_history.csv >> "$output_file"
head -n 5 trade_history.csv | tail -n 4 >> "$output_file"
tail -n 5 trade_history.csv >> "$output_file"
echo "" >> "$output_file"

# Analysis Output
echo "Analysis Output:" >> "$output_file"
if [ -f analysis.txt ]; then
    cat analysis.txt >> "$output_file"
else
    echo "analysis.txt not found" >> "$output_file"
fi
echo "" >> "$output_file"

# Partial Conditions Summary
echo "Partial Conditions Summary:" >> "$output_file"
echo "Total Partial Conditions: $(wc -l < partial_conditions.txt)" >> "$output_file"
echo "" >> "$output_file"

# RSI Statistics
echo "RSI Statistics:" >> "$output_file"
awk -F',' 'BEGIN {count=0; sum=0; min=999; max=-999} \
    $2 ~ /RSI=/ { \
        rsi = substr($2, 5); \
        count++; sum += rsi; \
        if (rsi < min) min = rsi; \
        if (rsi > max) max = rsi; \
        if (rsi < 25) count25++; \
    } \
    END { \
        print "  Count: " count; \
        print "  Mean: " (count > 0 ? sum/count : 0); \
        print "  Min: " (min != 999 ? min : "N/A"); \
        print "  Max: " (max != -999 ? max : "N/A"); \
        print "  RSI < 25 Count: " (count25 ? count25 : 0); \
    }' partial_conditions.txt >> "$output_file"
echo "" >> "$output_file"

# MACD > Signal Statistics
echo "MACD > Signal Statistics:" >> "$output_file"
awk -F',' 'BEGIN {count=0; macd_signal_count=0} \
    $3 ~ /MACD=/ && $4 ~ /Signal=/ { \
        count++; \
        macd = substr($3, 6); \
        signal = substr($4, 8); \
        if (macd > signal) macd_signal_count++; \
    } \
    END { \
        print "  MACD > Signal Count: " macd_signal_count; \
        print "  Percentage: " (count > 0 ? (macd_signal_count/count)*100 : 0); \
    }' partial_conditions.txt >> "$output_file"
echo "" >> "$output_file"

# Hist Statistics
echo "Hist Statistics:" >> "$output_file"
awk -F',' 'BEGIN {count=0; sum=0; min=999; max=-999; neg_count=0; hist_above=0} \
    $5 ~ /Hist=/ { \
        hist = substr($5, 6); \
        count++; sum += hist; \
        if (hist < min || min == 999) min = hist; \
        if (hist > max || max == -999) max = hist; \
        if (hist < 0) neg_count++; \
        if (hist > 0.001) hist_above++; \
    } \
    END { \
        print "  Count: " count; \
        print "  Mean: " (count > 0 ? sum/count : 0); \
        print "  Min: " (min != 999 ? min : "N/A"); \
        print "  Max: " (max != -999 ? max : "N/A"); \
        print "  Negative Hist Count: " neg_count; \
        print "  Hist > 0.001 Count: " hist_above; \
    }' partial_conditions.txt >> "$output_file"
echo "" >> "$output_file"

# Sample Partial Conditions (first 5)
echo "Sample Partial Conditions (First 5):" >> "$output_file"
head -n 5 partial_conditions.txt >> "$output_file"

# END prep4grok.sh
