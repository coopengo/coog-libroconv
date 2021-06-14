import os
import time
import tempfile
import shutil
from pathlib import Path
from subprocess import check_call, CalledProcessError, TimeoutExpired, DEVNULL

from flask import Flask, request, abort
from flask.helpers import make_response
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

max_try = os.environ.get('MAX_RETRY', 10)
libreoffice_timeout = os.environ.get('LIBRE_OFFICE_TIMEOUT', 60 * 3)
debug = os.environ.get('DEBUG_LIBREOFFICE', False)


def convert(output_format, out_dir, path, options):
    cmd = ['soffice'] + [
        '--headless',
        '--safe-mode',
        '--nolockcheck',
        '--nodefault',
        '--norestore',
        '--convert-to', output_format,
        '--outdir', out_dir, path]
    if output_format == 'csv':
        separator = options.get('csv_separator', ',')
        ascii_value = str(ord(separator))
        cmd += [
            f'--infilter="Text - txt - csv (StarCalc):{ascii_value},34,76,"']
    check_call(cmd, timeout=libreoffice_timeout,
            stderr=DEVNULL if debug else None)


class Converter(Resource):

    def post(self, output_format):
        file_ = request.files['file']
        options = request.form
        tmp_dir = tempfile.mkdtemp(prefix='libre')
        in_path = tmp_dir / Path(file_.filename)
        in_stem = in_path.stem
        file_.save(in_path)
        output_path = Path(tmp_dir) / (in_stem + '.' + output_format)
        try_count = 0
        while try_count < max_try:
            try_count += 1
            try:
                convert(output_format, tmp_dir, in_path, options)
            except (CalledProcessError, TimeoutExpired) as e:
                print(e)
            if output_path.exists():
                # yes, libreoffice can return 0 as exit code
                # and the file still be absent
                break
            time.sleep(0.1)
        else:
            abort(400, description=f'Tried {try_count} times. Aborting')
        converted_data = output_path.open('rb').read()
        shutil.rmtree(tmp_dir)
        response = make_response(converted_data)
        response.headers['Content-Type'] = "application/octet-stream"
        response.headers['Content-Disposition'] = \
                "inline; filename=converted.%s" % (output_format, )
        return response


@app.route("/liveness")
def liveness():
    # we only check that uwsgi and flask app are alive
    return "ok"


api.add_resource(Converter, '/unoconv/<string:output_format>/')
