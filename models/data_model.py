import sqlite3
import unicodedata
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta

DBFILENAME = 'checker.sqlite'

LEVELS = ['vide', 'faible', 'moyen', 'fort', 'plein']
LEVEL_TO_SCORE = {level: i for i, level in enumerate(LEVELS)}
ROLE_WEIGHTS = {
  'user': 1,
  'staff': 20,
  'admin': 1
}


def normalize_text(text):
  if text is None:
    return ''
  text = text.strip().lower()
  normalized = unicodedata.normalize('NFD', text)
  return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


# Utility functions

# cette fonction a pour but d'execute une requete SQL de type SELECT afin de
# recuperer des donnees de la base de donnee creer plus tot (db.sqlite)

# query: la requete ex. SELECT * FROM movies
# args: les arguments de la fonction, ex. 2010 pour le WHERE de
# SELECT * FROM movies WHERE year < 2010;
# all: pas obliger de mettre en entree, si il est a True, cela renvoit
# toutes les lignes sinon uniquement une seule
# db_name: nom du fichier qui contient la base de donnees (ici: db.sqlite)

# ex. d'appel:
# result = db_fetch('SELECT * FROM movies WHERE year < ?', (2010,), all=True)
# (2010,) et pas (2010) pour un tuple de un seul element
def db_fetch(query, args=(), all=False, db_name=DBFILENAME):
  with sqlite3.connect(db_name) as conn:
    # to allow access to columns by name in res
    conn.row_factory = sqlite3.Row
    # ici, on execute la requete
    cur = conn.execute(query, args)
    # convert to a python dictionary for convenience
    if all:
      res = cur.fetchall()
      if res:
        res = [dict(e) for e in res]
      else:
        res = []
    else:
      res = cur.fetchone()
      if res:
        res = dict(res)
  return res


# cette fonction fait la meme chose que la fonction ci-dessus mais pour
# l'insertion cette fois-ci (le parametre all n'est plus present desormais
# puisque cela n'aurait plus aucun sens)
def db_insert(query, args=(), db_name=DBFILENAME):
  with sqlite3.connect(db_name) as conn:
    cur = conn.execute(query, args)
    # commit pour sauvegarder les changements
    conn.commit()
    # renvoie l'id de la derniere ligne insere
    return cur.lastrowid


# pour toutes les requetes de tout types (pour les create par ex vu qu'on a
# pas fait de db_create)
def db_run(query, args=(), db_name=DBFILENAME):
  with sqlite3.connect(db_name) as conn:
    cur = conn.execute(query, args)
    conn.commit()


# pour les requetes de type UPDATE et DELETE
def db_update(query, args=(), db_name=DBFILENAME):
  with sqlite3.connect(db_name) as conn:
    cur = conn.execute(query, args)
    conn.commit()
    return cur.rowcount


##################FONCTION D'ACCES##################

def login(user, password):
  found = db_fetch('SELECT * FROM "user" WHERE username = ?', (user,))
  if found and check_password_hash(found['password_hash'], password):
    return found['id']
  return -1

def user_exists(user):
  found = db_fetch('SELECT * FROM "user" WHERE username = ?', (user,))
  if found is not None:
    return True
  return False

def is_user_banned(user_id):
  user = db_fetch('SELECT banned FROM "user" WHERE id = ?', (user_id,))
  if user is None:
    return -1
  return user['banned']

def new_user(user, password):
  user_id = db_insert('INSERT INTO "user" (username, password_hash) VALUES (?, ?)',
                      (user, generate_password_hash(password)))
  return user_id

def add_affluence(user_id, place_id, level):
  levels = ['vide', 'faible', 'moyen', 'moyen plus', 'fort', 'plein']
  if level not in levels:
    return False, 0
  # on prend la date actuel
  now_date = datetime.now()
  # on regarde le dernier signalement de l'utilisateur
  last_signal = db_fetch(
    'SELECT timestamp FROM affluence WHERE user_id = ? AND place_id = ? ORDER BY timestamp DESC LIMIT 1',
    (user_id, place_id)
    )
  # on fixe le temps d'attente entre les signalement a 10 minutes
  waiting_time = 10
  if last_signal:
    # conversion en objet datetime pour pouvoir fair des calculs
    last_time = datetime.fromisoformat(last_signal['timestamp'])
    difference = (now_date - last_time).total_seconds()
    if difference < waiting_time * 60:
      remaining_time = int((waiting_time*60 - difference)//60) + 1
      return False, remaining_time
  db_insert(
        'INSERT INTO affluence (user_id, place_id, niveau, timestamp) VALUES (?, ?, ?, ?)',
        (user_id, place_id, level, now_date)
  )
  return True, 0

def get_affluence(place_id):
  affluences = db_fetch(
    'SELECT * FROM affluence WHERE place_id = ? ORDER BY timestamp DESC',
    (place_id,),
    all=True
  )
  return affluences

# fonction pour recuperer les derniers affluences d'un
# utilisateur pour savoir si on le ban ou non (puisqu'on
# peut comparer ave d'autres utilisateurs)
# limite fixee de base a 15 pour gerer le cas ou un
# utilisateur a effectuer enormement d'affluence (genre 500)
def get_user_affluence(user_id, limit=15):
  return db_fetch(
    """
    SELECT a.niveau, a.timestamp, p.name as place_name
    FROM affluence a
    JOIN place p ON a.place_id = p.id
    WHERE a.user_id = ?
    ORDER BY a.timestamp DESC
    LIMIT ?
    """,
    (user_id, limit),
    all=True
  )

def get_places_by_name(place_name):
  if not place_name:
    return []
  places = db_fetch('SELECT * FROM place', all=True)
  needle = normalize_text(place_name)
  return [p for p in places if normalize_text(p.get('name', '')) == needle]

def get_affluence_avg_last10(place_id):
  cutoff = datetime.now() - timedelta(minutes=10)
  cutoff_str = cutoff.isoformat(sep=' ')
  affluences = db_fetch(
    """
    SELECT a.niveau, u.role
    FROM affluence a
    JOIN "user" u ON a.user_id = u.id
    WHERE a.place_id = ? AND a.timestamp >= ?
    ORDER BY a.timestamp DESC
    """,
    (place_id, cutoff_str),
    all=True
  )
  if not affluences:
    return None
  weighted_scores = []
  weights = []
  for a in affluences:
    niveau = a.get('niveau')
    if niveau in LEVEL_TO_SCORE:
      role = a.get('role', 'user')
      weight = ROLE_WEIGHTS.get(role, 1)
      weighted_scores.append(LEVEL_TO_SCORE[niveau] * weight)
      weights.append(weight)
  if not weighted_scores or not weights:
    return None
  avg_score = sum(weighted_scores) / sum(weights)
  avg_index = int(round(avg_score))
  avg_index = max(0, min(avg_index, len(LEVELS) - 1))
  return LEVELS[avg_index]

def update_user(user_id, username, old_password, new_password):
  user = db_fetch('SELECT * FROM "user" WHERE id = ?', (user_id,))
  if not user:
    return False, "Utilisateur introuvable"
  if not check_password_hash(user['password_hash'], old_password):
    return False, "Ancien mot de passe incorrect"
  if username and username != user['username']:
    existing = db_fetch('SELECT id FROM "user" WHERE username = ?', (username,))
    if existing:
      return False, "Nom d'utilisateur déjà pris"
  if username:
    db_run('UPDATE "user" SET username = ? WHERE id = ?', (username, user_id))

  if new_password:
    db_run('UPDATE "user" SET password_hash = ? WHERE id = ?',
           (generate_password_hash(new_password), user_id))

  return True, ""

##################FONCTION POUR RESPECTE LES RGPD##################

def delete_user(user_id):
  db_run('DELETE FROM affluence WHERE user_id = ?', (user_id,))
  db_run('DELETE FROM "user" WHERE id = ?', (user_id,))

def export_user_data(user_id):
  user = db_fetch('SELECT id, username FROM "user" WHERE id = ?', (user_id,))
  affluences = db_fetch(
      'SELECT place_id, niveau, timestamp FROM affluence WHERE user_id = ? ORDER BY timestamp DESC',
      (user_id,), all=True
  )
  return {
    'user': user,
    'affluence_reports': affluences
  }

##################FONCTION POUR MENU_RU##################

def ensure_menu_table():
  try:
    db_fetch('SELECT id FROM menu_ru WHERE id = 1')
  except sqlite3.OperationalError:
    db_run(
      """
      CREATE TABLE IF NOT EXISTS menu_ru (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        content TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        updated_by INTEGER,
        FOREIGN KEY (updated_by) REFERENCES user(id)
      )
      """
    )
    db_run(
      'INSERT OR IGNORE INTO menu_ru (id, content, updated_at, updated_by) VALUES (1, ?, ?, NULL)',
      ('Menu non disponible pour le moment.', datetime.now())
    )

def get_ru_menu():
  ensure_menu_table()
  menu = db_fetch('SELECT * FROM menu_ru WHERE id = 1')
  return menu

def update_ru_menu(content, user_id):
  ensure_menu_table()
  db_run(
    'UPDATE menu_ru SET content = ?, updated_at = ?, updated_by = ? WHERE id = 1',
    (content, datetime.now(), user_id)
  )

##################FONCTION POUR COMPUTER_BU##################

# fonction pour recuperer tous les pc de la BU (avec leur
# etat: libre ou occupe)
def get_all_computers():
  # on met all=True car on veut bien tous les pc
  return db_fetch("SELECT * FROM computer_bu", all=True)

# fonction pour savoir si un pc est libre ou non
def is_computer_free(computer_id):
  pc = db_fetch("SELECT user_id FROM computer_bu WHERE id = ?",
                (computer_id,))
  if pc is None:
    return False
  # pour savoir si un pc est libre ou pas on regarde s'il
  # n'a pas de user_id associe
  return pc['user_id'] is None

# fonction pour verifier si un utilisateur a deja occupe
# un pc (pour su'on l'empeche d'en prendre un autre et lui
# donner la possibilte de quitter son pc actuel)
def user_has_computer(user_id):
  pc = db_fetch("SELECT * FROM computer_bu WHERE user_id = ?",
                (user_id,))
  return pc is not None

# fonction pour prendre un pc
def take_computer(user_id, computer_id):
  # on verifie a l'aide des fonctions precedente si un
  # utilisateur a deja prit un pc ou non et si celui qui
  # veut prendre est libre ou non
  if user_has_computer(user_id):
    return False, "Vous occupé déja un PC"
  if not is_computer_free(computer_id):
    return False, "Ce PC est déjà occupé"
  db_run(
    "UPDATE computer_bu SET user_id = ? WHERE id = ?",
    (user_id, computer_id)
  )
  return True, ""

# fonction pour libere son pc
def release_computer(user_id):
  pc = db_fetch("SELECT id FROM computer_bu WHERE user_id = ?", (user_id,))
  if not pc:
    return False, "Vous n'avez aucun PC à libérer"
  db_run("UPDATE computer_bu SET user_id = NULL WHERE user_id = ?", (user_id,))
  return True, ""