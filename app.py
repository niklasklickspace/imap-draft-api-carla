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


# ----------------------------
# NEW: Delete AI Drafts safely
# ----------------------------
@app.route('/delete-ai-drafts', methods=['POST'])
def delete_ai_drafts():
    """
    Delete (or move to Trash) drafts that contain the AI marker header.
    Safety defaults:
      - Only operates in Drafts (or a provided folder)
      - Requires AI header filter (cannot be disabled)
      - Dry-run enabled by default
      - Moves to Trash by default (safer than hard delete)

    JSON body example:
    {
      "host": "001stdmail.shapememory.eu",
      "user": "user@domain",
      "password": "*****",
      "folder": "Drafts",                 # optional, default "Drafts"
      "trash_folder": "Trash",            # optional, default "Trash"
      "dry_run": true,                    # optional, default true
      "mode": "move",                     # "move" (default) or "delete"
      "expunge": true,                    # optional, default true
      "header_name": "X-Processed-By",    # optional, default "X-Processed-By"
      "header_value": "n8n-ai-agent",     # optional, default "n8n-ai-agent"
      "days": 14                          # optional, if provided -> only BEFORE this age
    }
    """
    try:
        data = request.json or {}

        host = data['host']
        user = data['user']
        password = data['password']

        folder = data.get('folder', 'Drafts')
        trash_folder = data.get('trash_folder', 'Trash')
        dry_run = bool(data.get('dry_run', True))
        mode = data.get('mode', 'move')  # "move" or "delete"
        expunge = bool(data.get('expunge', True))

        # AI header filter is MANDATORY (as requested)
        header_name = data.get('header_name', 'X-Processed-By')
        header_value = data.get('header_value', 'n8n-ai-agent')
        if not header_name or not header_value:
            return jsonify({
                'status': 'error',
                'message': 'AI header filter is required (header_name + header_value).'
            }), 400

        # optional age filter
        days = data.get('days', None)
        date_clause = None
        if days is not None:
            try:
                days = int(days)
                cutoff = datetime.utcnow() - timedelta(days=days)
                date_clause = cutoff.strftime("%d-%b-%Y")  # IMAP date format
            except Exception:
                return jsonify({'status': 'error', 'message': 'Invalid "days" value'}), 400

        M = imaplib.IMAP4_SSL(host, 993)
        M.login(user, password)

        # strictly operate only in given folder (default: Drafts)
        typ, _ = M.select(f'"{folder}"', readonly=False)
        if typ != 'OK':
            M.logout()
            return jsonify({'status': 'error', 'message': f'Cannot select folder "{folder}"'}), 400

        # Build SEARCH criteria: always filter by AI header; add BEFORE if days provided
        # Multiple criteria are ANDed by IMAP.
        if date_clause:
            search_criteria = ['HEADER', header_name, f'"{header_value}"', 'BEFORE', date_clause]
        else:
            search_criteria = ['HEADER', header_name, f'"{header_value}"']

        result, data_ids = M.search(None, *search_criteria)
        if result != 'OK':
            M.logout()
            return jsonify({'status': 'error', 'message': 'IMAP SEARCH failed'}), 500

        ids = data_ids[0].split() if data_ids and data_ids[0] else []
        matched = len(ids)

        # Dry run: report only
        if dry_run or matched == 0:
            M.close()
            M.logout()
            return jsonify({
                'status': 'ok',
                'dry_run': True,
                'folder': folder,
                'matched_count': matched,
                'message': 'Dry-run (no changes)' if dry_run else 'No drafts matched'
            }), 200

        # Safety: only two modes allowed
        if mode not in ('move', 'delete'):
            M.close(); M.logout()
            return jsonify({'status': 'error', 'message': 'Invalid mode. Use "move" or "delete".'}), 400

        # Execute changes
        for num in ids:
            if mode == 'move':
                # Move to Trash: COPY then mark \Deleted in source
                M.copy(num, trash_folder)
                M.store(num, '+FLAGS', r'(\Deleted)')
            else:
                # Hard delete: mark \Deleted in Drafts
                M.store(num, '+FLAGS', r'(\Deleted)')

        if expunge:
            M.expunge()

        M.close()
        M.logout()

        return jsonify({
            'status': 'ok',
            'dry_run': False,
            'folder': folder,
            'matched_count': matched,
        }), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
