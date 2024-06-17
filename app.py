import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute(
        "SELECT symbol, SUM(shares), price FROM purchases WHERE userid = ? GROUP BY symbol;", session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])[0]["cash"]
    grand_total = cash
    userinfo = []
    for i in range(len(stocks)):
        symbol = stocks[i]["symbol"]
        shares = stocks[i]["SUM(shares)"]
        price = lookup(symbol)["price"]
        holding = shares * price
        grand_total += price * shares
        if shares == 0:
            continue
        userinfo.append([symbol, shares, price, holding])

    return render_template("index.html", userinfo=userinfo, cash=cash, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":
        ticker = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        if not ticker or len(ticker) > 5:
            return apology("Please enter a correct ticker code")

        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("Please enter a correct amount of shares to purchase")

        info = lookup(ticker)
        if info is None:
            return apology("Please enter a correct stock symbol")

        price = info["price"]
        total_cost = int(shares) * price
        cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])[0]["cash"]

        if cash < total_cost:
            return apology("Do not have enough cash to buy enough shares")

        new_cash = cash - total_cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", new_cash, session["user_id"])

        now = datetime.now()
        f_now = now.strftime('%Y-%m-%d:%H:%M:%S')

        db.execute("INSERT INTO purchases (userid, date, symbol, shares, price) VALUES(?, ?, ?, ?, ?);",
                   session["user_id"], f_now, ticker, shares, price)
        format_total_cost = usd(total_cost)
        flash(f"Bought {shares} shares of {ticker} for {format_total_cost}!")

        return redirect("/")
    """Buy shares of stock"""


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change-password.html")

    if request.method == "POST":
        username = request.form.get("username")
        old_password = request.form.get("old_password")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not old_password or not confirmation:
            return apology("Please enter all fields")

        if not password == confirmation:
            return apology("New passwords dont match")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], old_password):
            return apology("invalid username and/or password", 403)

        db.execute("UPDATE users SET hash = ? WHERE username = ?",
                   generate_password_hash(password), username)

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute(
        "SELECT symbol, shares, price, date FROM purchases WHERE userid = ?", session["user_id"])
    userinfo = []
    for i in range(len(stocks)):
        symbol = stocks[i]["symbol"]
        shares = stocks[i]["shares"]
        price = stocks[i]["price"]
        date = stocks[i]["date"]
        transaction = ""
        if shares < 0:
            transaction = "Sell"
        else:
            transaction = "Buy"
        userinfo.append([transaction, symbol, abs(shares), price, date])

    return render_template("history.html", userinfo=userinfo)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        ticker = request.form.get("symbol")

        info = lookup(ticker)

        if not ticker or len(ticker) > 5 or info is None:
            return apology("Please enter a correct ticker code", 400)

        return render_template("quoted.html", info=info)


@app.route("/register", methods=["GET", "POST"])
def register():
    # Clear the session
    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)
        # Ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # Check if username already exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 0:
            return apology("username already exists", 400)

        # Insert new user into the database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
                   request.form.get("username"), generate_password_hash(request.form.get("password")))

        # Retrieve the newly created user's ID
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Store the user ID in the session
        session["user_id"] = rows[0]["id"]

        # Redirect to the homepage
        return redirect("/")

    # If the request method is GET, render the registration form
    if request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM purchases WHERE userid = ?  GROUP BY symbol HAVING total_shares > 0", session["user_id"])

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)

    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))

        if not symbol or not shares:
            return apology("Fill in all requirments")

        if int(shares) <= 0:
            return apology("Please enter a correct amount of shares")

        shares = int(shares)

        for stock in stocks:
            if stock["symbol"] == symbol:
                if stock["total_shares"] < shares:
                    return apology("not enough shares")
                else:
                    info = lookup(symbol)
                    if info is None:
                        return apology("Please enter a correct symbol")
                    price = info["price"]
                    total_sale = price * shares

                    db.execute("UPDATE users SET cash = cash + ? WHERE id = ?",
                               total_sale, session["user_id"])

                    now = datetime.now()
                    f_now = now.strftime('%Y-%m-%d:%H:%M:%S')
                    db.execute("INSERT INTO purchases (userid, date, symbol, shares, price) VALUES(?, ?, ?, ?, ?);",
                               session["user_id"], f_now, symbol, shares * -1, info["price"])

                    return redirect("/")

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
