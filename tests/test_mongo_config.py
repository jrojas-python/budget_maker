import logging

import pytest
from pydantic import ValidationError

import app.database as database_module
from settings.config import Settings, ensure_safe_test_mongo_uri


def test_settings_accept_standard_and_srv_mongo_uris():
    local_settings = Settings(
        _env_file=None,
        mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker?authSource=admin",
        test_mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
    )
    atlas_settings = Settings(
        _env_file=None,
        mongo_uri="mongodb+srv://atlas_user:atlas_password@cluster0.example.mongodb.net/?retryWrites=true&w=majority",
        test_mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
    )

    assert local_settings.mongo_uri.startswith("mongodb://")
    assert atlas_settings.mongo_uri.startswith("mongodb+srv://")
    assert atlas_settings.masked_mongo_uri() == (
        "mongodb+srv://atlas_user:******@cluster0.example.mongodb.net/?retryWrites=true&w=majority"
    )


def test_settings_reject_invalid_mongo_scheme():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            mongo_uri="postgresql://localhost:5432/budget_maker",
            test_mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
        )


@pytest.mark.parametrize(
    ("unsafe_uri", "expected_error"),
    [
        (
            "mongodb+srv://atlas_user:atlas_password@cluster0.example.mongodb.net/budget_maker_test",
            "mongodb://",
        ),
        (
            "mongodb://bm_local_admin:bm_local_password@mongodb:27017/budget_maker_test?authSource=admin",
            "localhost",
        ),
        (
            "mongodb://bm_local_admin:bm_local_password@localhost:27017/otra_base?authSource=admin",
            "budget_maker_test",
        ),
    ],
)
def test_test_mongo_uri_rejects_external_or_wrong_database(unsafe_uri: str, expected_error: str):
    with pytest.raises(ValueError, match=expected_error):
        ensure_safe_test_mongo_uri(unsafe_uri)


@pytest.mark.asyncio
async def test_init_db_uses_selected_database_and_masks_logs(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    class FakeDatabase:
        def __init__(self, name: str):
            self.name = name
            self.commands: list[str] = []

        async def command(self, command_name: str):
            self.commands.append(command_name)
            return {"ok": 1}

    class FakeClient:
        def __init__(self, uri: str):
            self.uri = uri
            self.databases: dict[str, FakeDatabase] = {}
            self.closed = False

        def __getitem__(self, name: str) -> FakeDatabase:
            if name not in self.databases:
                self.databases[name] = FakeDatabase(name)
            return self.databases[name]

        def close(self) -> None:
            self.closed = True

    captured: dict[str, object] = {}

    async def fake_init_beanie(*, database, document_models):
        captured["database"] = database
        captured["document_models"] = document_models

    test_settings = Settings(
        _env_file=None,
        mongo_uri="mongodb+srv://atlas_user:atlas_password@cluster0.example.mongodb.net/?retryWrites=true&w=majority",
        mongo_db_name="budget_maker",
        test_mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
    )

    monkeypatch.setattr(database_module, "settings", test_settings)
    monkeypatch.setattr(database_module, "AsyncIOMotorClient", FakeClient)
    monkeypatch.setattr(database_module, "init_beanie", fake_init_beanie)
    monkeypatch.setattr(database_module, "mongo_client", None)

    with caplog.at_level(logging.INFO):
        await database_module.init_db()

    fake_client = database_module.mongo_client
    assert fake_client is not None
    assert isinstance(fake_client, FakeClient)
    assert fake_client.uri == test_settings.mongo_uri
    assert captured["database"].name == "budget_maker"
    assert captured["database"].commands == ["ping"]
    assert {model.__name__ for model in captured["document_models"]} == {
        "GlobalConfig",
        "Product",
        "Budget",
        "User",
        "Category",
    }
    assert "atlas_password" not in caplog.text
    assert "atlas_user:******" in caplog.text

    await database_module.close_db()
    assert fake_client.closed is True
    assert database_module.mongo_client is None


@pytest.mark.asyncio
async def test_init_db_propagates_connection_failures(monkeypatch: pytest.MonkeyPatch):
    class FailingDatabase:
        async def command(self, command_name: str):
            raise RuntimeError("auth failed")

    class FailingClient:
        def __init__(self, uri: str):
            self.uri = uri
            self.database = FailingDatabase()
            self.closed = False

        def __getitem__(self, name: str) -> FailingDatabase:
            return self.database

        def close(self) -> None:
            self.closed = True

    created_clients: list["FailingClient"] = []

    def fake_client_factory(uri: str) -> "FailingClient":
        instance = FailingClient(uri)
        created_clients.append(instance)
        return instance

    init_beanie_called = False

    async def fake_init_beanie(*, database, document_models):
        nonlocal init_beanie_called
        init_beanie_called = True

    test_settings = Settings(
        _env_file=None,
        mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker?authSource=admin",
        mongo_db_name="budget_maker",
        test_mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
    )

    monkeypatch.setattr(database_module, "settings", test_settings)
    monkeypatch.setattr(database_module, "AsyncIOMotorClient", fake_client_factory)
    monkeypatch.setattr(database_module, "init_beanie", fake_init_beanie)
    monkeypatch.setattr(database_module, "mongo_client", None)

    with pytest.raises(RuntimeError, match="auth failed"):
        await database_module.init_db()

    assert init_beanie_called is False
    assert database_module.mongo_client is None
    assert len(created_clients) == 1
    assert created_clients[0].closed is True


@pytest.mark.parametrize(
    ("unsafe_uri", "expected_error"),
    [
        (
            "mongodb://localhost:27017/budget_maker_test?authSource=admin",
            "usuario y contraseña",
        ),
        (
            "mongodb://bm_local_admin:@localhost:27017/budget_maker_test?authSource=admin",
            "usuario y contraseña",
        ),
        (
            "mongodb://bm_local_admin:secret@localhost:27017/budget_maker_test",
            "authSource=admin",
        ),
        (
            "mongodb://bm_local_admin:secret@localhost:27017?authSource=admin",
            "budget_maker_test",
        ),
    ],
)
def test_test_mongo_uri_rejects_missing_auth_requirements(unsafe_uri: str, expected_error: str):
    with pytest.raises(ValueError, match=expected_error):
        ensure_safe_test_mongo_uri(unsafe_uri)


@pytest.mark.asyncio
async def test_lifespan_bootstraps_mongo_and_closes_it_on_shutdown(monkeypatch: pytest.MonkeyPatch):
    """El lifespan de FastAPI debe inicializar y cerrar Mongo, y sembrar datos por defecto."""
    import main as main_module

    calls: list[str] = []

    async def fake_init_db() -> None:
        calls.append("init_db")

    async def fake_close_db() -> None:
        calls.append("close_db")

    class FakeConfigUseCases:
        async def seed_defaults(self) -> None:
            calls.append("seed_defaults")

    class FakeAuthUseCases:
        async def seed_superadmin(self) -> None:
            calls.append("seed_superadmin")

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "close_db", fake_close_db)
    monkeypatch.setattr(main_module, "get_config_use_cases", lambda: FakeConfigUseCases())
    monkeypatch.setattr(main_module, "get_auth_use_cases", lambda: FakeAuthUseCases())

    async with main_module.lifespan(main_module.app):
        assert calls == ["init_db", "seed_defaults", "seed_superadmin"]

    assert calls == ["init_db", "seed_defaults", "seed_superadmin", "close_db"]
