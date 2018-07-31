#!/usr/bin/env python
from .rperle import RPERLE


class RMINRLE(RPERLE):
    """A benchmark for multi-objective simulation optimization on integer lattices"""
    def perle(self, aold):
        """return an LWEP at a particular sample size m """
        aold1 = self.get_min(aold) | aold
        anew = self.rle(aold1)
        return anew, self.gbar, self.sehat
