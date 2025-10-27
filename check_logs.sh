#!/bin/bash

echo "=== Docker Container Log Sizes ==="
echo ""

total_size=0

for container in api livetranslator-cost_tracker-1 livetranslator-mt_router-1 livetranslator-mt_worker-1 livetranslator-persistence-1 livetranslator-postgres-1 livetranslator-redis-1 livetranslator-room_cleanup-1 livetranslator-stt_router-1 livetranslator-stt_worker-1 livetranslator-web-1; do
    log_file=$(docker inspect --format='{{.LogPath}}' $container 2>/dev/null)

    if [ -n "$log_file" ] && [ -f "$log_file" ]; then
        size=$(stat -c%s "$log_file" 2>/dev/null)
        if [ -n "$size" ]; then
            size_mb=$(echo "scale=2; $size / 1024 / 1024" | bc)
            total_size=$(echo "$total_size + $size" | bc)
            printf "%-35s %10s MB\n" "$container:" "$size_mb"
        fi
    fi
done

echo ""
echo "----------------------------------------"
total_mb=$(echo "scale=2; $total_size / 1024 / 1024" | bc)
total_gb=$(echo "scale=2; $total_size / 1024 / 1024 / 1024" | bc)
printf "%-35s %10s MB (%.2f GB)\n" "TOTAL:" "$total_mb" "$total_gb"
