"""
Unit tests for prompt language directives in config/prompts.xml.

CEO Requirement: All prompts must strictly use Traditional Chinese (繁體中文)
unless the user explicitly requests English or another language.

These tests verify that prompts do NOT instruct the LLM to match the language
of the source article (which causes English article sources to produce English
summaries), and instead mandate Traditional Chinese output.
"""

import os
import xml.etree.ElementTree as ET
import pytest

# Path to prompts.xml relative to this test file
PROMPTS_XML_PATH = os.path.join(
    os.path.dirname(__file__), '../../config/prompts.xml'
)


def load_prompts_xml():
    """Parse and return prompts.xml as an ElementTree."""
    tree = ET.parse(PROMPTS_XML_PATH)
    return tree.getroot()


def get_all_prompt_text(root):
    """Collect all text content from <promptString> and <returnStruc> elements."""
    texts = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            texts.append(elem.text.strip())
    return "\n".join(texts)


def get_prompt_by_ref(root, ref_name):
    """Find a <Prompt ref="..."> element and return its full text content.

    Handles both namespaced ({http://nlweb.ai/base}Prompt) and plain (Prompt) tags.
    """
    for prompt in root.iter():
        # Match regardless of namespace prefix
        local_tag = prompt.tag.split('}')[-1] if '}' in prompt.tag else prompt.tag
        if local_tag == 'Prompt' and prompt.get('ref') == ref_name:
            parts = []
            for elem in prompt.iter():
                if elem.text and elem.text.strip():
                    parts.append(elem.text.strip())
            return "\n".join(parts)
    return None


@pytest.mark.unit
class TestPromptLanguageDirectives:
    """Tests that verify prompts mandate Traditional Chinese output."""

    def test_prompts_xml_exists_and_is_valid_xml(self):
        """Ensure the prompts.xml file exists and is valid XML."""
        assert os.path.exists(PROMPTS_XML_PATH), (
            f"prompts.xml not found at {PROMPTS_XML_PATH}"
        )
        root = load_prompts_xml()
        assert root is not None

    def test_ranking_prompt_does_not_use_item_language(self):
        """RankingPrompt must NOT instruct LLM to use item's language for description.

        Root cause: 'same language as the item's description' causes English
        source articles to produce English summaries.
        """
        root = load_prompts_xml()
        text = get_prompt_by_ref(root, 'RankingPrompt')
        assert text is not None, "RankingPrompt not found in prompts.xml"

        forbidden_phrase = "same language as the item"
        assert forbidden_phrase not in text, (
            f"RankingPrompt still contains '{forbidden_phrase}' — "
            "this causes English article summaries. Must mandate 繁體中文 instead."
        )

    def test_ranking_prompt_mandates_traditional_chinese(self):
        """RankingPrompt promptString must explicitly mandate Traditional Chinese."""
        root = load_prompts_xml()
        text = get_prompt_by_ref(root, 'RankingPrompt')
        assert text is not None, "RankingPrompt not found in prompts.xml"

        # Must contain an explicit Traditional Chinese mandate
        has_mandate = "繁體中文" in text
        assert has_mandate, (
            "RankingPrompt does not mandate 繁體中文 in its promptString. "
            "Add an explicit instruction requiring Traditional Chinese output."
        )

    def test_ranking_prompt_for_generate_does_not_use_question_language(self):
        """RankingPromptForGenerate must NOT use 'same language as the user's question'
        for descriptions.

        This causes English-language queries or English articles to produce
        English descriptions.
        """
        root = load_prompts_xml()
        text = get_prompt_by_ref(root, 'RankingPromptForGenerate')
        assert text is not None, "RankingPromptForGenerate not found in prompts.xml"

        forbidden_phrase = "Write the description in the same language as the user's question"
        assert forbidden_phrase not in text, (
            f"RankingPromptForGenerate still contains '{forbidden_phrase}'. "
            "Must mandate 繁體中文 instead."
        )

    def test_ranking_prompt_for_generate_mandates_traditional_chinese(self):
        """RankingPromptForGenerate promptString must explicitly mandate Traditional Chinese."""
        root = load_prompts_xml()
        text = get_prompt_by_ref(root, 'RankingPromptForGenerate')
        assert text is not None, "RankingPromptForGenerate not found in prompts.xml"

        has_mandate = "繁體中文" in text
        assert has_mandate, (
            "RankingPromptForGenerate does not mandate 繁體中文 in its promptString."
        )

    def test_summarize_results_prompt_return_struc_mandates_traditional_chinese(self):
        """SummarizeResultsPrompt returnStruc must mandate Traditional Chinese for summary.

        'string in the same language as the user's question' causes English
        summaries when the user's question is in English.
        """
        root = load_prompts_xml()
        text = get_prompt_by_ref(root, 'SummarizeResultsPrompt')
        assert text is not None, "SummarizeResultsPrompt not found in prompts.xml"

        forbidden_phrase = "same language as the user's question"
        assert forbidden_phrase not in text, (
            f"SummarizeResultsPrompt still contains '{forbidden_phrase}' in returnStruc. "
            "Must mandate 繁體中文 instead."
        )

    def test_no_prompt_instructs_matching_item_language_for_description(self):
        """No prompt anywhere should instruct the LLM to use the item's language
        for generating descriptions.

        This is the root cause of English summaries from English sources.
        """
        root = load_prompts_xml()
        all_text = get_all_prompt_text(root)

        forbidden_phrase = "same language as the item's description"
        assert forbidden_phrase not in all_text, (
            f"Found '{forbidden_phrase}' in prompts.xml. "
            "This causes English article sources to produce English descriptions. "
            "Replace with 繁體中文 mandate."
        )
