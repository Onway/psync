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
import tempfile

parser = optparse.OptionParser(conflict_handler="resolve")
parser.add_option("--generate_config", action="store_true", help="generate config")
parser.add_option("-f", "--file", default="", dest="cfile", help="config file path")
parser.add_option("-c", "--cmp", action="store_true", dest="cmp", help="compare file")
parser.add_option("-d", "--down", action="store_true", dest="down", help="download files")
parser.add_option("-h", "--host", default="", dest="host", help="host alias")
(options, args) = parser.parse_args()

config = {}
host = None

def make_host_args(host_config, cmd_type="rsync"):
    ssh_name = host_config.get("ssh_name", "")
    if ssh_name != "":
        return (ssh_name, [])

    user = host_config["user"]
    ip = host_config["host"]
    port = host_config["port"]
    ssh_key = host_config["ssh_key"]

    user_host = "{}@{}".format(user, ip)
    if cmd_type == "ssh":
        return (user_host, [ "-p", port, "-i", ssh_key ])
    else:
        return (user_host, [ "-e", "ssh -p %d -i %s" % (port, ssh_key) ]
        

def join_local_paths(local_dir, files):
    cwd = os.getcwd()
    dir_ = os.path.abspath(local_dir)

    paths = []
    for f in files:
        fpath = os.path.abspath(os.path.join(cwd, f))
        assert fpath.startswith(dir_)
        if fpath == dir_:
            paths += [ os.path.join(dir_, item) for item in os.listdir(dir_) ]
        else:
            paths.append(fpath)

    return paths


def group_dir_files(local_paths, local_dir, remote_dir, is_up=True):
    ldir = os.path.abspath(local_dir)
    rdir = os.path.abspath(remote_dir)

    dest_src_dict = {}
    for lpath in local_paths:
        rpath = lpath.replace(ldir, rdir)

        if is_up:
            dest = os.path.dirname(rpath)
            src = lpath
        else:
            dest = os.path.dirname(lpath)
            src = rpath

        if dest not in dest_src_dict:
            dest_src_dict[dest] = [ src ]
        else:
            dest_src_dict[dest].append(src)

    print(dest_src_dict)
    return dest_src_dict


def run_rsync_cmd(cmd_args):
    print(cmd_args)
    print(subprocess.list2cmdline(cmd_args))
    p = subprocess.Popen(pargs, stdout=sys.stdout, stderr=sys.stderr)
    exit_code = p.wait()
    if exit_code != 0:
        sys.exit(exit_code)


def do_up_rsync(config, host, files):
    local_dir = host["local_path"]
    remote_dir = host["remote_path"]
    local_paths = join_local_paths(local_dir, files)
    dest_src_dict = group_dir_files(local_paths, local_dir, remote_dir, True)

    host_name, host_args = make_host_args(host)
    for dir_, files in dest_src_dict.items():
        cmd_args = [ "rsync", config.get("rsync_args", "") ]
        cmd_args += host_args
        for f in files:
            cmd_args.append(f)
        cmd_args.append("{}:{}".format(host_name, dir_))

        run_rsync_cmd(cmd_args)


def do_down_rsync(config, host, files):
    local_dir = host["local_path"]
    remote_dir = host["remote_path"]
    local_paths = join_local_paths(local_dir, files)
    dest_src_dict = group_dir_files(local_paths, local_dir, remote_dir, False)

    host_name, host_args = make_host_args(host)
    for dir_, files in dest_src_dict.items():
        cmd_args = [ "rsync", config.get("rsync_args", "") ]
        cmd_args += host_args
        cmd_args.append("{}:{}".format(host_args[0], " ".join(files)))
        cmd_args.append(dir_)

        run_rsync_cmd(cmd_args)


def default_config_path():
    return os.path.join(os.environ["HOME"], ".psync_config.py")


def generate_config():
    config_file = default_config_path()
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

diff_cmd = 'vimdiff'
"""

    with open(config_file, "w") as f:
        f.write(txt)
    print("%s generated!" % config_file)


def read_config():
    config_file = default_config_path()
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
    if len(args) == 0:
        args.append(".")

    assert len(args) == 1
    cwd = os.getcwd()
    local_prefix = host["local_path"]
    remote_prefix = host["remote_path"]
    p = os.path.abspath(os.path.join(cwd, args[0]))
    assert p.startswith(local_prefix)
    assert os.path.exists(p)
    dest = p.replace(local_prefix, remote_prefix)
    if os.path.isfile(p):
        ssh_cmd = "cat %s" % dest
    else:
        ssh_cmd = "ls -1 %s" %dest

    cmp_host = make_host_args(host, cmd_type="ssh")
    pargs = [ "ssh" ] + cmp_host[1]
    pargs.append(cmp_host[0])
    pargs.append(ssh_cmd)
    print(subprocess.list2cmdline(pargs))

    diff_cmd = config.get("diff_cmd", "diff")
    with tempfile.NamedTemporaryFile("w+t") as f, tempfile.NamedTemporaryFile("w+t") as f2:
        if os.path.isdir(p):
            subp = subprocess.Popen(["ls", "-1", p], stdout=f2.file, stderr=sys.stderr)
            subp.wait()
            p = f2.name

        subp = subprocess.Popen(pargs, stdout=f.file, stderr=sys.stderr)
        exit_code = subp.wait()
        if exit_code != 0:
            sys.exit(exit_code)

        diff_args = [diff_cmd, p, f.name]
        print(subprocess.list2cmdline(diff_args))
        subp = subprocess.Popen(diff_args, stdout=sys.stdout, stderr=sys.stderr)
        subp.wait()


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
