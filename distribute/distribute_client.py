#!/usr/bin/env python3
import argparse
import os
from os.path import dirname, abspath
import time
import pathlib
import socket
from IPy import IP


#
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Distribution client.')
    parser.add_argument('-e','--experiment', help='Which experiment to run. Omit to run all.', default=0)
    parser.add_argument('-t','--target', help='Target IP addresses.', required=True)
    parser.add_argument('-l','--lmk', help='Email to notify when done.', default=False)
    parser.add_argument('-o','--origin', help='IP of the master node.', required=True)
    parser.add_argument('-d','--origin-dir', help='Directory to store results on the master.', required=True)
    parser.add_argument('-r','--remaining', help='IPs of the nodes remaining in the queue.', default=[])
    args = parser.parse_args()

    my_ip = str(socket.gethostbyname(socket.gethostname()))
    local = args.origin == my_ip
    print(args)

    # Find experiment.py
    script_dir_parent = dirname(dirname(abspath(__file__)))
    experiments_dir_path = pathlib.Path("{}/experiments".format(script_dir_parent))
    experiments_dir = experiments_dir.absolute().as_posix()