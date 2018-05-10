import matplotlib.pyplot as pyp
import matplotlib
#matplotlib.rcParams['text.latex.preamble'] = ['\usepackage{ucal}']
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
fontProperties = {'family':'Times New Roman', 'weight': 'normal', 'size': 18}


def gen_counterplot():
    """generate the counter-example plot"""
    # initialize data (all are LEPs)
    x1 = (3, 3)
    x2 = (2, 3)
    x3 = (3, 2)
    x4 = (2, 2)
    x5 = (5, 3)
    x6 = (4, 4)
    x7 = (4 ,3)
    x8 = (5, 4)
    xpts = [x1, x2, x3, x4, x5]
    xgwep = [x8]
    xlep = [x6, x7]
    # set objectives values from left to right
    y1 = (0.75, 5.20)
    y2 = (0.96, 3.80)
    y3 = (1.55, 2.23)
    y6 = (2.15, 4.75)
    y4 = (2.30, 1.35)
    y7 = (2.85, 3.60)
    y5 = (3.25, 0.95)
    y8 = (4.05, 0.95)
    ypts = [y1, y2, y3, y4, y5]
    ygwps = [y8]
    ylep = [y6, y7]
    # initialize plot for feasible domain
    fig1 = pyp.figure(1, figsize=(11, 3))
    ax1 = fig1.add_subplot(121)
    ax1.set_xlim(1.5, 5.5)
    ax1.set_ylim(1.5, 4.5)
    # remove top and right enclosing lines
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    # remove tick marks
    ax1.set_xticks([])
    ax1.set_xticklabels([])
    ax1.set_yticks([])
    ax1.set_yticklabels([])
    # axes labels x_1, x_2
    f1xlab = r'$x_1$'
    f1ylab = r'$x_2$'
    ax1.set_xlabel(f1xlab, fontProperties)
    ax1.set_ylabel(f1ylab, fontProperties)
    # draw dashed outline around feasible space
    vx = [1.65, 2.65, 3.65, 5.35]
    vs = [1.75, 3.45, 1.75, 2.55]
    vy = [3.45, 4.40, 2.55, 4.40]
    hy = [3.45, 4.40, 1.75, 2.55]
    hs = [1.65, 2.65, 1.65, 3.65]
    hx = [2.65, 5.35, 3.65, 5.35]
    # ax1.vlines(vx, vs, vy, linestyle='dashed')
    # ax1.hlines(hy, hs, hx, linestyle='dashed')
    xzip = list(zip(*xpts))
    xxdata = xzip[0]
    xydata = xzip[1]
    ax1.scatter(xxdata, xydata, marker='o', edgecolor='black', facecolors='black', alpha=1.0, s=50, label=r'GEP')
    xwzip = list(zip(*xgwep))
    xwxdata = xwzip[0]
    xwydata = xwzip[1]
    ax1.scatter(xwxdata, xwydata, marker='o', edgecolor='black', facecolors='None', alpha=1.0, s=50, label=r'GWEP')
    xlepzip = list(zip(*xlep))
    xlepxdata = xlepzip[0]
    xlepydata = xlepzip[1]
    ax1.scatter(xlepxdata, xlepydata, marker='o', edgecolor='gray', facecolors='gray', alpha=1.0, s=70, label=r'$\mathcal{N}_1$-LEP')
    annoff = (-10, 10)
    x1str = r'$\boldsymbol{\mathrm{x}}_1^{\mathrm{min}}$'
    x2str = r'$\boldsymbol{\mathrm{x}}_2^*$'
    x3str = r'$\boldsymbol{\mathrm{x}}_3^*$'
    x4str = r'$\boldsymbol{\mathrm{x}}_4^{\mathrm{min}}$'
    x5str = r'$\boldsymbol{\mathrm{x}}_5^{\mathrm{min}}$'
    x6str = r'$\boldsymbol{\mathrm{x}}_6^{\mathrm{min}}$'
    x7str = r'$\boldsymbol{\mathrm{x}}_7^*$'
    x8str = r'$\boldsymbol{\mathrm{x}}_8^{\mathrm{min}}$'
    ax1.annotate(x1str, xy=x1, xytext=annoff, textcoords='offset points')
    ax1.annotate(x2str, xy=x2, xytext=annoff, textcoords='offset points')
    ax1.annotate(x3str, xy=x3, xytext=annoff, textcoords='offset points')
    ax1.annotate(x4str, xy=x4, xytext=annoff, textcoords='offset points')
    ax1.annotate(x5str, xy=x5, xytext=annoff, textcoords='offset points')
    ax1.annotate(x6str, xy=x6, xytext=annoff, textcoords='offset points')
    ax1.annotate(x7str, xy=x7, xytext=annoff, textcoords='offset points')
    ax1.annotate(x8str, xy=x8, xytext=annoff, textcoords='offset points')
    #ax1.annotate(r'\boldmath{$x_9^{\mbox{min}}$}', xy=x9, xytext=(-10, 5), textcoords='offset points', fontsize=12)
    #ax1.annotate(r'$\mathrm{\mathcal{X}}$', xy=(2.0, 4.0), xytext=(0, 0), textcoords='offset points')
    #initialize plot for objective space
    ax2 = fig1.add_subplot(122)
    # set axes labels g_1, g_2
    f2xlab = r'$g_1$'
    f2ylab = r'$g_2$'
    ax2.set_xlim(0.25, 4.5)
    ax2.set_ylim(0.25, 6.0)
    ax2.set_xlabel(f2xlab, fontProperties)
    ax2.set_ylabel(f2ylab, fontProperties)
    # remove top and right enclosing lines
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    # remove tick marks
    ax2.set_xticks([])
    ax2.set_xticklabels([])
    ax2.set_yticks([])
    ax2.set_yticklabels([])
    # connect equal dimensions
    yhy = [0.95]
    yhs = [0]
    yhx = [10]
    ax2.hlines(yhy, yhs, yhx, linestyle='dashed', color='gray', alpha=0.4)
    yzip = list(zip(*ypts))
    yxdata = yzip[0]
    yydata = yzip[1]
    ax2.scatter(yxdata, yydata, marker='o', edgecolor='black', facecolors='black', alpha=1.0, s=70)
    ywzip = list(zip(*ygwps))
    ywxdata = ywzip[0]
    ywydata = ywzip[1]
    ax2.scatter(ywxdata, ywydata, marker='o', edgecolor='black', facecolors='None', alpha=1.0, s=70, )
    ylepzip = list(zip(*ylep))
    ylepxdata = ylepzip[0]
    ylepydata = ylepzip[1]
    ax2.scatter(ylepxdata, ylepydata, marker='o', edgecolor='gray', facecolors='gray', alpha=1.0, s=70)
    # # modify legend styling
    legend = ax1.legend(bbox_to_anchor=(0.1, 0.9), fontsize=13, scatterpoints=1, handletextpad=0.00, borderaxespad=0, bbox_transform=pyp.gcf().transFigure)
    lframe = legend.get_frame()
    lframe.set_facecolor('1')
    lframe.set_edgecolor('1')
    lframe.set_alpha(0.0)
    boldg = r'$\boldsymbol{\mathrm{g}}$' + r'('
    y1str = boldg + x1str + r')'
    y2str = boldg + x2str + r')'
    y3str = boldg + x3str + r')'
    y4str = boldg + x4str + r')'
    y5str = boldg + x5str + r')'
    y6str = boldg + x6str + r')'
    y7str = boldg + x7str + r')'
    y8str = boldg + x8str + r')'
    ax2.annotate(y1str, xy=y1, xytext=annoff, textcoords='offset points')
    ax2.annotate(y2str, xy=y2, xytext=annoff, textcoords='offset points')
    ax2.annotate(y3str, xy=y3, xytext=annoff, textcoords='offset points')
    ax2.annotate(y4str, xy=y4, xytext=annoff, textcoords='offset points')
    ax2.annotate(y5str, xy=y5, xytext=annoff, textcoords='offset points')
    ax2.annotate(y6str, xy=y6, xytext=annoff, textcoords='offset points')
    ax2.annotate(y7str, xy=y7, xytext=annoff, textcoords='offset points')
    ax2.annotate(y8str, xy=y8, xytext=annoff, textcoords='offset points')
    fig1.savefig('../ScenData/ctrexample.pdf', transparent=True, bbox_inches='tight', pad_inches=0)
    pyp.show()


def main():
    gen_counterplot()

if __name__ == '__main__':
    main()
