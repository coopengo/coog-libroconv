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


def call_libreoffice(output_format, out_dir, path, options):
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
            stderr=None if debug else DEVNULL)


def convert(output_format, out_dir, path, options):
    in_stem = path.stem
    output_file_path = Path(out_dir) / (in_stem + '.' + output_format)
    try_count = 0
    while try_count < max_try:
        try_count += 1
        try:
            call_libreoffice(output_format, out_dir, path, options)
        except (CalledProcessError, TimeoutExpired) as e:
            print(e)
        if output_file_path.exists():
            # yes, libreoffice can return 0 as exit code
            # and the file still be absent
            converted_data = output_file_path.open('rb').read()
            shutil.rmtree(out_dir)
            return converted_data
        time.sleep(0.1)
    else:
        abort(400, description=f'Tried {try_count} times. Aborting')


class Converter(Resource):

    def post(self, output_format):
        file_ = request.files['file']
        options = request.form
        tmp_dir = tempfile.mkdtemp(prefix='libre')
        in_path = tmp_dir / Path(file_.filename)
        file_.save(in_path)
        converted_data = convert(output_format, tmp_dir, in_path, options)
        response = make_response(converted_data)
        response.headers['Content-Type'] = "application/octet-stream"
        response.headers['Content-Disposition'] = \
                "inline; filename=converted.%s" % (output_format, )
        return response


@app.route("/liveness")
def liveness():
    tmp_dir = tempfile.mkdtemp(prefix='test')
    in_path = Path('/app/tests/test_liveness.odt')
    convert('pdf', tmp_dir, in_path, {})
    return "ok"


api.add_resource(Converter, '/unoconv/<string:output_format>/')
