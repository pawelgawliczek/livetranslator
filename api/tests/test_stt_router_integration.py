"""
DEPRECATED: Tests for old global STT settings system removed.

This file has been deprecated and all tests removed. The global STT provider
settings system (SystemSettings table with stt_partial_provider_default and
stt_final_provider_default) was replaced by language-based routing in Migration 006.

For current STT routing tests, see:
- api/tests/test_stt_language_router_integration.py (23 comprehensive tests)

The old /api/admin/settings/stt endpoint has been replaced with:
- /api/admin/languages (list configured languages)
- /api/admin/languages/{language} (get/update language-specific routing)

Configuration is now stored in the stt_routing_config table with routing based on:
- Language (pl-PL, ar-EG, en-US, *)
- Mode (partial/final)
- Quality tier (standard/budget)
"""

# This file intentionally left empty - all tests removed as deprecated
