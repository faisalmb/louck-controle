import pytest


class FakeKeyring:
    def __init__(self):
        self.data: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.data:
            raise KeyError(username)
        del self.data[(service, username)]


@pytest.fixture
def fake_keyring():
    return FakeKeyring()
