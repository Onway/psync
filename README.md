# psync.py
A script based on rsync for synchronizing files written in python.

## Install
`pip install psyncf`

## Usage
1. Generate the default configuration file:

		psync --generate_config

	then modify `~/.psync_config.py` for remote host and directory config.
	
2. Upload the whole directory, just type:
	
		psync

3. Upload some files, use:

		psync f1 f2 f3
		
4. For more usages, see:

		psync --help
