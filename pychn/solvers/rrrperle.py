#!/usr/bin/env python
from .rperle import RPERLE


class RRRPERLE(RPERLE):
    """R-PERLE but with random restarts"""
    def __str__(self):
        return 'rrrp'
