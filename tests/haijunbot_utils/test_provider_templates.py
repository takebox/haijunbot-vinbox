# -*- coding: utf-8 -*-
"""The shipped template and schema cover every provider lane."""

import json
from pathlib import Path

import yaml

from haijunbot.haijunbot_utils import free_providers as fp

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "config.example.yaml"
SCHEMA = ROOT / "src" / "haijunbot" / "haijunbot_data" / "config_schema.json"


def test_template_is_valid_yaml_with_every_provider():
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    entries = data["llms"]
    template_providers = {entry["llm_config"]["provider"] for entry in entries.values()}
    assert template_providers == set(fp.provider_ids())
    for entry in entries.values():
        assert entry["platform"] == "free"
        assert entry["model"]
        assert "openai_api_key" in entry["llm_config"]


def test_template_starts_free_and_keeps_paid_last():
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    assert data["llm_group"] == "free-first"
    groups = data["llm_groups"]
    assert groups["free-first"]["fallback_group"] == "free-backup"
    assert groups["free-backup"]["fallback_group"] == "paid-optional"
    first = groups["free-first"]["normal_llm"]
    assert data["llms"][first]["llm_config"]["provider"] in fp.free_provider_ids()
    paid = groups["paid-optional"]["normal_llm"]
    assert data["llms"][paid]["llm_config"]["provider"] in fp.paid_provider_ids()


def test_template_has_no_filled_key():
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    for entry in data["llms"].values():
        assert entry["llm_config"]["openai_api_key"] == ""


def test_schema_offers_every_provider():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]["llms"]["additionalProperties"]["properties"]
    assert props["platform"]["default"] == "free"
    provider = props["llm_config"]["properties"]["provider"]
    assert provider["enum"] == fp.provider_ids()
    assert set(provider["enum"]) == set(fp.provider_ids())


def test_every_provider_documents_where_to_get_a_key():
    for row in fp.providers_table():
        assert "signup_url" in row
        if row["tier"] == fp.TIER_FREE and row["id"] not in (
            "9router",
            "omniroute",
            "opencode",
        ):
            assert row["signup_url"].startswith("https://"), row["id"]
