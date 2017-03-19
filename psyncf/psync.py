# -*- coding: utf-8 -*-

"""A script based on rsync for synchronizing files"""

import os
import sys
import argparse
import subprocess
import tempfile
import logging


def do_sync(config, hosts, files, is_up=True):
    if len(files) == 0:
        files.append(".")
    logging.debug(files)

    if is_up:
        for host in hosts:
            do_up_sync(config, host, files)
    else:
        do_down_sync(config, hosts[0], files)


def do_up_sync(config, host, files):
    local_dir, remote_dir = get_config_dirs(host)
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


def do_down_sync(config, host, files):
    local_dir, remote_dir = get_config_dirs(host)
    local_paths = join_local_paths(local_dir, files)
    dest_src_dict = group_dir_files(local_paths, local_dir, remote_dir, False)

    host_name, host_args = make_host_args(host)
    for dir_, files in dest_src_dict.items():
        cmd_args = [ "rsync", config.get("rsync_args", "") ]
        cmd_args += host_args
        cmd_args.append("{}:{}".format(host_name, " ".join(files)))
        cmd_args.append(dir_)

        run_shell_cmd(cmd_args)


def do_compare(config, host, files):
    assert len(files) == 1 and os.path.isfile(files[0])
    logging.debug(files)

    local_dir, remote_dir = get_config_dirs(host)
    local_file = join_local_paths(local_dir, files, False)[0]
    remote_file = local_file.replace(local_dir, remote_dir)

    host_name, host_args = make_host_args(host, cmd_type="ssh")
    cmd_args = [ "ssh" ] + host_args
    cmd_args.append(host_name)
    cmd_args.append("cat %s" % remote_file)

    with tempfile.NamedTemporaryFile("w+t") as remote_output:
        run_shell_cmd(cmd_args, stdout=remote_output)

        diff_cmd = config.get("diff_cmd", "diff").split()
        diff_args = diff_cmd + [local_file, remote_output.name]
        run_shell_cmd(diff_args)


def generate_config(file_path):
    config_file = file_path if file_path else default_config_path()
    if os.path.isfile(config_file):
        print("%s already exist!" % config_file)
        return

    txt = """# Configuration file for psync.

# The key of the `hosts` is a host alias used by -h option.
# `ssh_name` is a hostname that matches one of the patterns given after the `Host` keyword in `ssh_config` file.
# `ssh_key` specify the identity_file for ssh.
# `paths` specify directory mapping between local and remote host.
hosts = {
    'localhost': {
        'ssh_name': 'localhost',
        'host': '',
        'port': 0,
        'user': '',
        'ssh_key': '',
        'paths': [
            {
                'local_dir': '',
                'remote_dir': ''
            }
        ],
    },
}

# Without -h option, use this for default.
default_host = 'localhost'

# Options given to `rsync` command.
rsync_args = '-avzC'

# Use this diff command when -c spcified.
diff_cmd = 'vimdiff'
"""

    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        logging.debug(txt)
        return

    with open(config_file, "w") as f:
        f.write(txt)
    print("%s generated!" % config_file)


def read_config(file_path, host_names):
    config_file = file_path if file_path else default_config_path()
    logging.debug(config_file)

    local = {}
    with open(config_file) as f:
        exec(f.read(), {}, local)
    logging.debug(local)
    
    if not host_names:
        host_names.append(local["default_host"])

    hosts = [ local["hosts"][name] for name in host_names ]
    logging.debug(hosts)
    return local, hosts


def default_config_path():
    return os.path.join(os.environ["HOME"], ".psync_config.py")


def get_config_dirs(host):
    cwd = os.getcwd()
    logging.debug(cwd)
    for dirs in host["paths"]:
        local_dir = os.path.abspath(dirs['local_dir'])
        remote_dir = os.path.abspath(dirs['remote_dir'])
        if cwd.startswith(local_dir):
            return local_dir, remote_dir


def make_host_args(host_config, cmd_type="rsync"):
    """Make up command arguments for rsync or ssh.

    Returns:
        (hostname, [arguments]) 
    """
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
        args = (user_host, [ "-p", str(port), "-i", ssh_key ])
    else:
        args = (user_host, [ "-e", "ssh -p %d -i %s" % (port, ssh_key) ])

    logging.debug(args)
    return args
        

def join_local_paths(local_dir, files, extend_root=True):
    """Return the local absolute paths of `files`.

    Args:
        local_dir: file's path must starts with this directory.
        files: list of files or directories.
        extend_root: return the sub entries when a file is `local_dir`.

    Returns:
        A list of local absolute paths
    """
    cwd = os.getcwd()
    dir_ = os.path.abspath(local_dir)

    paths = []
    for f in files:
        fpath = os.path.abspath(os.path.join(cwd, f))
        assert fpath.startswith(dir_)
        if fpath == dir_ and extend_root:
            paths += [ os.path.join(dir_, item) for item in os.listdir(dir_) ]
        else:
            paths.append(fpath)

    logging.debug(paths)
    return paths


def group_dir_files(local_paths, local_dir, remote_dir, is_up=True):
    """Group the source paths by their destination directory.

    Args:
        local_paths: local paths of files or directories to sync.
        is_up: is upload files. The source and destination may exchange
            according to this parameter.

    Returns:
        A dict likes { 'dest_dir': '[src_paths_list]' }.
    """
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


def main():
    parser = argparse.ArgumentParser(conflict_handler="resolve")
    parser.add_argument("--generate_config", action="store_true", help="generate config file")
    parser.add_argument("--debug", action="store_true", help="try operation but sync nothing")
    parser.add_argument("-C", "--config", default="", dest="cfile", help="specify config file path")
    parser.add_argument("-c", "--cmp", action="store_true", dest="cmp", help="compare file")
    parser.add_argument("-d", "--down", action="store_true", dest="down", help="download files")
    parser.add_argument("-h", "--host", default=[], dest="hosts", action="append", help="host alias from config file")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG,
                            format="%(funcName)s: %(message)s")

    if args.generate_config:
        generate_config(args.cfile)
        sys.exit(0)

    config, hosts = read_config(args.cfile, args.hosts)
    if args.cmp or args.down:
        assert len(hosts) == 1

    if args.cmp:
        do_compare(config, hosts[0], args.files)
    else:
        do_sync(config, hosts, args.files, not args.down)

    sys.exit(0)


if __name__ == "__main__":
    main()
