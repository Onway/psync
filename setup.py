# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name="psyncf",
    version="1.0.0",
    description="A script based on rsync for synchronizing files",
    long_description="",
    url="https://github.com/Onway/psync",
    author="Onway",
    author_email="aluohuai@126.com",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=[ "psyncf" ],
    entry_points={
        'console_scripts': [
            'psync=psyncf.psync:main',
        ]
    },
)
