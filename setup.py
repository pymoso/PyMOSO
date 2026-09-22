"""Packaging settings."""

from os.path import abspath, dirname, join
from setuptools import setup
from pymoso import __version__


this_dir = abspath(dirname(__file__))
with open(join(this_dir, 'README.md'), encoding='utf-8') as file:
    long_description = file.read()


setup(
    name='pymoso',
    version=__version__,
    description=(
        'Python Multi-Objective Simulation Optimization: a package for '
        'using, implementing, and testing simulation optimization algorithms.'
    ),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Kyle Cooper',
    author_email='kyle@kylescooper.com',
    url='https://github.com/pymoso/PyMOSO',
    license='MIT',
    packages=[
        'pymoso',
        'pymoso.solvers',
        'pymoso.commands',
        'pymoso.prng',
        'pymoso.problems',
        'pymoso.testers',
    ],
    install_requires=[],
    entry_points={
        'console_scripts': [
            'pymoso = pymoso.cli:main',
        ],
    },
    python_requires='>=3.10',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
    ],
)
