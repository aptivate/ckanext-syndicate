import cgi

from six import StringIO

test_file = StringIO()
test_file.name = "test_file.txt"
test_file.write("test")


class UploadLocalFileStorage(cgi.FieldStorage):
    def __init__(self, fp, *args, **kwargs):
        self.name = fp.name
        self.filename = fp.name
        self.file = fp


test_upload_file = UploadLocalFileStorage(test_file)


def _get_context(context):
    from ckan import model

    return {
        "model": context.get("model", model),
        "session": context.get("session", model.Session),
        "user": context.get("user"),
        "ignore_auth": context.get("ignore_auth", False),
    }
