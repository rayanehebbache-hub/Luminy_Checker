import sqlite3
from werkzeug.security import generate_password_hash

DBFILENAME = 'checker.sqlite'

# Utility function
def db_run(query, args=(), db_name=DBFILENAME):
  with sqlite3.connect(db_name) as conn:
    cur = conn.execute(query, args)
    conn.commit()

#A chaque éxecution du code, si on avais déjà créer avant les tables, sa va supprimer les tables et tous leurs contenus.
def load(db_name=DBFILENAME):
  db_run('DROP TABLE IF EXISTS affluence')
  db_run('DROP TABLE IF EXISTS place')
  db_run('DROP TABLE IF EXISTS "user"')
  db_run('DROP TABLE IF EXISTS computer_bu')
  db_run('DROP TABLE IF EXISTS menu_ru')

  db_run("CREATE TABLE affluence (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, place_id INTEGER NOT NULL, niveau TEXT NOT NULL CHECK (niveau IN ('vide', 'faible', 'moyen', 'fort', 'plein')), timestamp TIMESTAMP NOT NULL, FOREIGN KEY (user_id) REFERENCES user(id), FOREIGN KEY (place_id) REFERENCES place(id))")
  db_run('CREATE TABLE place (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)')
  db_run("""
         CREATE TABLE user (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'staff', 'admin')),
          banned INTEGER NOT NULL DEFAULT 0 CHECK (banned IN (0,1))
        )
        """)
  db_run("""
         CREATE TABLE computer_bu (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          user_id INTEGER,
          FOREIGN KEY (user_id) REFERENCES user(id)
        )
        """)
  db_run("""
         CREATE TABLE menu_ru (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          content TEXT NOT NULL,
          updated_at TIMESTAMP NOT NULL,
          updated_by INTEGER,
          FOREIGN KEY (updated_by) REFERENCES user(id)
        )
        """)
  
  lieux = [
      'Restaurant universitaire',
      'Cafétéria BU',
      'Cafétéria RU',
      'Bibliothèque',
      'Arrêt de bus',
  ]
  for name in lieux:
    db_run('INSERT INTO place (name) VALUES (?)', (name,))

  # creation de comptes admin
  admins = [
    ('admin1@univ-amu.fr', 'Admin123&'),
    ('admin2@univ-amu.fr', 'Admin123&'),
    ('admin3@univ-amu.fr', 'Admin123&')
  ]
  for email, password in admins:
    hashed_password = generate_password_hash(password)
    db_run("INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
           (email, hashed_password, 'admin')
    )
  
  # creation de comptes staff
  staffs = [
    ('staff1@univ-amu.fr', 'Staff123&'),
    ('staff2@univ-amu.fr', 'Staff123&'),
    ('staff3@univ-amu.fr', 'Staff123&')
  ]
  for email, password in staffs:
    hashed_password = generate_password_hash(password)
    db_run("INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
           (email, hashed_password, 'staff')
    )

  db_run(
      "INSERT INTO menu_ru (id, content, updated_at, updated_by) VALUES (1, ?, datetime('now'), NULL)",
      ("Menu non disponible pour le moment.",)
  )

  # initialisation de 12 pc avec user_id initialise a vide
  # car on ne sait pas encore qui va occuper ce pc
  for i in range(1, 13):
    db_run("""
          INSERT INTO computer_bu (name, user_id)
          VALUES (?, NULL)
          """, (f'PC {i}',))

load()
