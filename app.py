import os

from bson import ObjectId
from pymongo import MongoClient
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# MongoDB connection
uri = "mongodb+srv://aryanpatel0705:8RjhJ29drFuP0NSs@financedb.stlcwww.mongodb.net/?retryWrites=true&w=majority&appName=financedb"
client = MongoClient(uri)
db = client.get_database('financedb')

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


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
    user_id = ObjectId(session["user_id"])

    # Retrieve user's cash balance
    user = db.users.find_one({"_id": user_id})
    cash = user.get("cash")

    # Aggregate purchases to get stocks summary
    pipeline = [
    {"$match": {"userid": user_id}},
    {"$addFields": {"shares": {"$toInt": "$shares"}}}, 
    {"$group": {
        "_id": "$symbol",
        "total_shares": {"$sum": "$shares"}
    }}
    ]

    # Execute aggregation pipeline
    stocks = list(db.purchases.aggregate(pipeline))

    # Calculate grand total including cash and stock holdings
    grand_total = cash
    userinfo = []

    for stock in stocks:
        symbol = stock["_id"]
        shares = stock["total_shares"]
        price = lookup(symbol)["price"]  # Assuming lookup function retrieves current price
        holding = shares * price
        grand_total += holding
        if shares > 0:  # Only include stocks with non-zero shares
            
            userinfo.append([symbol, shares, price, holding])

    return render_template("index.html", userinfo=userinfo, cash=cash, grand_total=grand_total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":
        
        user = db.users.find_one({"_id": ObjectId(session["user_id"])})

        ticker = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        if not ticker or len(ticker) > 5:
            flash(f"Please enter a correct ticker code")
            return render_template("buy.html")
            #return apology("Please enter a correct ticker code")

        if not shares or not shares.isdigit() or int(shares) <= 0:
            flash(f"Please enter a correct amount of shares to purchase")
            return render_template("buy.html")
            #return apology("Please enter a correct amount of shares to purchase")

        info = lookup(ticker)
        if info is None:
            flash(f"Please enter a correct stock symbol")
            return render_template("buy.html")
            #return apology("Please enter a correct stock symbol")

        price = info["price"]
        total_cost = int(shares) * price
        cash = user.get("cash")

        if cash < total_cost:
            flash(f"Do not have enough cash to buy enough shares")
            return render_template("buy.html")
            #return apology("Do not have enough cash to buy enough shares")

        new_cash = cash - total_cost
        db.users.update_one({"_id": ObjectId(session["user_id"])}, {"$set": {"cash": new_cash}})

        now = datetime.now()
        f_now = now.strftime('%Y-%m-%d:%H:%M:%S')
        obj_user_id = ObjectId(session["user_id"])

        db.purchases.insert_one({"userid": obj_user_id, "date": f_now, "symbol": ticker, "shares": shares, "price": price})
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
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Retrieve user from MongoDB
        user = db.users.find_one({"_id": ObjectId(session["user_id"])})

        if not user or not check_password_hash(user["hash"], old_password):
            flash("Incorrect password")
            return render_template("change-password.html")

        if new_password != confirm_password:
            flash("Passwords do not match")
            return render_template("change-password.html")

        # Update password hash in MongoDB
        new_hashed_password = generate_password_hash(new_password)
        db.users.update_one({"_id": user["_id"]}, {"$set": {"hash": new_hashed_password}})

        flash("Password changed successfully")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = list(db.purchases.find({"userid": ObjectId(session["user_id"])}, {"_id": 0, "symbol": 1, "shares": 1, "price": 1, "date": 1}))
    userinfo = []
    for i in range(len(stocks)):
        symbol = stocks[i]["symbol"]
        shares = int(stocks[i]["shares"])
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
        username = request.form.get("username")
        password = request.form.get("password")
        # Ensure username was submitted
        if not request.form.get("username"):
            flash(f"Please type in a username")
            return render_template("login.html")
            #return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash(f"Please type in a password")
            return render_template("login.html")
            #return apology("must provide password", 403)

        # Query user from MongoDB
        user = db.users.find_one({"username": username})

        # Ensure username exists and password is correct
        if not user or not check_password_hash(user["hash"], password):
            flash("Invalid username and/or password")
            return render_template("login.html")
            #return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = str(user["_id"])

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
            flash(f"Please enter a correct ticker code")
            return render_template("quote.html")
            #return apology("Please enter a correct ticker code", 400)

        return render_template("quoted.html", info=info)


@app.route("/register", methods=["GET", "POST"])
def register():
    # Clear the session
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Default cash gained when signing up
        default_cash = 10000

        # Ensure username was submitted
        if not request.form.get("username"):
            flash(f"must provide username")
            return render_template("register.html")
            #return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            flash(f"must provide password")
            return render_template("register.html")
            #return apology("must provide password", 400)
        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            flash(f"must provide confirmation")
            return render_template("register.html")
            #return apology("must provide confirmation", 400)
        # Ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            flash(f"passwords do not match")
            return render_template("register.html")
            #return apology("passwords do not match", 400)

        # Check if username already exists
        if db.users.find_one({"username": username}):
            flash("Username already exists")
            return render_template("register.html")

        # Insert new user into MongoDB
        hashed_password = generate_password_hash(password)
        db.users.insert_one({"username": username, "hash": hashed_password, "cash": default_cash})

        # Retrieve the newly created user from MongoDB
        user = db.users.find_one({"username": username})

        # Store the user ID in the session
        session["user_id"] = str(user["_id"])

        # Redirect to the homepage
        return redirect("/")

    # If the request method is GET, render the registration form
    if request.method == "GET":
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    user_id = ObjectId(session["user_id"])

    pipeline = [
    {"$match": {"userid": user_id}},  # Match documents for the specific user
    {"$addFields": {"shares": {"$toInt": "$shares"}}},  # Convert shares to integer if they are stored as strings
    {"$group": {
        "_id": "$symbol",
        "total_shares": {"$sum": "$shares"}
    }},
    {"$match": {"total_shares": {"$gt": 0}}},  # Filter out groups with total_shares <= 0
    {"$project": {  # Rename _id to symbol
        "_id": 0,
        "symbol": "$_id",
        "total_shares": 1
    }}
    ]


    stocks = list(db.purchases.aggregate(pipeline))
    print(stocks)

    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)

    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))

        if not symbol or not shares:
            flash(f"Fill in all requirments")
            return render_template("sell.html", stocks=stocks)
            #return apology("Fill in all requirments")

        if int(shares) <= 0:
            flash(f"Please enter a correct amount of shares")
            return render_template("sell.html", stocks=stocks)
            #return apology("Please enter a correct amount of shares")

        shares = int(shares)

        for stock in stocks:
            if stock["symbol"] == symbol:
                if stock["total_shares"] < shares:
                    flash(f"not enough shares")
                    return render_template("sell.html", stocks=stocks)
                    #return apology("not enough shares")
                else:
                    info = lookup(symbol)
                    if info is None:
                        flash(f"Please enter a correct symbol")
                        return render_template("sell.html", stocks=stocks)
                        #return apology("Please enter a correct symbol")
                    price = info["price"]
                    total_sale = price * shares
                    new_cash = total_sale + db.users.find_one({"_id": ObjectId(session["user_id"])}).get("cash")

                    db.users.update_one({"_id": ObjectId(session["user_id"])}, {"$set": {"cash": new_cash}})

                    now = datetime.now()
                    f_now = now.strftime('%Y-%m-%d:%H:%M:%S')

                    obj_user_id = ObjectId(session["user_id"])

                    db.purchases.insert_one({"userid": obj_user_id, "date": f_now, "symbol": symbol, "shares": shares * -1, "price": price})

                    return redirect("/")

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
