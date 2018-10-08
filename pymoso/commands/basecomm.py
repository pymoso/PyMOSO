"""The base command."""
import os
import pathlib
import time
import collections
from datetime import date
from .. import chnutils as mprun
from .. import solvers
from .. import problems
from .. import testers
from random import Random
from json import dump
import traceback


def check_expname(name):
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
    mydir = name
    pathlib.Path(name).mkdir(exist_ok=True)
    humfilen = 'err_' + name + '.txt'
    humpth = os.path.join(name, humfilen)
    with open(humpth, 'w') as f1:
        f1.write(errmsg)


def save_metadata(name, humantxt):
    mydir = name
    pathlib.Path(name).mkdir(exist_ok=True)
    humfilen = name + '.txt'
    humpth = os.path.join(name, humfilen)
    with open(humpth, 'w') as f1:
        dump(humantxt, f1, indent=4, separators=(',', ': '))


def gen_humanfile(name, probn, solvn, budget, runtime, param, vals, startseed, endseed):
    today = date.today()
    tstr = today.strftime("%A %d. %B %Y")
    timestr = time.strftime('%X')
    dnames = ('Name', 'Problem', 'Algorithm', 'Budget', 'Run time', 'Day', 'Time', 'Params', 'Param Values', 'start seed', 'end seed')
    ddate = (name, probn, solvn, budget, runtime, tstr, timestr, param, vals, startseed, endseed)
    ddict = collections.OrderedDict(zip(dnames, ddate))
    return ddict


def save_metrics(name, exp, metdata):
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
    pref = 'rundata_'
    rundatn = pref + name + '.txt'
    rundpth = os.path.join(name, rundatn)
    with open(rundpth, 'w') as f2:
        f2.write(lesstr)


class BaseComm(object):
    """A base command."""

    def __init__(self, options, *args, **kwargs):
        self.options = options
        self.args = args
        self.kwargs = kwargs

    def run(self):
        raise NotImplementedError('You must implement the run() method yourself!')
