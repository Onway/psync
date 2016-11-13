#!/usr/bin/env python3

""" usage

psync --generate_config
psync [-d] [-h alias-host ] // 当前工作目录上传到默认机器
psync [-d] [file1, file2, … fileN] [-h alias-host] // 指定文件上传到默认机器
psync -c file1 [-h alias-host] // 对比文件

"""

import os
import sys
import optparse
import subprocess
import shlex

parser = optparse.OptionParser(conflict_handler="resolve")
parser.add_option("--generate_config", action="store_true", help="generate config")
parser.add_option("-f", "--file", default="", dest="cfile", help="config file path")
parser.add_option("-c", "--cmp", action="store_true", dest="cmp", help="compare file")
parser.add_option("-d", "--down", action="store_true", dest="down", help="download files")
parser.add_option("-h", "--host", default="", dest="host", help="host alias")
(options, args) = parser.parse_args()

config = {}
host = None


def get_host_args():
    assert type(host) == dict
    ssh_name = host.get("ssh_name", "")
    if ssh_name != "":
        return (ssh_name, [])

    user = host["user"]
    ip = host["host"]
    port = host["port"]
    ssh_key = host["ssh_key"]
    return ("{}@{}".format(user, ip),
            [ "-e", "ssh -p %d -i %s" % (port, ssh_key) ])


def do_down_rsync():
    cwd = os.getcwd()
    local_prefix = host["local_path"]

    srcs = []
    for p in args:
        src = os.path.abspath(os.path.join(cwd, p))
        assert src.startswith(local_prefix)
        if src == local_prefix:
            srcs += [ os.path.join(src, f) for f in os.listdir(src) ]
        else:
            srcs.append(src)

    remote_prefix = host["remote_path"]
    dests = {}
    for p in srcs:
        d = os.path.dirname(p)
        p = p.replace(local_prefix, remote_prefix)
        if d not in dests:
            dests[d] = [ p ]
        else:
            dests[d].append(p)

    print(srcs)
    print(dests)

    host_args = get_host_args()
    for key, value in dests.items():
        pargs = [ "rsync", config.get("rsync_args", "") ]
        pargs += host_args[1]
        t = "{}:{}".format(host_args[0], " ".join(value))
        pargs.append(t)
        pargs.append(key)
        print(pargs)
        print(subprocess.list2cmdline(pargs))
        p = subprocess.Popen(pargs, stdout=sys.stdout, stderr=sys.stderr)
        exit_code = p.wait()
        if exit_code != 0:
            sys.exit(exit_code)


def do_up_rsync():
    cwd = os.getcwd()
    local_prefix = host["local_path"]

    srcs = []
    for p in args:
        src = os.path.abspath(os.path.join(cwd, p))
        assert src.startswith(local_prefix)
        if src == local_prefix:
            srcs += [ os.path.join(src, f) for f in os.listdir(src) ]
        else:
            srcs.append(src)

    remote_prefix = host["remote_path"]
    dests = {}
    for p in srcs:
        d = os.path.dirname(p.replace(local_prefix, remote_prefix))
        if d not in dests:
            dests[d] = [ p ]
        else:
            dests[d].append(p)

    print(srcs)
    print(dests)

    host_args = get_host_args()
    for key, value in dests.items():
        pargs = [ "rsync", config.get("rsync_args", "") ]
        pargs += host_args[1]
        for f in value:
            pargs.append(f)
        pargs.append("{}:{}".format(host_args[0], key))
        print(pargs)
        print(subprocess.list2cmdline(pargs))
        p = subprocess.Popen(pargs, stdout=sys.stdout, stderr=sys.stderr)
        exit_code = p.wait()
        if exit_code != 0:
            sys.exit(exit_code)


def generate_config():
    config_file = os.path.join(os.environ["HOME"], ".psync_config.py")
    if os.path.isfile(config_file):
        print("%s already exist!" % config_file)
        return

    txt = """hosts = {
    'localhost': {
        'ssh_name': 'localhost',
        'host': '',
        'port': 0,
        'user': '',
        'ssh_key': '',
        'remote_path': '',
        'local_path': '',
    },
}

default_host = 'localhost'

rsync_args = '-avzC'
"""

    with open(config_file, "w") as f:
        f.write(txt)
    print("%s generated!" % config_file)


def read_config():
    config_file = os.path.join(os.environ["HOME"], ".psync_config.py")
    if options.cfile != "":
        config_file = options.cfile

    local = {}
    with open(config_file) as f:
        exec(f.read(), {}, local)
    
    host_key = local["default_host"]
    if len(options.host) > 0 :
        host_key = options.host

    global host
    global config
    config = local
    host = config["hosts"][host_key]
    assert host.get("local_path", "") != ""
    assert host.get("remote_path", "") != ""


def do_compare():
    print("do_compare")
    pass


def do_sync():
    print(args)
    if len(args) == 0:
        args.append(".")

    if options.down:
        do_down_rsync()
    else:
        do_up_rsync()


if __name__ == "__main__":
    if options.generate_config:
        generate_config()
        sys.exit(0)
    read_config()

    if options.cmp:
        do_compare()
        sys.exit(0)

    do_sync()
    sys.exit(0)
