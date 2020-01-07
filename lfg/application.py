import os
import re

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import datetime_convert, login_required, time_convert

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///lfg.db")


@app.route("/")
@login_required
def index():
    """Show user's inbox"""

    # Query database for user's messages
    messages = db.execute("SELECT mess_id, from_user, subject, read, sent FROM messages WHERE to_user = (SELECT username FROM users WHERE id = :id) AND to_del = 0",
                          id=session["user_id"])

    # Convert time sent to a more readable format
    for message in messages:
        message['sent'] = datetime_convert(message['sent'])

    return render_template("inbox.html", messages=messages)


@app.route("/browse")
@login_required
def browse():
    """Show all joinable campaigns"""

    # https://stackoverflow.com/questions/10562915/selecting-rows-with-id-from-another-table
    # Query database for joinable campaigns
    campaigns = db.execute("SELECT camp_id, camp_name, setting, players, max, freq, day, time, zone FROM campaigns WHERE players < max AND dm != :id AND camp_id NOT IN (SELECT camp_id FROM characters WHERE id = :id AND camp_id IS NOT NULL)",
                           id=session["user_id"])

    return render_template("browse.html", campaigns=campaigns)


@app.route("/camp", methods=["GET"])
@login_required
def camp():
    """Show selected campaign"""

    # Query database for selected campaign
    camp = db.execute("SELECT camp_id, dm, username, camp_name, setting, players, max, freq, day, time, zone, details FROM campaigns INNER JOIN users ON campaigns.dm = users.id WHERE camp_id = :camp_id",
                      camp_id=request.args.get("camp_id"))

    # If SELECT fails, return error
    if not camp:
        return render_template("error.html", code='500', message=['Could not find campaign.'])

    # Query database for all characters that have joined this campaign
    chars = db.execute("SELECT char_id, id, char_name, bg, char_lvl, class_lvl, char_class, archetype, multi, race, subrace FROM characters WHERE camp_id = :camp_id",
                       camp_id=camp[0]['camp_id'])

    # Convert multiclass to a more readable format
    for char in chars:
        if char['multi'] == 0:
            char['multi'] = 'No'
        else:
            char['multi'] = 'Yes'

    # Set player status
    player = False
    for char in chars:
        if session["user_id"] == char["id"]:
            player = True
            break
        else:
            player = False

    # Show leave button if user is a player
    if player == True:
        show_player = True
    else:
        show_player = False

    # Show delete, edit, & remove player buttons & hide message link if user is the dm
    if session["user_id"] == camp[0]["dm"]:
        show_dm = True
    else:
        show_dm = False

    return render_template("camp.html", name=camp[0]["camp_name"], camp=camp, chars=chars, show_player=show_player, show_dm=show_dm)


@app.route("/campaigns")
@login_required
def campaigns():
    """Show user's campaigns"""

    # https://stackoverflow.com/questions/10562915/selecting-rows-with-id-from-another-table
    # Query database for campaigns where user is a player
    char_camps = db.execute("SELECT camp_id, username, camp_name, setting, players, max, freq, day, time, zone FROM campaigns INNER JOIN users ON campaigns.dm = users.id WHERE camp_id IN (SELECT camp_id FROM characters WHERE id = :id AND camp_id IS NOT NULL)",
                            id=session["user_id"])

    # Query database for campaigns where user is the dm
    campaigns = db.execute("SELECT camp_id, camp_name, setting, players, max, freq, day, time, zone FROM campaigns WHERE dm = :dm",
                           dm=session["user_id"])

    return render_template("campaigns.html", char_camps=char_camps, campaigns=campaigns)


@app.route("/camp_edit", methods=["GET"])
@login_required
def get_camp_edit():
    """Allow editing of selected campaign"""

    # Query database for selected campaign
    camp = db.execute("SELECT camp_id, dm, camp_name, setting, players, max, freq, day, time, zone, details FROM campaigns WHERE camp_id = :camp_id",
                      camp_id=request.args.get("camp_id"))

    # If SELECT fails, return error
    if not camp:
        return render_template("error.html", code='500', message=['Could not find campaign.'])

    # Only show campaign editor if user is the dm
    if not session["user_id"] == camp[0]["dm"]:
        return render_template("error.html", code='403', message=['Unauthorized campaign access.'])

    return render_template("camp_edit.html", name=camp[0]["camp_name"], camp=camp)


@app.route("/camp_edit", methods=["POST"])
@login_required
def post_camp_edit():
    """Submit edits to selected campaign"""

    # Inialize error checking
    errors = []

    # Server validation for setting text field
    if not request.form.get("setting"):
        errors.append("Please provide a setting / adventure.")

    # Ensure a positive whole number was provided for player count
    digit_max = request.form.get("max").isdigit()

    if digit_max == False:
        errors.append("Player count must be a number between 1 & 20.")
    else:
        max_players = int(request.form.get("max"))

        # Ensure character level doesn't exceed 20
        if max_players < 1 or max_players > 20:
            errors.append("Player count must be a number between 1 & 20.")

    # Server validation for correct time format
    if request.form.get("time"):
        full = re.fullmatch(r"(^[01]\d\:[0-5]\d [AP]M)", request.form.get("time"))
        if full == None:
            errors.append("Time format: 00:00 AM/PM.")
        else:
            if not full == None:
                time = request.form.get("time")

    else:
        time = 'TBD'

    # Server validation for correct time zone format
    if request.form.get("zone"):
        if not re.fullmatch(r"(^[a-zA-Z]{2,5})", request.form.get("zone")):
            errors.append("Please provide a time zone.")
        else:
            zone = request.form.get("zone").upper()

    else:
        errors.append("Please provide a time zone.")

    # If errors exist, render error template
    if not errors == []:
        code = '400'
        return render_template("error.html", code=code, message=errors)

    else:
        camp_id = request.form.get("update")

        # UPDATE selected character
        new_camp = db.execute("UPDATE campaigns SET setting = :setting, max = :max, freq = :freq, day = :day, time = :time, zone = :zone, details = :details WHERE camp_id = :camp_id AND dm = :dm",
                              setting=request.form.get("setting"), max=request.form.get("max"), freq=request.form.get("freq"), day=request.form.get("day"),
                              time=time, zone=zone, details=request.form.get("details"), camp_id=camp_id, dm=session["user_id"])

        # If UPDATE fails, return error
        if not new_camp:
            return render_template("error.html", code='500', message=['Could not update campaign.'])

        # Show success message & redirect to main character page
        flash('Your campaign has been successfully updated!', category='info')

        # https://stackoverflow.com/questions/17057191/redirect-while-passing-arguments
        return redirect(url_for(".camp", camp_id=camp_id))


@app.route("/camp_gen", methods=["GET"])
@login_required
def get_camp_gen():
    """Check user's campaign limit before rendering campaign creator"""

    # Query database for user's character limit
    number = db.execute("SELECT camp_limit FROM users WHERE id = :id",
                        id=session["user_id"])

    camp_limit = int(number[0]['camp_limit'])

    # Show error message if limit has been reached
    if camp_limit <= 0:
        flash('Your campaign limit has been reached.\nYou must delete a campaign before you can make a new one.', category='error')
        return redirect("/campaigns")

    else:
        return render_template("camp_gen.html")


@app.route("/camp_gen", methods=["POST"])
@login_required
def post_camp_gen():
    """Submit form for campaign creation"""

    # Inialize error checking
    errors = []

    # Server validation for campaign name text field
    if not request.form.get("camp_name"):
        errors.append("Please provide a campaign name.")

    # Server validation for setting text field
    if not request.form.get("setting"):
        errors.append("Please provide a setting / adventure.")

    # Server validation for correct time format
    if request.form.get("time"):
        full = re.fullmatch(r"(^[01]\d\:[0-5]\d [AP]M)", request.form.get("time"))
        military = re.fullmatch(r"(^[012]\d\:[0-5]\d)", request.form.get("time"))
        if full == None and military == None:
            errors.append("Time format: 00:00 AM/PM.")
        else:
            if not full == None:
                time = request.form.get("time")
            elif not military == None:
                time = time_convert(request.form.get("time"))

    else:
        time = 'TBD'

    # Server validation for correct time zone format
    if request.form.get("zone"):
        if not re.fullmatch(r"(^[a-zA-Z]{2,5})", request.form.get("zone")):
            errors.append("Please provide a time zone.")
        else:
            zone = request.form.get("zone").upper()

    else:
        errors.append("Please provide a time zone.")

    # Ensure a positive whole number was provided for player count
    digit_max = request.form.get("max").isdigit()

    if digit_max == False:
        errors.append("Player count must be a number between 1 & 20.")
    else:
        max_players = int(request.form.get("max"))

        # Ensure character level doesn't exceed 20
        if max_players < 1 or max_players > 20:
            errors.append("Player count must be a number between 1 & 20.")

    # If errors exist, render error template
    if not errors == []:
        code = '400'
        return render_template("error.html", code=code, message=errors)

    else:
        # UPDATE user's campaign limit
        camp_limit = db.execute("UPDATE users SET camp_limit = camp_limit - 1 WHERE id = :id AND camp_limit > 0",
                                id=session["user_id"])

        # If UPDATE fails, return error
        if not camp_limit:
            flash('Your campaign limit has been reached.\nYou must delete a campaign before you can make a new one.', category='error')

        else:
            # INSERT campaign into DB
            camp = db.execute("INSERT INTO campaigns (dm, camp_name, setting, max, freq, day, time, zone, details) VALUES (:dm, :camp_name, :setting, :max, :freq, :day, :time, :zone, :details)",
                              dm=session["user_id"], camp_name=request.form.get("camp_name"), setting=request.form.get("setting"), max=max_players, freq=request.form.get("freq"),
                              day=request.form.get("day"), time=time, zone=zone, details=request.form.get("details"))

            # Show success or error message
            if not camp:
                return render_template("error.html", code='500', message=['Could not create campaign.'])
            else:
                flash('Your campaign has been successfully created!', category='info')

        return redirect("/campaigns")


@app.route("/char", methods=["GET"])
@login_required
def char():
    """Show selected character"""

    # Query database for selected character
    char = db.execute("SELECT char_id, id, username, camp_id, char_name, bg, char_lvl, class_lvl, char_class, archetype, race, subrace, multi, multi_info, style, weapon, magic_items, notes, bs FROM characters INNER JOIN users USING(id) WHERE char_id = :char_id",
                      char_id=request.args.get("char_id"))

    # If SELECT fails, return error
    if not char:
        return render_template("error.html", code='500', message=['Could not find character.'])

    if char[0]["camp_id"] == None:
        camp = None
        dm = False
        show_remove = False

    else:
        # Query database for campaign name if character has joined a campaign
        camp = db.execute("SELECT dm, camp_name FROM campaigns WHERE camp_id = :camp_id",
                          camp_id=char[0]['camp_id'])

        # If SELECT fails, show error message
        if not camp:
            flash("Could not find character's campaign.", category='error')

        else:
            # Set dm status
            if session["user_id"] == camp[0]["dm"]:
                dm = True
                show_remove = True
            else:
                dm = False
                show_remove = False

    # Show backstory if user owns character or is the character's dm
    if session["user_id"] == char[0]["id"] or dm == True:
        show_bs = True
    else:
        show_bs = False

    # Show edit button & hide message link if user owns character
    if session["user_id"] == char[0]["id"]:
        show_me = True
    else:
        show_me = False

    return render_template("char.html", name=char[0]["char_name"], char=char, camp=camp, show_remove=show_remove, show_bs=show_bs, show_me=show_me)


@app.route("/characters")
@login_required
def characters():
    """Show user's characters"""

    # Query database for user's characters
    characters = db.execute("SELECT char_id, char_name, bg, char_lvl, class_lvl, char_class, archetype, multi, race, subrace FROM characters WHERE id = :id",
                            id=session["user_id"])

    # Convert multiclass to a more readable format
    for char in characters:
        if char['multi'] == 0:
            char['multi'] = 'No'
        else:
            char['multi'] = 'Yes'

    return render_template("characters.html", characters=characters)


@app.route("/char_edit", methods=["GET"])
@login_required
def get_char_edit():
    """Allow editing of selected character"""

    # Query database for selected character
    char = db.execute("SELECT char_id, id, camp_id, char_name, bg, char_lvl, class_lvl, char_class, archetype, race, subrace, multi, multi_info, style, weapon, magic_items, notes, bs FROM characters WHERE char_id = :char_id",
                      char_id=request.args.get("char_id"))

    # If SELECT fails, return error
    if not char:
        return render_template("error.html", code='500', message=['Could not find character.'])

    # Only show character editor if user owns character
    if not session["user_id"] == char[0]["id"]:
        return render_template("error.html", code='403', message=['Unauthorized character access.'])

    # Set campaign to "None" if character has not joined one
    if char[0]["camp_id"] == None:
        camp = None

    else:
        # Query database for campaign name if character has joined a campaign
        camp = db.execute("SELECT camp_name FROM campaigns WHERE camp_id = :camp_id",
                          camp_id=char[0]['camp_id'])

        # If SELECT fails, show error message
        if not camp:
            flash("Could not find character's campaign.", category='error')

    return render_template("char_edit.html", name=char[0]["char_name"], char=char, camp=camp)


@app.route("/char_edit", methods=["POST"])
@login_required
def post_char_edit():
    """Submit edits to selected character"""

    # Inialize error checking
    errors = []

    # Server validation for class text field
    if not request.form.get("char_class"):
        errors.append("Please provide a class.")

    # Ensure a positive whole number was provided for character level
    digit_char = request.form.get("char_lvl").isdigit()

    if digit_char == False:
        errors.append("Character level must be a number between 1 & 20.")
    else:
        char_lvl = int(request.form.get("char_lvl"))

        # Ensure character level doesn't exceed 20
        if char_lvl < 1 or char_lvl > 20:
            errors.append("Character level must be a number between 1 & 20.")

    # Ensure a positive whole number was provided for class level
    digit_class = request.form.get("class_lvl").isdigit()

    if digit_class == False:
        errors.append("Class level must be a number between 1 & 20.")
    else:
        class_lvl = int(request.form.get("class_lvl"))

        # Ensure that class level doesn't exceed character level
        if class_lvl < 1 or class_lvl > char_lvl:
            errors.append("Class level must not exceed character level.")

    # If errors exist, render error template
    if not errors == []:
        code = '400'
        return render_template("error.html", code=code, message=errors)

    else:
        char_id = request.form.get("update")

        # UPDATE selected character
        new_char = db.execute("UPDATE characters SET char_lvl = :char_lvl, class_lvl = :class_lvl, char_class = :char_class, archetype = :archetype, multi = :multi, multi_info = :multi_info, style = :style, weapon = :weapon, magic_items = :magic_items, notes = :notes, bs = :bs WHERE char_id = :char_id AND id = :id",
                              char_lvl=request.form.get("char_lvl"), class_lvl=request.form.get("class_lvl"), char_class=request.form.get("char_class"), archetype=request.form.get("archetype"),
                              multi=request.form.get("multi"), multi_info=request.form.get("multi_info"), style=request.form.get("style"), weapon=request.form.get("weapon"),
                              magic_items=request.form.get("magic_items"), notes=request.form.get("notes"), bs=request.form.get("bs"), char_id=char_id, id=session["user_id"])

        # If UPDATE fails, return error
        if not new_char:
            return render_template("error.html", code='500', message=['Could not update character.'])

        # Show success message & redirect to main character page
        flash('Your character has been successfully updated!', category='info')

        # https://stackoverflow.com/questions/17057191/redirect-while-passing-arguments
        return redirect(url_for(".char", char_id=char_id))


@app.route("/char_gen", methods=["GET"])
@login_required
def get_char_gen():
    """Check user's character limit before rendering character creator"""

    # Query database for user's character limit
    number = db.execute("SELECT char_limit FROM users WHERE id = :id",
                        id=session["user_id"])

    char_limit = int(number[0]['char_limit'])

    # Show error message if limit has been reached
    if char_limit <= 0:
        flash('Your character limit has been reached.\nYou must delete a character before you can make a new one.', category='error')
        return redirect("/characters")

    else:
        return render_template("char_gen.html")


@app.route("/char_gen", methods=["POST"])
@login_required
def post_char_gen():
    """Submit form for character creation"""

    # Inialize error checking
    errors = []

    # Server validation for character name text field
    if not request.form.get("char_name"):
        errors.append("Please provide a character name.")

    # Server validation for background text field
    if not request.form.get("bg"):
        errors.append("Please provide a background.")

    # Ensure a positive whole number was provided for character level
    digit_char = request.form.get("char_lvl").isdigit()

    if digit_char == False:
        errors.append("Character level must be a number between 1 & 20.")
    else:
        char_lvl = int(request.form.get("char_lvl"))

        # Ensure character level doesn't exceed 20
        if char_lvl < 1 or char_lvl > 20:
            errors.append("Character level must be a number between 1 & 20.")

    # Ensure a positive whole number was provided for class level
    digit_class = request.form.get("class_lvl").isdigit()

    if digit_class == False:
        errors.append("Class level must be a number between 1 & 20.")
    else:
        class_lvl = int(request.form.get("class_lvl"))

        # Ensure that class level doesn't exceed character level
        if class_lvl < 1 or class_lvl > char_lvl:
            errors.append("Class level must not exceed character level.")

    # Server validation for class selection
    if request.form.get("class") == "class_select":
        if not request.form.get("class_select"):
            errors.append("Please choose a class.")
        else:
            char_class = request.form.get("class_select")
    elif request.form.get("class") == "class_other":
        if not request.form.get("class_other"):
            errors.append("Please provide a class.")
        else:
            char_class = request.form.get("class_other")
    else:
        errors.append("Invalid class selection.")

    # Server validation for race selection
    if request.form.get("race") == "race_select":
        if not request.form.get("race_select"):
            errors.append("Please choose a race.")
        else:
            race = request.form.get("race_select")
    elif request.form.get("race") == "race_other":
        if not request.form.get("race_other"):
            errors.append("Please provide a race.")
        else:
            race = request.form.get("race_other")
    else:
        errors.append("Invalid race selection.")

    # Server validation for fighting style select menu
    if not request.form.get("style"):
        errors.append("Please choose a fighting style.")

    # Server validation for primary weapon select menu
    if not request.form.get("weapon"):
        errors.append("Please choose a primary weapon.")

    # If errors exist, render error template
    if not errors == []:
        code = '400'
        return render_template("error.html", code=code, message=errors)

    else:
        # UPDATE user's character limit
        char_limit = db.execute("UPDATE users SET char_limit = char_limit - 1 WHERE id = :id AND char_limit > 0",
                                id=session["user_id"])

        # If UPDATE fails, return error
        if not char_limit:
            flash('Your character limit has been reached.\nYou must delete a character before you can make a new one.', category='error')

        else:
            # INSERT character into DB
            char = db.execute("INSERT INTO characters (id, char_name, bg, char_lvl, class_lvl, char_class, archetype, race, subrace, multi, style, weapon) VALUES (:id, :char_name, :bg, :char_lvl, :class_lvl, :char_class, :archetype, :race, :subrace, :multi, :style, :weapon)",
                              id=session["user_id"], char_name=request.form.get("char_name"), bg=request.form.get("bg"), char_lvl=char_lvl, class_lvl=class_lvl, char_class=char_class, archetype=request.form.get("archetype"),
                              race=race, subrace=request.form.get("subrace"), multi=request.form.get("multi"), style=request.form.get("style"), weapon=request.form.get("weapon"))

            # Show success or error message
            if not char:
                return render_template("error.html", code='500', message=['Could not create character.'])
            else:
                flash('Your character has been successfully created!', category='info')

        return redirect("/characters")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    valid_name = False
    username = request.args.get("username")

    # If no username is provided return false
    if len(username) < 1:
        valid_name = False

    else:
        # Query database for username
        rows = db.execute("SELECT username FROM users WHERE username = :username",
                          username=username)

        # If username exists return false, else true
        if len(rows) >= 1:
            valid_name = False
        else:
            valid_name = True

    return jsonify(valid_name)


@app.route("/compose", methods=["GET", "POST"])
@login_required
def compose():
    """Render form for composing messages"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Inialize error checking
        errors = []

        # Ensure username was submitted
        if not request.form.get("to_user"):
            errors.append('Please provide one username.')

        # Ensure subject was submitted
        elif not request.form.get("subject"):
            errors.append('Please provide a subject.')

        # Ensure message was submitted
        elif not request.form.get("message"):
            errors.append('Please provide a message.')

        # If errors exist, render error template
        if not errors == []:
            code = '400'
            return render_template("error.html", code=code, message=errors)

        # Query database for username
        to_user = db.execute("SELECT username FROM users WHERE username = :username",
                             username=request.form.get("to_user"))

        # If SELECT fails, return error
        if not len(to_user) == 1:
            return render_template("error.html", code='400', message=['Invalid username. Please provide only one at a time.'])

        else:
            # Insert new message into database, while querying for current user's username
            new_mess = db.execute("INSERT INTO messages (to_user, from_user, subject, message) VALUES (:to_user, (SELECT username FROM users WHERE id = :id), :subject, :message)",
                                  to_user=request.form.get("to_user"), id=session["user_id"], subject=request.form.get("subject"), message=request.form.get("message"))

            # If INSERT fails, return error
            if not new_mess:
                return render_template("error.html", code='500', message=['Could not send message.'])

            # Show success message & redirect to inbox
            flash('Your message has been sent!', category='info')
            return redirect("/sent")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("compose.html", to_user="", subject="")


@app.route("/delete", methods=["GET"])
@login_required
def delete():
    """Deletes selected message(s)"""

    marked = False
    checked = request.args.getlist("checked[]")

    # If list is empty, show error
    if checked == None:
        marked = False
        flash('No boxes were checked.', category='error')

    else:
        marked = True

        for box in checked:
            mess_id = box

            # Query database for usernames and delete status
            mess = db.execute("SELECT to_user, from_user, to_del, from_del FROM messages WHERE mess_id = :mess_id",
                              mess_id=mess_id)

            # If SELECT fails, return error
            if not mess:
                return render_template("error.html", code='500', message=['Message could not be deleted.'])

            # Query database for current user's username
            user = db.execute("SELECT username FROM users WHERE id = :id",
                              id=session["user_id"])

            # If SELECT fails, return error
            if not user:
                return render_template("error.html", code='403', message=['You are not logged in.'])

            # Only continue if user is the sender or receiver
            if not user[0]["username"] == mess[0]["from_user"] and not user[0]["username"] == mess[0]["to_user"]:
                return render_template("error.html", code='403', message=['Unauthorized message access.'])

            # Update delete status for sender if receiver status is false
            if user[0]["username"] == mess[0]["from_user"] and mess[0]["from_del"] == 0 and mess[0]["to_del"] == 0:
                from_del = db.execute("UPDATE messages SET from_del = :from_del WHERE mess_id = :mess_id",
                                      from_del=True, mess_id=mess_id)

                # If UPDATE fails, return error
                if not from_del:
                    return render_template("error.html", code='500', message=['Message could not be deleted.'])

            # Delete message from database if receiver status is true
            elif user[0]["username"] == mess[0]["from_user"] and mess[0]["from_del"] == 0 and mess[0]["to_del"] == 1:
                delete = db.execute("DELETE FROM messages WHERE mess_id = :mess_id",
                                    mess_id=mess_id)

                # If DELETE fails, return error
                if not delete:
                    return render_template("error.html", code='500', message=['Message could not be deleted.'])

            # Update delete status for receiver if sender status is false
            elif user[0]["username"] == mess[0]["to_user"] and mess[0]["to_del"] == 0 and mess[0]["from_del"] == 0:
                to_del = db.execute("UPDATE messages SET to_del = :to_del WHERE mess_id = :mess_id",
                                    to_del=True, mess_id=mess_id)

                # If UPDATE fails, return error
                if not to_del:
                    return render_template("error.html", code='500', message=['Message could not be deleted.'])

            # Delete message from database if sender status is true
            elif user[0]["username"] == mess[0]["to_user"] and mess[0]["to_del"] == 0 and mess[0]["from_del"] == 1:
                delete = db.execute("DELETE FROM messages WHERE mess_id = :mess_id",
                                    mess_id=mess_id)

                # If DELETE fails, return error
                if not delete:
                    return render_template("error.html", code='500', message=['Message could not be deleted.'])

            else:
                return render_template("error.html", code='400', message=['You have already deleted this message.'])

        # Show success message
        flash('Message has been successfully deleted!', category='info')

    return jsonify(marked)


@app.route("/del_camp", methods=["POST"])
@login_required
def del_camp():
    """Deletes selected campaign"""

    # UPDATE user's campaign limit
    camp_limit = db.execute("UPDATE users SET camp_limit = camp_limit + 1 WHERE id = :id AND char_limit < 10",
                            id=session["user_id"])

    # If UPDATE fails, show error message
    if not camp_limit:
        return render_template("error.html", code='500', message=['Campaign could not be deleted.'])

    else:
        camp_id = request.form.get("delete")

        # Reset camp_id on all characters with the selected campaign's id to NULL
        update = db.execute("UPDATE characters SET camp_id = NULL WHERE camp_id = :camp_id",
                            camp_id=camp_id)

        # DELETE selected campaign from database
        delete = db.execute("DELETE FROM campaigns WHERE camp_id = :camp_id AND dm = :dm",
                            camp_id=camp_id, dm=session["user_id"])

        # If DELETE fails, show error message
        if not delete:
            return render_template("error.html", code='500', message=['Campaign could not be deleted.'])

        # Show success message & redirect to campaigns
        flash('Campaign has been successfully deleted!', category='info')
        return redirect("/campaigns")


@app.route("/del_char", methods=["POST"])
@login_required
def del_char():
    """Deletes selected character"""

    # UPDATE user's character limit
    char_limit = db.execute("UPDATE users SET char_limit = char_limit + 1 WHERE id = :id AND char_limit < 10",
                            id=session["user_id"])

    # If UPDATE fails, show error message
    if not char_limit:
        return render_template("error.html", code='500', message=['Character could not be deleted.'])

    else:
        # DELETE selected character from database
        delete = db.execute("DELETE FROM characters WHERE char_id = :char_id AND id = :id",
                            char_id=request.form.get("delete"), id=session["user_id"])

        # If DELETE fails, show error message
        if not delete:
            return render_template("error.html", code='500', message=['Character could not be deleted.'])

        # Show success message & redirect to campaigns
        flash('Character has been successfully deleted!', category='info')
        return redirect("/characters")


@app.route("/join", methods=["GET"])
@login_required
def get_join():
    """Render form for joining selected campaign"""

    camp_id = request.args.get("camp_id")

    # Query database for user's characters that are not in campaigns
    chars = db.execute("SELECT char_id, char_name FROM characters WHERE id = :id AND camp_id IS NULL",
                       id=session["user_id"])

    # If SELECT fails, show error & redirect to campaign page
    if not chars:
        flash('You have no available characters.', category='error')

        # https://stackoverflow.com/questions/17057191/redirect-while-passing-arguments
        return redirect(url_for(".camp", camp_id=camp_id))

    else:
        return render_template("join.html", camp_id=camp_id, chars=chars)


@app.route("/join", methods=["POST"])
@login_required
def post_join():
    """Join selected campaign"""

    camp_id = request.form.get("join")

    # UPDATE campaign's player count
    update_camp = db.execute("UPDATE campaigns SET players = players + 1 WHERE camp_id = :camp_id AND players < max",
                             camp_id=camp_id)

    # If UPDATE fails, show error
    if not update_camp:
        return render_template("error.html", code='400', message=['Campaign is full, you cannot join.'])

    else:
        # UPDATE user's character limit
        update_char = db.execute("UPDATE characters SET camp_id = :camp_id WHERE char_id = :char_id AND id = :id AND camp_id IS NULL",
                                 camp_id=camp_id, char_id=request.form.get("chars"), id=session["user_id"])

        # Show success or error message
        if not update_char:
            flash('Character could not join the campaign.', category='error')
        else:
            flash('Character has successfully join the campaign!', category='info')

        # https://stackoverflow.com/questions/17057191/redirect-while-passing-arguments
        return redirect(url_for(".camp", camp_id=camp_id))


@app.route("/leave", methods=["POST"])
@login_required
def leave():
    """Leave selected campaign"""

    camp_id = request.form.get("leave")

    # UPDATE campaign's player count
    update_camp = db.execute("UPDATE campaigns SET players = players - 1 WHERE camp_id = :camp_id AND players > 0",
                             camp_id=camp_id)

    # If UPDATE fails, show error
    if not update_camp:
        return render_template("error.html", code='500', message=['Character could not be removed from campaign.'])

    else:
        # Query database for campaign's dm
        dm = db.execute("SELECT dm FROM campaigns WHERE camp_id = :camp_id",
                        camp_id=camp_id)

        # If user is the character's dm, remove character from campaign
        if dm[0]["dm"] == session["user_id"]:
            update_dm = db.execute("UPDATE characters SET camp_id = NULL WHERE camp_id = :camp_id",
                                   camp_id=camp_id)

            # Show success or error message
            if not update_dm:
                return render_template("error.html", code='500', message=['Character could not be removed from campaign.'])
            else:
                flash('Character has been removed from campaign!', category='info')

        # If user owns the character, remove character from campaign
        else:
            update_char = db.execute("UPDATE characters SET camp_id = NULL WHERE camp_id = :camp_id AND id = :id",
                                     camp_id=camp_id, id=session["user_id"])

            # Show success or error message
            if not update_char:
                flash('Character could not be removed from campaign.', category='error')
            else:
                flash('Character has been removed from campaign!', category='info')

        # https://stackoverflow.com/questions/17057191/redirect-while-passing-arguments
        return redirect(url_for(".camp", camp_id=camp_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Inialize error checking
        errors = []

        # Ensure username was submitted
        if not request.form.get("username"):
            errors.append('Please provide a username.')

        # Ensure password was submitted
        elif not request.form.get("password"):
            errors.append('Please provide a password.')

        # If errors exist, render error template
        if not errors == []:
            code = '403'
            return render_template("error.html", code=code, message=errors)

        # Query database for username
        rows = db.execute("SELECT id, username, hash FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if not len(rows) == 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("error.html", code='403', message=['Invalid username and/or password.'])

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


@app.route("/message", methods=["GET"])
@login_required
def message():
    """Show selected message"""

    # Query database for selected message
    mess = db.execute("SELECT mess_id, to_user, from_user, subject, message, read FROM messages WHERE mess_id = :mess_id",
                      mess_id=request.args.get("mess_id"))

    # If SELECT fails, return error
    if not mess:
        return render_template("error.html", code='500', message=['Could not find message.'])

    # Query database for user's username
    user = db.execute("SELECT username FROM users WHERE id = :id",
                      id=session["user_id"])

    # If SELECT fails, return error
    if not user:
        return render_template("error.html", code='403', message=['You are not logged in.'])

    # Only show message if user is the sender or receiver
    if not user[0]["username"] == mess[0]["from_user"] and not user[0]["username"] == mess[0]["to_user"]:
        return render_template("error.html", code='403', message=['Unauthorized message access.'])

    # Hide reply button if user is the sender
    if user[0]["username"] == mess[0]["from_user"]:
        show_reply = False
    else:
        show_reply = True

        # Mark message as read, if seen by reciever for the 1st time
        if mess[0]["read"] == False:
            read = db.execute("UPDATE messages SET read = :read WHERE mess_id = :mess_id",
                              read=True, mess_id=request.args.get("mess_id"))

    return render_template("message.html", mess=mess, show_reply=show_reply)


@app.route("/read", methods=["GET"])
@login_required
def read():
    """Marks selected messages as read"""

    marked = False
    checked = request.args.getlist("checked[]")

    # If list is empty, show error
    if checked == None:
        marked = False
        flash('No boxes were checked.', category='error')

    else:
        marked = True
        btn = request.args.get("btn")

        for box in checked:
            mess_id = box

            # Query database for reciever's username
            mess = db.execute("SELECT to_user, read FROM messages WHERE mess_id = :mess_id",
                              mess_id=mess_id)

            # If SELECT fails, return error
            if not mess:
                return render_template("error.html", code='500', message=['Could not find message.'])

            if btn == 'read':

                # Continue if message read status is false
                if mess[0]["read"] == 0:

                    # Query database for current user's username
                    user = db.execute("SELECT username FROM users WHERE id = :id",
                                      id=session["user_id"])

                    # If SELECT fails, return error
                    if not user:
                        return render_template("error.html", code='403', message=['You are not logged in.'])

                    # Only continue if user is the receiver
                    if not user[0]["username"] == mess[0]["to_user"]:
                        return render_template("error.html", code='403', message=['Unauthorized message access.'])

                    read = db.execute("UPDATE messages SET read = :read WHERE mess_id = :mess_id",
                                      read=True, mess_id=mess_id)

                    # If UPDATE fails, return error
                    if not read:
                        return render_template("error.html", code='500', message=['Could not mark message as read.'])

            elif btn == 'unread':

                # Continue if message read status is true
                if mess[0]["read"] == 1:

                    # Query database for current user's username
                    user = db.execute("SELECT username FROM users WHERE id = :id",
                                      id=session["user_id"])

                    # If SELECT fails, return error
                    if not user:
                        return render_template("error.html", code='403', message=['You are not logged in.'])

                    # Only continue if user is the receiver
                    if not user[0]["username"] == mess[0]["to_user"]:
                        return render_template("error.html", code='403', message=['Unauthorized message access.'])

                    read = db.execute("UPDATE messages SET read = :read WHERE mess_id = :mess_id",
                                      read=False, mess_id=mess_id)

                    # If UPDATE fails, return error
                    if not read:
                        return render_template("error.html", code='500', message=['Could not mark message as unread.'])

        # Show success message
        if btn == 'read':
            flash('Selected messages have been marked as read!', category='info')
        elif btn == 'unread':
            flash('Selected messages have been marked as unread!', category='info')

    return jsonify(marked)


@app.route("/register", methods=["GET", "POST"])
# Modified login
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Inialize error checking
        errors = []

        # Ensure a username was provided
        if not request.form.get("username"):
            errors.append('Please provide username.')

        # Ensure a password was provided
        elif not request.form.get("password"):
            errors.append('Please provide password.')

        # Ensure password was retyped
        elif not request.form.get("confirmation"):
            errors.append('Please retype password.')

        # Ensure retyped password matches original password
        elif not request.form.get("password") == request.form.get("confirmation"):
            errors.append('Passwords do not match')

        # If errors exist, render error template
        if not errors == []:
            code = '400'
            return render_template("error.html", code=code, message=errors)

        # Hash password for security
        password = generate_password_hash(request.form.get("password"))

        # Insert new user into database
        new = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                         username=request.form.get("username"), hash=password)

        # If INSERT fails, return error
        if not new:
            return render_template("error.html", code='400', message=['Username unavailable'])

        # Log in new user
        rows = db.execute("SELECT id FROM users WHERE username = :username",
                          username=request.form.get("username"))

        session["user_id"] = rows[0]["id"]

        # Show success message
        flash('You were successfully registered and logged in!', category='info')

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/reply", methods=["GET"])
@login_required
def reply():
    """Render compose with to & subject filled in"""

    return render_template("compose.html", to_user=request.args.get("to_user"), subject=request.args.get("subject"))


@app.route("/sent")
@login_required
def sent():
    """Show user's sent messages"""

    # Query database for user's sent messages
    sent_messes = db.execute("SELECT mess_id, to_user, subject, sent FROM messages WHERE from_user = (SELECT username FROM users WHERE id = :id) AND from_del = 0",
                             id=session["user_id"])

    # Convert time sent to a more reabable format
    for message in sent_messes:
        message['sent'] = datetime_convert(message['sent'])

    return render_template("sent.html", sent_messes=sent_messes)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return render_template("error.html", code=e.code, message=[e.name])


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
