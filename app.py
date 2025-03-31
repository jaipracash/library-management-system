import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.debug import console
from werkzeug.security import generate_password_hash, check_password_hash
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import random
import string
import logging

logging.basicConfig(level=logging.DEBUG)

# Define filter functions first
def datetimeformat(value, format='%Y-%m-%d'):
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value)
    return value.strftime(format)

def stringtodate(value):
    if isinstance(value, str):
        return datetime.datetime.fromisoformat(value)
    return value

# Then create the Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Register the filters with Jinja2
app.jinja_env.filters['datetimeformat'] = datetimeformat
app.jinja_env.filters['stringtodate'] = stringtodate

# Initialize Firebase
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')


# Firebase Admin SDK Initialization
def initialize_firebase():
    try:
        # Check if Firebase app already exists to avoid reinitialization
        if not firebase_admin._apps:
            # Try to get credentials from environment variables first
            if all(k in os.environ for k in [
                'FIREBASE_TYPE', 'FIREBASE_PROJECT_ID', 'FIREBASE_PRIVATE_KEY_ID',
                'FIREBASE_PRIVATE_KEY', 'FIREBASE_CLIENT_EMAIL', 'FIREBASE_CLIENT_ID',
                'FIREBASE_AUTH_URI', 'FIREBASE_TOKEN_URI',
                'FIREBASE_AUTH_PROVIDER_CERT_URL', 'FIREBASE_CLIENT_CERT_URL'
            ]):
                cred = credentials.Certificate({
                    "type": os.environ.get("FIREBASE_TYPE"),
                    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
                    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
                    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
                    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
                    "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
                    "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
                    "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_CERT_URL"),
                    "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL")
                })
            else:
                # Fall back to service account file if exists (for local development)
                if os.path.exists("serviceAccountKey.json"):
                    cred = credentials.Certificate("serviceAccountKey.json")
                else:
                    raise ValueError("No Firebase credentials provided")

            firebase_admin.initialize_app(cred)
            logging.info("Firebase Admin SDK initialized successfully")

        return firestore.client()

    except Exception as e:
        logging.error(f"Error initializing Firebase: {str(e)}")
        raise


# Initialize Firebase
try:
    db = initialize_firebase()
except Exception as e:
    logging.error(f"Failed to initialize Firebase: {str(e)}")
    db = None

# Collection names
USERS_COLLECTION = "users"
BOOKS_COLLECTION = "books"
TRANSACTIONS_COLLECTION = "transactions"
MEMBERS_COLLECTION = "members"



def get_firebase_config():
    """Returns Firebase configuration for client-side use"""
    return {
        "apiKey": "YOUR_API_KEY",
        "authDomain": "YOUR_PROJECT.firebaseapp.com",
        "projectId": "YOUR_PROJECT_ID",
        "storageBucket": "YOUR_BUCKET.appspot.com",
        "messagingSenderId": "YOUR_SENDER_ID",
        "appId": "YOUR_APP_ID"
    }


@app.route('/')
def index():
    # Always redirect to login, regardless of session
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_ref = db.collection(USERS_COLLECTION).document(username)
        user_data = user_ref.get()

        if user_data.exists:
            user_dict = user_data.to_dict()
            if check_password_hash(user_dict['password'], password):
                session['username'] = username
                session['user_details'] = {
                    'name': user_dict['name'],
                    'email': user_dict.get('email', ''),
                    'role': user_dict.get('role', 'user')
                }
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Invalid password', 'error')
        else:
            flash('Username not found', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        email = request.form.get('email', '')

        user_ref = db.collection(USERS_COLLECTION).document(username)
        if user_ref.get().exists:
            flash('Username already exists', 'error')
        else:
            user_ref.set({
                'username': username,
                'password': generate_password_hash(password),
                'name': name,
                'email': email,
                'role': 'user'
            })
            flash('Registration successful! Please login', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_details', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


def get_recent_transactions(limit=5):
    """Fetch recent transactions from Firestore"""
    try:
        # Get the most recent transactions (both issued and returned)
        transactions_ref = db.collection(TRANSACTIONS_COLLECTION)

        # Order by issue_date descending and limit results
        recent_transactions = transactions_ref.order_by(
            'issue_date', direction=firestore.Query.DESCENDING
        ).limit(limit).stream()

        transactions = []
        for trans in recent_transactions:
            trans_data = trans.to_dict()
            trans_data['id'] = trans.id

            # Calculate days overdue if not returned
            if not trans_data.get('returned'):
                due_date = datetime.datetime.strptime(trans_data['due_date'], '%Y-%m-%d')
                today = datetime.datetime.now()
                trans_data['days_overdue'] = (today - due_date).days if today > due_date else 0
            else:
                trans_data['days_overdue'] = 0

            # Convert string dates to datetime objects for template formatting
            trans_data['issue_date'] = datetime.datetime.strptime(trans_data['issue_date'], '%Y-%m-%d')
            trans_data['due_date'] = datetime.datetime.strptime(trans_data['due_date'], '%Y-%m-%d')

            transactions.append(trans_data)

        return transactions

    except Exception as e:
        logging.error(f"Error fetching recent transactions: {str(e)}")
        return []

@app.route('/home')
@app.route('/dashboard')
def home():
    stats = {
        'total_books': len([doc for doc in db.collection('books').stream()]),
        'available_books': len([doc for doc in db.collection('books').where('status', '==', 'available').stream()]),
        'issued_books': len([doc for doc in db.collection('books').where('status', '==', 'issued').stream()]),
        'transactions': get_recent_transactions()
    }
    return render_template('dashboard.html', **stats)

@app.route('/books')
def books():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get all books from Firestore
    books_ref = db.collection(BOOKS_COLLECTION).stream()
    books = []
    for book in books_ref:
        book_data = book.to_dict()
        book_data['id'] = book.id  # Include document ID
        books.append(book_data)

    return render_template('books.html',
                           books=books,
                           user=session['user_details'])


@app.route('/add_book', methods=['POST'])
def add_book():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()

        # Check if ISBN exists
        existing = db.collection(BOOKS_COLLECTION).where('isbn', '==', data['isbn']).get()
        if len(existing) > 0:
            return jsonify({'error': 'Book with this ISBN already exists'}), 400

        # Add new book
        db.collection(BOOKS_COLLECTION).add({
            'title': data['title'],
            'author': data['author'],
            'isbn': data['isbn'],
            'status': 'available',
            'added_by': session['username'],
            'added_date': datetime.datetime.now().isoformat()
        })
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_book', methods=['POST'])
def update_book():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        book_id = data.get('id')

        if not book_id:
            return jsonify({'error': 'Book ID is required'}), 400

        # Get the book reference
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book = book_ref.get()

        if not book.exists:
            return jsonify({'error': 'Book not found'}), 404

        # Update the book
        book_ref.update({
            'title': data.get('title'),
            'author': data.get('author'),
            'status': data.get('status')
        })

        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error updating book: {str(e)}")  # Log the error
        return jsonify({'error': str(e)}), 500


@app.route('/delete_book', methods=['POST'])
def delete_book():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        book_id = data.get('id')

        if not book_id:
            return jsonify({'error': 'Book ID is required'}), 400

        # Get the book reference
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book = book_ref.get()

        if not book.exists:
            return jsonify({'error': 'Book not found'}), 404

        # Delete the book
        book_ref.delete()

        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error deleting book: {str(e)}")  # Log the error
        return jsonify({'error': str(e)}), 500


@app.route('/members')
def members():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get all members from Firestore
    members_ref = db.collection(MEMBERS_COLLECTION).stream()
    members = []
    for member in members_ref:
        member_data = member.to_dict()
        member_data['id'] = member.id  # Include document ID
        members.append(member_data)

    return render_template('members.html',
                           members=members,
                           user=session['user_details'])


@app.route('/add_member', methods=['POST'])
def add_member():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()

        # Generate 4-character member ID (2 letters + 2 numbers)
        letters = random.choices(string.ascii_uppercase, k=2)
        numbers = random.choices(string.digits, k=2)
        member_id = ''.join(letters + numbers)

        # Add new member
        member_ref = db.collection(MEMBERS_COLLECTION).document()
        member_ref.set({
            'member_id': member_id,
            'name': data.get('name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'address': data.get('address'),
            'dob': data.get('dob'),
            'membership_date': datetime.datetime.now().isoformat(),
            'added_by': session['username']
        })

        return jsonify({
            'success': True,
            'member_id': member_id
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_member', methods=['POST'])
def update_member():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        member_id = data.get('id')

        if not member_id:
            return jsonify({'error': 'Member ID is required'}), 400

        # Update the member
        db.collection(MEMBERS_COLLECTION).document(member_id).update({
            'name': data.get('name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'address': data.get('address'),
            'dob': data.get('dob')
        })

        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/delete_member', methods=['POST'])
def delete_member():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        member_id = data.get('id')

        if not member_id:
            return jsonify({'error': 'Member ID is required'}), 400

        # Delete the member
        db.collection(MEMBERS_COLLECTION).document(member_id).delete()

        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/transactions')
def transactions():
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        # Get all transactions
        transactions_ref = db.collection(TRANSACTIONS_COLLECTION).stream()
        all_transactions = []

        for trans in transactions_ref:
            trans_data = trans.to_dict()
            trans_data['id'] = trans.id

            # Convert string dates to datetime objects for calculation
            issue_date = datetime.datetime.strptime(trans_data['issue_date'], '%Y-%m-%d')
            due_date = datetime.datetime.strptime(trans_data['due_date'], '%Y-%m-%d')

            # Calculate days remaining (negative if overdue)
            days_remaining = (due_date - datetime.datetime.now()).days
            trans_data['days_remaining'] = days_remaining

            # Format dates for display
            trans_data['issue_date_display'] = issue_date.strftime('%Y-%m-%d')
            trans_data['due_date_display'] = due_date.strftime('%Y-%m-%d')

            if trans_data.get('return_date'):
                return_date = datetime.datetime.strptime(trans_data['return_date'], '%Y-%m-%d')
                trans_data['return_date_display'] = return_date.strftime('%Y-%m-%d')

            all_transactions.append(trans_data)

        # Separate into issued and returned
        issued_transactions = [t for t in all_transactions if not t.get('returned')]
        returned_transactions = [t for t in all_transactions if t.get('returned')]

        today = datetime.datetime.now().strftime('%Y-%m-%d')
        due_date = (datetime.datetime.now() + datetime.timedelta(days=14)).strftime('%Y-%m-%d')

        return render_template('transactions.html',
                               issued_transactions=issued_transactions,
                               returned_transactions=returned_transactions,
                               today=today,
                               due_date=due_date)

    except Exception as e:
        flash(f'Error loading transactions: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/issue_book', methods=['POST'])
def issue_book():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        book_input = data.get('book_id')  # Could be ISBN or doc ID
        member_id = data.get('member_id')

        # First try to find by document ID
        book_ref = db.collection(BOOKS_COLLECTION).document(book_input)
        book = book_ref.get()

        if not book.exists:
            # If not found by ID, try to find by ISBN
            books_ref = db.collection(BOOKS_COLLECTION).where('isbn', '==', book_input).limit(1)
            books = [doc for doc in books_ref.stream()]
            if not books:
                return jsonify({'error': 'Book not found'}), 404
            book = books[0]
            book_ref = db.collection(BOOKS_COLLECTION).document(book.id)

        book_data = book.to_dict()

        if book_data.get('status') != 'available':
            return jsonify({'error': 'Book is not available for issue'}), 400

        # Get member details
        members_ref = db.collection(MEMBERS_COLLECTION).where('member_id', '==', member_id).limit(1)
        members = [doc for doc in members_ref.stream()]
        if not members:
            return jsonify({'error': 'Member not found'}), 404
        member = members[0]
        member_data = member.to_dict()

        # Create transaction
        transaction_ref = db.collection(TRANSACTIONS_COLLECTION).document()
        transaction_ref.set({
            'book_id': book_ref.id,
            'book_title': book_data.get('title'),
            'member_id': member_id,
            'member_name': member_data.get('name'),
            'issue_date': data.get('issue_date'),
            'due_date': data.get('due_date'),
            'return_date': None,
            'returned': False,
            'issued_by': session['username']
        })

        # Update book status
        book_ref.update({'status': 'issued'})

        return jsonify({'success': True}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/return_book', methods=['POST'])
def return_book():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        book_input = data.get('book_id')
        return_date = data.get('return_date')
        condition = data.get('condition', 'good')

        # Find the book
        books_ref = db.collection(BOOKS_COLLECTION).where('isbn', '==', book_input).limit(1)
        books = [doc for doc in books_ref.stream()]

        if not books:
            return jsonify({'error': 'Book not found'}), 404

        book = books[0]
        book_ref = db.collection(BOOKS_COLLECTION).document(book.id)

        # Find the active transaction
        transactions_ref = db.collection(TRANSACTIONS_COLLECTION) \
            .where('book_id', '==', book.id) \
            .where('returned', '==', False) \
            .limit(1)
        transactions = [doc for doc in transactions_ref.stream()]

        if not transactions:
            return jsonify({'error': 'No active transaction found for this book'}), 404

        transaction = transactions[0]
        transaction_ref = db.collection(TRANSACTIONS_COLLECTION).document(transaction.id)

        # Update transaction
        transaction_ref.update({
            'return_date': return_date,
            'returned': True,
            'condition': condition,
            'returned_by': session['username']
        })

        # Update book status based on condition
        new_status = 'available' if condition == 'good' else condition
        book_ref.update({'status': new_status})

        return jsonify({'success': True}), 200

    except Exception as e:
        logging.error(f"Error in return_book: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_book_details')
def get_book_details():
    try:
        isbn = request.args.get('isbn')  # Get the ISBN from the query parameter
        if not isbn:
            return jsonify({'error': 'ISBN is required'}), 400

        # Query the books collection where isbn matches the provided value
        books_ref = db.collection(BOOKS_COLLECTION).where('isbn', '==', isbn).limit(1)
        books = [doc for doc in books_ref.stream()]

        if books:  # If a book is found
            book_data = books[0].to_dict()
            book_data['id'] = books[0].id  # Include the document ID if needed
            logging.debug(f"Book found: {book_data}")
            return jsonify(book_data)
        else:
            logging.debug(f"No book found with ISBN: {isbn}")
            return jsonify(None), 200

    except Exception as e:
        logging.error(f"Error in get_book_details: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/get_member_details')
def get_member_details():
    member_id = request.args.get('member_id')

    # First try to find by document ID
    member_ref = db.collection(MEMBERS_COLLECTION).document(member_id)
    member = member_ref.get()

    if member.exists:
        return jsonify(member.to_dict())

    # If not found by document ID, try to find by member_id field
    members_ref = db.collection(MEMBERS_COLLECTION).where('member_id', '==', member_id).limit(1)
    members = [doc.to_dict() for doc in members_ref.stream()]

    if members:
        return jsonify(members[0])

    return jsonify(None)


@app.route('/get_all_transactions')
def get_all_transactions():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        transactions_ref = db.collection(TRANSACTIONS_COLLECTION).stream()
        transactions = []
        for trans in transactions_ref:
            trans_data = trans.to_dict()
            trans_data['id'] = trans.id
            transactions.append(trans_data)

        return jsonify(transactions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_transaction_details')
def get_transaction_details():
    try:
        isbn = request.args.get('isbn')
        if not isbn:
            return jsonify({'error': 'ISBN is required'}), 401

        # First find the book
        books_ref = db.collection(BOOKS_COLLECTION).where('isbn', '==', isbn).limit(1)
        books = [doc for doc in books_ref.stream()]

        if not books:
            return jsonify({'error': 'Book not found'}), 404

        book = books[0]

        # Then find active transaction
        transactions_ref = db.collection(TRANSACTIONS_COLLECTION) \
            .where('book_id', '==', book.id) \
            .where('returned', '==', False) \
            .limit(1)
        transactions = [doc for doc in transactions_ref.stream()]

        if not transactions:
            return jsonify({'error': 'No active transaction found for this book'}), 404

        transaction = transactions[0]
        return jsonify(transaction.to_dict())

    except Exception as e:
        logging.error(f"Error in get_transaction_details: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)