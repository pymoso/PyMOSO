#!/usr/bin/env python
from .rperle import RPERLE
from math import ceil, pow


class RP_NORE(RPERLE):
    def __str__(self):
        return 'rp-nore'

    def calc_delta(self, se):
        """return RLE relaxation for an iteration nu"""
        return 0


class RMINRLE(RPERLE):
    def __str__(self):
        return 'rmin'

    def perle(self, aold):
        """return an LWEP at a particular sample size m """
        aold1 = self.get_min(aold) | aold
        anew = self.rle(aold1)
        return anew, self.gbar, self.sehat


class RRLE(RPERLE):
    def __str__(self):
        return 'rrle'

    def perle(self, aold):
        """return an LWEP at a particular sample size m """
        anew = self.rle(aold)
        return anew, self.gbar, self.sehat


class RRLE_NORE(RRLE):
    def __str__(self):
        return 'rrle-nore'

    def calc_delta(self, se):
        """return RLE relaxation for an iteration nu"""
        return 0


class RRLE_FULLRE(RRLE):
    def __str__(self):
        return 'rrle-fullre'

    def calc_delta(self, se):
        """return RLE relaxation for an iteration nu"""
        return float('inf')


class RPE(RPERLE):
    def __str__(self):
        return 'rpe'

    def perle(self, aold):
        """return an LWEP at a particular sample size m """
        anew = self.pe(aold)
        return anew, self.gbar, self.sehat


class RP_FULLRE(RPERLE):
    def __str__(self):
        return 'rp-fullre'

    def calc_delta(self, se):
        """return RLE relaxation for an iteration nu"""
        return float('inf')


class RPE_NORE(RPE):
    def __str__(self):
        return 'rpe-nore'

    def fse(self, se):
        """return diminishing standard error function for an iteration nu"""
        return 0
