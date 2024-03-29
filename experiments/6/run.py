#!/usr/bin/env python3
import argparse
import sys
import os
# sys.path.insert(1, "{}/..".format(os.path.dirname(os.path.abspath(__file__))))
import json
import time

def run_client(target, arguments, results_dir, num=0):
    buffer_length = arguments.get('buffer_length', 65000)
    _time = arguments.get('time', 15)
    udp = arguments.get('udp', False)
    command = "sudo iperf {} 2>&1 >> {}/{}/{}/local-{} &".format(
        " ".join([
            "-u" if udp else "",
            "-i 0.5",
            "-t {}".format(_time),
            "-f m",
            "-l {}".format(buffer_length),
            "-c {}".format(str(target)),
            "-b 10g" if udp else ""
        ]),
        results_dir, arguments.get("_run"), str(target), num
    )
    print(command)
    os.system(command)


if __name__ == "__main__":
    args = json.loads(sys.argv[2])
    clients = args.get('clients', 1)
    for i in range(0, clients):
        run_client(sys.argv[1], args, sys.argv[3], i)
    time.sleep(18)