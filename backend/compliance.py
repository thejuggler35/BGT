import re


def _term_matches(text, phrase):
    escaped = re.escape(phrase.strip())
    return list(re.finditer(rf"(?<!\w){escaped}(?!\w)", text, re.IGNORECASE))


def _fact_findings(text, facts):
    results = []
    seen = set()
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    quantity_pattern = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mg|ml|g|kg|%)\b", re.IGNORECASE)
    for fact in facts:
        if fact["value"] is None or not fact["unit"]:
            continue
        expected = float(fact["value"])
        for chunk in chunks:
            if fact["product"].casefold() not in chunk.casefold():
                continue
            fact_terms = [
                word.casefold()
                for word in re.findall(r"[a-zA-Z]+", fact["fact"])
                if word.casefold() not in {"per", "the", "a", "an", "contains", "serving", "added"}
            ]
            if not any(re.search(rf"\b{re.escape(word)}\b", chunk, re.IGNORECASE) for word in fact_terms):
                continue
            for match in quantity_pattern.finditer(chunk):
                if match.group(2).casefold() != fact["unit"].casefold():
                    continue
                actual = float(match.group(1))
                if actual == expected:
                    continue
                key = (fact["product"].casefold(), match.group(0).casefold(), fact["fact"].casefold())
                if key in seen:
                    continue
                seen.add(key)
                sentence = chunk.strip()
                results.append(
                    {
                        "category": "fact",
                        "title": f"Check the {fact['fact'].lower()} claim",
                        "severity": "attention",
                        "matched_text": sentence,
                        "explanation": (
                            f"The draft states {match.group(0)}, while the saved product fact "
                            f"records {expected:g} {fact['unit']}."
                        ),
                        "evidence": f"Approved: {fact['product']}: {fact['fact']}, {expected:g} {fact['unit']}.",
                        "guideline": f"{fact['product']} / {fact['fact']}",
                        "suggestion": f"Update the claim to {expected:g} {fact['unit']} or confirm it with a reviewer.",
                    }
                )
    return results


def check_content(text, rules):
    findings = []
    for term in rules["restricted_terms"]:
        for match in _term_matches(text, term["phrase"]):
            findings.append(
                {
                    "category": "restricted_term",
                    "title": f"Review restricted phrase: {term['phrase']}",
                    "severity": "attention",
                    "matched_text": match.group(0),
                    "explanation": term["explanation"] or "This phrase is listed as restricted in the brand guidelines.",
                    "evidence": f"Restricted term in the saved guidelines: “{term['phrase']}”.",
                    "guideline": term["phrase"],
                    "suggestion": "Replace this phrase with wording that can be supported by an approved product fact.",
                }
            )
    findings.extend(_fact_findings(text, rules["product_facts"]))

    for term in rules["preferred_terms"]:
        if not _term_matches(text, term["phrase"]):
            findings.append(
                {
                    "category": "preferred_term",
                    "title": f"Consider using “{term['phrase']}”",
                    "severity": "suggestion",
                    "matched_text": "",
                    "explanation": term["explanation"] or "This preferred term is not present in the draft; use it only if it fits naturally.",
                    "evidence": f"Preferred wording in the saved guidelines: “{term['phrase']}”.",
                    "guideline": term["phrase"],
                    "suggestion": f"Consider adding “{term['phrase']}” where it fits the writer’s intent.",
                }
            )

    uppercase_words = re.findall(r"\b[A-Z]{3,}\b", text)
    if len(uppercase_words) >= 2:
        findings.append(
            {
                "category": "tone",
                "title": "Check the emphasis and tone",
                "severity": "info",
                "matched_text": ", ".join(uppercase_words[:6]),
                "explanation": (
                    "Several all-caps words may read as shouting. This is a transparent style heuristic, "
                    "not a confirmed brand violation."
                ),
                "evidence": f"Detected all-caps words: {', '.join(uppercase_words[:6])}.",
                "guideline": f"Brand voice: {', '.join(rules['brand_voice'])}. {rules['tone_characteristics']}".strip(),
                "suggestion": "Use sentence case for emphasis, and keep the message clear and confident.",
            }
        )
    return findings
