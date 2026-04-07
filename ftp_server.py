import os
import logging
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

FTP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ftp_data")
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", "changeme")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("ftp_server")


class LoggingHandler(FTPHandler):
    def on_file_received(self, file):
        logger.info(f"File ricevuto: {file}")

    def on_incomplete_file_received(self, file):
        logger.warning(f"File incompleto rimosso: {file}")
        os.remove(file)


def main():
    os.makedirs(FTP_DIR, exist_ok=True)

    authorizer = DummyAuthorizer()
    authorizer.add_user("webmais", FTP_PASSWORD, FTP_DIR, perm="elradfmw")

    handler = LoggingHandler
    handler.authorizer = authorizer
    handler.passive_ports = range(60000, 60100)

    server = FTPServer(("0.0.0.0", 21), handler)
    logger.info(f"FTP server avviato su porta 21 - directory: {FTP_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()
