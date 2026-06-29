"""
PII protection guardrail using Microsoft Presidio.
Detects and anonymizes sensitive data (names, emails, phones, locations, SSNs).
"""
import os
from typing import Optional

# Workaround for Intel OpenMP library duplicate initialization crash in Anaconda environments
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
except ImportError:
    # Fail-safe placeholders if libraries are not installed locally yet
    AnalyzerEngine = None
    AnonymizerEngine = None


class PresidioPIIFilter:
    """Enterprise PII Filter using Microsoft Presidio Analyzer and Anonymizer."""

    def __init__(self):
        self.enabled = AnalyzerEngine is not None and AnonymizerEngine is not None
        if self.enabled:
            try:
                self.analyzer = AnalyzerEngine()
                self.anonymizer = AnonymizerEngine()
            except Exception as e:
                print(f"[!] Presidio failed to load (likely missing spaCy model): {e}")
                self.enabled = False
        else:
            print("[*] Presidio libraries not installed. PII filter running in mock/basic mode.")

    def analyze_and_anonymize(self, text: str) -> tuple[str, list[dict], bool]:
        """
        Scan text for PII entities, replace them with safe tokens, and return tracking metadata.
        
        Returns:
            anonymized_text: The scrubbed text with placeholders (e.g. <PERSON_0>)
            mapping: A list of dicts mapping placeholders back to original values
            has_pii: Boolean indicating if any PII was detected
        """
        if not text or not text.strip():
            return text, [], False

        if not self.enabled:
            # Fallback to basic regex-based scrubbing for demo purposes
            return self._basic_regex_scrub(text)

        try:
            # 1. Analyze the text for PII
            results = self.analyzer.analyze(
                text=text,
                language="en",
                entities=["PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD", "PERSON"]
            )
            
            if not results:
                return text, [], False

            # 2. Anonymize results using placeholders
            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results
            )
            
            # 3. Create mapping of placeholders to original text
            # Anonymizer replaces from right-to-left to keep indices valid.
            # We construct a mapping for de-anonymization later if needed.
            mapping = []
            for item in anonymized_result.items:
                mapping.append({
                    "placeholder": f"<{item.entity_type}>",
                    "original": text[item.start:item.end]
                })

            return anonymized_result.text, mapping, True

        except Exception as e:
            print(f"[!] Presidio execution failed: {e}")
            return self._basic_regex_scrub(text)

    def de_anonymize(self, anonymized_text: str, mapping: list[dict]) -> str:
        """Restore original PII data into anonymized responses for authorized views."""
        text = anonymized_text
        for map_item in mapping:
            placeholder = map_item["placeholder"]
            original = map_item["original"]
            text = text.replace(placeholder, original, 1)
        return text

    def _basic_regex_scrub(self, text: str) -> tuple[str, list[dict], bool]:
        """Regex-based fallback filter when NLP Presidio engine is unavailable."""
        import re
        email_regex = r"[\w\.-]+@[\w\.-]+\.\w+"
        phone_regex = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        
        scrubbed = text
        mapping = []
        has_pii = False

        # Email check
        emails = re.findall(email_regex, text)
        for idx, email in enumerate(emails):
            placeholder = f"<EMAIL_{idx}>"
            scrubbed = scrubbed.replace(email, placeholder)
            mapping.append({"placeholder": placeholder, "original": email})
            has_pii = True

        # Phone check
        phones = re.findall(phone_regex, text)
        for idx, phone in enumerate(phones):
            placeholder = f"<PHONE_{idx}>"
            scrubbed = scrubbed.replace(phone, placeholder)
            mapping.append({"placeholder": placeholder, "original": phone})
            has_pii = True

        return scrubbed, mapping, has_pii
