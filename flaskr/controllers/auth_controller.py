"""
auth_controller.py
------------------
Controller (View layer in Flask terms) for authentication routes.

Responsibilities:
  - Handle HTTP request/response cycle for /auth/* routes
  - Delegate all data access to UserModel
  - Render templates or redirect as appropriate
"""

import functools
import os

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

from flaskr.models.user import UserModel

bp = Blueprint('auth', __name__, url_prefix='/auth')

NO_DB = os.environ.get('NO_DB', 'false').lower() == 'true'


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def login_required(view):
    """Redirect to login page if the user is not authenticated."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


# ---------------------------------------------------------------------------
# Before-request hook — populate g.user on every request
# ---------------------------------------------------------------------------

@bp.before_app_request
def load_logged_in_user():
    if NO_DB:
        g.user = None
        return

    user_id = session.get('user_id')
    g.user = UserModel.get_by_id(user_id) if user_id else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if NO_DB:
        flash('Registration is not available in this version.')
        return redirect(url_for('core.index'))

    if request.method == 'POST':
        username  = request.form['username']
        email     = request.form['email']
        password  = request.form['password']
        cpassword = request.form['cpassword']
        error     = None

        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        elif not cpassword:
            error = 'Confirm your password is required.'
        elif password != cpassword:
            error = 'Password is different from Password confirmation!'

        if error is None:
            try:
                UserModel.create(username, email, password)
            except Exception:
                error = f'Email {email} is already registered.'
            else:
                return redirect(url_for('auth.login'))

        flash(error)

    return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if NO_DB:
        flash('Login is not available in this version.')
        return redirect(url_for('core.index'))

    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        error    = None

        user = UserModel.get_by_email(email)

        if user is None or not UserModel.verify_password(user, password):
            error = 'Incorrect email or password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('core.index'))
