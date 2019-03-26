"""
Summary
-------
Provide the tester for the Bus Scheduling problem.
"""
from ..problems import bsprob
from math import sqrt


def get_ranx0(rng):
	"""
	Uniformly sample from the feasible space.

	Parameters
	----------
	rng : prng.MRG32k3a object

	Returns
	-------
	x0 : tuple of int
		The randomly chosen point
	"""
	tau = 100
	q = 9
	mr = range(tau)
	x0 = tuple(rng.choice(mr) for i in range(q))
	return x0


def true_g(x):
	"""
	Compute the expected values of a point.

	Parameters
	----------
	x : tuple of int
		A feasible point

	Returns
	-------
	tuple of float
		The objective values
	"""
	lambd = 10
	q = 9
	c0 = 100
	tau = 100
	xext = list(x).extend([0, tau])
	xsrt = sorted(xext)
	obj1 = 0
	obj2 = 0
	for i in range(1, q + 1):
		indic = xsrt[i] - xsrt[i - 1]
		pass_cost = sqrt(lamd*indic) if indic > 0 else 0
		fixed_cost = c0*indic if indic > 0 else 0
		obj1 += pass_cost + fixed_cost
		obj2 += indic**2
	return obj1, obj2*(lambd/2.0)


class BSTester(object):
	"""
	Store useful data for working with the Bus Scheduling problem

	Attributes
	----------
	ranorc : chnbase.Oracle class, BSProb
	true_g : function, true_g
	get_ranx0 : function, get_ranx0
	"""
	def __init__(self):
		self.ranorc = bsprob.BSProb
		#self.answer = myanswer
		self.true_g = true_g
		self.get_ranx0 = get_ranx0

	def metric(self, eles):
		"""
		Compute a metric from a simulated solution to the true solution. For
		the Bus scheduling problem, the true solution is unkown and this
		function exists to allow using the testsolve command.

		Parameters
		----------
		eles : set of tuple of numbers
			Simulated solution

		Returns
		-------
		float
			The performance metric
		"""
		return 0
