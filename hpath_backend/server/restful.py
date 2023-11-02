"""The simulation server.

REST API
--------

..
  #pylint: disable=line-too-long

+---------------------------------------+-----------------+------------------------------------------------------+
| **Endpoint**                          | **HTTP Method** | **Python function signature**                        |
+=======================================+=================+======================================================+
| ``/``                                 | GET             | :py:func:`~hpath.restful.server.hello_world()`       |
+                                       +-----------------+------------------------------------------------------+
|                                       | DELETE          | :py:func:`~hpath.restful.server.reset()`             |
+---------------------------------------+-----------------+------------------------------------------------------+
| ``/scenarios/``                       | POST            | :py:func:`~hpath.restful.server.new_scenario_rest`   |
|                                       +-----------------+------------------------------------------------------+
|                                       | GET             | :py:func:`~hpath.restful.server.list_scenarios_rest` |
+---------------------------------------+-----------------+------------------------------------------------------+
| ``/scenarios/<scenario_id>/status/``  | GET             | :py:func:`~hpath.restful.server.status_rest`         |
+---------------------------------------+-----------------+------------------------------------------------------+
| ``/scenarios/<scenario_id>/results/`` | GET             | :py:func:`~hpath.restful.server.results_rest`        |
+---------------------------------------+-----------------+------------------------------------------------------+
| ``/multi/``                           | POST            | :py:func:`~hpath.restful.server.new_multi_rest`      |
|                                       +-----------------+------------------------------------------------------+
|                                       | GET             | :py:func:`~hpath.restful.server.list_multis_rest`    |
+---------------------------------------+-----------------+------------------------------------------------------+
| ``/multi/<analysis_id>/status/``      | GET             | :py:func:`~hpath.restful.server.status_multi_rest`   |
+---------------------------------------+-----------------+------------------------------------------------------+
| ``/multi/<analysis_id>/results/``     | GET             | :py:func:`~hpath.restful.server.results_multi_rest`  |
+---------------------------------------+-----------------+------------------------------------------------------+

..
  #pylint: enable=line-too-long
"""

import json
from http import HTTPStatus

import flask
from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException

from conf import PORT
from .. import db

app = Flask(__name__)


@app.errorhandler(HTTPException)
def handle_exception(exc: HTTPException):
    """Return JSON instead of HTML (the default) for HTTP errors."""
    # start with the correct headers and status code from the error
    response = exc.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": exc.code,
        "name": exc.name,
        "description": exc.description,
    }, separators=(',', ':'))
    response.content_type = "application/json"
    return response


@app.route('/')
def hello_world() -> Response:
    """Return a simple HTML message, unless the request body is 'PING' (returns 'PONG' instead.)"""
    if request.get_data(as_text=True) == 'PING':
        return Response('PONG', status=HTTPStatus.OK, mimetype='text/plain')
    return Response("<h1>Hello World!</h1>", status=HTTPStatus.OK)


@app.route('/submit/', methods=['POST'])
def new_scenario_rest() -> Response:
    """Process POST request for creating a new scenario or multi-scenario analysis."""
    configs = request.form.configs
    params = request.form.params
    db.submit_scenarios(configs, params)
    return Response(None, status=HTTPStatus.OK)


@app.route('/scenarios/')
def list_scenarios_rest() -> Response:
    """Return a dict of scenarios on the server. Used to populate a Dash AG Grid."""
    scenarios = db.list_scenarios()
    return flask.jsonify(scenarios)


# TODO remaining endpoints


if __name__ == '__main__':
    db.init()
    app.run(host='0.0.0.0', port=PORT, debug=True)
