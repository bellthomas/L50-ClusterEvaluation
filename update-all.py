import os
hosts = os.environ["HOSTS"]
if hosts:
    for host in hosts.split(","):
        os.system("ssh L50@{} 'cd ~/x; git pull'".format(host))
