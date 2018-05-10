"""Packaging settings."""

import os
from codecs import open
from os.path import abspath, dirname, join
from subprocess import call
from setuptools import setup, Command
from ioboso import __version__


this_dir = abspath(dirname(__file__))
with open(join(this_dir, 'README.rst'), encoding='utf-8') as file:
    long_description = file.read()


class CleanCommand(Command):
    """Custom clean command to tidy up the project root."""
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -vrf ./build ./dist ./*.pyc ./*.tgz ./*.egg-info')


setup(
    name = 'ioboso',
    version = __version__,
    description = 'An integer-ordered simulation-optimization package in Python.',
    long_description = long_description,
    author = 'Kyle Cooper',
    author_email = 'coope149@purdue.edu',
    packages = ['ioboso', 'ioboso.solvers', 'ioboso.commands'],
    install_requires = ['docopt'],
    entry_points = {
        'console_scripts': [
            'ioboso = ioboso.cli:main',
        ],
    },
    cmdclass={
        'clean': CleanCommand,
    },
    package_data = {
        'ioboso': ['../prnseeds/orcseeds.pkl', '../prnseeds/solseeds.pkl', '../prnseeds/xorseeds.pkl'],
    },
)
