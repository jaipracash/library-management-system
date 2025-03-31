// Initialize Firebase
const firebaseConfig = {
    apiKey: "AIzaSyA9xQUAKtMqSuidauDqLCrB-qjhOVn_2Fk",
    authDomain: "complaint-tracker-95305.firebaseapp.com",
    databaseURL: "https://complaint-tracker-95305.firebaseio.com",
    projectId: "complaint-tracker-95305",
    storageBucket: "complaint-tracker-95305.appspot.com",
    messagingSenderId: "1006349794330",
    appId: "1:1006349794330:web:1572e968e4c167d97ba5a3",
    measurementId: "G-S8YF0D0FGX"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Firebase references
const db = firebase.database();
const auth = firebase.auth();
const booksRef = db.ref('books');
const membersRef = db.ref('members');
const transactionsRef = db.ref('transactions');

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    // Check current page and load appropriate data
    const path = window.location.pathname;

    if (path.includes('home') || path === '/') {
        loadDashboardStats();
        loadRecentTransactions();
    } else if (path.includes('books')) {
        loadBooks();
        setupBookForm();
    } else if (path.includes('transactions')) {
        loadTransactions();
        setupTransactionForm();
    } else if (path.includes('members')) {
        loadMembers();
        setupMemberForm();
    }

    // Setup logout button
    const logoutBtn = document.querySelector('.btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            logoutUser();
        });
    }
});

// ======================
// AUTHENTICATION FUNCTIONS
// ======================

function loginUser(email, password) {
    auth.signInWithEmailAndPassword(email, password)
        .then((userCredential) => {
            // Redirect to home page
            window.location.href = '/home';
        })
        .catch((error) => {
            console.error("Login error:", error);
            showAlert('error', error.message);
        });
}

function logoutUser() {
    auth.signOut()
        .then(() => {
            window.location.href = '/login';
        })
        .catch((error) => {
            console.error("Logout error:", error);
        });
}

// ======================
// DASHBOARD FUNCTIONS
// ======================

function loadDashboardStats() {
    // Total books count
    booksRef.once('value')
        .then((snapshot) => {
            const totalBooks = snapshot.numChildren();
            document.getElementById('total-books-count').textContent = totalBooks;

            // Calculate available books
            let availableBooks = 0;
            snapshot.forEach((book) => {
                if (book.val().status === 'available') {
                    availableBooks++;
                }
            });
            document.getElementById('available-books-count').textContent = availableBooks;
            document.getElementById('issued-books-count').textContent = totalBooks - availableBooks;
        });
}

function loadRecentTransactions() {
    const tbody = document.querySelector('#recent-transactions tbody');
    if (!tbody) return;

    transactionsRef.orderByChild('date').limitToLast(5).on('value', (snapshot) => {
        tbody.innerHTML = '';

        snapshot.forEach((childSnapshot) => {
            const transaction = childSnapshot.val();
            const tr = document.createElement('tr');

            tr.innerHTML = `
                <td>${transaction.book_id || ''}</td>
                <td>${transaction.member_id || ''}</td>
                <td>${formatDate(transaction.issue_date) || ''}</td>
                <td>${formatDate(transaction.due_date) || ''}</td>
                <td>
                    <span class="status-badge ${transaction.returned ? 'returned' : 'pending'}">
                        ${transaction.returned ? 'Returned' : 'Pending'}
                    </span>
                </td>
            `;

            tbody.appendChild(tr);
        });
    });
}

// ======================
// BOOKS MANAGEMENT
// ======================

function loadBooks() {
    const tbody = document.querySelector('#books-table tbody');
    if (!tbody) return;

    booksRef.orderByChild('title').on('value', (snapshot) => {
        tbody.innerHTML = '';
        let index = 1;

        snapshot.forEach((childSnapshot) => {
            const book = childSnapshot.val();
            const tr = document.createElement('tr');

            tr.innerHTML = `
                <td>${index++}</td>
                <td>${book.title || ''}</td>
                <td>${book.author || ''}</td>
                <td>${book.category || ''}</td>
                <td>${book.isbn || ''}</td>
                <td>
                    <span class="status-badge ${book.status === 'available' ? 'available' : 'issued'}">
                        ${book.status || ''}
                    </span>
                </td>
                <td>
                    <button class="btn btn-edit" onclick="editBook('${childSnapshot.key}')">Edit</button>
                    <button class="btn btn-delete" onclick="deleteBook('${childSnapshot.key}')">Delete</button>
                </td>
            `;

            tbody.appendChild(tr);
        });
    });
}

function setupBookForm() {
    const form = document.getElementById('book-form');
    if (!form) return;

    // Check if we're editing a book
    const urlParams = new URLSearchParams(window.location.search);
    const bookId = urlParams.get('id');

    if (bookId) {
        // Load book data
        booksRef.child(bookId).once('value')
            .then((snapshot) => {
                const book = snapshot.val();
                if (book) {
                    document.getElementById('title').value = book.title || '';
                    document.getElementById('author').value = book.author || '';
                    document.getElementById('category').value = book.category || '';
                    document.getElementById('isbn').value = book.isbn || '';
                    if (document.getElementById('status')) {
                        document.getElementById('status').value = book.status || 'available';
                    }
                }
            });
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const bookData = {
            title: document.getElementById('title').value,
            author: document.getElementById('author').value,
            category: document.getElementById('category').value,
            isbn: document.getElementById('isbn').value,
            updatedAt: firebase.database.ServerValue.TIMESTAMP
        };

        if (document.getElementById('status')) {
            bookData.status = document.getElementById('status').value;
        } else {
            bookData.status = 'available';
            bookData.added_date = new Date().toISOString().split('T')[0];
        }

        if (bookId) {
            // Update existing book
            booksRef.child(bookId).update(bookData)
                .then(() => {
                    showAlert('success', 'Book updated successfully');
                    setTimeout(() => window.location.href = '/books', 1500);
                })
                .catch((error) => {
                    showAlert('error', error.message);
                });
        } else {
            // Add new book
            booksRef.push(bookData)
                .then(() => {
                    showAlert('success', 'Book added successfully');
                    form.reset();
                    setTimeout(() => window.location.href = '/books', 1500);
                })
                .catch((error) => {
                    showAlert('error', error.message);
                });
        }
    });
}

function editBook(bookId) {
    window.location.href = `/edit_book?id=${bookId}`;
}

function deleteBook(bookId) {
    if (confirm('Are you sure you want to delete this book?')) {
        booksRef.child(bookId).remove()
            .then(() => {
                showAlert('success', 'Book deleted successfully');
            })
            .catch((error) => {
                showAlert('error', error.message);
            });
    }
}

// ======================
// TRANSACTIONS MANAGEMENT
// ======================

function loadTransactions() {
    const pendingTbody = document.querySelector('#pending-transactions tbody');
    const returnedTbody = document.querySelector('#returned-transactions tbody');

    transactionsRef.orderByChild('date').on('value', (snapshot) => {
        if (pendingTbody) pendingTbody.innerHTML = '';
        if (returnedTbody) returnedTbody.innerHTML = '';
        let pendingIndex = 1;
        let returnedIndex = 1;

        snapshot.forEach((childSnapshot) => {
            const transaction = childSnapshot.val();
            const tr = document.createElement('tr');

            tr.innerHTML = `
                <td>${transaction.returned ? returnedIndex++ : pendingIndex++}</td>
                <td>${transaction.book_id || ''}</td>
                <td>${transaction.member_id || ''}</td>
                <td>${formatDate(transaction.issue_date) || ''}</td>
                <td>${formatDate(transaction.due_date) || ''}</td>
                <td>${transaction.returned ? formatDate(transaction.return_date) : 'Not returned'}</td>
                <td>
                    ${!transaction.returned ?
                        `<button class="btn btn-primary" onclick="returnTransaction('${childSnapshot.key}')">Return</button>` :
                        ''}
                </td>
            `;

            if (transaction.returned && returnedTbody) {
                returnedTbody.appendChild(tr);
            } else if (pendingTbody) {
                pendingTbody.appendChild(tr);
            }
        });
    });
}

function setupTransactionForm() {
    const form = document.getElementById('transaction-form');
    if (!form) return;

    // Check if we're returning a book
    const urlParams = new URLSearchParams(window.location.search);
    const transactionId = urlParams.get('id');

    if (transactionId) {
        // Load transaction data
        transactionsRef.child(transactionId).once('value')
            .then((snapshot) => {
                const transaction = snapshot.val();
                if (transaction) {
                    document.getElementById('book-id').textContent = transaction.book_id;
                    document.getElementById('member-id').textContent = transaction.member_id;
                    document.getElementById('issue-date').textContent = formatDate(transaction.issue_date);
                    document.getElementById('due-date').textContent = formatDate(transaction.due_date);
                }
            });
    } else {
        // Load available books for issuing
        booksRef.orderByChild('status').equalTo('available').on('value', (snapshot) => {
            const bookSelect = document.getElementById('book-select');
            if (!bookSelect) return;

            bookSelect.innerHTML = '<option value="">Select a book</option>';

            snapshot.forEach((childSnapshot) => {
                const book = childSnapshot.val();
                const option = document.createElement('option');
                option.value = childSnapshot.key;
                option.textContent = `${book.title} (${book.isbn})`;
                bookSelect.appendChild(option);
            });
        });
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        if (transactionId) {
            // Return a book
            const returnData = {
                returned: true,
                return_date: new Date().toISOString().split('T')[0],
                updatedAt: firebase.database.ServerValue.TIMESTAMP
            };

            // Get the book ID first
            transactionsRef.child(transactionId).once('value')
                .then((snapshot) => {
                    const transaction = snapshot.val();
                    if (!transaction) throw new Error('Transaction not found');

                    // Update transaction
                    return transactionsRef.child(transactionId).update(returnData)
                        .then(() => {
                            // Update book status
                            return booksRef.child(transaction.book_id).update({
                                status: 'available',
                                updatedAt: firebase.database.ServerValue.TIMESTAMP
                            });
                        });
                })
                .then(() => {
                    showAlert('success', 'Book returned successfully');
                    setTimeout(() => window.location.href = '/transactions', 1500);
                })
                .catch((error) => {
                    showAlert('error', error.message);
                });
        } else {
            // Issue a new book
            const bookId = document.getElementById('book-select').value;
            const memberId = document.getElementById('member-id-input').value;
            const issueDate = document.getElementById('issue-date-input').value;
            const dueDate = document.getElementById('due-date-input').value;

            if (!bookId || !memberId || !issueDate || !dueDate) {
                showAlert('error', 'Please fill all fields');
                return;
            }

            const transactionData = {
                book_id: bookId,
                member_id: memberId,
                issue_date: issueDate,
                due_date: dueDate,
                returned: false,
                date: firebase.database.ServerValue.TIMESTAMP
            };

            // First update the book status
            booksRef.child(bookId).update({
                status: 'issued',
                updatedAt: firebase.database.ServerValue.TIMESTAMP
            })
            .then(() => {
                // Then create the transaction
                return transactionsRef.push(transactionData);
            })
            .then(() => {
                showAlert('success', 'Book issued successfully');
                form.reset();
                setTimeout(() => window.location.href = '/transactions', 1500);
            })
            .catch((error) => {
                showAlert('error', error.message);
            });
        }
    });
}

function returnTransaction(transactionId) {
    window.location.href = `/return_book?id=${transactionId}`;
}

// ======================
// MEMBERS MANAGEMENT
// ======================

function loadMembers() {
    const tbody = document.querySelector('#members-table tbody');
    if (!tbody) return;

    membersRef.on('value', (snapshot) => {
        tbody.innerHTML = '';
        let index = 1;

        snapshot.forEach((childSnapshot) => {
            const member = childSnapshot.val();
            const tr = document.createElement('tr');

            tr.innerHTML = `
                <td>${index++}</td>
                <td>${childSnapshot.key}</td>
                <td>${member.name || ''}</td>
                <td>${member.email || ''}</td>
                <td>${member.phone || ''}</td>
                <td>
                    <button class="btn btn-edit" onclick="editMember('${childSnapshot.key}')">Edit</button>
                    <button class="btn btn-delete" onclick="deleteMember('${childSnapshot.key}')">Delete</button>
                </td>
            `;

            tbody.appendChild(tr);
        });
    });
}

function setupMemberForm() {
    const form = document.getElementById('member-form');
    if (!form) return;

    // Check if we're editing a member
    const urlParams = new URLSearchParams(window.location.search);
    const memberId = urlParams.get('id');

    if (memberId) {
        // Load member data
        membersRef.child(memberId).once('value')
            .then((snapshot) => {
                const member = snapshot.val();
                if (member) {
                    document.getElementById('name').value = member.name || '';
                    document.getElementById('email').value = member.email || '';
                    document.getElementById('phone').value = member.phone || '';
                }
            });
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const memberData = {
            name: document.getElementById('name').value,
            email: document.getElementById('email').value,
            phone: document.getElementById('phone').value,
            updatedAt: firebase.database.ServerValue.TIMESTAMP
        };

        if (memberId) {
            // Update existing member
            membersRef.child(memberId).update(memberData)
                .then(() => {
                    showAlert('success', 'Member updated successfully');
                    setTimeout(() => window.location.href = '/members', 1500);
                })
                .catch((error) => {
                    showAlert('error', error.message);
                });
        } else {
            // Add new member
            membersRef.push(memberData)
                .then(() => {
                    showAlert('success', 'Member added successfully');
                    form.reset();
                })
                .catch((error) => {
                    showAlert('error', error.message);
                });
        }
    });
}

function editMember(memberId) {
    window.location.href = `/edit_member?id=${memberId}`;
}

function deleteMember(memberId) {
    if (confirm('Are you sure you want to delete this member?')) {
        membersRef.child(memberId).remove()
            .then(() => {
                showAlert('success', 'Member deleted successfully');
            })
            .catch((error) => {
                showAlert('error', error.message);
            });
    }
}

// ======================
// UTILITY FUNCTIONS
// ======================

function formatDate(dateString) {
    if (!dateString) return '';
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;

    const container = document.querySelector('.main-content') || document.body;
    container.insertBefore(alertDiv, container.firstChild);

    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

// Make functions available globally for HTML onclick attributes
window.editBook = editBook;
window.deleteBook = deleteBook;
window.returnTransaction = returnTransaction;
window.editMember = editMember;
window.deleteMember = deleteMember;

// ======================
// AUTHENTICATION FUNCTIONS
// ======================

function registerUser(email, password, name) {
    return firebase.auth().createUserWithEmailAndPassword(email, password)
        .then((userCredential) => {
            // Add user data to Realtime Database
            const user = userCredential.user;
            return db.ref('users/' + user.uid).set({
                name: name,
                email: email,
                role: 'librarian', // Default role
                createdAt: firebase.database.ServerValue.TIMESTAMP
            });
        })
        .then(() => {
            return { success: true, message: 'Registration successful' };
        })
        .catch((error) => {
            return { success: false, message: error.message };
        });
}

function loginUser(email, password) {
    return firebase.auth().signInWithEmailAndPassword(email, password)
        .then(() => {
            return { success: true, message: 'Login successful' };
        })
        .catch((error) => {
            return { success: false, message: error.message };
        });
}

function logoutUser() {
    return firebase.auth().signOut()
        .then(() => {
            return { success: true, message: 'Logout successful' };
        })
        .catch((error) => {
            return { success: false, message: error.message };
        });
}

function getCurrentUser() {
    return new Promise((resolve) => {
        const unsubscribe = firebase.auth().onAuthStateChanged((user) => {
            unsubscribe();
            resolve(user);
        });
    });
}

// Initialize auth state listener
firebase.auth().onAuthStateChanged((user) => {
    if (user) {
        // User is signed in
        console.log('User logged in:', user.email);

        // You can store user data in session or use directly
        if (window.location.pathname === '/login' || window.location.pathname === '/register') {
            window.location.href = '/home';
        }
    } else {
        // User is signed out
        console.log('User logged out');

        // Redirect to login if not on auth pages
        if (!['/login', '/register'].includes(window.location.pathname)) {
            window.location.href = '/login';
        }
    }
});

// Simple form validation example
document.addEventListener('DOMContentLoaded', function() {
    // Add any client-side validation if needed
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Example: Validate password length
            const password = form.querySelector('input[type="password"]');
            if (password && password.value.length < 6) {
                e.preventDefault();
                alert('Password must be at least 6 characters');
            }
        });
    });
});