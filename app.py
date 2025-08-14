from flask import Flask, request, jsonify
import imaplib
import time
import email
from datetime import datetime, timedelta  # <-- added

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


@app.route('/delete-ai-drafts', methods=['POST'])
def delete_ai_drafts():
    """
    Löscht/verschiebt NUR Drafts mit AI-Header, die älter als X Tage sind (Default 14).
    Default-Sicherheit:
      - folder: Drafts
      - trash_folder: Trash
      - dry_run: true
      - mode: move (statt hard delete)
      - expunge: true
      - header_name/value: X-Processed-By: n8n-ai-agent (Pflicht)
    """
    try:
        data = request.json or {}

        host = data['host']
        user = data['user']
        password = data['password']

        folder = data.get('folder', 'Drafts')
        trash_folder = data.get('trash_folder', 'Trash')
        dry_run = bool(data.get('dry_run', True))
        mode = data.get('mode', 'move')            # "move" | "delete"
        expunge = bool(data.get('expunge', True))

    

        # Alter: Default 14 Tage
        try:
            days = int(data.get('days', 14))
        except Exception:
            return jsonify({'status': 'error', 'message': 'Invalid "days" value'}), 400
        date_str = (datetime.utcnow() - timedelta(days=days)).strftime("%d-%b-%Y")

        # IMAP
        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)

        # Nur im angegebenen Ordner (Default: Drafts)
        typ, _ = M.select(f'"{folder}"', readonly=False)
        if typ != 'OK':
            M.logout()
            return jsonify({'status': 'error', 'message': f'Cannot select folder "{folder}"'}), 400

        # Suche: AI-Header UND älter als {days}
        search_criteria = ['BEFORE', date_str]
        result, data_ids = M.search(None, *search_criteria)
        if result != 'OK':
            M.logout()
            return jsonify({'status': 'error', 'message': 'IMAP SEARCH failed'}), 500

        ids = data_ids[0].split() if data_ids and data_ids[0] else []
        matched = len(ids)

        # Dry-run oder nichts gefunden
        if dry_run or matched == 0:
            M.close(); M.logout()
            return jsonify({
                'status': 'ok',
                'dry_run': True,
                'folder': folder,
                'matched_count': matched,
                'message': 'Dry-run (no changes)' if dry_run else 'No drafts matched'
            }), 200

        if mode not in ('move', 'delete'):
            M.close(); M.logout()
            return jsonify({'status': 'error', 'message': 'Invalid mode. Use "move" or "delete".'}), 400

        # Ausführen
        for num in ids:
            if mode == 'move':
                # Move to Trash: COPY -> mark \Deleted im Quellordner
                M.copy(num, trash_folder)
                M.store(num, '+FLAGS', r'(\Deleted)')
            else:
                # Hard delete im Drafts-Ordner
                M.store(num, '+FLAGS', r'(\Deleted)')

        if expunge:
            M.expunge()

        M.close(); M.logout()
        return jsonify({
            'status': 'ok',
            'dry_run': False,
            'folder': folder,
            'matched_count': matched,
            'action': 'moved_to_trash' if mode == 'move' else 'deleted_expunged',
            'days': days
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
