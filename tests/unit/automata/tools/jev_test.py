"""Jev protocol and failure checks; all HTTP calls are mocked."""

import copy
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

TOOL_ROOT = Path(__file__).parents[4] / "src/automata/tools/jev"
sys.path.insert(0, str(TOOL_ROOT))
import jev as client  # noqa: E402
import jev_contract as contract  # noqa: E402


@pytest.fixture
def request_data():
    return {
        "model": contract.MODEL,
        "state": "Synthetic refund question",
        "questions": {
            "route": {
                "type": "choice",
                "instructions": "Choose a relevant department.",
                "criteria": {"billing": "Payments", "none": "No suitable option"},
            }
        },
    }


@pytest.fixture
def response_data():
    return {
        "model": contract.MODEL,
        "answers": {
            "route": {
                "type": "choice",
                "choice": "billing",
                "probabilities": {"billing": 0.95, "none": 0.05},
                "confidence": 0.8,
            }
        },
        "usage": {"input_tokens": 300, "output_tokens": 30},
    }


@pytest.fixture
def connection(monkeypatch, response_data):
    conn = Mock()
    conn.getresponse.return_value.status = 200
    conn.getresponse.return_value.read.return_value = json.dumps(response_data).encode()
    factory = Mock(return_value=conn)
    monkeypatch.setattr(client.http.client, "HTTPSConnection", factory)
    return conn, factory


def test_valid_plan_and_preserved_output(request_data, response_data):
    body, plan = contract.preflight(request_data, 0.005, 20)
    assert json.loads(body) == request_data
    assert plan["reserved_list_cost_usd"] <= 0.005
    assert plan["maximum_requests"] == 1 and plan["retries"] == 0
    assert contract.validate_response(response_data, request_data) == response_data
    assert "Synthetic" not in json.dumps(plan)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b"NaN", b"Infinity", b"\xff", b"{"])
def test_invalid_json_is_sanitized(raw):
    with pytest.raises(contract.JevError, match="Expected UTF-8 JSON"):
        contract.decode(raw)


@pytest.mark.parametrize(
    "field,value",
    [("model", "jev-latest"), ("state", None), ("state", ""), ("questions", []), ("questions", {})],
)
def test_invalid_request(request_data, field, value):
    request_data[field] = value
    with pytest.raises(contract.JevError):
        contract.validate_request(request_data)


def test_unknown_and_missing_fields(request_data):
    for field in request_data:
        invalid = copy.deepcopy(request_data)
        del invalid[field]
        with pytest.raises(contract.JevError):
            contract.validate_request(invalid)
    request_data["credential"] = "DO_NOT_PRINT"
    with pytest.raises(contract.JevError) as error:
        contract.validate_request(request_data)
    assert "DO_NOT_PRINT" not in str(error.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("type", "noul"),
        ("type", "score"),
        ("instructions", ""),
        ("criteria", {"only": "one"}),
        ("criteria", {"a": 7, "b": None}),
        ("criteria", {"a\n": "bad", "b": None}),
        ("criteria", {f"a{i}": None for i in range(256)}),
    ],
)
def test_question_contract(request_data, field, value):
    request_data["questions"]["route"][field] = value
    with pytest.raises(contract.JevError):
        contract.validate_request(request_data)


def test_limits_and_nonfinite_nested_input(request_data):
    request_data["state"] = "x" * contract.MAX_INPUT_BYTES
    with pytest.raises(contract.JevError, match="16 KiB"):
        contract.validate_request(request_data)
    request_data["state"] = {"n": float("inf")}
    with pytest.raises(contract.JevError):
        contract.validate_request(request_data)
    request_data["state"] = "ok"
    question = request_data["questions"]["route"]
    request_data["questions"] = {f"q{i}": question for i in range(17)}
    with pytest.raises(contract.JevError):
        contract.validate_request(request_data)


@pytest.mark.parametrize("budget", [0, -1, 0.0001, float("nan"), float("inf"), True])
def test_bad_budget(request_data, budget):
    with pytest.raises(contract.JevError):
        contract.preflight(request_data, budget, 20)


@pytest.mark.parametrize("timeout", [0, -1, 121, float("nan"), float("inf"), True])
def test_bad_timeout(request_data, timeout):
    with pytest.raises(contract.JevError):
        contract.preflight(request_data, 0.005, timeout)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 1.1, True, 10**400])
def test_bad_probability(request_data, response_data, value):
    response_data["answers"]["route"]["probabilities"]["billing"] = value
    with pytest.raises(contract.JevError):
        contract.validate_response(response_data, request_data)


def test_wrong_choice_model_ids_and_usage(request_data, response_data):
    for modifier in (
        lambda d: d.update(model="unexpected"),
        lambda d: d.update(answers={}),
        lambda d: d["answers"]["route"].update(choice="none"),
        lambda d: d["answers"]["route"].update(choice=["billing"]),
        lambda d: d["answers"]["route"].update(confidence=True),
        lambda d: d["answers"]["route"].update(probabilities={"billing": 0.3, "none": 0.3}),
        lambda d: d.update(usage={"input_tokens": True, "output_tokens": 2}),
        lambda d: d.update(usage={"input_tokens": 65537, "output_tokens": 2}),
    ):
        invalid = copy.deepcopy(response_data)
        modifier(invalid)
        with pytest.raises(contract.JevError):
            contract.validate_response(invalid, request_data)


def test_rounding_not_silently_normalized(request_data, response_data):
    response_data["answers"]["route"]["probabilities"]["billing"] = 0.94
    result = contract.validate_response(response_data, request_data)
    assert result["answers"]["route"]["probabilities"] == {"billing": 0.94, "none": 0.05}


def test_multiple_questions(request_data, response_data):
    request_data["questions"]["second"] = copy.deepcopy(request_data["questions"]["route"])
    response_data["answers"]["second"] = copy.deepcopy(response_data["answers"]["route"])
    assert len(contract.validate_response(response_data, request_data)["answers"]) == 2


def test_credentials_are_explicit_and_file_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ENV_FAKE")
    assert client.read_key(None) == "ENV_FAKE"
    path = tmp_path / "key"
    path.write_text("FILE_FAKE\n")
    assert client.read_key(path) == "FILE_FAKE"
    monkeypatch.delenv("TYPESAFE_API_KEY")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "jev.apikey").write_text("NO_DISCOVERY")
    with pytest.raises(contract.JevError):
        client.read_key(None)


@pytest.mark.parametrize("value", [b"", b"a\nb", b"Bearer TOKEN", b"a" * 4097, b"\xff"])
def test_bad_key_is_not_printed(value, tmp_path):
    path = tmp_path / "key"
    path.write_bytes(value)
    with pytest.raises(contract.JevError) as error:
        client.read_key(path)
    assert "TOKEN" not in str(error.value)


def test_one_fixed_host_request_without_key_leak(request_data, connection):
    conn, factory = connection
    body = contract.validate_request(request_data)
    result = client.evaluate(request_data, body, "SECRET_FAKE", 20)
    factory.assert_called_once()
    assert factory.call_args.args == ("api.typesafe.ai",)
    assert factory.call_args.kwargs["context"].check_hostname
    conn.request.assert_called_once()
    assert conn.request.call_args.args == ("POST", "/v1/systemone")
    assert conn.request.call_args.kwargs["headers"]["Authorization"] == "Bearer SECRET_FAKE"
    assert "SECRET_FAKE" not in json.dumps(result)
    assert result["estimated_list_cost_usd"] == 300 * 0.042 / 1_000_000
    conn.close.assert_called_once()


def test_credential_in_input_is_blocked(request_data, connection):
    conn, _ = connection
    request_data["state"] = "SECRET_FAKE"
    with pytest.raises(contract.JevError) as error:
        client.evaluate(request_data, contract.validate_request(request_data), "SECRET_FAKE", 20)
    assert error.value.outcome == "not_sent"
    conn.request.assert_not_called()


@pytest.mark.parametrize("status", [301, 302, 401, 403, 422, 429, 500, 529])
def test_http_errors_no_redirect_retry_or_body_logging(request_data, connection, status):
    conn, _ = connection
    conn.getresponse.return_value.status = status
    conn.getresponse.return_value.read.return_value = b"SECRET_FAKE"
    with pytest.raises(contract.JevError) as error:
        client.evaluate(request_data, contract.validate_request(request_data), "SECRET_FAKE", 20)
    assert error.value.outcome == "response_received"
    assert "SECRET_FAKE" not in str(error.value)
    conn.request.assert_called_once()
    conn.getresponse.return_value.read.assert_not_called()


def test_timeout_is_uncertain_and_not_retried(request_data, connection):
    conn, _ = connection
    conn.request.side_effect = TimeoutError("SECRET_FAKE")
    with pytest.raises(contract.JevError) as error:
        client.evaluate(request_data, contract.validate_request(request_data), "SECRET_FAKE", 20)
    assert error.value.outcome == "outcome_unknown"
    assert "SECRET_FAKE" not in str(error.value)
    conn.request.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "raw",
    [
        b"not JSON SECRET_FAKE",
        b"x" * (contract.MAX_RESPONSE_BYTES + 1),
        b'{"model":"unexpected","secret":"SECRET_FAKE"}',
    ],
)
def test_bad_response_is_sanitized(request_data, connection, raw):
    conn, _ = connection
    conn.getresponse.return_value.read.return_value = raw
    with pytest.raises(contract.JevError) as error:
        client.evaluate(request_data, contract.validate_request(request_data), "SECRET_FAKE", 20)
    assert "SECRET_FAKE" not in str(error.value)
    assert error.value.outcome == "response_received"


def test_offline_does_not_read_credentials_or_touch_network(request_data, monkeypatch, capsys):
    monkeypatch.setattr(client, "read_input", lambda _: request_data)
    key = Mock(side_effect=AssertionError("must not read credentials"))
    network = Mock(side_effect=AssertionError("must not contact network"))
    monkeypatch.setattr(client, "read_key", key)
    monkeypatch.setattr(client, "evaluate", network)
    client.judge("input.json")
    assert json.loads(capsys.readouterr().out)["network_requests"] == 0
    key.assert_not_called()
    network.assert_not_called()


def test_cli_transport_failure_is_structured(request_data, monkeypatch, capsys, connection):
    conn, _ = connection
    conn.request.side_effect = TimeoutError("SECRET_FAKE")
    monkeypatch.setattr(client, "read_input", lambda _: request_data)
    monkeypatch.setattr(client, "read_key", lambda _: "SECRET_FAKE")
    with pytest.raises(SystemExit) as error:
        client.judge("input.json", execute=True, max_cost_usd=0.005)
    assert error.value.code == 3
    streams = capsys.readouterr()
    assert not streams.out and "SECRET_FAKE" not in streams.err
    assert json.loads(streams.err)["outcome"] == "outcome_unknown"
    conn.request.assert_called_once()


def test_execute_requires_budget_before_reading_key(request_data, monkeypatch, capsys):
    monkeypatch.setattr(client, "read_input", lambda _: request_data)
    key = Mock(side_effect=AssertionError("must not read credentials"))
    monkeypatch.setattr(client, "read_key", key)
    with pytest.raises(SystemExit) as error:
        client.judge("input.json", execute=True)
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().err)["outcome"] == "not_sent"
    key.assert_not_called()
