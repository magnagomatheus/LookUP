from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

bp = Blueprint('core', __name__)


@bp.route('/', methods=('GET', 'POST'))
def core():

    #sending data
    if (request.method == "POST"):
        # efetuar html da localizacao
        return "Nothing"
    # first access
    else:
        return render_template("core/index.html")
