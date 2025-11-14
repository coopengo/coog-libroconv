import os
import sys
import time
import tempfile
import shutil
from pathlib import Path
from subprocess import check_call, CalledProcessError, TimeoutExpired, DEVNULL
from flask import Flask, request, abort
from flask.helpers import make_response
from flask_restful import Resource, Api
from werkzeug.utils import secure_filename

app = Flask(__name__)
api = Api(app)

max_try = os.environ.get("MAX_RETRY", 10)
libreoffice_timeout = os.environ.get("LIBRE_OFFICE_TIMEOUT", 60 * 3)


def validate_namespace(namespace):
    # Check namespace integrity

    namespace = secure_filename(namespace)

    if (
        not namespace
        or ".." in namespace
        or "/" in namespace
        or "\\" in namespace
    ):
        abort(400, description="Invalid namespace")
    return namespace


def create_temp_dir(namespace=None):
    if namespace:
        namespace = validate_namespace(namespace)
        namespace_base = Path("/tmp/") / f"{namespace}"
        namespace_base.mkdir(parents=True, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(prefix="convert_", dir=namespace_base)
    else:
        tmp_dir = tempfile.mkdtemp(prefix="libre")

    return tmp_dir


def call_libreoffice(output_format, out_dir, path, options):
    cmd = ["soffice"] + [
        "--headless",
        "--safe-mode",
        "--nolockcheck",
        "--nodefault",
        "--norestore",
        "--convert-to",
        output_format,
        "--outdir",
        out_dir,
        path,
    ]
    if output_format == "csv":
        separator = options.get("csv_separator", ",")
        ascii_value = str(ord(separator))
        cmd += [
            f'--infilter="Text - txt - csv (StarCalc):{ascii_value},34,76,"'
        ]

    # SECURITY: please never add shell=True to check_call
    check_call(cmd, timeout=libreoffice_timeout)


def convert(output_format, out_dir, path, options):
    in_stem = path.stem
    output_file_path = Path(out_dir) / (in_stem + "." + output_format)
    try_count = 0

    try:
        while try_count < max_try:
            try_count += 1
            try:
                call_libreoffice(output_format, out_dir, path, options)
            except (CalledProcessError, TimeoutExpired) as e:
                print(e, file=sys.stderr)
            if output_file_path.exists():
                # yes, libreoffice can return 0 as exit code
                # and the file still be absent
                converted_data = output_file_path.open("rb").read()
                return converted_data
            else:
                message = (
                    f"Libreoffice was successfully called, but no converted file was found"
                    f" [try number {try_count}]"
                )
                print(message, file=sys.stderr)

            time.sleep(0.1)

        abort(400, description=f"Tried {try_count} times. Aborting")
    finally:
        if Path(out_dir).exists():
            shutil.rmtree(out_dir)


class Converter(Resource):
    """Convertisseur sans namespace (comportement original)"""

    def post(self, output_format):
        return self._convert_file(output_format, namespace=None)

    def _convert_file(self, output_format, namespace=None):
        file_ = request.files["file"]
        options = request.form
        tmp_dir = create_temp_dir(namespace)
        try:
            in_path = tmp_dir / Path(file_.filename)
            file_.save(str(in_path))
            converted_data = convert(output_format, tmp_dir, in_path, options)
            response = make_response(converted_data)
            response.headers["Content-Type"] = "application/octet-stream"
            response.headers["Content-Disposition"] = (
                f"inline; filename=converted.{output_format}"
            )
            return response

        except Exception:
            if Path(tmp_dir).exists():
                shutil.rmtree(tmp_dir)
            raise


class NamespacedConverter(Converter):
    def post(self, output_format, namespace):
        return self._convert_file(output_format, namespace=namespace)


@app.route("/liveness")
def liveness():
    tmp_dir = create_temp_dir()
    try:
        in_path = Path("/app/tests/test_liveness.odt")
        if not in_path.exists():
            abort(500, description="Fichier de test manquant")
        convert("pdf", tmp_dir, in_path, {})
        return "ok"
    except Exception as e:
        return f"error: {str(e)}", 500
    finally:
        if Path(tmp_dir).exists():
            shutil.rmtree(tmp_dir)


api.add_resource(Converter, "/unoconv/<string:output_format>/")
api.add_resource(
    NamespacedConverter, "/unoconv/<string:output_format>/<string:namespace>/"
)
