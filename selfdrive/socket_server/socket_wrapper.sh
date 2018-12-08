#!/bin/sh
finish() {
  echo "exiting socket_server"
  pkill -SIGINT -P $$
}

trap finish EXIT

while true; do
  python socket_server.py &
  wait $!
done

