"""Production settings must fail closed without reading private environment files."""
import pytest
from pydantic import ValidationError
from app.config import Settings


def production(**overrides):
    return Settings(_env_file=None, **{'ENV': 'production', 'SECRET_KEY': 'a' * 64,
                    'CORS_ORIGINS': 'https://research.example.org', **overrides})


@pytest.mark.parametrize('secret', ['change-me-in-production', 'short',
                                  'development-only-change-me-before-hosting',
                                  'REPLACE_WITH_A_LONG_RANDOM_PRODUCTION_SECRET', 'GENERATE_WITH_SETUP' * 2])
def test_production_rejects_default_or_placeholder_signing_secrets(secret):
    with pytest.raises(ValidationError):
        production(SECRET_KEY=secret)


@pytest.mark.parametrize('origin', ['', '*', 'http://localhost:3002', 'https://example.org/path',
                                   'https://example.org/', 'https://user:pass@example.org',
                                   'https://example.org?debug=true', 'https://YOUR_SOCIALSCOPE_DOMAIN',
                                   'https://example.org:invalid', 'https://example.org:99999',
                                   'https://example.org\n'])
def test_production_requires_explicit_https_origins(origin):
    with pytest.raises(ValidationError):
        production(CORS_ORIGINS=origin)


def test_production_accepts_explicit_https_origin_and_no_optional_provider_keys():
    settings = production(CORS_ORIGINS='https://research.example.org, https://research.example.org:8445',
                          XPOZ_API_KEY='', SOCIALVAULT_API_KEY='', OPENAI_API_KEY='')
    assert settings.ENV == 'production'
    assert settings.get_cors_origins() == ['https://research.example.org', 'https://research.example.org:8445']


def test_development_allows_local_settings():
    settings = Settings(_env_file=None, ENV='development', SECRET_KEY='development-only',
                        CORS_ORIGINS='http://localhost:3102')
    assert settings.ENV == 'development'


def test_validation_errors_do_not_print_secret_inputs():
    secret = 'REPLACE_WITH_DO_NOT_PRINT_THIS_PRIVATE_INPUT'
    with pytest.raises(ValidationError) as caught:
        production(SECRET_KEY=secret)
    assert secret not in str(caught.value)
