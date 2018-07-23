#!/usr/bin/env python
from .rperle import RPERLE


class RMINRLE(RPERLE):
    def __str__(self):
        return 'rmin'

    def perle(self, aold):
        """return an LWEP at a particular sample size m """
        aold1 = self.get_min(aold) | aold
        anew = self.rle(aold1)
        return anew, self.gbar, self.sehat
