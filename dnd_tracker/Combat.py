from collections import Counter, defaultdict
import logging

import numpy as np

logger = logging.getLogger(__name__)

_stats = ['str', 'dex', 'con', 'int', 'wis', 'cha']

_combat_css = """
<style>
table.combat_tracker {
    text-align: center;
    margin-left: auto;
    margin-right: auto;
}

table.combat_tracker th {
    font-size: 107%;
    border-bottom: 2px dashed gray;
}

table.combat_tracker th, td {
    padding: 0.25em 1em;
}

table.combat_tracker tr:nth-child(even) {
    background-color: #f0f0f0;
}
</style>
"""

_damage_types = [
    ('acid', 'a', 'ac'),
    ('bludgeoning', 'b', 'bl'),
    ('cold', 'c', 'co'),
    ('fire', 'i', 'fi'),
    ('force', 'f', 'fo'),
    ('lightning', 'l', 'li'),
    ('necrotic', 'n', 'ne'),
    ('piercing', 'p', 'pi'),
    ('poison', 'o', 'po'),
    ('radiant', 'r', 'ra'),
    ('slashing', 's', 'sl'),
    ('thunder', 't', 'th'),
]

_damage_type_map = {None: None}

for names in _damage_types:
    canonical_name = names[0]
    for name in names:
        _damage_type_map[name] = canonical_name

def get_damage_type(type=None):
    return _damage_type_map[type]

def cubeellipse_intensity(theta, lam=0.5, lam_r1=.1, lam_r2=.05, gamma=1., s=0., r=1., h=1.):
    """Compute a cubeellipse colormap with pseudo-random intensity variations

    cubeellipse_intensity is an analogous colormap to cubehelix, but
    in an ellipse perpendicular to the color cube diagonal rather than
    in a helix along the color cube diagonal (with additional
    intensity variations). It can be used for generating categorical
    color maps, for example.

    :param theta: angle array for colors
    :param lam: scalar lambda value about which the ellipse will expand
    :param lam_r1: major axis of ellipse in `lam` space
    :param lam_r2: minor axis of ellipse in `lam` space
    :param gamma: `lam` rescaling factor: `lam <- lam**gamma`
    :param s: The hue of the starting color: (0, 1, 2) -> (blue, red, green) at `lam=0`
    :param r: Number of rotations through R->G->B to make (in `lam`-space)
    :param h: Hue parameter controlling saturation
    """

    theta %= 2*np.pi

    if lam_r2 is None:
        lam_r2 = lam_r1

    lamtheta = 1 + 480*np.sqrt(theta) - 1024*theta**2
    lam = lam + np.cos(lamtheta)*lam_r1 + np.sin(lamtheta)*lam_r2
    lam = lam**gamma

    a = h*lam*(1 - lam)*.5
    v = np.array([[-.14861, 1.78277], [-.29227, -.90649], [1.97294, 0.]], dtype=np.float32)
    ctarray = np.array([np.cos(theta*r + s), np.sin(theta*r + s)], dtype=np.float32)
    return np.clip(lam + a*v.dot(ctarray), 0, 1).T

class Character:
    def __init__(self, combat, name, initiative, number=None, ac=None, resistances={},
                hp=None, dex=None, saves=None):
        self.combat = combat
        self.name = name
        self.initiative = initiative
        self.number = number
        self.ac = ac
        self.resistances = dict(resistances)
        self.hp = self.initial_hp = hp
        self.dex = dex
        self.saves = saves

    def get_true_damage(self, amount, type=None):
        type = get_damage_type(type)
        return int(amount*self.resistances.get(type, 1))

    def take_damage(self, amount, type=None):
        type = get_damage_type(type)
        true_amount = self.get_true_damage(amount, type)
        self.combat._record_take_damage(self, amount, type, true_amount)
        if self.hp is not None:
            self.hp -= true_amount
            self.hp = max(0, self.hp)

    def damage(self, other, amount, type=None):
        type = get_damage_type(type)
        true_amount = other.get_true_damage(amount, type)
        if other.hp is not None:
            true_amount = min(other.hp, true_amount)
        self.combat._record_damage(self, other, amount, type, true_amount)
        other.take_damage(amount, type)
        return self.combat

    def set_ac(self, value):
        self.ac = ac

    def heal(self, amount):
        self.hp += amount
        self.combat._record_heal(self, amount)

    def get_numbered_name(self):
        return self.name + (' {}'.format(self.number) if self.number is not None else '')

def initiative_sort_key(character):
    dex = character.dex or 10
    number = character.number or 0
    return (-character.initiative, -dex, character.name, number)

class Combat:
    """Manage a single combat encounter.

    Characters are added to combat via :py:func:`add`.
    """
    def __init__(self, campaign, name):
        self.campaign = campaign
        self.name = name
        self.combatants = []
        self.combatant_name_counts = Counter()
        self._damage_warnings = set()

        self._initialize_db()

    def _initialize_db(self):
        with self.campaign._connection as c:
            c.execute('CREATE TABLE IF NOT EXISTS combats '
                      '(name STR, campaign_id INT, '
                      'CONSTRAINT unique_campaign_name UNIQUE (name, campaign_id)'
                      'ON CONFLICT IGNORE)')
            c.execute('INSERT INTO combats VALUES (?, ?)',
                      (self.name, self.campaign._db_id))

            for (identifier,) in c.execute(
                    'SELECT rowid FROM combats WHERE name = ? AND campaign_id = ?',
                    (self.name, self.campaign._db_id)):
                pass

            self._db_id = identifier

            c.execute('CREATE TABLE IF NOT EXISTS damage_taken '
                      '(combat_id INT, target TEXT, type TEXT, amount INT, true_amount INT)')
            c.execute('CREATE TABLE IF NOT EXISTS damage_given '
                      '(combat_id INT, target TEXT, source TEXT, type TEXT, amount INT, true_amount INT)')
            c.execute('CREATE TABLE IF NOT EXISTS healing '
                      '(combat_id INT, target TEXT, true_amount INT)')

            c.execute('DELETE FROM damage_taken WHERE combat_id = ?', (self._db_id,))
            c.execute('DELETE FROM damage_given WHERE combat_id = ?', (self._db_id,))
            c.execute('DELETE FROM healing WHERE combat_id = ?', (self._db_id,))

    def add(self, name, initiative, **kwargs):
        """Add a character to combat.

        Characters with duplicate names automatically have their number incremented.

        :param name: Name of the character to add to combat.
        :param initiative: Value to use when ordering characters in combat.
        :param ac: Armor class value to display in combat
        :param resistances: Dictionary of per-type damage modifiers (such as 0.5 or 2) to apply to each damage type
        :param hp: Hit points to use for characters that should have their HP tracked
        :param dex: Dexterity ability score to use to break ties in initiative order
        :param saves: Dictionary of per-ability score saving throw modifiers to display
        """
        kwargs = self.campaign.get_combat_stats(name, **kwargs)

        self.combatant_name_counts[name] += 1
        count = self.combatant_name_counts[name]
        if 'number' not in kwargs and count > 1:
            kwargs['number'] = count

        combatant = Character(self, name, initiative, **kwargs)
        self.combatants.append(combatant)
        self.combatants.sort(key=initiative_sort_key)

        for res in combatant.resistances:
            key = (combatant.name, res)
            if res not in _damage_type_map and key not in self._damage_warnings:
                self._damage_warnings.add(key)
                msg = ('{}: Non-trivial resistance type "{}" will not be '
                       'automatically applied').format(*key)
                logger.warning(msg)

        return combatant

    def plot_damage_summary(self, figure=None, received=False):
        """Create a bar plot of the damage given or received by each combatant."""
        if figure is None:
            import matplotlib, matplotlib.pyplot as pp
            figure = pp.figure()

        if received:
            return self.plot_damage_received(figure)
        else:
            return self.plot_damage_given(figure)

    def plot_damage_given(self, figure):
        ax = figure.gca()
        xs = list(range(len(self.combatants)))
        damage_given = defaultdict(lambda: 0)

        query = 'SELECT source, true_amount FROM damage_given WHERE combat_id = ?'
        values = (self._db_id,)
        for (source, true_amount) in self.campaign._connection.execute(query, values):
            # ignore healing given as negative damage
            damage_given[source] += max(0, true_amount)

        ys = [damage_given[c.get_numbered_name()] for c in self.combatants]
        ax.bar(xs, ys)
        ax.set_xticks(xs)
        ax.set_xticklabels([c.get_numbered_name() for c in self.combatants],
                           rotation=45, ha='right')
        ax.set_title('Damage Given')
        return figure

    def plot_damage_received(self, figure):
        from matplotlib.patches import Patch

        ax = figure.gca()
        damage_received = defaultdict(Counter)

        query = 'SELECT source, target, true_amount FROM damage_given WHERE combat_id = ?'
        values = (self._db_id,)
        for (source, target, true_amount) in self.campaign._connection.execute(query, values):
            # ignore healing given as negative damage
            damage_received[target][source] += max(0, true_amount)

        sorted_names = [c.get_numbered_name() for c in self.combatants]
        name_colors = defaultdict(lambda:
                                  cubeellipse_intensity(len(name_colors), h=1.3))
        column_xs = defaultdict(lambda: len(column_xs))

        xs = []
        bottoms = []
        heights = []
        colors = []
        for dest in sorted_names:
            if dest not in damage_received:
                continue
            dest_received = damage_received[dest]
            cumulative = 0
            for src in sorted_names:
                if src not in dest_received:
                    continue

                xs.append(column_xs[dest])
                bottoms.append(cumulative)
                heights.append(dest_received[src])
                cumulative += heights[-1]
                colors.append(name_colors[src])

        legend_pieces = [Patch(facecolor=color, edgecolor=None, label=name)
                         for (name, color) in sorted(name_colors.items())]

        ax.bar(xs, heights, bottom=bottoms, color=colors)
        ax.set_xticks(list(range(len(column_xs))))
        ax.set_xticklabels(list(column_xs.keys()), rotation=45, ha='right')
        ax.legend(handles=legend_pieces)
        ax.set_title('Damage Received')
        return figure

    def show(self):
        """Immediately display the combat table"""
        import IPython, IPython.display
        IPython.display.display(self)

    def remove(self, combatant):
        """Remove a character from combat."""
        self.combatants.remove(combatant)

    def _record_take_damage(self, target, amount, type, true_amount):
        query = 'INSERT INTO damage_taken VALUES (?, ?, ?, ?, ?)'
        values = (self._db_id, target.get_numbered_name(), type, amount, true_amount)
        self.campaign._connection.execute(query, values)

    def _record_damage(self, source, target, amount, type, true_amount):
        query = 'INSERT INTO damage_given VALUES (?, ?, ?, ?, ?, ?)'
        values = (self._db_id, target.get_numbered_name(),
                  source.get_numbered_name(), type, amount, true_amount)
        self.campaign._connection.execute(query, values)

    def _record_heal(self, target, amount):
        query = 'INSERT INTO healing VALUES (?, ?, ?)'
        values = (self._db_id, target.get_numbered_name(), amount)
        self.campaign._connection.execute(query, values)

    def _repr_html_(self):
        pieces = []

        pieces.append(_combat_css)
        pieces.append('<table class="combat_tracker">')
        pieces.append('<thead><tr>')
        pieces.append('<th><b>Name</b></th>')
        pieces.append('<th><b>AC</b></th>')
        pieces.append('<th><b>HP</b></th>')
        pieces.append('<th style="min-width: 3em"></th>')
        for stat in _stats:
            pieces.append('<th><b>{}</b></th>'.format(stat.upper()))
        pieces.append('</tr></thead>')

        for char in self.combatants:
            pieces.append('<tr>')
            name = char.get_numbered_name()
            if char.hp is not None:
                percentage = round(100*char.hp/char.initial_hp)
                health = '{} ({:d}%)'.format(char.hp, percentage)
            else:
                health = ''

            pieces.append('<td><b>{}</b></td>'.format(name))
            pieces.append('<td><b>{}</b></td>'.format(char.ac))
            pieces.append('<td><b>{}</b></td>'.format(health))
            pieces.append('<td></td>')

            if char.saves:
                pieces.extend('<td>{}</td>'.format(char.saves.get(stat, 0)) for stat in _stats)
            else:
                pieces.extend(len(_stats)*['<td></td>'])
            pieces.append('</tr>')
        pieces.append('</table>')

        return ''.join(pieces)
