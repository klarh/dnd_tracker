import json
import sqlite3

from .Combat import Combat

sqlite3.register_converter('JSON', json.loads)

class Campaign:
    """Keep a record of statistics associated with characters.

    :param name: Name to associate with the campaign
    :param filename: Filename to use for persistent campaign data (default: do not persist data)
    """
    def __init__(self, name=None, filename=':memory:'):
        self.name = name
        self.filename = filename

        self._initialize_db()

    def _initialize_db(self):
        self._connection = sqlite3.connect(
            self.filename, detect_types=sqlite3.PARSE_DECLTYPES)

        with self._connection as c:
            c.execute('CREATE TABLE IF NOT EXISTS campaigns '
                      '(name STR UNIQUE ON CONFLICT IGNORE)')

            c.execute('INSERT INTO campaigns VALUES (?)', (self.name,))

            for (identifier,) in c.execute(
                    'SELECT rowid FROM campaigns WHERE name = ?', (self.name,)):
                pass

            self._db_id = identifier

            c.execute('CREATE TABLE IF NOT EXISTS combat_stats '
                      '(name STR UNIQUE ON CONFLICT REPLACE, '
                      'attributes JSON)')

    def begin_combat(self, name):
        return Combat(self, name)

    def get_combat_stats(self, name, **kwargs):
        result = {}
        for (result,) in self._connection.execute(
                'SELECT attributes FROM combat_stats WHERE name = ?',
                (name,)):
            pass
        result.update(kwargs)
        return result

    def set_combat_stats(self, name, **kwargs):
        stats = self.get_combat_stats(name, **kwargs)

        self._connection.execute(
            'INSERT INTO combat_stats VALUES (?, ?)',
            (name, json.dumps(stats)))

default_campaign = Campaign('default')

def begin_combat(name):
    """Quickly begin combat in a default (initially empty) campaign."""
    return default_campaign.begin_combat(name)
