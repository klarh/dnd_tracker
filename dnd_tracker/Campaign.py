from collections import defaultdict
from .Combat import Combat

class Campaign:
    def __init__(self, name=None):
        self.name = name
        self._combat_stats = defaultdict(dict)

    def begin_combat(self, name):
        return Combat(self, name)

    def get_combat_stats(self, name, **kwargs):
        result = dict(self._combat_stats[name])
        result.update(kwargs)
        return result

    def set_combat_stats(self, name, **kwargs):
        self._combat_stats[name].update(kwargs)

default_campaign = Campaign('default')

def begin_combat(name):
    return default_campaign.begin_combat(name)
