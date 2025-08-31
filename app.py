from flask import Flask, request, redirect, render_template, jsonify
from linkvertise import LinkvertiseClient
import hashlib
import hmac
import random
import time
import os

app = Flask(__name__)

USER_ID = 00000  # Linkvertise ID
ANTI_BYPASS_TOKEN = ""  # Anti Bypass Token

SECRET_KEY = os.urandom(32).hex()  # generate random key for HMAC or u can put your own static key here
client = LinkvertiseClient(
    user_id=USER_ID,  
    anti_bypass_token=ANTI_BYPASS_TOKEN 
)

verification_status = {}

# generate hash to validate later
def generate_secure_hash(user_id, timestamp):
    message = f"{user_id}{timestamp}"
    return hmac.new(
        SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

# validate the generated hash
def verify_secure_hash(user_id, timestamp, provided_hash):
    expected_hash = generate_secure_hash(user_id, timestamp)
    return hmac.compare_digest(expected_hash, provided_hash)

def check_referral_header():
    referrer = request.headers.get('Referer')
    
    if not referrer:
        return False
    
    return 'linkvertise.com' in referrer or 'link-to.net' in referrer

@app.route('/')
def index():
    return render_template('index.html', status='generated')

@app.route('/generate')
def generate_link():
    user_id = str(int(time.time())) + str(random.randint(1000, 9999))
    timestamp = str(int(time.time()))
    secure_hash = generate_secure_hash(user_id, timestamp)
    destination_url = f"http://127.0.0.1:5000/verify_success?user_id={user_id}&ts={timestamp}&hash={secure_hash}"  # change this to your domain or whatever distnation
    
    try:
        linkvertise_url = client.linkvertise(USER_ID, destination_url)
        verification_status[user_id] = {
            'status': 'pending',
            'timestamp': timestamp,
            'hash': secure_hash
        }
        return render_template('index.html', 
                              status='link_created', 
                              link=linkvertise_url, 
                              user_id=user_id)
    except Exception as e:
        print(f"Linkvertise API error: {e}")
        return render_template('index.html', status='error')

@app.route('/verify_success')
def verify_success():
    user_id = request.args.get('user_id')
    timestamp = request.args.get('ts')
    provided_hash = request.args.get('hash')
    
    if not check_referral_header():
        if user_id and user_id in verification_status:
            verification_status[user_id]['status'] = 'bypass_detected'
        return render_template('index.html', status='bypass_detected')
    if not verify_secure_hash(user_id, timestamp, provided_hash):
        if user_id and user_id in verification_status:
            verification_status[user_id]['status'] = 'bypass_detected'
        return render_template('index.html', status='bypass_detected')
    
    if int(time.time()) - int(timestamp) > 3600:
        if user_id and user_id in verification_status:
            verification_status[user_id]['status'] = 'bypass_detected'
        return render_template('index.html', status='bypass_detected')
    
    if user_id and user_id in verification_status:
        verification_status[user_id]['status'] = 'verified'
        return render_template('index.html', status='verified')
    
    return redirect('/')

@app.route('/check')
def check_verification():
    user_id = request.args.get('user_id')
    
    if not user_id or user_id not in verification_status:
        return "Invalid user ID", 400
    
    status = verification_status[user_id]['status']
    
    if status == 'verified':
        return render_template('index.html', status='verified')
    elif status == 'bypass_detected':
        return render_template('index.html', status='bypass_detected')
    else:
        return render_template('index.html', status='pending', user_id=user_id)

@app.route('/api/status/<user_id>')
def api_status(user_id):
    if user_id not in verification_status:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({
        'user_id': user_id,
        'status': verification_status[user_id]['status']
    })

if __name__ == '__main__':

    app.run(debug=True, port=5000)
