"""CSRF Lab: one Flask app with a VULNERABLE and a SECURE version of the same form.
For learning only. Run it on localhost; never deploy it."""
import hmac
import secrets

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "lab-only-secret-change-me"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

USERS = {
    "alice": {"password": "password123", "balance": 5000},
    "bob": {"password": "bobpass", "balance": 1000},
}
LOG = []  # (mode, sender, receiver, amount)


# ---------- CSRF protection helpers (used only by the secure routes) ----------
def get_csrf_token():
    """Create one random token per session and reuse it for every form."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def verify_csrf():
    """Reject the request unless the submitted token matches the session token."""
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(sent, expected):  # constant-time compare
        abort(403)


app.jinja_env.globals["csrf_token"] = get_csrf_token


# ---------- shared logic ----------
def transfer(mode):
    sender = session["user"]
    receiver = request.form.get("to", "").strip().lower()
    try:
        amount = int(request.form.get("amount", ""))
    except ValueError:
        amount = 0
    if receiver not in USERS or receiver == sender:
        flash("Choose a different, existing account to send to.", "error")
    elif not 0 < amount <= USERS[sender]["balance"]:
        flash("Enter an amount between 1 and your balance.", "error")
    else:
        USERS[sender]["balance"] -= amount
        USERS[receiver]["balance"] += amount
        LOG.append((mode, sender, receiver, amount))
        flash(f"Sent ${amount:,} to {receiver}.", "ok")
    return redirect(url_for(mode))


def page(mode):
    if "user" not in session:
        return redirect(url_for("login"))
    me = session["user"]
    return render_template("dashboard.html", mode=mode, me=me,
                           balance=USERS[me]["balance"], log=reversed(LOG[-8:]),
                           others=[u for u in USERS if u != me])


# ---------- routes ----------
@app.route("/")
def index():
    return redirect(url_for("vulnerable"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip().lower()
        if u in USERS and USERS[u]["password"] == request.form.get("password"):
            session.clear()
            session["user"] = u
            return redirect(url_for("vulnerable"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/reset")
def reset():
    USERS["alice"]["balance"], USERS["bob"]["balance"] = 5000, 1000
    LOG.clear()
    return redirect(request.referrer or url_for("vulnerable"))


# VULNERABLE: trusts any POST that carries the session cookie.
@app.route("/vulnerable")
def vulnerable():
    return page("vulnerable")


@app.route("/vulnerable/transfer", methods=["POST"])
def vulnerable_transfer():
    if "user" not in session:
        return redirect(url_for("login"))
    return transfer("vulnerable")


# SECURE: same action, but the request must prove it came from our own form.
@app.route("/secure")
def secure():
    return page("secure")


@app.route("/secure/transfer", methods=["POST"])
def secure_transfer():
    if "user" not in session:
        return redirect(url_for("login"))
    verify_csrf()
    return transfer("secure")


@app.errorhandler(403)
def forbidden(_):
    return render_template("blocked.html"), 403


if __name__ == "__main__":
    app.run(port=5000, debug=True)
