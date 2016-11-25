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
import logging

def make_host_args(host_config, cmd_type="rsync"):
    ssh_name = host_config.get("ssh_name", "")
    if ssh_name != "":
        args = (ssh_name, [])
        logging.debug(args)
        return args

    user = host_config["user"]
    ip = host_config["host"]
    port = host_config["port"]
    ssh_key = host_config["ssh_key"]

    user_host = "{}@{}".format(user, ip)
    if cmd_type == "ssh":
        args = (user_host, [ "-p", port, "-i", ssh_key ])
    else:
        args = (user_host, [ "-e", "ssh -p %d -i %s" % (port, ssh_key) ])

    logging.debug(args)
    return args
        

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

    logging.debug(paths)
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

    logging.debug(dest_src_dict)
    return dest_src_dict


def run_shell_cmd(cmd_args, stdout=sys.stdout, stderr=sys.stderr):
    logging.debug(cmd_args)
    print(subprocess.list2cmdline(cmd_args))

    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        return

    p = subprocess.Popen(cmd_args, stdout=stdout, stderr=stderr)
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

        run_shell_cmd(cmd_args)


def do_down_rsync(config, host, files):
    local_dir = host["local_path"]
    remote_dir = host["remote_path"]
    local_paths = join_local_paths(local_dir, files)
    dest_src_dict = group_dir_files(local_paths, local_dir, remote_dir, False)

    host_name, host_args = make_host_args(host)
    for dir_, files in dest_src_dict.items():
        cmd_args = [ "rsync", config.get("rsync_args", "") ]
        cmd_args += host_args
        cmd_args.append("{}:{}".format(host_name, " ".join(files)))
        cmd_args.append(dir_)

        run_shell_cmd(cmd_args)


def default_config_path():
    return os.path.join(os.environ["HOME"], ".psync_config.py")


def generate_config(file_path):
    config_file = file_path if file_path else default_config_path()
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

    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        logging.debug(txt)
        return

    with open(config_file, "w") as f:
        f.write(txt)
    print("%s generated!" % config_file)


def read_config(file_path, host_name):
    config_file = file_path if file_path else default_config_path()
    logging.debug(config_file)

    local = {}
    with open(config_file) as f:
        exec(f.read(), {}, local)
    logging.debug(local)
    
    host_key = host_name if host_name else local["default_host"]
    return local, local["hosts"][host_key]


def do_compare(config, host, files):
    if len(files) == 0:
        files.append(".")

    assert len(files) == 1
    cwd = os.getcwd()
    local_prefix = host["local_path"]
    remote_prefix = host["remote_path"]
    p = os.path.abspath(os.path.join(cwd, files[0]))
    assert p.startswith(local_prefix)
    assert os.path.exists(p)
    dest = p.replace(local_prefix, remote_prefix)
    if os.path.isfile(p):
        ssh_cmd = "cat %s" % dest
    else:
        ssh_cmd = "ls -1 %s" %dest

    host_name, host_args = make_host_args(host, cmd_type="ssh")
    pargs = [ "ssh" ] + host_args
    pargs.append(host_name)
    pargs.append(ssh_cmd)
    print(subprocess.list2cmdline(pargs))

    diff_cmd = config.get("diff_cmd", "diff")
    with tempfile.NamedTemporaryFile("w+t") as f, tempfile.NamedTemporaryFile("w+t") as f2:
        if os.path.isdir(p):
            run_shell_cmd(["ls", "-1", p], stdout=f2.file)
            p = f2.name

        run_shell_cmd(pargs, stdout=f.file)

        diff_args = [diff_cmd, p, f.name]
        run_shell_cmd(diff_args)


def do_sync(config, host, files, is_up=True):
    if len(files) == 0:
        files.append(".")
    logging.debug(files)

    if is_up:
        do_up_rsync(config, host, files)
    else:
        do_down_rsync(config, host, files)


if __name__ == "__main__":
    parser = optparse.OptionParser(conflict_handler="resolve")
    parser.add_option("--generate_config", action="store_true", help="generate config")
    parser.add_option("--debug", action="store_true", help="debug")
    parser.add_option("-f", "--file", default="", dest="cfile", help="config file path")
    parser.add_option("-c", "--cmp", action="store_true", dest="cmp", help="compare file")
    parser.add_option("-d", "--down", action="store_true", dest="down", help="download files")
    parser.add_option("-h", "--host", default="", dest="host", help="host alias")
    options, args = parser.parse_args()

    if options.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(funcName)s: %(message)s")

    if options.generate_config:
        generate_config(options.cfile)
        sys.exit(0)
    config, host = read_config(options.cfile, options.host)

    if options.cmp:
        do_compare(config, host, args)
    else:
        do_sync(config, host, args, not options.down)

    sys.exit(0)
