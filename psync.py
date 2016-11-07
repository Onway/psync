#!/usr/bin/env python3

import os
import sys
import optparse

parser = optparse.OptionParser(conflict_handler="resolve")
parser.add_option("--generate_config", action="store_true", help="generate config")
parser.add_option("-d", "--down", action="store_true", dest="down", help="download files")
parser.add_option("-h", "--host", default="", dest="host", help="host alias")
(options, args) = parser.parse_args()

if __name__ == "__main__":
    if options.generate_config:
        print(options.generate_config)
        sys.exit(0)

    sys.path.append(os.environ["HOME"])
    config = __import__("psync_config")
    host = config.hosts.get(options.host if options.host != "" else config.default_host)
    assert host is not None
    print(host)
