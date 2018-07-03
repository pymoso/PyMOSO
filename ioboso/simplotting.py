import pickle
import matplotlib.pyplot as pyp
import matplotlib.animation as animation
#import brewer2mpl
import matplotlib
matplotlib.rcParams['font.family'] = 'serif'
matplotlib.rcParams['font.serif'] = 'Times New Roman'
matplotlib.rcParams['font.size'] = 14
matplotlib.rcParams['mathtext.fontset'] = 'custom'
matplotlib.rcParams['mathtext.rm'] = 'Times New Roman'
matplotlib.rcParams['mathtext.it'] = 'Times New Roman'
matplotlib.rcParams['mathtext.bf'] = 'Times New Roman:bold'
matplotlib.rcParams['mathtext.default'] = 'regular'
matplotlib.rcParams['text.usetex'] = 'True'
matplotlib.rcParams['text.latex.preamble']=[r'\usepackage{amsmath}']
labelfontProperties = {'family':'Times New Roman', 'weight': 'normal', 'size': 18}

def gen_paramplot(fnlst, paramlst, pref, suff, probname):
    title = r'Set distance by parameter value\\Simulation budget = 1M, ' + probname
    dhlab = r'Distance'
    xlab = r'Parameter value'
    dkeys = ('AB', 'BA')
    dlabs = (r'$d(g(\hat{\mathcal{P}}), \mathcal{E})$', r'$d(\mathcal{E}, g(\hat{\mathcal{P}}))$')
    labdicts = dict(zip(dkeys, dlabs))
    dat = dict()
    for fn in fnlst:
        with open(pref+fn+suff, 'rb') as h:
            dat[fn] = pickle.load(h)
    pyp.rc('text', usetex=True)
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    vlx = paramlst
    vlymin = [0]*len(paramlst)
    vlymax = [100]*len(paramlst)
    ax1.vlines(vlx, vlymin, vlymax, linestyle='dashed', color='lightgray', alpha=0.4)
    col = ['gray', 'blue', 'gray', 'blue', 'darkgray', 'red', 'yellow']
    sty = ['-', '--', ':', '--', '-']
    for ctr, datakey in enumerate(dkeys):
        X = []
        Y25 = []
        Y75 = []
        for find, fn in enumerate(fnlst):
            X.append(paramlst[find])
            Y25.append(dat[fn][datakey]['Y12'][-1])
            Y75.append(dat[fn][datakey]['Y18'][-1])
        ax1.fill_between(X, Y25, Y75, alpha=0.8, linewidth=0, color=col[ctr], label=labdicts[datakey])
    # remove top and right enclosing lines
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.set_title(title)
    ax1.set_xlabel(xlab)
    ax1.set_ylabel(dhlab)
    ax1.set_axisbelow(True)
    legend = ax1.legend(loc=1, fontsize=10, scatterpoints=1, handletextpad=0.00)
    frame = legend.get_frame()
    frame.set_facecolor('1.0')
    frame.set_edgecolor('1.0')
    #ax1.grid(axis='y', color="0.8", alpha=0.3, linestyle='-', linewidth=1)
    ax1.tick_params(length=0)
    # remove tick marks
    ax1.set_yticks([0, 1, 2, 3, 4, 5])
    ax1.set_xticks([0, 1, 2])
    # ax1.set_xticklabels([0, 1, 2])
    # ax1.tick_params(length=0)
    ax1.set_xlim(0, 2)
    ymax = 5
    ax1.set_ylim(0, ymax)
    #ax1.set_xticks(paramlst)
    #ax1.set_xticklabels(['$'+str(int(j/mydiv))+'$' for j in tixlst])
    fig1.savefig('../ScenData/paramplt.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    pyp.show()


def plot_hdquantplot(fnlst, lblst, pref, suff, budget, savename, ymax, should_show=False):
    """plot the hausdorf distances per simulation effort for a set of runs"""
    title = r'Quantiles of Hausdorf distance'
    dhlab = r'$d_H(g(\hat{\mathcal{P}}), \mathcal{E})$'
    xlab = r'Total simulation effort ($w_\nu$) x $10^6$'
    labmul = 1000000
    datakey = 'hd'
    num_xticks = 5
    dat = dict()
    for fn in fnlst:
        with open(pref+fn+suff, 'rb') as h:
            dat[fn] = pickle.load(h)
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    col = ['black', 'gray', 'blue', 'darkgray', 'red', 'yellow', 'limegreen', 'orange']
    sty = ['-', '--', ':', '--', '-']
    #bmap = brewer2mpl.get_map('Set2', 'qualitative', 8)
    #col = bmap.mpl_colors
    s0 = 1
    sx = budget + 1
    sn = 1
    X = dict()
    ctr = 0
    for find, fn in enumerate(fnlst):
        X = dat[fn][datakey]['X'][s0:sx:sn]
        Y05 = dat[fn][datakey]['Y105'][s0:sx:sn]
        Y25 = dat[fn][datakey]['Y12'][s0:sx:sn]
        Y50 = dat[fn][datakey]['Y15'][s0:sx:sn]
        Y75 = dat[fn][datakey]['Y18'][s0:sx:sn]
        Y95 = dat[fn][datakey]['Y195'][s0:sx:sn]
        #line05 = ax1.plot(X, Y05, linewidth=1.5, color=col[ctr], linestyle=sty[ctr])
        line25 = ax1.plot(X, Y25, linewidth=1.5, color=col[find], linestyle=sty[find])
        line50 = ax1.plot(X, Y50, linewidth=1.5, color=col[find], linestyle=sty[find], label=lblst[fn])
        line75 = ax1.plot(X, Y75, linewidth=1.5, color=col[find], linestyle=sty[find])
        #line95 = ax1.plot(X, Y95, linewidth=1.5, color=col[ctr], linestyle=sty[ctr])
        ctr += 1
    ax1.set_title(title, y=1.05)
    ax1.set_ylabel(dhlab)
    ax1.set_xlabel(xlab)
    mydiv = budget/num_xticks
    ax1.set_axisbelow(True)
    ax1.tick_params(length=0)
    ax1.set_xlim(0, budget)
    ax1.set_ylim(0, ymax)
    ytix = [(i/num_xticks)*ymax for i in range(num_xticks + 1)]
    ax1.set_yticks(ytix, False)
    ax1.set_yticklabels(['$'+str(tic)+'$' for tic in ytix])
    tixlst = [(i/num_xticks)*budget for i in range(num_xticks + 1)]
    ax1.set_xticks(tixlst, False)
    ax1.set_xticklabels(['$'+str(j/labmul)+'$' for j in tixlst])
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    # modify legend styling
    legend = ax1.legend(loc=1, fontsize=10, scatterpoints=1, handletextpad=0.00, ncol=1)
    lframe = legend.get_frame()
    lframe.set_facecolor('1')
    lframe.set_edgecolor('1')
    #ax1.grid()
    pyp.savefig(savename, transparent=True, bbox_inches='tight', pad_inches=0)
    if should_show:
        pyp.show()


def show_rleplot(rundat):
    """plot the points found by RLE per retrospective iteration"""
    with open(rundat, 'rb') as h:
        dat = pickle.load(h)
    exp = 10
    for nu in dat[exp]['phat']:
        pyp.figure(1)
        d1, d2 = zip(*mcD)
        pyp.scatter(d1, d2, s=2, color='b', alpha=0.2)
        Xp1 = mydat1['phat'][nu]
        Xc = mydat1['crpts'].get(nu, set())
        Xp1 -= Xc
        p11, p12 = zip(*Xp1)
        pyp.scatter(p11, p12, s=5, color='r')
        if Xc:
            c11, c12 = zip(*Xc)
            pyp.scatter(c11, c12, s=5, color='y')
        pyp.xlabel('$x_1$')
        pyp.ylabel('$x_2$')
        pyp.savefig( + '__' + str(nu) + '.pdf')
        pyp.clf()


def plot_testproblem(test, should_show=False):
    """plot the feasible space, function space, and Pareto set of a problem"""
    from ioboso.simoptutils import feas2set, get_biparetos, get_les
    fn = test.tname
    xdic = test.detorc.get_feasspace()
    dim = test.detorc.dim
    nobj = test.detorc.num_obj
    mcX = set(feas2set(xdic))
    gdict = {x: test.detorc.g(x) for x in mcX}
    paretos = get_biparetos(gdict)
    leslst = get_les(gdict)
    unloc = set()
    for les in leslst:
        unloc |= les
    xdom = {d: [] for d in range(dim)}
    xpar = {d: [] for d in range(dim)}
    xloc = {d: [] for d in range(dim)}
    ydom = {o: [] for o in range(nobj)}
    ypar = {o: [] for o in range(nobj)}
    yloc = {o: [] for o in range(nobj)}
    for x in mcX - unloc - paretos:
        for d in range(dim):
            xdom[d].append(x[d])
        for o in range(nobj):
            ydom[o].append(gdict[x][o])
    for x in unloc - paretos:
        for d in range(dim):
            xloc[d].append(x[d])
        for o in range(nobj):
            yloc[o].append(gdict[x][o])
    for x in paretos:
        for d in range(dim):
            xpar[d].append(x[d])
        for o in range(nobj):
            ypar[o].append(gdict[x][o])
    print('..... drawing plot objects in feasible space .....')
    fig1 = pyp.figure(1, figsize=(11, 5))
    # plot 3d if needed
    if dim < 3:
        ax1 = fig1.add_subplot(121)
        # dominated points
        Xdomplt = ax1.scatter(xdom[0], xdom[1], color='lightgray', alpha=0.2, s=1, label='Dominated points')
        # LES
        Xlocplt = ax1.scatter(xloc[0], xloc[1], color='black', alpha=0.6, s=18, label='LES members')
        # nondominated
        Xparplt = ax1.scatter(xpar[0], xpar[1], color='black', s=20, label='Non-dominated points')
        ax1.set_title(test.tname + ' feasible points')
    else:
        from mpl_toolkits.mplot3d import Axes3D
        ax1 = fig1.add_subplot(121, projection='3d')
        # dominated points
        #Xdomplt = ax1.scatter(xdom[0], xdom[1], xdom[2], color='gray', alpha=0.1, s=10, label='Dominated points')
        # LES
        Xlocplt = ax1.scatter(xloc[0], xloc[1], xloc[2], color='darkgray', alpha=0.7, s=13, label='LES members')
        # nondominated
        Xparplt = ax1.scatter(xpar[0], xpar[1], xpar[2], color='black', s=20, label='Non-dominated points')
        ax1.set_title(test.tname + ' feasible points', y=1.08)
    # set up labels, plot edges, and title
    ax1.set_xlabel(r'$x_1$', labelfontProperties)
    xmin = min(mcX, key=lambda x: x[0])
    xmax = max(mcX, key=lambda x: x[0])
    ax1.set_xlim(xmin[0], xmax[0])
    ax1.set_ylabel(r'$x_2$', labelfontProperties)
    ymin = min(mcX, key=lambda x: x[1])
    ymax = max(mcX, key=lambda x: x[1])
    ax1.set_ylim(ymin[1],ymax[1])
    # add z axis if needed
    if dim == 3:
        ax1.set_zlabel(r'$x_3$')
        zmin = min(mcX, key=lambda x: x[2])
        zmax = max(mcX, key=lambda x: x[2])
        ax1.set_zlim(zmin[2], zmax[2])
    # modify legend styling
    legend = ax1.legend(loc=1, fontsize=10, scatterpoints=1, handletextpad=0.00, ncol=1)
    lframe = legend.get_frame()
    lframe.set_facecolor('1')
    lframe.set_edgecolor('1')
    # remove top and right enclosing lines
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    # ax1.set_xticks([])
    ax1.set_xticklabels([r'$'+ str(int(t)) + '$' for t in ax1.get_xticks()])
    # ax1.set_yticks([])
    ax1.set_yticklabels([r'$'+ str(int(t)) + '$' for t in ax1.get_yticks()])

    print('..... drawing plot objects in objective space .....')
    ax2 = fig1.add_subplot(122)
    if dim < 3:
        #dominated
        Ydomplt = ax2.scatter(ydom[0], ydom[1], color='lightgray', alpha=0.2, s=1, label='Dominated points')
    #LES
    Ylocplt = ax2.scatter(yloc[0], yloc[1], color='black', alpha=0.6, s=18, label='LES members')
    #non Dominated
    Yparplt = ax2.scatter(ypar[0], ypar[1], color='black', s=20, label='Non-dominated points')
    #set up labels, plot edges, and title
    ax2.set_title(test.tname + ' objective values')
    ax2.set_xlabel(r'$g_1$', labelfontProperties)
    xmin = min(mcX, key=lambda x: gdict[x][0])
    xmax = max(mcX, key=lambda x: gdict[x][0])
    ax2.set_xlim(gdict[xmin][0] - 0.2, gdict[xmax][0] + 0.2)
    ax2.set_ylabel(r'$g_2$', labelfontProperties)
    ymin = min(mcX, key=lambda x: gdict[x][1])
    ymax = max(mcX, key=lambda x: gdict[x][1])
    ax2.set_ylim(gdict[ymin][1] - 0.2, gdict[ymax][1] + 0.2)
    # remove top and right enclosing lines
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.set_xticklabels([r'$' + str(t) + '$' for t in ax2.get_xticks()])
    ax2.set_yticklabels([r'$' + str(t) + '$' for t in ax2.get_yticks()])
    print('..... saving plot to ' + fn + '.pdf .....')
    fig1.savefig(fn + '.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    if should_show:
        pyp.show()



def show_crawlcomp(fn1, fn2):
    """plot points found in RLE for two different runs"""
    with open(fn1, 'rb') as h1:
        rundata1 = pickle.load(h1)
    # with open(fn2, 'rb') as h2:
    #     rundata2 = pickle.load(h2)
    num_exp = len(rundata1)
    crpts1 = dict()
    # crpts2 = dict()
    # tct1 = 0
    tct2 = 0
    for exp in range(0, num_exp):
        for nu1 in rundata1[exp]['crpts'].keys():
            dd2 = rundata1[exp]['crpts'][nu1]
            cnt2 = len(dd2)
            tct2 += cnt2
            l2 = crpts1.get(nu1, 0)
            crpts1[nu1] = l2 + cnt2
    # for exp in range(0, num_exp):
    #     for nu1 in rundata2[exp]['crpts'].keys():
    #         dd2 = rundata2[exp]['crpts'][nu1]
    #         cnt2 = len(dd2)
    #         tct2 += cnt2
    #         l2 = crpts2.get(nu1, 0)
    #         crpts2[nu1] = l2 + cnt2
    NU1 = [x[0] for x in crpts1.items()]
    if NU1:
        NU1.remove(max(NU1))
    # NU2 = [x[0] for x in crpts2.items()]
    # if NU2:
    #     NU2.remove(max(NU2))
    TB1 = [crpts1[x]/num_exp for x in NU1]
    # TB2 = [crpts2[x]/num_exp for x in NU2]
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    clpe1line = ax1.plot(NU1, TB1, color='black', linestyle='-', label=r'RPERLE, with k=max and deltabox, $\beta_\epsilon = 0.4, \beta_\delta=0.35$')
#    clpe2line = ax1.plot(NU2, TB2, color='blue', linestyle='--', label=r'RPERLE, k=min $\beta=0.5, \gamma=0.4$')
    ax1.set_xlabel(r'Retrospective Iteration $\nu$', fontsize=24)
    ax1.set_ylabel(r'Points added in searches', fontsize=24)
    ax1.set_title('Test Problem 1a, 100 replications')
    pyp.legend()
    pyp.show()


def show_tbcomp(rundata1, rundata2):
    """plot number of points found via traceback per retrospective iteration"""
    num_exp = len(rundata1)
    tb_dclpe = dict()
    tb_dtspe = dict()
    tct1 = 0
    tct2 = 0
    for exp in range(0, num_exp):
        for nu1 in rundata1[exp]['tb_pts'].keys():
            dd1 = rundata1[exp]['tb_pts'][nu1]
            cnt1 = len(dd1)
            tct1 += cnt1
            l1 = tb_dclpe.get(nu1, 0)
            tb_dclpe[nu1] = l1 + cnt1
        for nu2 in rundata2[exp]['tb_pts'].keys():
            dd2 = rundata2[exp]['tb_pts'][nu2]
            cnt2 = len(dd2)
            tct2 += cnt2
            l2 = tb_dtspe.get(nu2, 0)
            tb_dtspe[nu2] = l2 + cnt2
    NU1 = [x[0] for x in tb_dclpe.items()]
    NU1.remove(max(NU1))
    NU2 = [x[0] for x in tb_dtspe.items()]
    NU2.remove(max(NU2))
    TB1 = [tb_dclpe[x]/num_exp for x in NU1]
    TB2 = [tb_dtspe[x]/num_exp for x in NU2]
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    clpeline = ax1.plot(NU1, TB1, color='blue', linestyle='-', label='Two-sided Pe')
    tspeline = ax1.plot(NU2, TB2, color='green', linestyle='--', label='Classic Pe')
    ax1.set_xlabel(r'Retrospective Iteration $nu$', fontsize=24)
    ax1.set_ylabel(r'Mean points found in traceback', fontsize=24)
    ax1.legend()
    pyp.show()


def show_bindb(names, pref, suff, labels, datakey, budget, num_macroreps, num_splits):
    """plot number of SPLINE instances bound by b"""
    ylab = r'SPLINE Instances'
    xlab = r'Retrospective Iteration'
    title = r'Mean Number of SPLINE Instances bound by $b$'
    num_xticks = 5
    mydiv = budget/num_xticks
    stages = [int(budget*i/num_splits) for i in range(1, num_splits + 1)]
    nameslist = dict()
    for name in names:
        nameslist[name] = [pref+name+str(j)+suff for j in stages]
    dat = dict()
    namecount = {name: dict() for name in names}
    expctr = dict()
    pyp.rc('text', usetex=True)
    colors = ['black', 'black', 'gray', 'limegreen', 'darkgray']
    sty = ['-', '--', ':', '--', '-']
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    for nind, name in enumerate(names):
        expctr[name] = 0
        for fn in nameslist[name]:
            with open(fn, 'rb') as h:
                dat[fn] = pickle.load(h)
            num_exp = len(dat[fn])
            for exp in range(0, num_exp):
                expctr[name] += 1
                for nu in dat[fn][exp][datakey].keys():
                    num_b = dat[fn][exp][datakey][nu]
                    nameb = namecount[name].get(nu, 0)
                    namecount[name][nu] = nameb + num_b
    for nind, name in enumerate(names):
        lastnu = sorted(list(namecount[name]))[-1]
        print(name, ' RA: ', lastnu, ' Number of experiments: ', expctr[name])
        X = list(namecount[name].keys())
        Y = [namecount[name][nu]/expctr[name] for nu in X]
        bline = ax1.plot(X, Y, color=colors[nind], linestyle=sty[nind], label=labels[nind])
    # ax1.annotate(r'$m=14, b=54,$ hi $b=216$', xy=(20, 3), xytext=(-80, 50), textcoords='offset points',arrowprops=dict(arrowstyle="->", connectionstyle="arc3"))
    # ax1.annotate(r'$m=609, b=2436,$ hi $b=9744$', xy=(60, 14), xytext=(-170, 10), textcoords='offset points',arrowprops=dict(arrowstyle="->", connectionstyle="arc3"))
    ax1.set_xlabel(xlab)
    ax1.set_ylabel(ylab)
    legend = ax1.legend(loc=2, fontsize=10, scatterpoints=1, handletextpad=0.00)
    frame = legend.get_frame()
    frame.set_facecolor('1.0')
    frame.set_edgecolor('1.0')
    ax1.set_title(title)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', color="0.8", alpha=0.3, linestyle='-', linewidth=1)
    ax1.set_axisbelow(True)
    ax1.tick_params(length=0)
    pyp.savefig('../ScenData/bindbplot.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    pyp.show()

def indep_qplot(names, pref, suff, labels, title, budget, num_macroreps, num_splits):
    dhlab = r'$d_H(g(\hat{\mathcal{P}}), \mathcal{E})$'
    xlab = r'Total simulation effort ($w_\nu$) x $10^6$'
    datakey = 'hd'
    meankey = 'mean'
    sekey = 'se'
    num_xticks = 5
    mydiv = budget/num_xticks
    stages = [int(budget*i/num_splits) for i in range(1, num_splits + 1)]
    nameslist = dict()
    for name in names:
        nameslist[name] = [pref+name+str(j)+suff for j in stages]
    dat = dict()
    pyp.rc('text', usetex=True)
    colors = ['black', 'black', 'gray', 'limegreen', 'darkgray']
    sty = ['-', '--', ':', '--', '-']
    # bmap = brewer2mpl.get_map('Set2', 'qualitative', 7)
    # colors = bmap.mpl_colors
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    linehandles = []
    split_size = int(budget/num_splits)
    for nind, name in enumerate(names):
        for fn in nameslist[name]:
            with open(fn, 'rb') as h:
                dat[fn] = pickle.load(h)
        md = dict()
        s0 = 0
        sz = split_size
        sn = 1
        X = []
        Y05 = []
        Y25 = []
        Y50 = []
        Y75 = []
        Y95 = []
        lind = 0
        for i, fn in enumerate(nameslist[name]):
            md[fn] = dat[fn][datakey]
            datX = md[fn]['X']
            newX = [x for x in datX if x >= s0 and x < sz]
            X.extend(newX)
            num_ind = len(newX)
            y05 = md[fn]['Y105'][lind:lind + num_ind]
            y25 = md[fn]['Y12'][lind:lind + num_ind]
            y50 = md[fn]['Y15'][lind:lind + num_ind]
            y75 = md[fn]['Y18'][lind:lind + num_ind]
            y95 = md[fn]['Y195'][lind:lind + num_ind]
            Y05.extend(y05)
            Y25.extend(y25)
            Y50.extend(y50)
            Y75.extend(y75)
            Y95.extend(y95)
            lind += num_ind
            s0 += split_size
            sz += split_size
        #line05 = ax1.plot(X[1:], Y05[1:], linewidth=1.5, color=colors[nind], linestyle=sty[nind])
        line25 = ax1.plot(X[1:], Y25[1:], linewidth=1.5, color=colors[nind], linestyle=sty[nind])
        line50 = ax1.plot(X[1:], Y50[1:], linewidth=1.5, color=colors[nind], linestyle=sty[nind], label=labels[nind])
        line75 = ax1.plot(X[1:], Y75[1:], linewidth=1.5, color=colors[nind], linestyle=sty[nind])
        #line75 = ax1.plot(X[1:], Y95[1:], linewidth=1.5, color=colors[nind], linestyle=sty[nind])
    legend = ax1.legend(loc=1, fontsize=10, scatterpoints=1, handletextpad=0.00)
    frame = legend.get_frame()
    frame.set_facecolor('1.0')
    frame.set_edgecolor('1.0')
    ax1.set_title(title)
    ax1.set_ylabel(dhlab)
    ax1.set_xlabel(xlab)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', color="0.8", alpha=0.3, linestyle='-', linewidth=1)
    ax1.set_axisbelow(True)
    ax1.tick_params(length=0)
    ax1.set_xlim(0, budget)
    ymax = 5
    ax1.set_ylim(0, ymax)
    ytix = [(i/num_xticks)*ymax for i in range(num_xticks + 1)]
    ax1.set_yticks(ytix, False)
    ax1.set_yticklabels(['$'+str(tic)+'$' for tic in ytix])
    tixlst = [(i/num_xticks)*budget for i in range(num_xticks + 1)]
    ax1.set_xticks(tixlst, False)
    ax1.set_xticklabels(['$'+str(int(j/mydiv))+'$' for j in tixlst])
    pyp.savefig('../ScenData/indepquant.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    pyp.show()


def sample_path_plot(fn, tp):
    # initialize test problem data
    xdic = tp.detorc.get_feasspace()
    dim = tp.detorc.dim
    nobj = tp.detorc.num_obj
    mcX = set(feas2set(xdic))
    gdict = {x: tp.detorc.g(x) for x in mcX | {(0, 51), (51, 0)}}
    xtitle = r'Feasible Space'
    ytitle = r'Objective Space'
    domxlab = r'$x_1$'
    domylab = r'$x_2$'
    objxlab = r'$\bar{G}_1$'
    objylab = r'$\bar{G}_2$'
    expnum = 0
    # read in rundata
    datakey = 'phat'
    seedkey = 'runseed'
    epskey = 'epsilons'
    kconkey = 'kstar'
    dat = dict()
    with open(fn, 'rb') as h:
        dat = pickle.load(h)
    nulist = sorted(list(dat[expnum][datakey].keys()))
    # initialize plot
    pyp.rc('text', usetex=True)
    fig1 = pyp.figure(1, figsize=(15, 6))
    ax1 = fig1.add_subplot(121)
    ax1.set_title(xtitle)
    ax1.set_xlabel(domxlab)
    ax1.set_ylabel(domylab)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(False)
    ax1.set_axisbelow(True)
    ax1.tick_params(length=0)
    ax1.set_xlim(0, 50)
    ax1.set_ylim(0, 50)
    ax2 = fig1.add_subplot(122)
    ax2.set_title(ytitle)
    ax2.set_xlabel(objxlab)
    ax2.set_ylabel(objylab)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(False)
    ax2.set_axisbelow(True)
    ax2.tick_params(length=0)
    ax2.set_xlim(0, 25)
    ax2.set_ylim(0, 35)
    pars = get_biparetos(gdict)
    Px = list(zip(*pars))[0]
    Py = list(zip(*pars))[1]
    Ex = [gdict[x][0] for x in pars]
    Ey = [gdict[x][1] for x in pars]
    X1 = list(zip(*mcX-pars))[0]
    Y1 = list(zip(*mcX-pars))[1]
    X2 = [gdict[x][0] for x in mcX - pars]
    Y2 = [gdict[x][1] for x in mcX - pars]
    Xdomplt = ax1.scatter(X1, Y1, color='lightgray', alpha=0.5, s=1, label='Dominated points')
    Ydomplt = ax2.scatter(X2, Y2, color='lightgray', alpha=0.5, s=1, label='Dominated points')
    xparplt = ax1.scatter(Px, Py, color='lightblue', alpha=0.8, s=7, label='Efficient set')
    yparplt = ax2.scatter(Ex, Ey, color='lightblue', alpha=0.8, s=7, label='Image of efficient set')
    Xparline = ax1.scatter([], [], color='black', alpha=1.0, s=15, label='EALES members')
    Yparline = ax2.scatter([], [], color='black', alpha=1.0, s=15, label='Image of EALES')
    veps = ax2.vlines([], [], [], linestyle='dashed')
    heps = ax2.hlines([], [], [], linestyle='dashed')
    xtxtstr = r'$\nu=' + str(expnum) + '$\n' + '$m = 2$'
    Xtext = ax1.text(40, 45, xtxtstr)
    prnseed = dat[expnum][seedkey]
    prn = MRG32k3a(prnseed)
    orc = tp.ranorc(prn)
    orc.set_crnflag(True)
    is_rp = True
    def animate(nu, Xparline, Yparline, Xtext):
        phat = dat[expnum][datakey][nu]
        mnu = int(ceil(2*1.1**nu))
        gbar = dict()
        sedict = dict()
        # for x in phat:
        #     isfeas, fx, sex = orc.hit(x, mnu)
        #     gbar[x] = fx
        #     sedict[x] = sex
        orc.crn_advance()
        xtxtstr = r'$\nu=' + str(nu) + '$\n' + '$m = ' + str(mnu) + '$'
        Xtext.set_text(xtxtstr)
        ypar = [gdict[x] for x in phat]
        Xparline.set_offsets(list(phat))
        Yparline.set_offsets(ypar)
        return Xparline, Yparline, Xtext, Ydomplt,
    ani = animation.FuncAnimation(fig1, animate, nulist, interval=500, repeat=False, fargs=(Xparline, Yparline, Xtext))
    ani.save('../ScenData/rp_sp_mov.mp4', writer='ffmpeg')


def seg_plot_se(names, pref, suff, labels, budget, num_macroreps, num_splits):
    title = r'Mean Hausdorf Distances with Standard Error'
    dhlab = r'$d_H(g(\hat{\mathcal{P}}), \mathcal{E})$'
    xlab = r'Total simulation effort ($w_\nu$) x $10^6$'
    datakey = 'hd'
    meankey = 'mean'
    sekey = 'se'
    num_xticks = 5
    mydiv = budget/num_xticks
    stages = [int(budget*i/num_splits) for i in range(1, num_splits + 1)]
    nameslist = dict()
    for name in names:
        nameslist[name] = [pref+name+str(j)+suff for j in stages]
    dat = dict()
    pyp.rc('text', usetex=True)
    colors = ['black', 'black', 'gray', 'limegreen', 'darkgray']
    sty = ['-', '--', ':', '--', '-']
    # bmap = brewer2mpl.get_map('Set2', 'qualitative', 7)
    # colors = bmap.mpl_colors
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    linehandles = []
    split_size = int(budget/num_splits)
    for nind, name in enumerate(names):
        for fn in nameslist[name]:
            with open(fn, 'rb') as h:
                dat[fn] = pickle.load(h)
        md = dict()
        s0 = 0
        sz = split_size
        sn = 1
        X = []
        Y50 = []
        seu = []
        sel = []
        for i, fn in enumerate(nameslist[name]):
            md[fn] = dat[fn][datakey]
            datX = md[fn]['X']
            newX = [x for x in datX if x >= s0 and x <= sz]
            X.extend(newX)
            if newX:
                for x in newX:
                    xmean = dat[fn][meankey][x]
                    xse = dat[fn][sekey][x]
                    Y50.append(xmean)
                    seu.append(xmean + xse)
                    sel.append(xmean - xse)
            s0 += split_size
            sz += split_size
        pltline = ax1.plot(X[1:], Y50[1:], linewidth=1.5, color=colors[nind], linestyle=sty[nind], label=labels[nind])
        ax1.fill_between(X[1:], seu[1:], sel[1:], alpha=0.18, linewidth=0, color=colors[nind])
    legend = ax1.legend(loc=1, fontsize=10, scatterpoints=1, handletextpad=0.00)
    frame = legend.get_frame()
    frame.set_facecolor('1.0')
    frame.set_edgecolor('1.0')
    ax1.set_title(title)
    ax1.set_ylabel(dhlab)
    ax1.set_xlabel(xlab)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', color="0.8", alpha=0.3, linestyle='-', linewidth=1)
    ax1.set_axisbelow(True)
    ax1.tick_params(length=0)
    ax1.set_xlim(0, budget)
    ymax = 1
    ax1.set_ylim(0, ymax)
    ytix = [(i/num_xticks)*ymax for i in range(num_xticks + 1)]
    ax1.set_yticks(ytix, False)
    ax1.set_yticklabels(['$'+str(tic)+'$' for tic in ytix])
    tixlst = [(i/num_xticks)*budget for i in range(num_xticks + 1)]
    ax1.set_xticks(tixlst, False)
    ax1.set_xticklabels(['$'+str(int(j/mydiv))+'$' for j in tixlst])
    pyp.savefig('../ScenData/seg_se_plt.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    pyp.show()


def heat_anim(name, label, budget, tp):
    title = r'Solution density per '+ label + ' retrospective iteration'
    ylab = r'$x_2$'
    xlab = r'$x_1$'
    pkey = 'phat'
    dat = dict()
    nuhistd = dict()
    # get rundata from the file
    with open(name, 'rb') as h:
        dat = pickle.load(h)
    # generate the count of each points in each RA iteration
    num_exp = len(dat)
    for exp in range(num_exp):
        for nu in dat[exp][pkey]:
            nudict = nuhistd.get(nu, dict())
            nuhistd[nu] = nudict
            phat = dat[exp][pkey][nu]
            for p in phat:
                nump = nuhistd[nu].get(p, 0)
                nuhistd[nu][p] = nump + 1
    # get the feasible region points
    xdic = tp.detorc.get_feasspace()
    dim = tp.detorc.dim
    nobj = tp.detorc.num_obj
    mcX = set(feas2set(xdic))
    # plot the heatmap
    pyp.rc('text', usetex=True)
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    bmap = brewer2mpl.get_map('Greys', 'sequential', 8).mpl_colormap
    ax1.set_xlim(0, 50)
    ax1.set_ylim(0, 50)
    ax1.set_title(title)
    ax1.set_ylabel(ylab)
    ax1.set_xlabel(xlab)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    ax1.spines['bottom'].set_visible(False)
    ax1.set_yticks([], False)
    ax1.set_xticks([], False)
    X1 = list(zip(*mcX))[0]
    Y1 = list(zip(*mcX))[1]
    Xdomplt = ax1.scatter(X1, Y1, color='lightgray', alpha=0.5, s=1, label='Dominated points')
    Hexdat = ax1.hexbin([], [], C=[])
    xtxtstr = r'$\nu=' + str(0) + '$'
    Xtext = ax1.text(40, 45, xtxtstr)
    def animate(nu, Hexdat, Xtext):
        xtxtstr = r'$\nu=' + str(nu) + '$'
        Xtext.set_text(xtxtstr)
        # generate the heatmap data
        X1 = []
        Y1 = []
        Z1 = []
        for x in mcX:
            X1.append(x[0])
            Y1.append(x[1])
            z = nuhistd[nu].get(x, 0)
            Z1.append(z)
        Hexdat = ax1.hexbin(X1, Y1, C=Z1, cmap=bmap, gridsize=40, bins=None)
        return Hexdat, Xtext
    nulist = range(len(nuhistd))
    print('....Generating video of Algorithm ', label, ' with ', str(len(nulist)), ' iterations....')
    ani = animation.FuncAnimation(fig1, animate, nulist, interval=500, repeat=False, fargs=(Hexdat, Xtext))
    ani.save('../ScenData/heatnu.mp4', writer='ffmpeg')


def show_heatplt(name, label, budget, tp):
    title = r'Solution density per '+ label + ' retrospective iteration'
    ylab = r'$x_2$'
    xlab = r'$x_1$'
    pkey = 'phat'
    dat = dict()
    nuhistd = dict()
    # get rundata from the file
    with open(name, 'rb') as h:
        dat = pickle.load(h)
    # generate the count of each points in each RA iteration
    num_exp = len(dat)
    for exp in range(num_exp):
        for nu in dat[exp][pkey]:
            nudict = nuhistd.get(nu, dict())
            nuhistd[nu] = nudict
            phat = dat[exp][pkey][nu]
            for p in phat:
                nump = nuhistd[nu].get(p, 0)
                nuhistd[nu][p] = nump + 1
    # get the feasible region points
    xdic = tp.detorc.get_feasspace()
    dim = tp.detorc.dim
    nobj = tp.detorc.num_obj
    mcX = set(feas2set(xdic))
    # generate the heatmap data
    testnu = 35
    X1 = []
    Y1 = []
    Z1 = []
    for x in mcX:
        X1.append(x[0])
        Y1.append(x[1])
        z = nuhistd[testnu].get(x, 0)
        Z1.append(z)
    # plot the heatmap
    pyp.rc('text', usetex=True)
    fig1 = pyp.figure(1)
    ax1 = fig1.add_subplot(111)
    bmap = brewer2mpl.get_map('Greys', 'sequential', 8).mpl_colormap
    ax1.hexbin(X1, Y1, C=Z1, cmap=bmap, gridsize=40, bins=None)
    ax1.set_xlim(0, 50)
    ax1.set_ylim(0, 50)
    ax1.set_title(title)
    ax1.set_ylabel(ylab)
    ax1.set_xlabel(xlab)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    ax1.spines['bottom'].set_visible(False)
    ax1.set_yticks([], False)
    ax1.set_xticks([], False)
    pyp.savefig('../ScenData/heatplt.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    pyp.show()


def main():
    # gen_bindb()
    # gen_se_plt()
    # gen_counterplot()
    gen_quanplt()
    # get_rundat_stats()
    # gen_indep_quant()
    # gen_sp_anim()
    # show_paramplt()
    # gen_heatplt()


def show_paramplt():
    pref = '../../RPxxxMay2_TP1a_1000/'
    probname = 'TP1a'
    suff = '_' + probname + '_pltdat.pkl'
    #names = ('rmin400', 'rmin401', 'rmin402', 'rmin403', 'rmin404', 'rmin405', 'rmin406', 'rmin407', 'rmin408', 'rmin409', 'rmin410', 'rmin411', 'rmin412', 'rmin413', 'rmin414', 'rmin415')
    names = ('rp400', 'rp401', 'rp402', 'rp403', 'rp404', 'rp405', 'rp406', 'rp407', 'rp408', 'rp409', 'rp410', 'rp411', 'rp412', 'rp413', 'rp414', 'rp415')
    labd = {name: name for name in names}
    params1 = tuple(0.4 for name in names)
    params2 = tuple(i/10 for i in range(len(names)))
    gen_paramplot(names, params2, pref, suff, probname)


def gen_sp_anim():
    tp = '_TP1a_'
    mypref = '../../RPE_TP1a_FSE/'
    mysuff1 = tp + 'rundat.pkl'
    tag = 'rpe-08'
    n1 = mypref+tag+mysuff1
    tp = TP1aTester()
    sample_path_plot(n1, tp)


def get_rundat_stats():
    tp = '_TP1a_'
    mypref = '../../RPxx_TP1a_1000/'
    mysuff1 = tp + 'rundat.pkl'
    mysuff2 = tp + 'pltdat.pkl'
    tag = 'rp49'
    n1 = mypref+tag+mysuff1
    n2 = mypref+tag+mysuff2
    with open(n1, 'rb') as h1:
        rundata1 = pickle.load(h1)
    with open(n2, 'rb') as h2:
        pltdat1 = pickle.load(h2)
    num_instances = len(rundata1)
    last_iter = list(rundata1.keys())[-1]
    print('Algorithm tag: ', tag)
    print('Test Problem tag: ', tp)
    print('Number of Instances: ', num_instances)
    for nu in rundata1[last_iter]['kstar']:
        print(nu, rundata1[last_iter]['kstar'][nu])


def gen_quanplt():
    n1 = 'rp'
    n2 = 'rrle'
    n3 = 'moc'
    n4 = 'rrle4400000'
    l1 = r'R-P$\varepsilon$RLE'
    l2 = r'R-RLE'
    l3 = r'MO-COMPASS'
    l4 = r'R-RLE'
    pref = '../testrun/'
    suff = '_plt.pkl'
    # names = ('rrle-fullre', 'rrle-02', 'rrle-04', 'rrle-06',  'rrle-nore')
    # names = ('rp-fullre', 'rp-02', 'rp-04', 'rp-06',  'rp-nore')
    # names = ('rpe-02', 'rpe-04', 'rpe-06', 'rpe-08', 'rpe-nore', 'rrle-02', 'rrle-04', 'rrle-06', 'rrle-08', 'rrle-nore')
    # labels = (r'R-P$\varepsilon$, $\beta_\varepsilon=0.2$', r'R-P$\varepsilon$, $\beta_\varepsilon=0.4$', r'R-P$\varepsilon$, $\beta_\varepsilon=0.6$', r'R-P$\varepsilon$, $\beta_\varepsilon=0.8$', r'R-P$\varepsilon$, $\delta=0$', r'R-RLE, $\beta_\gamma=0.2$', r'R-RLE, $\beta_\gamma=0.4$', r'R-RLE, $\beta_\gamma=0.6$', r'R-RLE, $\beta_\gamma=0.8$',r'R-RLE, $\delta=0$')
    # labels = (r'R-RLE, infinite relaxation', r'R-RLE, $\gamma=0.2$', r'R-RLE, $\gamma=0.4$', r'R-RLE, $\gamma=0.6$', r'R-RLE, no relaxation')
    # labels = (r'R-P$\varepsilon$RLE, infinite relaxation', r'R-P$\varepsilon$RLE, $\gamma=0.2$', r'R-P$\varepsilon$RLE, $\gamma=0.4$', r'R-P$\varepsilon$RLE, $\gamma=0.6$', r'R-P$\varepsilon$RLE, no relaxation')
    # names = ('rp49', 'rp55', 'rp435', 'rp39', 'rp59')
    # labels = (r'R-P$\varepsilon$RLE, $\beta_\varepsilon=0.4, \beta_\delta=0.9$', r'R-P$\varepsilon$RLE, $\beta_\varepsilon=0.5, \beta_\delta=0.5$', r'R-P$\varepsilon$RLE, $\beta_\varepsilon=0.4, \beta_\delta=0.35$', r'R-P$\varepsilon$RLE, $\beta_\varepsilon=0.3, \beta_\delta=0.9$', r'R-P$\varepsilon$RLE, $\beta_\varepsilon=0.5, \beta_\delta=0.9$')
    # labd = dict(zip(names, labels))
    # print(labd)
    # names = ('rmin400', 'rmin401', 'rmin402', 'rmin403', 'rmin404', 'rmin405', 'rmin406', 'rmin407', 'rmin408', 'rmin409', 'rmin410', 'rmin411', 'rmin412', 'rmin413', 'rmin414', 'rmin415')
    # names = ('rp400', 'rp401', 'rp402', 'rp403', 'rp404', 'rp405', 'rp406', 'rp407', 'rp408', 'rp409', 'rp410', 'rp411', 'rp412', 'rp413', 'rp414', 'rp415')
    # labd = {name: name for name in names}
    # params1 = tuple(0.4 for name in names)
    # params2 = tuple(i/10 for i in range(len(names)))
    # paramrange = range(0, 21)
    # paramlst = [i/10 for i in paramrange]
    # names = tuple('rrle'+str(paramrange[i]) for i in paramrange)
    # labels = tuple('rrle'+str(paramrange[i]) for i in paramrange)
    names = ('testrun',)
    labd = {'testrun': 'testrun'}
    budget = 50000
    show_hdquantplot(names, labd, pref, suff, budget)


def gen_indep_quant():
    n1 = 'rp'
    n2 = 'rrle'
    n3 = 'moc'
    l1 = r'R-P$\varepsilon$RLE'
    l2 = r'R-RLE'
    l3 = r'MO-COMPASS'
    pref = '../../indep_hib/'
    suff = '_TP1a_pltdat.pkl'
    title = r'Quantiles of Hausdorf Distance'
    names = [n1, n2, n3]
    labels = [l1, l2, l3]
    budget = 5000000
    num_exp = 100
    num_splits = 25
    indep_qplot(names, pref, suff, labels, title, budget, num_exp, num_splits)


def gen_heatplt():
    pref = '../../RPxx_TP1a_1000/'
    suff = '_TP1a_rundat.pkl'
    n1 = 'rp49'
    l1 = r'R-P$\varepsilon$RLE, $\beta_\varepsilon=0.4, \beta_\delta=0.9$'
    budget = 5000000
    name = pref+n1+suff
    tp = TP1aTester()
    heat_anim(name, l1, budget, tp)


def gen_se_plt():
    n1 = 'rpnb'
    n2 = 'rrle'
    n3 = 'moc'
    n5 = 'rp'
    n6 = 'rp'
    l1 = r'R-P$\varepsilon$RLE, $b=8*1.1^\nu$'
    l2 = r'R-RLE'
    l3 = r'MO-COMPASS'
    l5 = r'R-P$\varepsilon$RLE'
    l6 = r'R-P$\varepsilon$RLE, $b=8*1.1^\nu$, FindNewLWEP always non-empty'
    pref = '../../RP_TP1a_indep/'
    suff = '_TP1a_pltdat.pkl'
    names = [n1]
    labels = [l5]
    budget = 5000000
    num_exp = 100
    num_splits = 25
    seg_plot_se(names, pref, suff, labels, budget, num_exp, num_splits)


def gen_bindb():
    n1 = 'rphib'
    n2 = 'rrlehib'
    n3 = 'rp'
    n4 = 'rrle'
    n5 = 'rpnb'
    l1 = r'R-P$\varepsilon$RLE, $b=32*1.1^\nu$'
    l2 = r'R-RLE, $b=32*1.1^\nu$'
    l3 = r'R-P$\varepsilon$RLE, $b=8*1.1^\nu$'
    l4 = r'R-RLE, $b=8*1.1^\nu$'
    l5 = r'R-P$\varepsilon$RLE, $b=8*1.2^\nu$'
    pref = '../../indep_hib/'
    suff = '_TP1a_rundat.pkl'
    names = [n1, n2, n3, n4, n5]
    labels = [l1, l2, l3, l4, l5]
    budget = 500000
    num_exp = 100
    num_splits = 25
    show_bindb(names, pref, suff, labels, 'bind', budget, num_exp, num_splits)


if __name__ == '__main__':
    main()
