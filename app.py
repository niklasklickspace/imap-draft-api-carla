from flask import Flask, request, jsonify
import imaplib
import time
import email

app = Flask(__name__)

@app.route('/create-draft', methods=['POST'])
def create_draft():
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

        return jsonify({'status': 'draft created'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/flag-message', methods=['POST'])
def flag_message():
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

        # Suche nach Message-ID
        result, data = M.search(None, f'(HEADER Message-ID "{message_id}")')
        if result != 'OK' or not data or not data[0]:
            M.logout()
            return jsonify({'status': 'not_found', 'message': f'Message-ID {message_id} not found'}), 404

        for num in data[0].split():
            M.store(num, '+FLAGS', '\\Flagged')

        M.logout()
        return jsonify({'status': 'message flagged'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
