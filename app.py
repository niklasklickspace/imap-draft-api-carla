from flask import Flask, request, jsonify
import imaplib, time

app = Flask(__name__)

# 1. Draft erstellen
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

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 2. UID suchen (per Subject oder From)
@app.route('/get-uid', methods=['POST'])
def get_uid():
    try:
        data = request.json
        host = data['host']
        user = data['user']
        password = data['password']
        folder = data.get('folder', 'INBOX')
        subject = data.get('subject')
        sender = data.get('from')

        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)
        M.select(folder)

        if subject:
            criteria = f'(HEADER Subject "{subject}")'
        elif sender:
            criteria = f'(FROM "{sender}")'
        else:
            criteria = 'ALL'

        result, data = M.uid('SEARCH', None, criteria)
        M.logout()

        if result == 'OK' and data[0]:
            uid_list = data[0].split()
            return jsonify({'status': 'success', 'uids': [uid.decode() for uid in uid_list]}), 200
        else:
            return jsonify({'status': 'not_found', 'uids': []}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 3. Mail flaggen (z. B. \Flagged oder benutzerdefiniert)
@app.route('/flag-message', methods=['POST'])
def flag_message():
    try:
        data = request.json
        host = data['host']
        user = data['user']
        password = data['password']
        uid = data['uid']
        flag = data.get('flag', '\\Flagged')
        folder = data.get('folder', 'INBOX')

        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)
        M.select(folder)
        result = M.uid('STORE', uid, '+FLAGS', f'({flag})')
        M.logout()

        if result[0] == 'OK':
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'result': result}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
