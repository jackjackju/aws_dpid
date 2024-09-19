#!/bin/bash

# Directory where your log files are stored
LOG_DIR="./log"

# File to store all running times
OUTPUT_FILE="./log/total.txt"
RBC_FILE="./log/totalrbc.txt"
REFRESH_FILE="./log/totalrefresh.txt"

truncate -s 0 $OUTPUT_FILE
truncate -s 0 $RBC_FILE
truncate -s 0 $REFRESH_FILE

# Loop through each log file in the directory
for LOG_FILE in $LOG_DIR/consensus-node-*.log
do
    # Use tail to get the last five lines of the file, then awk to extract the running time
    tail -n 1 $LOG_FILE | awk '{printf "%.3f\n", $11}' >> "$OUTPUT_FILE"
    tail -n 3 $LOG_FILE | head -n 1 |  awk '{printf "%.3f\n", $11}' >> "$RBC_FILE"
    tail -n 2 $LOG_FILE | head -n 1 |  awk '{printf "%.3f\n", $11}' >> "$REFRESH_FILE"
done

echo "All running times have been appended to $OUTPUT_FILE $RBC_FILE $REFRESH_FILE"\

awk '{sum+=$1} END {print "Total Mean: " sum/NR}' $OUTPUT_FILE | sort -n
awk '{sum+=$1} END {print "RBC Mean: " sum/NR}' $RBC_FILE | sort -n
awk '{sum+=$1} END {print "Refresh Mean: " sum/NR}' $REFRESH_FILE | sort -n



