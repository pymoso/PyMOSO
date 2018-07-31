#!/usr/bin/env python
from .rperle import RPERLE
from ..chnutils import get_x0


class RRRPERLE(RPERLE):
    """R-PERLE with random restarts."""
    def perle(self, aold):
        """Return an LWEP at a particular sample size m."""
        num_RR = range(8)
        RR = set()
        orc1 = self.orc
        prn = self.sprn
        for i in num_RR:
            RR |= {get_x0(orc1, prn)}
        a1 = self.pe(aold | RR)
        anew = self.rle(a1)
        return anew, self.gbar, self.sehat
