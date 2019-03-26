"""
Summary
-------
Provides implementation of the Bus Scheduling problem for use in PyMOSO.
"""
from ..chnbase import Oracle

class BSProb(Oracle):
    """
    An Oracle that simulates the Test Simple SO problem.

    Attributes
    ----------
    num_obj : int, 2
    dim : int
        The maximum number of buses to schedule between 0 and tau. Default is 9.
    tau : int
        The amount of time to simulate passenger arrivals and schedule buses.
    lambd : float
        The rate of passenger arrivals. Default is 10.
    gamma : float
        Exponential factor of the cost of passengers. Default is 0.5.
    c0 : float
        The flat cost of scheduling a bus. Default is 100.

    Parameters
    ----------
    rng : prng.MRG32k3a object

    See also
    --------
    chnbase.Oracle
    """
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 9
        self.tau = 100
        self.lambd = 10
        self.gamma = 0.5
        self.c0 = 100
        super().__init__(rng)

    def g(self, x, rng):
        """
        Simulates one replication of the Bus Scheduling problem. PyMOSO requires
        that all valid Oracles implement an Oracle.g.

        Parameters
        ----------
        x : tuple of int
        rng : prng.MRG32k3a object

        Returns
        -------
        isfeas : bool
        tuple of float
            simulated objective values
        """
        ### Bus Scheduling Problem Parameters
        # the length of the day > 0
        tau = self.tau
        # the arrival rate > 0
        arrlambda = self.lambd
        # the constant cost
        c0 = self.c0
        # the power gamma
        gamma = self.gamma
        # check feasibility
        isfeas = True
        for i in x:
            if i < 0 or i > tau:
                    isfeas = False
        # simulate arrivals
        waitsum = None
        buscost = None
        if isfeas:
            # get buses after time 0
            newx = list(set(sorted(tuple(xi for xi in x if xi > 0 and not xi == tau))))
            if newx:
                num_buses = len(newx)
                numperbus = [0 for bus in newx]
                bustime = newx[0]
            else:
                bustime = tau
            tarrive = 0
            # simulate first arrival time now
            tarrive += rng.expovariate(arrlambda)
            currbus = 0
            waitsum = 0
            numlastbus = 0
            numarrive = 0
            while tarrive <= tau:
                numarrive += 1
                bus_not_found = True
                if tarrive < bustime and not bustime == tau:
                    numperbus[currbus] += 1
                    bus_not_found = False
                if tarrive > bustime and bus_not_found:
                    bustime = tau
                    bus_i = 0
                    while bus_i < num_buses and bus_not_found:
                        if newx[bus_i] >= tarrive and newx[bus_i] < bustime:
                            bus_not_found = False
                            bustime = newx[bus_i]
                            currbus = bus_i
                            numperbus[bus_i] += 1
                        bus_i += 1
                if bustime == tau and bus_not_found:
                    numlastbus += 1
                    bus_not_found = True
                waitsum += (bustime - tarrive)
                tarrive += rng.expovariate(arrlambda)
##            if not sum(numperbus) + numlastbus == numarrive:
##                print('-- -- number of arrivals does not match number of bus boarders. wtf?')
##          print(x, newx, waitsum, numperbus, num_buses)
            if newx:
                buscost1 = sum([c0 + numperbus[bus]**gamma for bus in range(num_buses)])
            else:
                buscost1 = 0
            buscost2 = c0 + numlastbus**gamma
            buscost = buscost1 + buscost2
##          print(x, newx, waitsum, numperbus, buscost)
        return isfeas, (buscost, waitsum)
