#!/usr/bin/env python3
import os
import paramiko

def run_remote_setup(exp_num, target, pswd):
    if os.path.exists("{}/remote.py".format(exp_num)):
        print("Setting up remote for experiment {}...".format(exp_num))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(str(target), username='L50', password=pswd)
        cmd = "python3 ~/L50-ClusterEvaluation/experiments/{}/remote.py"
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
        print("stdout:  " + str(ssh_stdout.read()))
        print("stderr:  " + str(ssh_stderr.read()))

        print("Remote setup complete for experiment {}.\n".format(exp_num))
    else:
        print("No remote setup for experiment {}.".format(exp_num))