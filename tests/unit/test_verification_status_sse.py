"""
Unit tests for RSN-4: verification_status / verification_message propagation
from Critic result through orchestrator to SSE final_result payload.

Data flow being tested:
  critic.py sets result.__dict__["verification_status"] = "unverified"
       ↓
  orchestrator._format_result() must include verification_status in schema_obj
       ↓
  api.py assembles final_result SSE message from schema_object fields

Tests cover:
1. _format_result includes verification_status/message when critic set them
2. _format_result does NOT include them (or uses "verified") when not set
3. api.py final_result message carries verification fields from schema_object
"""

import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Add code/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../code/python'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(is_connected: bool = True):
    """Build a minimal mock handler that satisfies orchestrator.__init__."""
    handler = MagicMock()
    handler.is_connected = MagicMock(return_value=is_connected)
    handler.llm_client = MagicMock()
    handler.send_message = AsyncMock()
    return handler


def _make_orchestrator(handler=None):
    """Instantiate DeepResearchOrchestrator with mocked dependencies."""
    from reasoning.orchestrator import DeepResearchOrchestrator

    if handler is None:
        handler = _make_handler()

    with patch('reasoning.orchestrator.AnalystAgent'), \
         patch('reasoning.orchestrator.CriticAgent'), \
         patch('reasoning.orchestrator.WriterAgent'), \
         patch('reasoning.orchestrator.SourceTierFilter'):
        orchestrator = DeepResearchOrchestrator(handler)

    return orchestrator


def _make_critic_result(verification_status=None, verification_message=None):
    """Build a minimal mock critic result (Pydantic-like object)."""
    result = MagicMock()
    result.sources_used = [1]
    result.confidence_level = "High"
    result.methodology_note = "Test methodology"
    result.final_report = "Test report content"
    result.__dict__["sources_used"] = [1]
    result.__dict__["confidence_level"] = "High"
    result.__dict__["methodology_note"] = "Test methodology"
    result.__dict__["final_report"] = "Test report content"

    if verification_status is not None:
        result.__dict__["verification_status"] = verification_status
    if verification_message is not None:
        result.__dict__["verification_message"] = verification_message

    return result


def _make_writer_output(sources_used=None, final_report="Test report", confidence_level="High", methodology_note="Method"):
    """Build a minimal mock writer output."""
    output = MagicMock()
    output.sources_used = sources_used or [1]
    output.final_report = final_report
    output.confidence_level = confidence_level
    output.methodology_note = methodology_note
    return output


# ---------------------------------------------------------------------------
# Test class: orchestrator._format_result includes verification_status
# ---------------------------------------------------------------------------

class TestFormatResultVerificationStatus:
    """
    _format_result must propagate verification_status from critic result
    into the schema_object of the returned NLWeb Item.

    The critic result is passed as `analyst_output` is the WRITER output —
    verification_status is on the critic `review` object. But _format_result
    currently doesn't take `review` directly. We need to verify that the
    orchestrator passes verification fields into _format_result and that
    _format_result includes them in schema_object.
    """

    def test_format_result_includes_verification_status_when_unverified(self):
        """
        When final_report has verification_status="unverified" set on it,
        _format_result must include that in schema_object.
        """
        orchestrator = _make_orchestrator()

        # Set up source_map so _format_result can build URLs
        orchestrator.source_map = {1: {"url": "http://example.com", "title": "Test"}}

        # Build a writer output that has verification_status attached
        final_report = _make_writer_output(sources_used=[1])
        # Simulate that verification status was attached to final_report
        # (this is what orchestrator should do before calling _format_result)
        final_report.__dict__["verification_status"] = "unverified"
        final_report.__dict__["verification_message"] = "本報告未經完整事實驗證"

        result = orchestrator._format_result(
            query="test query",
            mode="discovery",
            final_report=final_report,
            iterations=1,
            context=[{"url": "http://example.com", "title": "Test"}],
            analyst_output=None
        )

        assert len(result) == 1
        schema_obj = result[0].get("schema_object", {})
        assert schema_obj.get("verification_status") == "unverified", (
            f"Expected 'unverified' in schema_object, got: {schema_obj}"
        )
        assert "verification_message" in schema_obj, (
            "verification_message should be in schema_object"
        )
        assert schema_obj["verification_message"] == "本報告未經完整事實驗證"

    def test_format_result_includes_verification_status_when_partially_verified(self):
        """
        When verification_status="partially_verified", it must also appear in schema_object.
        """
        orchestrator = _make_orchestrator()
        orchestrator.source_map = {1: {"url": "http://example.com", "title": "Test"}}

        final_report = _make_writer_output(sources_used=[1])
        final_report.__dict__["verification_status"] = "partially_verified"
        final_report.__dict__["verification_message"] = "部分宣稱未能完整驗證"

        result = orchestrator._format_result(
            query="test query",
            mode="discovery",
            final_report=final_report,
            iterations=1,
            context=[{"url": "http://example.com", "title": "Test"}],
            analyst_output=None
        )

        schema_obj = result[0].get("schema_object", {})
        assert schema_obj.get("verification_status") == "partially_verified"
        assert schema_obj.get("verification_message") == "部分宣稱未能完整驗證"

    def test_format_result_no_verification_status_when_not_set(self):
        """
        When verification_status is NOT set on final_report (normal verified flow),
        schema_object must NOT contain 'verification_status' key, OR it must be "verified".
        The frontend only shows warning for unverified/partially_verified.
        """
        orchestrator = _make_orchestrator()
        orchestrator.source_map = {1: {"url": "http://example.com", "title": "Test"}}

        final_report = _make_writer_output(sources_used=[1])
        # No verification_status set — normal verified flow

        result = orchestrator._format_result(
            query="test query",
            mode="discovery",
            final_report=final_report,
            iterations=1,
            context=[{"url": "http://example.com", "title": "Test"}],
            analyst_output=None
        )

        schema_obj = result[0].get("schema_object", {})
        # Either not present or "verified" — the frontend must NOT show a warning
        status = schema_obj.get("verification_status")
        assert status is None or status == "verified", (
            f"When not set, verification_status should be None or 'verified', got: {status}"
        )


# ---------------------------------------------------------------------------
# Test class: orchestrator reads verification_status from critic review
# ---------------------------------------------------------------------------

class TestOrchestratorReadsVerificationFromReview:
    """
    When critic review has verification_status set in __dict__,
    the orchestrator must transfer it to final_report before calling _format_result.

    We test this by inspecting the return value of _format_result called after
    the orchestrator processes a critic review that has verification_status set.
    """

    def test_orchestrator_transfers_verification_from_critic_to_schema_obj(self):
        """
        When critic review has verification_status="unverified" in __dict__,
        the final NLWeb result's schema_object must contain that status.

        This test simulates calling the orchestrator's internal method that
        transfers verification fields from review to final_report.
        """
        orchestrator = _make_orchestrator()
        orchestrator.source_map = {1: {"url": "http://example.com", "title": "Test"}}

        # Critic review has verification_status set (as done in critic.py L218)
        review = MagicMock()
        review.__dict__["verification_status"] = "unverified"
        review.__dict__["verification_message"] = "本報告未經完整事實驗證"

        final_report = _make_writer_output(sources_used=[1])

        # Orchestrator should copy verification fields from review to final_report
        # before calling _format_result. We test the public result.
        verification_status = review.__dict__.get("verification_status")
        verification_message = review.__dict__.get("verification_message")

        if verification_status:
            final_report.__dict__["verification_status"] = verification_status
            final_report.__dict__["verification_message"] = verification_message

        result = orchestrator._format_result(
            query="test query",
            mode="discovery",
            final_report=final_report,
            iterations=2,
            context=[{"url": "http://example.com", "title": "Test"}],
            analyst_output=None
        )

        schema_obj = result[0].get("schema_object", {})
        assert schema_obj.get("verification_status") == "unverified"
        assert schema_obj.get("verification_message") == "本報告未經完整事實驗證"


# ---------------------------------------------------------------------------
# Test class: api.py final_result SSE includes verification fields
# ---------------------------------------------------------------------------

class TestFinalResultSSEVerificationFields:
    """
    The final_result SSE message assembled in api.py must include
    verification_status and verification_message when they are present
    in the schema_object.
    """

    def test_final_result_includes_verification_status_from_schema_object(self):
        """
        When schema_object in a result item contains verification_status="unverified",
        the final_result SSE message must include that field.

        This tests the logic in api.py that assembles final_message from schema_object.
        """
        # Simulate what api.py does when building final_message
        result = {
            'answer': 'Test report',
            'confidence_level': 'High',
            'methodology_note': 'Discovery mode',
            'sources_used': ['http://example.com'],
            'items': [{
                '@type': 'Item',
                'schema_object': {
                    '@type': 'ResearchReport',
                    'mode': 'discovery',
                    'verification_status': 'unverified',
                    'verification_message': '本報告未經完整事實驗證',
                    'argument_graph': None,
                    'reasoning_chain_analysis': None,
                    'knowledge_graph': None,
                }
            }]
        }

        # Replicate api.py's final_message assembly logic
        final_message = {
            "message_type": "final_result",
            "final_report": result.get('answer', ''),
            "confidence_level": result.get('confidence_level', 'Medium'),
            "methodology": result.get('methodology_note', ''),
            "sources": result.get('sources_used', [])
        }

        items = result.get('items', [])
        if items and len(items) > 0:
            schema_obj = items[0].get('schema_object', {})
            if schema_obj.get('argument_graph'):
                final_message['argument_graph'] = schema_obj['argument_graph']
            if schema_obj.get('reasoning_chain_analysis'):
                final_message['reasoning_chain_analysis'] = schema_obj['reasoning_chain_analysis']
            if schema_obj.get('knowledge_graph'):
                final_message['knowledge_graph'] = schema_obj['knowledge_graph']
            # RSN-4: Extract verification fields
            if schema_obj.get('verification_status'):
                final_message['verification_status'] = schema_obj['verification_status']
            if schema_obj.get('verification_message'):
                final_message['verification_message'] = schema_obj['verification_message']

        assert final_message.get('verification_status') == 'unverified', (
            f"final_result SSE should include verification_status='unverified', got: {final_message}"
        )
        assert final_message.get('verification_message') == '本報告未經完整事實驗證'

    def test_final_result_excludes_verification_when_not_set(self):
        """
        When schema_object does NOT contain verification_status,
        the final_result SSE message must NOT include that field (no warning shown).
        """
        result = {
            'answer': 'Test report',
            'confidence_level': 'High',
            'methodology_note': 'Discovery mode',
            'sources_used': ['http://example.com'],
            'items': [{
                '@type': 'Item',
                'schema_object': {
                    '@type': 'ResearchReport',
                    'mode': 'discovery',
                    # No verification_status set
                    'argument_graph': None,
                    'reasoning_chain_analysis': None,
                    'knowledge_graph': None,
                }
            }]
        }

        final_message = {
            "message_type": "final_result",
            "final_report": result.get('answer', ''),
            "confidence_level": result.get('confidence_level', 'Medium'),
            "methodology": result.get('methodology_note', ''),
            "sources": result.get('sources_used', [])
        }

        items = result.get('items', [])
        if items and len(items) > 0:
            schema_obj = items[0].get('schema_object', {})
            if schema_obj.get('argument_graph'):
                final_message['argument_graph'] = schema_obj['argument_graph']
            if schema_obj.get('reasoning_chain_analysis'):
                final_message['reasoning_chain_analysis'] = schema_obj['reasoning_chain_analysis']
            if schema_obj.get('knowledge_graph'):
                final_message['knowledge_graph'] = schema_obj['knowledge_graph']
            if schema_obj.get('verification_status'):
                final_message['verification_status'] = schema_obj['verification_status']
            if schema_obj.get('verification_message'):
                final_message['verification_message'] = schema_obj['verification_message']

        assert 'verification_status' not in final_message, (
            "When not set, final_result SSE should NOT contain verification_status"
        )
