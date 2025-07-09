from flask import Flask, request, jsonify
import imaplib, time

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

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/flag-message', methods=['POST'])
def flag_message():
    try:
        data = request.json
        host = data['host']
        user = data['user']
        password = data['password']
        mailbox = data.get('mailbox', 'INBOX')
        uid = data['uid']
        flag = data.get('flag', '\\Flagged')  # Apple Mail unterstützt \Flagged sichtbar als Stern

        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)
        M.select(mailbox)
        M.uid('STORE', uid, '+FLAGS', f'({flag})')
        M.logout()

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
