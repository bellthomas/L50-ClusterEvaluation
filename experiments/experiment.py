#!/usr/bin/env python3
import argparse
import os
import time
from IPy import IP
from remote_setup import run_remote_setup, reset_remote
from importlib import import_module
import getpass
import yaml
import json
import uuid
import pathlib
import socket
import smtplib
import ssl
from email.message import EmailMessage
import datetime
import random
from crosstalk import crosstalk, stop_crosstalk_both

#
def run_experiment(targets, definition, _id=str(uuid.uuid4()), cross=False):
    experiment_source = definition.get("src", definition.get("id", -1))
    if validate_experiment(experiment_source):
        # Init experiment.
        exp_num = definition.get("id", -1)
        print("---[BEGIN EXPERIMENT]---\n")
        results_dir = prepare_for_experiment(_id, ", ".join(targets), definition)

        # Iterate over arguments variations.
        argument_sets = definition.get('parameters', [[]])
        for i in range(len(argument_sets)): 
            args = argument_sets[i].copy()
            args["_id"] = _id
            args["_run"] = i
            args["_desc"] = definition.get('description', '(none)')
            args["_origin"] = str(socket.gethostbyname(socket.gethostname()))
            serialised_args = json.dumps(args)

            # Coordinate and execute according to target policy.
            targets_config = definition.get("targets", {})
            strategy = targets_config.get("strategy", 'Each')
            recipient = targets_config.get("recipient", False)
            simultaneous = targets_config.get("simultaneous", False)
            timeout = targets_config.get("timeout", 0)

            if strategy == 'Combination':
                for t in range(1, len(targets)+1):
                    victimList = random.sample(targets, t)
                    victims = ",".join(victimList)
                    run = (t-1) + i*len(targets)

                    args["_run"] = run
                    args["_victims"] = victims
                    serialised_args = json.dumps(args)

                    # Explicitly make combination results dir.
                    pathlib.Path("{}/{}/{}".format(results_dir, run, victims)).mkdir(parents=True, exist_ok=True)
                    for vic in victimList:
                        pathlib.Path("{}/{}/{}".format(results_dir, run, vic)).mkdir(parents=True, exist_ok=True)

                    print("Selected {} victims: {}".format(t, victims))
                    prepare_for_target(_id, run, victims, definition, argument_sets[i])
                    print("-- Experiment {}.{}.{} (Crosstalk: False) --".format(exp_num, run, t))
                    print("Targets: {}".format(victims))
                    print("Description: {}".format(definition.get('description', '(none)')))
                    print("Argument set: {}".format(args))
                    run_in_mode(experiment_source, victims, serialised_args, _id, run, results_dir, recipient, simultaneous, timeout)
                    print("")

            elif strategy == 'Single':
                t = 0
                target = random.sample(targets, 1)[0]

                crosstalkers = [] if not cross else random.sample([t for t in targets if t != target], 2)
                if cross:
                    crosstalk(crosstalkers[0], crosstalkers[1], "1000m")

                prepare_for_target(_id, i, target, definition, argument_sets[i])
                print("-- Experiment {}.{}.{} (Crosstalk: {}) --".format(exp_num, i, t, cross))
                print("Target: {}".format(target))
                print("Description: {}".format(definition.get('description', '(none)')))
                print("Argument set: {}".format(args))
                run_in_mode(experiment_source, target, serialised_args, _id, i, results_dir, recipient, simultaneous, timeout)
                
                if cross:
                    stop_crosstalk_both(crosstalkers[0], crosstalkers[1])
                print("")

            else:
                for t in range(len(targets)):
                    target = targets[t]
                    crosstalkers = [] if not cross else random.sample([t for t in targets if t != target], 2)
                    if cross:
                        crosstalk(crosstalkers[0], crosstalkers[1], "1000m")

                    prepare_for_target(_id, i, target, definition, argument_sets[i])
                    print("-- Experiment {}.{}.{} (Crosstalk: {}) --".format(exp_num, i, t, cross))
                    print("Target: {}".format(target))
                    print("Description: {}".format(definition.get('description', '(none)')))
                    print("Argument set: {}".format(args))
                    run_in_mode(experiment_source, target, serialised_args, _id, i, results_dir, recipient, simultaneous, timeout)
                    
                    if cross:
                        stop_crosstalk_both(crosstalkers[0], crosstalkers[1])
                    print("")


        print("---[END EXPERIMENT]---\n")
        print("\nID: {}\n".format(_id))
    else:
        print("Invalid experiment source.")


def run_in_mode(experiment_source, target, serialised_args, _id, i, results_dir, recipient=False, simultaneous=False, timeout=0):
    if simultaneous:
        # Simultaneous. (Start everyone at the same time)
        run_remote_setup(experiment_source, target, serialised_args, _id, sleep=False)
        directory = os.path.dirname(os.path.abspath(__file__))
        os.system("python3 {}/{}/run.py {} '{}' {}".format(
            directory, experiment_source, target, serialised_args, results_dir
        ))
        time.sleep(2)
        reset_remote(experiment_source, target, _id, i, results_dir)
    elif recipient:
        # Receiver mode. (Set self up first)
        directory = os.path.dirname(os.path.abspath(__file__))
        os.system("python3 {}/{}/run.py {} '{}' {}".format(
            directory, experiment_source, target, serialised_args, results_dir
        ))
        run_remote_setup(experiment_source, target, serialised_args, _id, sleep=False)
        
        print("Waiting for recipient to complete...")
        time.sleep(timeout + 2)
        print("Killing iperf...")
        os.system("sudo kill -9 $(pidof iperf)")
        os.system("tmux kill-session -t recipient-container")
        reset_remote(experiment_source, target, _id, i, results_dir)
    else:
        # Normal mode. (Set remote up first)
        run_remote_setup(experiment_source, target, serialised_args, _id, sleep=True)
        directory = os.path.dirname(os.path.abspath(__file__))
        os.system("python3 {}/{}/run.py {} '{}' {}".format(
            directory, experiment_source, target, serialised_args, results_dir
        ))
        time.sleep(2)
        reset_remote(experiment_source, target, _id, i, results_dir)


#
def validate_experiment(source):
    directory = os.path.dirname(os.path.abspath(__file__))
    return os.path.exists("{}/{}/run.py".format(directory, source))

#
def get_all_experiments():
    valid = True
    current = 0
    while(valid):
        current = current + 1
        valid = check_experiment_number(current)
    return range(1, current)

#
def prepare_for_experiment(_id, targets, meta):
    _desc = meta.get("description", "(none)")
    _paramSets = meta.get("parameters", [{}])
    _runs = len(_paramSets)
    _time = time.ctime()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for i in range(_runs):
        path = pathlib.Path("{}/results/data/{}/{}".format(script_dir, _id, i))
        path.mkdir(parents=True, exist_ok=True)
        results_dir = path.absolute().as_posix()

        # Write per-run explainer.
        f = open("{}/results/data/{}/{}/explain".format(script_dir, _id, i), "w+")
        f.write("{} -> {}\nDescription: {}\nTime: {}\nArgs: {}".format(
            str(socket.gethostbyname(socket.gethostname())),
            str(targets), _desc, _time, json.dumps(_paramSets[i])
        ))
        f.close()

    # Write top level explainer.
    f = open("{}/results/data/{}/overview".format(script_dir, _id), "w+")
    f.write("{} -> {}\nDescription: {}\nTime: {}\nRuns:\n".format(
        str(socket.gethostbyname(socket.gethostname())), 
        str(targets), _desc, _time
    ))
    for i in range(_runs):
        f.write("   {}: {}\n".format(i, json.dumps(_paramSets[i])))
    f.close()

    # Append to experiment log.
    f = open("{}/results/contents".format(script_dir), "a+")
    f.write("{}  {}  {}\n".format(
        meta.get('name', '(none)'), _time, _id
    ))
    f.close()

    return pathlib.Path("{}/results/data/{}".format(script_dir, _id)).absolute().as_posix()

#
def prepare_for_target(_id, run, target, meta, parameters):
    _desc = meta.get("description", "(none)")
    _time = time.ctime()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    path = pathlib.Path("{}/results/data/{}/{}/{}".format(script_dir, _id, run, target))
    path.mkdir(parents=True, exist_ok=True)
    results_dir = path.absolute().as_posix()

    # Write explainer for target in experiment run.
    f = open("{}/explain".format(results_dir), "a+")
    f.write("{} -> {}\nDescription: {}\nTime: {}\nArgs: {}".format(
        str(socket.gethostbyname(socket.gethostname())), str(target), 
        _desc, _time, parameters
    ))
    f.close()

#
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run an experiment.')
    parser.add_argument('-e','--experiment', help='Which experiment to run. Omit to run all.', default=0)
    parser.add_argument('-t','--target', help='Target IP address.', required=True)
    parser.add_argument('-l','--lmk', help='Email to notify when done.', default=False)
    parser.add_argument('-i','--uuid', help='(Internal use) Sets the UUID for the experiment.', default=False)
    args = parser.parse_args()
    print(args)

    # Init email notifications.
    smtp_pwd = ""
    if args.lmk:
        smtp_pwd = getpass.getpass('Hermes account password: ')
        with smtplib.SMTP_SSL("smtp.hermes.cam.ac.uk", 465, context=ssl.create_default_context()) as server:
            try:
                server.login("ahb36", "{}#!".format(smtp_pwd))
            except:
                print("SMTP verification failed...")
                exit(1)
            else:
                print("SMTP server verified.")

    directory = os.path.dirname(os.path.abspath(__file__))
    experiment_data = {}
    with open("{}/definitions.yml".format(directory), 'r') as stream:
        data = yaml.safe_load(stream)
        if 'experiments' in data:
            for item in data['experiments']:
                if 'id' in item:
                    experiment_data[item['id']] = item

    # Parse and verify targets.
    targets = []
    for target in ([t.strip() for t in args.target.split(",")] if "," in args.target else [args.target]):
        if target != str(socket.gethostbyname(socket.gethostname())):
            try:
                ip = IP(target)
                targets.append(target)
            except ValueError:
                print("Invalid IP address: {}".format(target))

    experiment_name = "all experiments" if args.experiment == 0 else "experiment {}".format(args.experiment)
    print("\nRunning {}...\n".format(experiment_name))

    start = datetime.datetime.now().replace(microsecond=0)
    _id = args.uuid if args.uuid else str(uuid.uuid4())
    print("Experiment {}".format(_id))

    if int(args.experiment) == 0:
        for experiment in experiment_data.keys():
            exp_definition = experiment_data.get(experiment, {})
            cross = exp_definition.get("crosstalk", False)
            run_experiment(targets, exp_definition, "{}-experiment-{}".format(_id, experiment))
            if cross:
                time.sleep(1)
                run_experiment(targets, exp_definition, "{}-experiment-{}-crosstalk".format(_id, experiment), cross=True)
            time.sleep(1)
    else:
        exp_definition = experiment_data.get(int(args.experiment), {})
        cross = exp_definition.get("crosstalk", False)
        run_experiment(targets, exp_definition, "{}-experiment-{}".format(_id, args.experiment))
        if cross:
            time.sleep(1)
            run_experiment(targets, exp_definition, "{}-experiment-{}-crosstalk".format(_id, args.experiment), cross=True)

    
    end = datetime.datetime.now().replace(microsecond=0)
    print("Duration: {}".format((end-start)))
    
    if args.lmk:
        msg = EmailMessage()
        msg.set_content("Yay!\nDuration: {}".format((end-start)))
        msg['Subject'] = 'L50 Run Complete'
        msg['From'] = "ahb36@cam.ac.uk"
        msg['To'] = args.lmk

        port = 465 
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.hermes.cam.ac.uk", port, context=context) as server:
            server.login("ahb36", "{}#!".format(smtp_pwd))
            server.send_message(msg)
