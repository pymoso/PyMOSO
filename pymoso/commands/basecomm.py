"""
Base class for implementing CLI commands. Most users will not need to
use these functions.
"""
import os
import sys
import pathlib
import time
import collections
import importlib.util
from datetime import date
from .. import chnutils as mprun
from .. import solvers
from .. import problems
from .. import testers
from random import Random
from json import dump
import traceback


def load_user_module(mod_name, filepath):
    """
    Load a user-supplied .py file as a module registered under mod_name
    (e.g. 'pymoso.problems.myproblem'), with that file's own directory
    temporarily on sys.path so a sibling import (`from helper import
    ...`) resolves. sys.path is restored to its prior state afterward,
    not left mutated -- this can run more than once in the same
    process (repeated CLI-class invocations, e.g. in tests), and a
    permanent sys.path append is a side effect callers should not
    inherit.

    Marks the module __pymoso_dynamic__ = True: nothing backs mod_name
    as a real, independently-importable module (it only exists because
    this function put it in sys.modules), so a class from it can't be
    sent to a --simpar worker process by the usual pickle-by-reference
    route -- chnbase.build_transport_descriptor checks this marker to
    decide whether a class needs source-bundle transport instead.

    Parameters
    ----------
    mod_name : str
    filepath : str
        Path to the .py file, as given on the command line.

    Returns
    -------
    module
    """
    file_dir = os.path.dirname(os.path.abspath(filepath))
    sys.path.insert(0, file_dir)
    try:
        spec = importlib.util.spec_from_file_location(mod_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.__pymoso_dynamic__ = True
        sys.modules[mod_name] = module
    finally:
        sys.path.remove(file_dir)
    return module


def check_expname(name):
    """
    Check that the experiment file has been generated and load its
    contents.

    Parameters
    ----------
    name : str

    Returns
    -------
    datstr: str
    """
    if not os.path.isdir(name):
        return False
    fn = name + '/' + name + '.txt'
    fpath = pathlib.Path(fn)
    if not fpath.is_file():
        return False
    with open(fn, 'r') as f1:
        datstr = json.load(f1)
    return datstr


def save_errortb(name, errmsg):
    """
    Save a message to a file.

    Parameters
    ----------
    name : str
    errmsg : str
    """
    mydir = name
    pathlib.Path(name).mkdir(exist_ok=True)
    humfilen = 'err_' + name + '.txt'
    humpth = os.path.join(name, humfilen)
    with open(humpth, 'w') as f1:
        f1.write(errmsg)


def save_metadata(name, humantxt):
    """
    Save an experiment metadata string to a file.

    Parameters
    ----------
    name : str
    humantxt : str
    """
    mydir = name
    pathlib.Path(name).mkdir(exist_ok=True)
    humfilen = name + '.txt'
    humpth = os.path.join(name, humfilen)
    with open(humpth, 'w') as f1:
        dump(humantxt, f1, indent=4, separators=(',', ': '))


def gen_humanfile(name, probn, solvn, budget, runtime, param, vals, startseed, endseed):
    """
    Generate a human-readable experiment metadata string

    Parameters
    ----------
    name : str
    probn : str
    budget : int
    runtime : float
    param : list
    vals : list
    startseed : tuple of int
    endseed : tuple of int

    Returns
    -------
    ddict : dict
        ordered dictionary of the parameters and values
    """
    today = date.today()
    tstr = today.strftime("%A %d. %B %Y")
    timestr = time.strftime('%X')
    dnames = ('Name', 'Problem', 'Algorithm', 'Budget', 'Run time', 'Day', 'Time', 'Params', 'Param Values', 'start seed', 'end seed')
    ddate = (name, probn, solvn, budget, runtime, tstr, timestr, param, vals, startseed, endseed)
    ddict = collections.OrderedDict(zip(dnames, ddate))
    return ddict


def save_metrics(name, exp, metdata):
    """
    Save metrics data output to the experiment file.

    Parameters
    ----------
    name : str
    exp : int
    metdata : dict
    """
    pref = 'metrics_' + str(exp) + '_'
    ispdatn = pref + name + '.txt'
    metdatpth = os.path.join(name, ispdatn)
    metlst = []
    for i in metdata:
        metlst.append(str(metdata[i]))
    metstr = '\n'.join(metlst)
    with open(metdatpth, 'w') as f1:
        f1.write(metstr)


def save_isp(name, exp, ispdat):
    """
    Save testsolve output to the experiment file.

    Parameters
    ----------
    name : str
    exp : int
    ispdat : dict
    """
    pref = 'ispdata_' + str(exp) + '_'
    ispdatn = pref + name + '.txt'
    ispdatpth = os.path.join(name, ispdatn)
    isplst = []
    for i in ispdat:
        isplst.append(str(ispdat[i]))
    ispstr = '\n'.join(isplst)
    with open(ispdatpth, 'w') as f1:
        f1.write(ispstr)


def save_les(name, lesstr):
    """
    Save solve output to experiment file.

    Parameters
    ----------
    name : str
    lesstr : str
    """
    pref = 'rundata_'
    rundatn = pref + name + '.txt'
    rundpth = os.path.join(name, rundatn)
    with open(rundpth, 'w') as f2:
        f2.write(lesstr)


class BaseComm(object):
    """
    A base CLI command.

    Attributes
    ----------
    options : list
        List of options specified via CLI
    args : tuple
        List of arguments specified via CLI
    kwargs : dict
        List of keyword arguments specified to CLI

    Parameters
    ----------
    options : list
    args : tuple
    kwargs : dict
    """

    def __init__(self, options, *args, **kwargs):
        self.options = options
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """
        Placeholder function that must be implemented in command sub-classes.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError('You must implement the run() method yourself!')
