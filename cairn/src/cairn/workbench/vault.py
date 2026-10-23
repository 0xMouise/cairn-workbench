import json
from pathlib import Path
from cryptography.fernet import Fernet


class Vault:
    def __init__(self, root: Path):
        path = root / "identity-key"
        if not path.exists():
            # Exclusive creation avoids replacing a key while another process starts.
            try:
                with path.open("xb") as handle:
                    handle.write(Fernet.generate_key())
                path.chmod(0o600)
            except FileExistsError:
                pass
        self.cipher = Fernet(path.read_bytes())

    def encrypt(self, headers):
        return self.cipher.encrypt(json.dumps(headers).encode()).decode()

    def decrypt(self, value):
        return json.loads(self.cipher.decrypt(value.encode()))
