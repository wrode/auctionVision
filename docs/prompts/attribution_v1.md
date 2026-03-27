# Attribution Agent Prompt v1

## Purpose

Determine if an auction lot is likely to be designed by a known Scandinavian Modern (Nordic) designer, and assign a confidence score to the attribution.

## Input Schema

```json
{
  "lot_id": "string",
  "title": "string",
  "description": "string",
  "estimated_price_sek": "number or null",
  "hammer_price_sek": "number or null",
  "images": ["url"],
  "furniture_type": "string (e.g., 'lounge_chair', 'dining_table')",
  "materials": ["string"],
  "condition": "string (e.g., 'excellent', 'good', 'fair')",
  "era_estimate": "string (e.g., '1950s')",
  "source": "string (e.g., 'auctionet')",
  "lot_url": "string"
}
```

## Output Schema

```json
{
  "primary_designer": {
    "name": "string or null",
    "country": "string or null",
    "confidence": "number (0.0-1.0)",
    "key_indicators": ["string"]
  },
  "adjacent_designers": [
    {
      "name": "string",
      "likelihood": "number (0.0-1.0)"
    }
  ],
  "is_designer_piece": "boolean",
  "designer_confidence": "number (0.0-1.0)",
  "reasoning": "string",
  "visual_evidence": "string (what you observed in images)",
  "text_evidence": "string (what the title/description told you)"
}
```

## Confidence Scoring Guide

- **0.9-1.0 (Certain)**: Maker's label visible, designer signature, published piece with verified provenance
- **0.7-0.9 (High)**: Strong style match, materials match known designer works, distinctive form language
- **0.5-0.7 (Moderate)**: Good era/style fit, reasonable material alignment, typical of designer but no definitive proof
- **0.3-0.5 (Low)**: Suggestive characteristics but many similar makers, period style but not distinctive
- **0.0-0.3 (Very Low)**: Generic period look, could be many makers, weak indicators

## Evaluation Approach

1. **Title & Description Parsing**
   - Look for explicit designer names, manufacturer names, model numbers
   - Note any qualifiers ("in the style of", "attributed to", "Danish Modern")
   - Extract era and material clues

2. **Style Analysis**
   - Compare form, proportions, structural approach to known works
   - Look for signature design language (e.g., Wegner's sculpted curves, Jacobsen's minimalism)
   - Consider furniture category context (seating vs. storage vs. tables)

3. **Material & Production Clues**
   - Teak, rosewood, and natural leather → higher likelihood of Danish/Scandinavian mid-century
   - Beech with natural finish → Scandinavian
   - Brass or chrome details common in specific designer works
   - Joinery details visible in images (dowels, mortise-and-tenon) suggest maker quality

4. **Visual Evidence from Images**
   - Look for distinctive form elements (leg style, back profile, armrest treatment)
   - Condition and patina can indicate age/authenticity
   - Proportional relationships and silhouette
   - Any visible labels, maker's marks, or construction details

5. **Price Alignment**
   - Does hammer price align with comparable authenticated pieces?
   - Underpriced items sometimes miss attribution
   - Overpriced items may be mis-attributed

## Common Pitfalls to Avoid

- **Attribution Creep**: Not every teak chair is Hans Wegner. Many similar makers exist.
- **Retroactive Label Reading**: Don't assume title is accurate; verify against images.
- **Over-Reliance on Era**: A 1960s chair isn't automatically a designer piece.
- **Ignoring Condition**: Restored or damaged pieces can hide identifying features.

## Failure Convention

If you cannot form a meaningful attribution, return:
```json
{
  "primary_designer": {
    "name": null,
    "confidence": 0.0
  },
  "is_designer_piece": false,
  "designer_confidence": 0.0,
  "reasoning": "Insufficient information to make attribution"
}
```

## Example Scenarios

### Scenario 1: Clear Attribution
**Input**: Title "Hans J Wegner Papa Bear Chair, Teak, c.1955"
**Output**:
```json
{
  "primary_designer": {
    "name": "Hans Wegner",
    "confidence": 0.95,
    "key_indicators": ["Title explicitly names designer", "Papa Bear chair is iconic Wegner model", "Teak material matches era"]
  },
  "is_designer_piece": true,
  "designer_confidence": 0.95
}
```

### Scenario 2: Ambiguous Match
**Input**: Title "Danish Modern Lounge Chair, Teak, c.1960", no images available
**Output**:
```json
{
  "primary_designer": {
    "name": null,
    "confidence": 0.4,
    "key_indicators": ["Teak material consistent with era", "Form described generically", "No distinctive features identified"]
  },
  "adjacent_designers": [
    {"name": "Hans Wegner", "likelihood": 0.3},
    {"name": "Arne Jacobsen", "likelihood": 0.25}
  ],
  "is_designer_piece": false,
  "designer_confidence": 0.4,
  "reasoning": "Insufficient distinctive features for confident attribution despite period appropriateness"
}
```

## Related Configuration

- Seed designer list: `config/designers.yaml`
- Known producers and aliases in designer data
- Scoring weight for attribution_confidence: `config/scoring.yaml` (arbitrage.weights.attribution_confidence)
