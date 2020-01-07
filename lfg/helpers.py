import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps
from time import strftime, strptime


def datetime_convert(timestamp):

    # Converts date timestamps to a more readable format
    time_db = strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    return strftime("%x %I:%M %p", time_db)


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def time_convert(giventime):

    # Converts time to 12 hour format with AM/PM
    gametime = strptime(giventime, "%H:%M")
    return strftime("%I:%M %p", gametime)