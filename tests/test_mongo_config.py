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
    assert atlas_settings.masked_mongo_uri() == "mongodb+srv://atlas_user:******@cluster0.example.mongodb.net/"


def test_settings_reject_invalid_mongo_scheme():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            mongo_uri="postgresql://localhost:5432/budget_maker",
            test_mongo_uri="mongodb://bm_local_admin:bm_local_password@localhost:27017/budget_maker_test?authSource=admin",
        )


def test_settings_load_mongo_environment_aliases(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "MONGO_URI",
        "mongodb+srv://atlas_user:atlas_password@cluster0.example.mongodb.net/?retryWrites=true&w=majority",
    )
    monkeypatch.setenv("MONGO_DB_NAME", "budget_maker_external")
    monkeypatch.setenv(
        "TEST_MONGO_URI",
        "mongodb://test_user:test_password@localhost:27017/budget_maker_test?authSource=admin",
    )

    configured_settings = Settings(_env_file=None)

    assert configured_settings.mongo_uri.startswith("mongodb+srv://")
    assert configured_settings.mongo_db_name == "budget_maker_external"
    assert configured_settings.test_mongo_uri.startswith("mongodb://")


@pytest.mark.parametrize(
    ("unsafe_uri", "expected_error"),
    [
        (
            "mongodb://test_user:test_password@localhost:27017,remote.example:27017/"
            "budget_maker_test?authSource=admin",
            "único host local",
        ),
        (
            "mongodb://test_user:test_password@localhost:27017/"
            "budget_maker_test?authSource=admin&authSource=users",
            "único authSource=admin",
        ),
    ],
)
def test_test_mongo_uri_rejects_multiple_hosts_or_auth_sources(
    unsafe_uri: str,
    expected_error: str,
):
    with pytest.raises(ValueError, match=expected_error):
        ensure_safe_test_mongo_uri(unsafe_uri)


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
async def test_init_db_closes_candidate_when_beanie_initialization_fails(monkeypatch: pytest.MonkeyPatch):
    class FakeDatabase:
        async def command(self, command_name: str):
            return {"ok": 1}

    class FakeClient:
        def __init__(self, uri: str):
            self.closed = False

        def __getitem__(self, name: str) -> FakeDatabase:
            return FakeDatabase()

        def close(self) -> None:
            self.closed = True

    created_clients: list[FakeClient] = []

    def fake_client_factory(uri: str) -> FakeClient:
        client = FakeClient(uri)
        created_clients.append(client)
        return client

    async def failing_init_beanie(*, database, document_models):
        raise RuntimeError("index creation failed")

    monkeypatch.setattr(database_module, "AsyncIOMotorClient", fake_client_factory)
    monkeypatch.setattr(database_module, "init_beanie", failing_init_beanie)
    monkeypatch.setattr(database_module, "mongo_client", None)

    with pytest.raises(RuntimeError, match="index creation failed"):
        await database_module.init_db()

    assert database_module.mongo_client is None
    assert created_clients[0].closed is True


@pytest.mark.asyncio
async def test_init_db_preserves_previous_client_when_reinitialization_fails(monkeypatch: pytest.MonkeyPatch):
    class PreviousClient:
        def __init__(self):
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class FailingDatabase:
        async def command(self, command_name: str):
            raise RuntimeError("connection failed")

    class FailingClient:
        def __init__(self, uri: str):
            self.closed = False

        def __getitem__(self, name: str) -> FailingDatabase:
            return FailingDatabase()

        def close(self) -> None:
            self.closed = True

    previous_client = PreviousClient()
    monkeypatch.setattr(database_module, "AsyncIOMotorClient", FailingClient)
    monkeypatch.setattr(database_module, "mongo_client", previous_client)

    with pytest.raises(RuntimeError, match="connection failed"):
        await database_module.init_db()

    assert database_module.mongo_client is previous_client
    assert previous_client.closed is False


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


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_seed", ["seed_defaults", "seed_superadmin"])
async def test_lifespan_closes_mongo_when_seed_fails(
    monkeypatch: pytest.MonkeyPatch,
    failing_seed: str,
):
    import main as main_module

    calls: list[str] = []

    async def fake_init_db() -> None:
        calls.append("init_db")

    async def fake_close_db() -> None:
        calls.append("close_db")

    class FakeConfigUseCases:
        async def seed_defaults(self) -> None:
            calls.append("seed_defaults")
            if failing_seed == "seed_defaults":
                raise RuntimeError("seed failed")

    class FakeAuthUseCases:
        async def seed_superadmin(self) -> None:
            calls.append("seed_superadmin")
            if failing_seed == "seed_superadmin":
                raise RuntimeError("seed failed")

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module, "close_db", fake_close_db)
    monkeypatch.setattr(main_module, "get_config_use_cases", lambda: FakeConfigUseCases())
    monkeypatch.setattr(main_module, "get_auth_use_cases", lambda: FakeAuthUseCases())

    with pytest.raises(RuntimeError, match="seed failed"):
        async with main_module.lifespan(main_module.app):
            pytest.fail("El lifespan no debe iniciar si falla un seed.")

    assert calls[-1] == "close_db"


def test_settings_accept_supabase_storage_configuration():
    configured = Settings(
        _env_file=None,
        mongo_uri="mongodb://atlas_user:atlas_password@localhost:27017/budget_maker?authSource=admin",
        test_mongo_uri="mongodb://tester:tester@localhost:27017/budget_maker_test?authSource=admin",
        supabase_url="https://Budget-Maker.supabase.co/",
        supabase_secret_key="service-role-key",
        supabase_products_bucket="products",
        supabase_media_bucket="media",
        supabase_branding_prefix="/branding/",
    )

    assert configured.supabase_url == "https://budget-maker.supabase.co"
    assert configured.supabase_products_bucket == "products"
    assert configured.supabase_media_bucket == "media"
    assert configured.supabase_branding_prefix == "branding"


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("supabase_url", "https://demo.supabase.co/path", "SUPABASE_URL"),
        ("supabase_products_bucket", "Products", "SUPABASE_PRODUCTS_BUCKET"),
        ("supabase_branding_prefix", "../branding", "SUPABASE_BRANDING_PREFIX"),
    ],
)
def test_settings_reject_invalid_supabase_storage_values(
    field_name: str,
    field_value: str,
    expected_error: str,
):
    payload = {
        "mongo_uri": "mongodb://atlas_user:atlas_password@localhost:27017/budget_maker?authSource=admin",
        "test_mongo_uri": "mongodb://tester:tester@localhost:27017/budget_maker_test?authSource=admin",
        field_name: field_value,
    }

    with pytest.raises(ValidationError, match=expected_error):
        Settings(_env_file=None, **payload)
