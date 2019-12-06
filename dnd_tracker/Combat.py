from collections import Counter

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
    ('electric', 'e', 'el'),
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

class Character:
    def __init__(self, combat, name, initiative, number=None, ac=None, resistances={},
                hp=None, dex=None, saves=None):
        self.combat = combat
        self.name = name
        self.initiative = initiative
        self.number = number
        self.ac = ac
        self.resistances = dict(resistances)
        self.hp = hp
        self.dex = dex
        self.saves = saves

    def take_damage(self, amount, type=None):
        type = _damage_type_map[type]
        true_amount = int(amount*self.resistances.get(type, 1))
        if self.hp is not None:
            self.hp -= true_amount
            self.hp = max(0, self.hp)

    def damage(self, other, amount, type=None):
        other.take_damage(amount, type)
        return self.combat

    def set_ac(self, value):
        self.ac = ac

    def heal(self, amount):
        self.hp += amount

def initiative_sort_key(character):
    dex = character.dex or 10
    number = character.number or 0
    return (-character.initiative, -dex, character.name, number)

class Combat:
    def __init__(self, campaign, name):
        self.campaign = campaign
        self.name = name
        self.combatants = []
        self.combatant_name_counts = Counter()

    def add(self, name, initiative, **kwargs):
        kwargs = self.campaign.get_combat_stats(name, **kwargs)

        self.combatant_name_counts[name] += 1
        count = self.combatant_name_counts[name]
        if 'number' not in kwargs and count > 1:
            kwargs['number'] = count

        combatant = Character(self, name, initiative, **kwargs)
        self.combatants.append(combatant)
        self.combatants.sort(key=initiative_sort_key)
        return combatant

    def remove(self, combatant):
        self.combatants.remove(combatant)

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
            name = char.name + (' {}'.format(char.number) if char.number is not None else '')
            health = str(char.hp) if char.hp is not None else ''

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
