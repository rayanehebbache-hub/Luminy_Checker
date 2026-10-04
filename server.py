from flask import Flask, session, flash, request, redirect, url_for, render_template, abort, jsonify
import models.data_model as model
import os
import re
from functools import wraps
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

app = Flask(__name__)

# cette ligne genere une cle de 24 octets
app.secret_key = os.urandom(24)

# login_required est un decorateur qui prend une fonction f en entree et
# verifie que l'utilisateur est bien connecte
def login_required(f):
  # @wraps pour garder les information de la fonction original
  @wraps(f)
  # * et ** pour passer facilement des collections d'arguments aux fonctions
  # * pour plusieurs valeurs sans les enumere
  # ** pour plusieurs valeurs sous forme de cle-valeur
  def decorated_function(*args, **kwargs):
    if 'user_id' not in session:
      # abort pour renvoyer un code d'erreur HTTP (401 ici)
      abort(401)
    return f(*args, **kwargs)
  return decorated_function

# meme logique que login_required mais avec une verification
# supplementaire, celle de verifier que l'utilisateur est
# bien le role admin
def admin_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if 'user_id' not in session:
      abort(401)
    user = model.db_fetch('SELECT role FROM "user" WHERE id = ?',
                          (session['user_id'],))
    if not user or user['role'] != 'admin':
      abort(403)
    return f(*args, **kwargs)
  return decorated_function

# meme logique encore
def staff_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if 'user_id' not in session:
      abort(401)
    user = model.db_fetch('SELECT role FROM "user" WHERE id = ?', (session['user_id'],))
    if not user or user['role'] != 'staff':
      abort(403)
    return f(*args, **kwargs)
  return decorated_function

def get_current_user_role():
  if 'user_id' in session:
    user = model.db_fetch('SELECT role FROM "user" WHERE id = ?', (session['user_id'],))
    if user:
      return user['role']
  return None

def is_valid_email(email):
  if not email:
    return False
  # re pour les regex, on utilise une regex pour s'assurer
  # que l'email "match" bien avec l'expression reguliere que
  # l'on souhaite
  # ici on veut juste que l'email soit au format suivant:
  # X@etu.univ-amu.fr ou X peut-etre ce que l'on veux et que
  # le etu. n'est pas necessaire (comme les expression
  # reguliere vu en automate au S3)
  return re.match(r'^[^@\s]+@(etu\.)?univ-amu\.fr$', email) is not None

def is_valid_password(password):
  # on utilise encore une fois des expression reguliere afin
  # de respecter les RGPD en faissant en sorte que tous les
  # utilisateurs respectent certaines mesure de securites
  # vis-a-vis de leur mot-de-passe
  
  # On verifie que le mot-de-passe:

  # 1. est d'au moins de longueur 8
  if not password or len(password) < 8:
    return False
  # 2. contient au moins une lettre majuscule
  if not re.search(r'[A-Z]', password):
    return False
  # 3. contient au moins un chiffre
  if not re.search(r'\d', password):
    return False
  # 4. contient au moins un caractere speciale
  if not re.search(r'[^A-Za-z0-9]', password):
    return False
  return True

########################################
# Routes des pages principales du site #
########################################

# on renvoit juste le template avec user_role pour afficher
# de nouvelle fonctionnalite ou non en fonction du role avec
# jinja2
# ex. avoir un lien en plus pour bannir un utilisateur si on
# le role
@app.get('/')
def home():
  user_role = get_current_user_role()
  return render_template('index.html', user_role=user_role)

@app.route('/login', methods=['GET'])
def login_form():
  return render_template('login.html')

@app.route('/new_user', methods=['GET'])
def new_user_form():
  return render_template('register.html')

@app.route('/login', methods=['POST'])
def login_post():
  email = request.form['email']
  password = request.form['password']
  if not is_valid_email(email):
    # error pour pouvoir afficher le message d'erreur avec
    # jinja2
    return render_template('login.html', error='Email invalide')
  user_id = model.login(email, password)
  if user_id != -1:
    session['user_id'] = user_id
    session['username'] = email
    return redirect('/')
  return render_template('login.html', error='Identifiants incorrects')

@app.route('/new_user', methods=['POST'])
def new_user_post():
  email = request.form['email']
  password = request.form['password']
  if not is_valid_email(email):
    return render_template('register.html',
                          error="Email invalide")
  if not is_valid_password(password):
    return render_template('register.html',
                          error="Le mot de passe doit contenir au moins 8 caracteres, une majuscule, un chiffre et un caractere special.")
  if model.user_exists(email):
    return render_template('register.html',
                          error="Cet utilisateur existe déjà")
  user_id = model.new_user(email, password)
  session['user_id'] = user_id
  session['username'] = email
  return redirect('/')

@app.get('/affluence')
def affluence_view():
  query_name = request.args.get('place', '').strip()
  if query_name:
    places = model.get_places_by_name(query_name)
    if not places:
      return render_template('place_not_found.html', place_name=query_name)
  else:
    places = model.db_fetch('SELECT * FROM place', all=True)
  for p in places:
    avg = model.get_affluence_avg_last10(p['id'])
    p['niveau'] = avg
  #Par défaut utilisateur pas banni si pas connecté, et s'il existe on recupere model.is_user_banned va retourner 0 ou 1 )
  user_banned = 0
  if 'user_id' in session:
    user_banned = model.is_user_banned(session['user_id'])
    if user_banned == -1:
      user_banned = 0
  return render_template('affluence.html', affluence=places, user_banned=user_banned)

@app.get('/settings')
@login_required
def settings():
  return render_template('settings.html')

@app.route('/settings/change_password', methods=['POST'])
@login_required
def change_password():
  # recuperation des valeurs du formulaire
  current = request.form.get('current_password')
  new_password = request.form.get('new_password')
  confirm_password = request.form.get('confirm_password')
  user = model.db_fetch('SELECT * FROM "user" WHERE id = ?', (session['user_id'],))
  # on verifie que le mot de passe actuel correspond a celui
  # entree
  if not user or not check_password_hash(user['password_hash'], current):
    # flash pour envoyer un message a l'utilisateur
    flash("Mot de passe actuel incorrect")
    return redirect("/settings")
  # on verifie que le nouveau mot de passe a bien etait
  # identiquement entree deux fois
  if new_password != confirm_password:
    flash("Les mots de passe ne correspondent pas")
    return redirect("/settings")
  # on verifie que le nouveau mot de passe respecte bien
  # certain principe de securite de base
  if not is_valid_password(new_password):
    flash("Mot de passe invalide : au moins 8 caractères, 1 majuscule, 1 chiffre, 1 caractère spécial")
    return redirect("/settings")
  hashed = generate_password_hash(new_password)
  model.db_run("UPDATE user SET password_hash = ? WHERE id = ?", (hashed, session['user_id']))
  flash("Mot de passe mis à jour avec succès", "success")
  return redirect("/settings")

@app.get('/menu')
def menu_view():
  menu = model.get_ru_menu()
  user_role = get_current_user_role()
  return render_template('menu.html', menu=menu, user_role=user_role)

@app.get('/menu/edit')
@login_required
@staff_required
def menu_edit_form():
  menu = model.get_ru_menu()
  return render_template('menu_edit.html', menu=menu)

@app.post('/menu/edit')
@login_required
@staff_required
def menu_edit_post():
  content = request.form['content']
  model.update_ru_menu(content, session['user_id'])
  return redirect(url_for('menu_view'))

@app.post('/signaler')
@login_required
def signaler():
  user_id = session['user_id']
  if model.is_user_banned(user_id) == 1:
    return "Utilisateur banni", 403
  place_id = int(request.form['place_id'])
  level = request.form['niveau']
  success, waiting_time = model.add_affluence(user_id, place_id, level)
  if not success:
    affluence = model.db_fetch('SELECT * FROM place', all=True)
    for p in affluence:
      avg = model.get_affluence_avg_last10(p['id'])
      p['niveau'] = avg
    user_banned = model.is_user_banned(user_id)
    error_message = "Vous avez déjà éffectué un signalament sur ce lieu récemment, veuillez attendre " + str(waiting_time) + " minutes avant de signaler de nouveau."
    return render_template('affluence.html', affluence=affluence, user_banned=user_banned, error_message=error_message)
  return redirect(url_for('affluence_view', place_id=place_id))

@app.post('/update_user')
@login_required
def update_user():
  user_id = session['user_id']
  username = request.form['username']
  password = request.form['password']
  model.update_user(user_id, username, password)
  session['username'] = username
  return redirect('/')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
  # on oublie pas de "clear" la session
  session.clear()
  return redirect('/')

###################ROUTES POUR RESPECTE LES RGPD###################

@app.post('/delete_user')
@login_required
def delete_user():
  user_id = session['user_id']
  model.delete_user(user_id)
  session.clear()
  return redirect('/')

@app.get('/export_data')
@login_required
def export_data():
  user_id = session['user_id']
  data = model.export_user_data(user_id)
  # jsonify pour renvoyer au format JSON impose pour respecte
  # les RGPD
  return jsonify(data)

###################ROUTES POUR COMPTE ADMIN###################

@app.get('/admin')
@login_required
@admin_required
def admin_panel_get():
  return render_template('admin.html', user_found=None)

@app.post('/admin/action')
@login_required
@admin_required
def admin_panel_post():
  email = request.form['email']
  user = model.db_fetch('SELECT * FROM "user" WHERE username = ?',
                        (email,))
  affluences = []
  if user:
    affluences = model.get_user_affluence(user['id'])
  return render_template('admin.html', user_found=user, affluences=affluences)

@app.post('/admin/role/<int:user_id>')
@login_required
@admin_required
def admin_set_role(user_id):
  role = request.form['role']
  # on recupere l'utilisateur qui nous interesse
  target_user = model.db_fetch('SELECT role FROM "user" WHERE id = ?', (user_id,))
  if not target_user:
    abort(404)
  # on empeche le fait de changer son propre role
  if user_id == session['user_id']:
    return "<p>Impossible de modifier votre propre rôle</p><a href='/admin'>Retour</a>"
  # on empeche le fait de changer le role d'un autre admin
  if target_user['role'] == 'admin':
    return "<p>Impossible de modifier le rôle d'un autre admin</p><a href='/admin'>Retour</a>"
  # on verifie que le role que l'on va rentrer dans la base
  # est correct
  if role not in ('user', 'staff'):
    abort(400)
  # application de la modification
  model.db_update('UPDATE "user" SET role = ? WHERE id = ?',
                  (role, user_id))
  return redirect(url_for('admin_panel_get'))
  
@app.post('/admin/action/<int:user_id>')
@login_required
@admin_required
def admin_action(user_id):
  user = model.db_fetch('SELECT * FROM "user" WHERE id = ?', (user_id,))
  if not user:
    abort(404)
  # on ne peut pas se ban soit meme
  if user_id == session['user_id']:
    return "<p>Impossible de se bannir soi-même</p><a href='/admin'>Retour</a>"
  # on ne peut pas ban un autre admin ou un membre du staff
  if user['role'] in ('admin', 'staff'):
    return f"<p>Impossible de bannir un {user['role']}</p><a href='/admin'>Retour</a>"
  # changement du statut banned
  if user['banned'] == 1:
    new_banned = 0
  else:
    new_banned = 1
  model.db_update('UPDATE "user" SET banned = ? WHERE id = ?',
                  (new_banned, user_id))
  return redirect(url_for('admin_panel_get'))

###################ROUTES POUR COMPUTER_BU###################

# route pour la vue des pc
@app.route('/computers', methods=['GET'])
@login_required
def computers_view():
  pcs = model.get_all_computers()
  return render_template('computers.html', computers=pcs,
                         user_id=session['user_id'])

# route avec methode POST pour prendre un pc
@app.route('/take_computer', methods=['POST'])
@login_required
def take_computer_route():
  user_id = session['user_id']
  computer_id = int(request.form['computer_id'])
  success, message = model.take_computer(user_id, computer_id)
  if not success:
    # message d'erreur avec un lien pour se sortir de cette
    # situation
    return "<p>" + message + "</p><a href='/computers'>Retour</a>"  
  return redirect('/computers')

# route avec methode POST pour libere un pc
@app.post('/release_computer')
@login_required
def release_computer_route():
  user_id = session['user_id']
  success, message = model.release_computer(user_id)
  return redirect('/computers')

if __name__ == "__main__":
    app.run(debug=True, use_reloader = False, port=5000)
