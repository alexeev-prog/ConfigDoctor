import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Generic, TypeVar, overload

from .exceptions import ConfigError

try:
    import toml
except ImportError:
    toml = None

try:
    import yaml
except ImportError:
    yaml = None

try:
    from pydantic import BaseModel, ValidationError
except ImportError:
    BaseModel = object
    ValidationError = Exception

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    FileSystemEventHandler = object
    Observer = None


T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


class ConfigType(Enum):
    """Project configuration types."""

    TOML = 0
    YAML = 1
    JSON = 2


def detect_config_type_by_extension(extension: str) -> ConfigType:
    """
    Detect config type by file extension.

    Args:
        extension: File extension string

    Returns:
        ConfigType: Detected config type

    Raises:
        ConfigError: If the extension is not supported

    """
    cleaned_extension = extension.lower().lstrip(".")

    if cleaned_extension == "json":
        return ConfigType.JSON
    if cleaned_extension in ("yaml", "yml"):
        return ConfigType.YAML
    if cleaned_extension == "toml":
        if toml is None:
            raise ConfigError("TOML support requires 'toml' package installation")
        return ConfigType.TOML

    raise ConfigError(f"Unsupported config file extension: {extension}")


class AbstractConfig(ABC):
    """This class describes an abstract configuration."""

    def __init__(self, config_path: str | Path):
        """
        Initialize a config object.

        Args:
            config_path: Filepath to config.

        Raises:
            ConfigError: If config file doesn't exist or is not a file

        """
        self.config_path = Path(config_path)
        self._validate_config_path()
        self._config: dict[str, Any] | None = None

    def _validate_config_path(self) -> None:
        """Validate that config path exists and is a file."""
        if not self.config_path.exists():
            raise ConfigError(f"Config file not found: {self.config_path}")
        if not self.config_path.is_file():
            raise ConfigError(f"Config path is not a file: {self.config_path}")

    @abstractmethod
    def _load_config(self) -> dict[str, Any]:
        """
        Load config from file.

        Returns:
            dict[str, Any]: Configuration as dictionary.

        Raises:
            ConfigError: If config loading fails

        """
        raise NotImplementedError

    def get_loaded_config(self) -> dict[str, Any]:
        """
        Get loaded config.

        Load config into dictionary if not already loaded.

        Returns:
            dict[str, Any]: Configuration as dictionary.

        Raises:
            ConfigError: If config loading fails

        """
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def reload(self) -> None:
        """Reload the configuration from disk."""
        self._config = self._load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Any: Configuration value or default

        """
        config = self.get_loaded_config()
        return config.get(key, default)


class AbstractConfigFactory(ABC):
    """Front-end to create abstract configuration objects."""

    @abstractmethod
    def create_config(self) -> AbstractConfig:
        """
        Create abstract config.

        Create an abstract configuration object.

        Returns:
            AbstractConfig: Abstract config instance

        """
        raise NotImplementedError


class ConfigFactory(AbstractConfigFactory):
    """Front-end to create configuration objects."""

    def __init__(self, config_path: str | Path):
        """
        Initialize a config factory.

        Create configuration objects with abstract factory pattern.

        Args:
            config_path: File path to config

        """
        self.config_path = Path(config_path)
        self.ext = detect_config_type_by_extension(self.config_path.suffix)

    def create_config(self) -> AbstractConfig:
        """
        Create and return config.

        Generate config object based on file extension.

        Returns:
            AbstractConfig: Config object instance

        Raises:
            ConfigError: If config type is not supported

        """
        if self.ext == ConfigType.JSON:
            return JSONConfig(self.config_path)
        if self.ext == ConfigType.TOML:
            return TOMLConfig(self.config_path)
        if self.ext == ConfigType.YAML:
            return YAMLConfig(self.config_path)
        raise ConfigError(f"Unsupported config type: {self.ext}")


class JSONConfig(AbstractConfig):
    """This class describes a JSON configuration."""

    def _load_config(self) -> dict[str, Any]:
        """
        Load JSON config from file.

        Returns:
            dict[str, Any]: Configuration as dictionary.

        Raises:
            ConfigError: If JSON parsing fails, file not found, or file is empty

        """
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except FileNotFoundError as e:
            raise ConfigError(f"Config file not found: {self.config_path}") from e
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}") from e


class TOMLConfig(AbstractConfig):
    """This class describes a TOML configuration."""

    def _load_config(self) -> dict[str, Any]:
        """
        Load TOML config from file.

        Returns:
            dict[str, Any]: Configuration as dictionary.

        Raises:
            ConfigError: If TOML parsing fails, file not found, or file is empty

        """
        if toml is None:
            raise ConfigError("TOML support requires 'toml' package installation")

        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return toml.loads(content)
        except FileNotFoundError as e:
            raise ConfigError(f"Config file not found: {self.config_path}") from e
        except toml.TomlDecodeError as e:
            raise ConfigError(f"Invalid TOML in config file: {e}") from e


class YAMLConfig(AbstractConfig):
    """This class describes a YAML configuration."""

    def _load_config(self) -> dict[str, Any]:
        """
        Load YAML config from file.

        Returns:
            dict[str, Any]: Configuration as dictionary.

        Raises:
            ConfigError: If YAML parsing fails, file not found, or file is empty

        """
        if yaml is None:
            raise ConfigError("YAML support requires 'PyYAML' package installation")

        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return yaml.safe_load(content) or {}
        except FileNotFoundError as e:
            raise ConfigError(f"Config file not found: {self.config_path}") from e
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}") from e


class ConfigFileEventHandler(FileSystemEventHandler):
    """Handler for config file changes."""

    def __init__(
        self,
        config_provider: "ConfigurationProvider",
        on_config_change: Callable[["ConfigurationProvider"], None] | None = None,
        on_config_error: Callable[["ConfigurationProvider", Exception], None]
        | None = None,
    ):
        """
        Initialize a Config File Event handler.

        This class based on file system event handler and reload
        config when file is modified.

        Args:
            config_provider: Configuration provider
            on_config_change: Callback to execute after successful config reload
            on_config_error: Callback to execute when config reload fails

        """
        self.config_provider = config_provider
        self.on_config_change = on_config_change
        self.on_config_error = on_config_error

    def on_modified(self, event):
        """Reload config when file is modified."""
        if event.src_path == str(self.config_provider.config.config_path):
            try:
                self.config_provider.reload()
                if self.on_config_change:
                    self.on_config_change(self.config_provider)
            except Exception as e:
                if self.on_config_error:
                    self.on_config_error(self.config_provider, e)


class ConfigurationProvider(Generic[M]):
    """This class describes a configuration provider with advanced features."""

    def __init__(
        self,
        config_path: str | Path,
        validation_model: type[M] | None = None,
        *,
        watch_for_changes: bool = False,
        on_config_change: Callable[["ConfigurationProvider"], None] | None = None,
        on_config_error: Callable[["ConfigurationProvider", Exception], None]
        | None = None,
        auto_reload: bool = True,
    ):
        """
        Constructs a new instance.

        Args:
            config_path: The configuration file path
            validation_model: Pydantic model for validation
            watch_for_changes: Whether to watch for file changes
            on_config_change: Callback to execute after successful config reload
            on_config_error: Callback to execute when config reload fails
            auto_reload: Whether to automatically reload config on file changes

        Raises:
            ConfigError: If validation fails or required dependencies are missing

        """
        self.factory = ConfigFactory(config_path)
        self.config = self.factory.create_config()
        self.validation_model = validation_model
        self._observer: Observer | None = None
        self.on_config_change = on_config_change
        self.on_config_error = on_config_error
        self.auto_reload = auto_reload

        if self.validation_model:
            self._validate_with_model()

        if watch_for_changes:
            if Observer is None:
                raise ConfigError(
                    "File watching requires 'watchdog' package installation"
                )
            self._start_watching()

    def _validate_with_model(self) -> None:
        """Validate configuration with pydantic model."""
        try:
            self.validation_model(**self.config.get_loaded_config())
        except ValidationError as e:
            raise ConfigError(f"Configuration validation failed: {e}") from e

    def _start_watching(self) -> None:
        """Start watching config file for changes."""
        self._observer = Observer()
        event_handler = ConfigFileEventHandler(
            self,
            on_config_change=self.on_config_change,
            on_config_error=self.on_config_error,
        )
        self._observer.schedule(event_handler, path=str(self.config.config_path.parent))
        self._observer.start()

    def stop_watching(self) -> None:
        """Stop watching config file for changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def __enter__(self) -> "ConfigurationProvider":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.stop_watching()

    def __call__(self) -> AbstractConfig:
        """
        Make configuration provider callable.

        Returns:
            AbstractConfig: Config object instance

        """
        return self.config

    @overload
    def get(self, key: str) -> Any: ...

    @overload
    def get(self, key: str, default: T) -> T: ...

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key (supports dot notation for nested keys).

        Args:
            key: Configuration key (can use dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Any: Configuration value or default

        """
        if "." in key:
            keys = key.split(".")
            return self.get_nested(*keys, default=default)

        return self.config.get(key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """
        Get a nested configuration value.

        Args:
            *keys: Nested keys to traverse
            default: Default value if any key not found

        Returns:
            Any: Nested configuration value or default

        """
        config = self.config.get_loaded_config()
        current = config

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return current

    def reload(self) -> None:
        """Reload the configuration from disk."""
        self.config.reload()
        if self.validation_model:
            self._validate_with_model()

    def as_dict(self) -> dict[str, Any]:
        """
        Get the entire configuration as a dictionary.

        Returns:
            dict[str, Any]: Complete configuration

        """
        return self.config.get_loaded_config()

    def as_model(self) -> M:
        """
        Get the entire configuration as a validated pydantic model.

        Returns:
            M: Validated configuration model

        Raises:
            ConfigError: If no validation model was provided or validation fails

        """
        if not self.validation_model:
            raise ConfigError("No validation model provided")

        try:
            return self.validation_model(**self.as_dict())
        except ValidationError as e:
            raise ConfigError(f"Configuration validation failed: {e}") from e

    def validate(self, required_keys: list[str]) -> bool:
        """
        Validate that required keys exist in the configuration.

        Args:
            required_keys: List of required key paths (can be nested with dot notation)

        Returns:
            bool: True if all required keys exist

        Raises:
            ConfigError: If any required key is missing

        """
        missing_keys = []
        config_dict = self.as_dict()

        for key_path in required_keys:
            keys = key_path.split(".")
            current = config_dict

            for key in keys:
                if not isinstance(current, dict) or key not in current:
                    missing_keys.append(key_path)
                    break
                current = current[key]

        if missing_keys:
            raise ConfigError(f"Missing required configuration keys: {missing_keys}")

        return True


def get_config_provider(
    config_path: str | Path,
    validation_model: type[M] | None = None,
    *,
    watch_for_changes: bool = False,
    use_cache: bool = True,
    on_config_change: Callable[[ConfigurationProvider], None] | None = None,
    on_config_error: Callable[[ConfigurationProvider, Exception], None] | None = None,
    auto_reload: bool = True,
) -> ConfigurationProvider[M]:
    """
    Get a configuration provider instance.

    Args:
        config_path: Path to the configuration file
        validation_model: Pydantic model for validation
        watch_for_changes: Whether to watch for file changes
        use_cache: Whether to use cached provider instance
        on_config_change: Callback to execute after successful config reload
        on_config_error: Callback to execute when config reload fails
        auto_reload: Whether to automatically reload config on file changes

    Returns:
        ConfigurationProvider: Configuration provider instance

    """
    if not use_cache:
        return ConfigurationProvider(
            config_path,
            validation_model,
            watch_for_changes=watch_for_changes,
            on_config_change=on_config_change,
            on_config_error=on_config_error,
            auto_reload=auto_reload,
        )

    cache_key = (
        str(config_path),
        validation_model,
        watch_for_changes,
        on_config_change,
        on_config_error,
        auto_reload,
    )

    @lru_cache(maxsize=32)
    def _cached_provider(*args) -> ConfigurationProvider:
        path, model, watch, change_cb, error_cb, reload = args
        return ConfigurationProvider(
            path,
            model,
            watch_for_changes=watch,
            on_config_change=change_cb,
            on_config_error=error_cb,
            auto_reload=reload,
        )

    return _cached_provider(*cache_key)
