"""
DEPRECATED: Tests for old per-room STT override system removed.

This file has been deprecated and all tests removed. The per-room STT provider
override system (stt_partial_provider and stt_final_provider fields on Room model)
was replaced by language-based routing in Migration 006.

For current STT routing tests, see:
- api/tests/test_stt_language_router_integration.py (23 comprehensive tests)

Configuration is now stored in the stt_routing_config table with routing based on:
- Language (pl-PL, ar-EG, en-US, *)
- Mode (partial/final)
- Quality tier (standard/budget)
"""

# This file intentionally left empty - all tests removed as deprecated
