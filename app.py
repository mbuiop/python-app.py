from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import random
import string

app = Flask(__name__)

# Simulated databases
users_db = []
sites_db = []
signals_db = [
    {"currency": "BTC", "direction": "خرید", "take_profit": 60000, "stop_loss": 55000},
    {"currency": "ETH", "direction": "فروش", "take_profit": 3000, "stop_loss": 3500},
    {"currency": "XRP", "direction": "خرید", "take_profit": 1.2, "stop_loss": 1.0}
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        code = ''.join(random.choices(string.digits, k=5))
        users_db.append({"username": username, "email": email, "password": password, "code": code})
        with open('data/users.json', 'w', encoding='utf-8') as f:
            json.dump(users_db, f, ensure_ascii=False)
        return jsonify({"success": True, "code": code})
    return render_template('register.html')

@app.route('/signals')
def signals():
    with open('data/signals.json', 'r', encoding='utf-8') as f:
        signals = json.load(f)
    return jsonify(signals)

@app.route('/sites')
def sites():
    with open('data/sites.json', 'r', encoding='utf-8') as f:
        sites = json.load(f)
    return jsonify(sites)

@app.route('/add-site', methods=['POST'])
def add_site():
    name = request.form.get('name')
    link = request.form.get('link')
    description = request.form.get('description')
    image = request.files.get('image')
    image_path = f"static/uploads/{image.filename}"
    image.save(image_path)
    sites_db.append({"name": name, "link": link, "description": description, "image": image_path})
    with open('data/sites.json', 'w', encoding='utf-8') as f:
        json.dump(sites_db, f, ensure_ascii=False)
    with open(f'data/user_{name}.html', 'w', encoding='utf-8') as f:
        f.write(f'<p>نام: {name}</p><p>لینک: {link}</p><p>توضیحات: {description}</p><img src="/{image_path}">')
    return jsonify({"success": True})

@app.route('/download-python')
def download_python():
    return send_file('static/moai.py', as_attachment=True)

@app.route('/download-html')
def download_html():
    return send_file('static/git.html', as_attachment=True)

@app.route('/announcement')
def announcement():
    try:
        with open('data/announcement.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"message": data.get("message", "")})
    except:
        return jsonify({"message": ""})

@app.route('/manage-users', methods=['POST'])
def manage_users():
    data = request.json
    email = data.get('email')
    users_db[:] = [user for user in users_db if user['email'] != email]
    with open('data/users.json', 'w', encoding='utf-8') as f:
        json.dump(users_db, f, ensure_ascii=False)
    return jsonify({"success": True})

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    os.makedirs('static/uploads', exist_ok=True)
    app.run(debug=True)
