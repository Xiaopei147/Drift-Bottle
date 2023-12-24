#!/bin/bash

count=0

trap "echo '本次写入了 $count 条数据。'; exit" SIGINT SIGTERM

while true; do
    # 从API获取JSON数据
    json_data=$(curl -s https://international.v1.hitokoto.cn/)

    # 读取JSON数据中的内容
    hitokoto=$(echo $json_data | jq -r '.hitokoto')
    created_at=$(date -d @$(echo $json_data | jq -r '.created_at') +"%Y-%m-%d %H:%M:%S")
    sender_id=$((1 + RANDOM % 2))

    # 将数据插入到数据库中
    mysql -u root -p123456 -h 172.17.0.2 -D plp -e "INSERT INTO bottles (message, created_at, sender_id) VALUES ('$hitokoto', '$created_at', $sender_id);"

    sleep 5
    # 增加写入数量
    ((count++))
done
