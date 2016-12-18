# psync.py
A script based on rsync for synchronizing code files written in python.

## Usage
1. Generate the default configuration file:

		psync.py --generate_config

	then modify `~/.psync_config.py` for remote host and directory config.
	
2. Upload the whole directory, just type:
	
		psync.py

3. Upload some files, use:

		psync.py f1 f2 f3
		
4. For more usages, see:

		psync.py --help
