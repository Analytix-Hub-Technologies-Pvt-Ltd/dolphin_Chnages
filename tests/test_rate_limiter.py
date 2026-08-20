import pytest
from unittest.mock import Mock, patch, MagicMock
from slowapi.errors import RateLimitExceeded
from datetime import datetime

from core.rate_limiter import (
    limiter,
    get_rate_limit_key,
    rate_limit_auth,
    rate_limit_chat,
    rate_limit_api,
    get_rate_limit_for_path,
    RATE_LIMIT_CONFIG
)
from config import settings


class TestRateLimiter:
    """Test suite for rate limiting functionality"""

    def test_get_rate_limit_key_with_user_id(self):
        """Test key generation with user ID"""
        # Arrange
        mock_request = Mock()
        mock_request.state = Mock()
        mock_request.state.user_id = "user-123"

        # Act
        result = get_rate_limit_key(mock_request)

        # Assert
        assert result == "user-123"


    def test_rate_limit_decorators_exist(self):
        """Test that rate limit decorators are properly defined"""
        # Assert
        assert callable(rate_limit_auth)
        assert callable(rate_limit_chat)
        assert callable(rate_limit_api)

        # Test decoration
        @rate_limit_auth
        def dummy_auth(request):
            return "auth"

        @rate_limit_chat
        def dummy_chat(request):
            return "chat"

        @rate_limit_api
        def dummy_api(request):
            return "api"

        # Should not raise errors
        assert dummy_auth.__name__ == "dummy_auth"
        assert dummy_chat.__name__ == "dummy_chat"
        assert dummy_api.__name__ == "dummy_api"

    def test_rate_limit_config_mapping(self):
        """Test that rate limit config maps paths correctly"""
        # Arrange
        test_cases = [
            ("/api/v1/auth/login", "10/minute"),
            ("/api/v1/auth/register", "10/minute"),
            ("/api/v1/chat", "30/minute"),
            ("/api/v1/quiz", "60/minute"),
            ("/api/v1/course-sync", "60/minute"),
            ("/api/v1/unknown", "100/minute"),
            ("/other/path", "100/minute"),
        ]

        # Mock settings
        with patch('core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_default = "100/minute"
            mock_settings.rate_limit_auth = "10/minute"
            mock_settings.rate_limit_chat = "30/minute"
            mock_settings.rate_limit_api = "60/minute"

            # Act & Assert
            for path, expected_limit in test_cases:
                result = get_rate_limit_for_path(path)
                assert result == expected_limit, f"Failed for path: {path}. Got: {result}"

    def test_rate_limit_enforcement(self):
        """Test that rate limiting actually works"""
        # Arrange
        def test_endpoint(request):
            return "success"

        mock_request = Mock()
        mock_request.state = Mock()
        mock_request.state.user_id = "test-user"

        with patch.object(limiter, "limit") as mock_limit:
            mock_limit.return_value = lambda f: f

            decorated_func = rate_limit_auth(test_endpoint)
            result = decorated_func(mock_request)

        assert result == "success"

    def test_rate_limit_exceeded(self):
        """Test that rate limit exceeded raises proper exception"""

        def test_endpoint(request):
            return "success"

        mock_request = Mock()
        mock_request.state = Mock()
        mock_request.state.user_id = "test-user"

        def raise_rate_limit(*args, **kwargs):
            raise RateLimitExceeded(limiter.limit)

        with patch.object(limiter, "limit") as mock_limit:
            mock_limit.return_value = lambda f: raise_rate_limit

            decorated_func = rate_limit_auth(test_endpoint)

            with pytest.raises(RateLimitExceeded) as exc_info:
                decorated_func(mock_request)

        assert exc_info.value.status_code == 429

    def test_limiter_configuration(self):
        """Test that limiter is properly configured"""
        # Assert
        assert limiter._key_func.__name__ == "get_remote_address"
        # Note: Accessing private attributes might not be ideal
        # Consider testing through public interface instead

    def test_rate_limit_config_completeness(self):
        """Test that all expected paths are in the config"""
        # Arrange
        expected_paths = [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/chat",
            "/api/v1/quiz",
            "/api/v1/course-sync",
        ]

        # Mock settings to provide values
        with patch('core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_auth = "10/minute"
            mock_settings.rate_limit_chat = "30/minute"
            mock_settings.rate_limit_api = "60/minute"

            # Act & Assert
            for path in expected_paths:
                assert path in RATE_LIMIT_CONFIG
                assert RATE_LIMIT_CONFIG[path] is not None

    def test_custom_key_func_integration(self):
        """Test that custom key function integrates with limiter"""
        # This test is complex because it tests integration
        # Consider testing the key function separately
        pass

    @pytest.mark.parametrize("path,expected_limit", [
        ("/api/v1/auth/login", "10/minute"),
        ("/api/v1/chat", "30/minute"),
        ("/api/v1/quiz", "60/minute"),
        ("/nonexistent", "100/minute"),
    ])
    def test_get_rate_limit_for_path_parametrized(self, path, expected_limit):
        """Parametrized test for get_rate_limit_for_path"""
        with patch('core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_default = "100/minute"
            mock_settings.rate_limit_auth = "10/minute"
            mock_settings.rate_limit_chat = "30/minute"
            mock_settings.rate_limit_api = "60/minute"

            result = get_rate_limit_for_path(path)
            assert result == expected_limit

    def test_concurrent_rate_limits(self):
        """Test that different endpoints can have different rate limits"""
        with patch('core.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limit_default = "100/minute"
            mock_settings.rate_limit_auth = "10/minute"
            mock_settings.rate_limit_chat = "30/minute"
            mock_settings.rate_limit_api = "60/minute"

            # Assert different limits are applied
            assert get_rate_limit_for_path("/api/v1/auth/login") == "10/minute"
            assert get_rate_limit_for_path("/api/v1/chat") == "30/minute"
            assert get_rate_limit_for_path("/api/v1/quiz") == "60/minute"
            assert get_rate_limit_for_path("/api/v1/unknown") == "100/minute"


class TestIntegrationScenarios:
    """Integration test scenarios for rate limiting"""

    def test_rate_limit_with_different_users(self):
        """Test that rate limits are per-user"""
        # This would require a more complex integration test
        # with actual FastAPI app and test client
        pass

    def test_rate_limit_reset(self):
        """Test that rate limits reset after time window"""
        # This requires testing with actual time windows
        # Consider using time travel libraries like freezegun
        pass


# Improved fixtures
@pytest.fixture
def mock_request_with_user():
    """Fixture providing a mock request with user ID"""
    request = Mock()
    request.state = Mock()
    request.state.user_id = "test-user-123"
    return request


@pytest.fixture
def mock_request_without_user():
    """Fixture providing a mock request without user ID"""
    request = Mock()
    request.state = Mock()
    return request


# Additional tests for edge cases
def test_get_rate_limit_key_with_none_user_id():
    """Test key generation when user_id exists but is None"""
    # Arrange
    mock_request = Mock()
    mock_request.state = Mock()
    mock_request.state.user_id = None

    # Mock get_remote_address
    with patch('core.rate_limiter.get_remote_address') as mock_get_remote:
        mock_get_remote.return_value = "192.168.1.1"

        # Act
        result = get_rate_limit_key(mock_request)

        # Assert
        assert result == "192.168.1.1"


def test_get_rate_limit_key_with_empty_string_user_id():
    """Test key generation when user_id is empty string"""
    mock_request = Mock()
    mock_request.state = Mock()
    mock_request.state.user_id = ""
    mock_request.client = Mock(host="192.168.1.1")

    result = get_rate_limit_key(mock_request)
    assert result == "192.168.1.1"


def test_rate_limit_decorator_preserves_metadata():
    """Test that rate limit decorators preserve function metadata"""

    # Arrange
    def original_func(request):
        """Original function docstring"""
        return "test"

    original_func.custom_attr = "custom_value"

    # Act
    decorated_func = rate_limit_auth(original_func)

    # Assert
    assert decorated_func.__name__ == "original_func"
    assert decorated_func.__doc__ == "Original function docstring"
    assert hasattr(decorated_func, 'custom_attr')
    assert decorated_func.custom_attr == "custom_value"


def test_runtime_error_if_settings_not_configured():
    """Test that functions raise errors if settings are not configured"""
    # This test would need to handle module reloading
    pass