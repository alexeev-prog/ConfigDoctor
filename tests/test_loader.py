from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest import raises

from configdoctor.config_reader import (
    AbstractConfig,
    ConfigError,
    ConfigFactory,
    ConfigFileEventHandler,
    ConfigType,
    ConfigurationProvider,
    JSONConfig,
    TOMLConfig,
    YAMLConfig,
    detect_config_type_by_extension,
    get_config_provider,
)
from configdoctor.exceptions import ConfigError as BaseConfigError


class TestDetectConfigType:
    def test_detect_json(self):
        assert detect_config_type_by_extension(".json") == ConfigType.JSON
        assert detect_config_type_by_extension("json") == ConfigType.JSON

    def test_detect_yaml(self):
        assert detect_config_type_by_extension(".yaml") == ConfigType.YAML
        assert detect_config_type_by_extension(".yml") == ConfigType.YAML
        assert detect_config_type_by_extension("yaml") == ConfigType.YAML
        assert detect_config_type_by_extension("yml") == ConfigType.YAML

    def test_detect_toml(self):
        assert detect_config_type_by_extension(".toml") == ConfigType.TOML
        assert detect_config_type_by_extension("toml") == ConfigType.TOML

    def test_toml_missing_dependency(self):
        with patch("configdoctor.config_reader.toml", None):
            with raises(ConfigError, match="TOML support requires"):
                detect_config_type_by_extension(".toml")

    def test_unsupported_extension(self):
        with raises(ConfigError, match="Unsupported config file extension"):
            detect_config_type_by_extension(".xml")


class TestAbstractConfig:
    def test_invalid_path(self, tmp_path):
        invalid_path = tmp_path / "nonexistent.json"
        with raises(ConfigError):
            JSONConfig(invalid_path)

    def test_directory_path(self, tmp_path):
        with raises(ConfigError):
            JSONConfig(tmp_path)


class TestJSONConfig:
    @pytest.fixture
    def json_file(self, tmp_path):
        file = tmp_path / "test.json"
        file.write_text('{"key": "value", "nested": {"inner": 42}}')
        return file

    def test_load_valid_json(self, json_file):
        config = JSONConfig(json_file)
        assert config.get_loaded_config() == {"key": "value", "nested": {"inner": 42}}

    def test_get_value(self, json_file):
        config = JSONConfig(json_file)
        assert config.get("key") == "value"
        assert config.get("nonexistent", "default") == "default"

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")
        config = JSONConfig(empty_file)
        assert config.get_loaded_config() == {}

    def test_invalid_json(self, tmp_path):
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid}")
        config = JSONConfig(invalid_file)
        with raises(ConfigError, match="Invalid JSON"):
            config.get_loaded_config()

    def test_reload(self, json_file):
        config = JSONConfig(json_file)
        config.get_loaded_config()
        json_file.write_text('{"new": "data"}')
        config.reload()
        assert config.get_loaded_config() == {"new": "data"}


class TestTOMLConfig:
    @pytest.fixture
    def toml_file(self, tmp_path):
        file = tmp_path / "test.toml"
        file.write_text("key = 'value'\n[nested]\ninner = 42")
        return file

    def test_load_valid_toml(self, toml_file):
        config = TOMLConfig(toml_file)
        assert config.get_loaded_config() == {"key": "value", "nested": {"inner": 42}}

    def test_toml_missing_dependency(self, tmp_path):
        test_file = tmp_path / "test.toml"
        test_file.touch()
        with patch("configdoctor.config_reader.toml", None):
            config = TOMLConfig(test_file)
            with raises(ConfigError, match="TOML support requires"):
                config.get_loaded_config()


class TestYAMLConfig:
    @pytest.fixture
    def yaml_file(self, tmp_path):
        file = tmp_path / "test.yaml"
        file.write_text("key: value\nnested:\n  inner: 42")
        return file

    def test_load_valid_yaml(self, yaml_file):
        config = YAMLConfig(yaml_file)
        assert config.get_loaded_config() == {"key": "value", "nested": {"inner": 42}}

    def test_yaml_missing_dependency(self, tmp_path):
        test_file = tmp_path / "test.yaml"
        test_file.touch()
        with patch("configdoctor.config_reader.yaml", None):
            config = YAMLConfig(test_file)
            with raises(ConfigError, match="YAML support requires"):
                config.get_loaded_config()

    def test_yaml_empty_content(self, tmp_path):
        file = tmp_path / "test.yaml"
        file.write_text("# Just a comment")
        config = YAMLConfig(file)
        assert config.get_loaded_config() == {}


class TestConfigFactory:
    @pytest.mark.parametrize(
        ("ext", "cls"),
        [
            (".json", JSONConfig),
            (".yaml", YAMLConfig),
            (".yml", YAMLConfig),
            (".toml", TOMLConfig),
        ],
    )
    def test_create_config(self, tmp_path, ext, cls):
        file = tmp_path / f"test{ext}"
        file.touch()
        factory = ConfigFactory(file)
        assert isinstance(factory.create_config(), cls)

    def test_unsupported_type(self, tmp_path):
        with raises(ConfigError):
            file = tmp_path / "test.xml"
            file.touch()
            factory = ConfigFactory(file)

            factory.create_config()


class TestConfigurationProvider:
    @pytest.fixture
    def config_file(self, tmp_path):
        file = tmp_path / "config.json"
        file.write_text('{"database": {"host": "localhost", "port": 5432}}')
        return file

    def test_basic_functionality(self, config_file):
        provider = ConfigurationProvider(config_file)
        assert provider.get("database.host") == "localhost"
        assert provider.get_nested("database", "port") == 5432

    def test_validation_model(self, config_file):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            database: dict

        provider = ConfigurationProvider(config_file, validation_model=TestModel)
        model = provider.as_model()
        assert isinstance(model, TestModel)
        assert model.database == {"host": "localhost", "port": 5432}

    def test_validation_error(self, config_file):
        from pydantic import BaseModel

        class TestModel(BaseModel):
            required_field: str

        with raises(ConfigError, match="Configuration validation failed"):
            ConfigurationProvider(config_file, validation_model=TestModel)

    def test_missing_validation_model(self, config_file):
        provider = ConfigurationProvider(config_file)
        with raises(ConfigError, match="No validation model provided"):
            provider.as_model()

    def test_validate_required_keys(self, config_file):
        provider = ConfigurationProvider(config_file)
        assert provider.validate(["database.host", "database.port"]) is True

    def test_validate_missing_keys(self, config_file):
        provider = ConfigurationProvider(config_file)
        with raises(ConfigError, match="Missing required configuration keys"):
            provider.validate(["database.host", "missing.key"])

    def test_watchdog_missing_dependency(self, config_file):
        with patch("configdoctor.config_reader.Observer", None):
            with raises(ConfigError, match="watchdog"):
                ConfigurationProvider(config_file, watch_for_changes=True)

    def test_context_manager(self, config_file):
        with ConfigurationProvider(config_file) as provider:
            assert provider.config is not None

    def test_callable(self, config_file):
        provider = ConfigurationProvider(config_file)
        assert isinstance(provider(), AbstractConfig)

    def test_stop_watching(self, config_file):
        with patch("configdoctor.config_reader.Observer") as mock_observer:
            provider = ConfigurationProvider(config_file, watch_for_changes=True)
            provider.stop_watching()
            mock_observer.return_value.stop.assert_called_once()
            mock_observer.return_value.join.assert_called_once()

    def test_auto_reload_false(self, config_file):
        provider = ConfigurationProvider(config_file, auto_reload=False)
        assert provider.auto_reload is False

    def test_watchdog_initialized(self, config_file):
        with patch("configdoctor.config_reader.Observer") as mock_observer:
            ConfigurationProvider(config_file, watch_for_changes=True)
            mock_observer.assert_called_once()
            mock_observer.return_value.start.assert_called_once()

    def test_without_pydantic(self, config_file):
        with (
            patch("configdoctor.config_reader.BaseModel", object),
            patch("configdoctor.config_reader.ValidationError", Exception),
        ):
            provider = ConfigurationProvider(config_file)
            assert provider is not None

    def test_pydantic_validation_error(self, config_file):
        with (
            patch("configdoctor.config_reader.BaseModel", object),
            patch("configdoctor.config_reader.ValidationError", Exception),
        ):
            with raises(Exception):
                ConfigurationProvider(config_file, validation_model=object)

    def test_stop_watching_without_observer(self, config_file):
        provider = ConfigurationProvider(config_file, watch_for_changes=False)
        provider.stop_watching()  # Should not raise an exception


class TestConfigFileEventHandler:
    def test_event_handler_callbacks(self):
        provider = Mock()
        provider.config = Mock()
        provider.config.config_path = Path("/test/config.yaml")
        provider.reload = Mock()

        change_callback = Mock()
        error_callback = Mock()

        handler = ConfigFileEventHandler(
            provider, on_config_change=change_callback, on_config_error=error_callback
        )

        event = Mock()
        event.src_path = "/test/config.yaml"

        handler.on_modified(event)
        change_callback.assert_called_once_with(provider)

        provider.reload.side_effect = Exception("Reload error")
        handler.on_modified(event)
        error_callback.assert_called_once_with(provider, provider.reload.side_effect)

    def test_event_handler_without_callbacks(self):
        provider = Mock()
        provider.config = Mock()
        provider.config.config_path = Path("/test/config.yaml")
        provider.reload = Mock()

        handler = ConfigFileEventHandler(provider)
        event = Mock()
        event.src_path = "/test/config.yaml"

        handler.on_modified(event)

    def test_event_handler_exception_without_error_callback(self):
        provider = Mock()
        provider.config = Mock()
        provider.config.config_path = Path("/test/config.yaml")
        provider.reload = Mock(side_effect=Exception("Reload error"))

        handler = ConfigFileEventHandler(provider)  # без error_callback
        event = Mock()
        event.src_path = "/test/config.yaml"

        # Должен просто игнорировать исключение, так как error_callback не установлен
        handler.on_modified(event)


class TestGetConfigProvider:
    @pytest.fixture
    def config_file(self, tmp_path):
        file = tmp_path / "config.json"
        file.write_text('{"test": "value"}')
        return file

    def test_without_cache(self, config_file):
        provider1 = get_config_provider(config_file)
        provider2 = get_config_provider(config_file)
        assert provider1 is not provider2

    def test_with_different_params(self, config_file):
        provider1 = get_config_provider(config_file, watch_for_changes=True)
        provider2 = get_config_provider(config_file, watch_for_changes=False)
        assert provider1 is not provider2


class TestExceptions:
    def test_config_error_inheritance(self):
        assert issubclass(ConfigError, BaseConfigError)
