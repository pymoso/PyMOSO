"""Packaging settings."""

import os
from codecs import open
from os.path import abspath, dirname, join
from subprocess import call
from setuptools import setup, Command
from pymoso import __version__


this_dir = abspath(dirname(__file__))
with open(join(this_dir, 'README.md'), encoding='utf-8') as file:
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
    name = 'pymoso',
    version = __version__,
    description = 'Python Multi-Objective Simulation Optimization: a package for using, implementing, and testing simulation optimization algorithms.',
    long_description = long_description,
    author = 'Kyle Cooper',
    author_email = 'coope149@purdue.edu',
    url = 'https://github.com/HunterResearch/PyMOSO',
    packages = ['pymoso', 'pymoso.solvers', 'pymoso.commands', 'pymoso.prng', 'pymoso.problems', 'pymoso.testers'],
    install_requires = ['docopt'],
    entry_points = {
        'console_scripts': [
            'pymoso = pymoso.cli:main',
        ],
    },
    python_requires='>=3.6.0',
    cmdclass={
        'clean': CleanCommand,
    },
)
