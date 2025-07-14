from flask import Flask, request, jsonify
import imaplib
import time
import email

app = Flask(__name__)

# Optional: Agent-Whitelist, damit nur bekannte Agents erlaubt sind
ALLOWED_AGENTS = {'carla', 'roberto'}

@app.route('/create-draft/<agent>', methods=['POST'])
def create_draft(agent):
    if agent not in ALLOWED_AGENTS:
        return jsonify({'status': 'error', 'message': f'Unknown agent: {agent}'}), 400

    try:
        data = request.json
        host = data['host']
        user = data['user']
        password = data['password']
        raw_message = data['raw_message']
        folder = data.get('folder', 'Drafts')

        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)
        M.append(folder, '\\Draft', imaplib.Time2Internaldate(time.time()), raw_message.encode('utf-8'))
        M.logout()

        return jsonify({'status': 'draft created', 'agent': agent}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'agent': agent}), 500


@app.route('/flag-message/<agent>', methods=['POST'])
def flag_message(agent):
    if agent not in ALLOWED_AGENTS:
        return jsonify({'status': 'error', 'message': f'Unknown agent: {agent}'}), 400

    try:
        data = request.json
        host = data['host']
        user = data['user']
        password = data['password']
        message_id = data['message_id']
        folder = data.get('folder', 'INBOX')

        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)
        M.select(folder)

        result, data = M.search(None, f'(HEADER Message-ID "{message_id}")')
        if result != 'OK' or not data or not data[0]:
            M.logout()
            return jsonify({'status': 'not_found', 'message': f'Message-ID {message_id} not found', 'agent': agent}), 404

        for num in data[0].split():
            M.store(num, '+FLAGS', '\\Flagged')

        M.logout()
        return jsonify({'status': 'message flagged', 'agent': agent}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e), 'agent': agent}), 500
